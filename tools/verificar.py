"""Harness único; sempre executado de hunt-analyzer, com dados temporários."""
import argparse
import ast
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from rastreabilidade import conferir_incidentes, diferencas, fontes, identidade, reservar_saida

ROOT = pathlib.Path(__file__).resolve().parents[1]
ANALISADOR = ROOT / 'hunt-analyzer'


def impressao_runtime():
    sys.path.insert(0, str(ROOT / 'instalador'))
    import montar_pacote as pacote
    # QA, compilação e atualização devem identificar o mesmo produto nativo.
    mods, _ = pacote.fecho([*pacote.ENTRADAS, 'hunt_launcher'])
    nomes = {pacote.caminhos_modulos()[m].relative_to(ANALISADOR).as_posix() for m in mods}
    nomes.update(pacote.DADOS)
    nomes.update(p.relative_to(ANALISADOR).as_posix() for d in pacote.DADOS_PASTAS
                 for p in (ANALISADOR / d).rglob('*') if p.is_file())
    h = hashlib.sha256()
    for nome in sorted(nomes):
        conteudo = (ANALISADOR / nome).read_bytes()
        if pathlib.Path(nome).suffix.lower() in {'.py', '.js', '.html', '.css', '.json', '.txt', '.bat'}:
            conteudo = conteudo.replace(b'\r\n', b'\n')
        h.update(nome.encode('utf8')); h.update(conteudo)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--perfil', choices=['rapido', 'completo', 'windows', 'compilado'], default='rapido')
    parser.add_argument('--saida', type=pathlib.Path)
    parser.add_argument('--executavel', type=pathlib.Path)
    args = parser.parse_args()
    saida = args.saida or ROOT / 'output' / 'harness' / time.strftime('%Y%m%d_%H%M%S')
    saida = reservar_saida(saida)
    antes = fontes(ROOT)
    (saida / 'fontes-inicio.json').write_text(json.dumps(antes, ensure_ascii=False, indent=2), encoding='utf8')
    resultado = {'schema': 2, 'id': identidade(), 'perfil': args.perfil, 'python': sys.version,
                 'node': subprocess.run(['node', '--version'], capture_output=True, text=True, check=True).stdout.strip(),
                 'fontes_sha256': antes['sha256'], 'runtime_sha256': impressao_runtime(), 'suites': []}
    with tempfile.TemporaryDirectory(prefix='rubinot-qa-') as tmp:
        d = pathlib.Path(tmp)
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'HUNT_QA_SAIDA': str(saida),
               'HUNT_DATA': str(d / 'hunt_data'), 'HUNT_FONTES_RAIZ': str(d / 'fontes'),
               'HUNT_CONFIGURACOES_RAIZ': str(d / 'configuracoes'), 'HUNT_APRENDIZADO_RAIZ': str(d / 'aprendizado'),
               'HUNT_CAPTURAS_RAIZ': str(d / 'capture'), 'HUNT_KS_RAIZ': str(d / 'KS'),
               'HUNT_AUXILIARES_CONFIG': str(d / 'auxiliares.json')}
        suites = [('sintaxe-js', ['node', '../tools/sintaxe_js.mjs'], 60),
                  ('lint', [sys.executable, '-m', 'ruff', 'check', 'rubinot', 'tests'], 30),
                  ('python', [sys.executable, '-m', 'coverage', 'run', '--data-file='+str(saida/'coverage'), '../tools/testes.py'], 180),
                  ('coverage', [sys.executable, '-m', 'coverage', 'json', '--data-file='+str(saida/'coverage'), '-o', str(saida/'coverage.json')], 30)]
        suites += [(p.stem, ['node', p.name], 600 if p.name == 'test_roda.js' else 180)
                   for p in sorted(ANALISADOR.glob('test_*.js')) if args.perfil != 'rapido' or p.name != 'test_roda.js']
        suites += [('tracker-solo', ['node', '../loe-hunt-tracker-solo/check.js'], 60),
                   ('snapshots-trackers', [sys.executable, '../tools/sincronizar_trackers.py', '--verificar'], 30)]
        if (ROOT / 'loe-hunt-tracker' / 'check.js').is_file():
            suites += [('tracker-party', ['node', '../loe-hunt-tracker/check.js'], 60)]
        if args.perfil in ('completo', 'windows'):
            suites += [('e2e', [sys.executable, '../tools/e2e.py'], 180)]
        if args.perfil == 'windows' and sys.platform != 'win32':
            resultado['suites'].append({'nome': 'windows', 'estado': 'falhou', 'motivo': 'Exige Windows'})
        if args.perfil == 'compilado':
            if not args.executavel or not args.executavel.is_file():
                resultado['suites'].append({'nome': 'compilado', 'estado': 'falhou', 'motivo': '--executavel obrigatório'})
            else:
                suites += [('compilado', [str(args.executavel.resolve()), '--autoteste', '--resultado', str(saida / 'compilado.json')], 90)]
        inicio = time.monotonic()
        try:
            caminhos = list(ANALISADOR.glob('*.py')) + list((ANALISADOR / 'rubinot').rglob('*.py')) + list((ANALISADOR / 'tests').rglob('*.py')) + list((ROOT / 'tools').glob('*.py'))
            for p in caminhos:
                ast.parse(p.read_text(encoding='utf8'), filename=str(p))
            resultado['suites'].append({'nome': 'sintaxe', 'estado': 'passou', 'arquivos': len(caminhos)})
        except SyntaxError as erro:
            resultado['suites'].append({'nome': 'sintaxe', 'estado': 'falhou', 'erro': str(erro)})
        for nome, cmd, timeout in suites:
            print(f'[{nome}] executando...', flush=True)
            t = time.monotonic()
            try:
                r = subprocess.run(cmd, cwd=ANALISADOR, env=env, capture_output=True, timeout=timeout)
                log = r.stdout + b'\n' + r.stderr
                estado = 'passou' if r.returncode == 0 else 'falhou'
                codigo = r.returncode
            except subprocess.TimeoutExpired as erro:
                log = (erro.stdout or b'') + b'\n' + (erro.stderr or b'')
                estado = 'inconclusivo_timeout'; codigo = None
            except OSError as erro:
                log = str(erro).encode('utf8'); estado = 'falhou'; codigo = None
            (saida / (nome + '.log')).write_bytes(log)
            resultado['suites'].append({'nome': nome, 'estado': estado, 'codigo': codigo, 'duracao_s': round(time.monotonic() - t, 2)})
            print(f'[{nome}] {estado}', flush=True)
        resultado['duracao_s'] = round(time.monotonic() - inicio, 2)
    try:
        catalogo = json.loads((ROOT / 'tools/incidentes.json').read_text(encoding='utf8'))
        testes = json.loads((saida / 'python-testes.json').read_text(encoding='utf8'))
        aceites = json.loads((saida / 'e2e-incidentes.json').read_text(encoding='utf8')) if args.perfil in ('completo', 'windows') else []
        resultado['incidentes'] = conferir_incidentes(catalogo, resultado['suites'], testes, args.perfil, aceites)
        estado = 'passou' if all(c['estado'] != 'falhou' for c in resultado['incidentes']) else 'falhou'
        resultado['suites'].append({'nome': 'incidentes', 'estado': estado})
    except (OSError, ValueError, KeyError) as erro:
        resultado['suites'].append({'nome': 'incidentes', 'estado': 'falhou', 'erro': str(erro)})
    try:
        depois = fontes(ROOT)
        resultado['fontes_finais_sha256'] = depois['sha256']
        resultado['runtime_final_sha256'] = impressao_runtime()
        resultado['arquivos_alterados_durante_qa'] = diferencas(antes['arquivos'], depois['arquivos'])
        estavel = antes == depois and resultado['runtime_sha256'] == resultado['runtime_final_sha256']
        resultado['suites'].append({'nome': 'integridade-fontes', 'estado': 'passou' if estavel else 'falhou'})
        (saida / 'fontes-fim.json').write_text(json.dumps(depois, ensure_ascii=False, indent=2), encoding='utf8')
    except (OSError, subprocess.SubprocessError, RuntimeError) as erro:
        resultado['suites'].append({'nome': 'integridade-fontes', 'estado': 'falhou', 'erro': str(erro)})
    resultado['ok'] = all(s['estado'] == 'passou' for s in resultado['suites'])
    (saida / 'resultado.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf8')
    print('PASSOU' if resultado['ok'] else 'FALHOU OU INCONCLUSIVO', str(saida))
    return 0 if resultado['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
