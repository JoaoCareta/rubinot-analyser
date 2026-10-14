"""Atualização reversível de arquivos de produto; dados pessoais ficam intactos."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import tempfile
from rastreabilidade import (fontes, produto as hashes_produto, reservar_saida,
                            trava_instalacao, validar_proveniencia, validar_qa)

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloco)
    return h.hexdigest()


def ativos():
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
        "Get-CimInstance Win32_Process -Filter \"Name='HuntAnalyzer.exe'\" | Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True, check=True)
    return r.stdout.strip()


def validar(exe, saida):
    from rastreabilidade import identidade
    destino = saida / ('autoteste-' + sha(exe)[:12] + '-' + identidade() + '.json')
    subprocess.run([str(exe), '--autoteste', '--resultado', str(destino)], cwd=exe.parent, check=True, timeout=90)
    r = json.loads(destino.read_text(encoding='utf8'))
    if not r.get('ok') or not r.get('compilado'):
        raise RuntimeError('Autoteste nativo não aprovou o aplicativo.')
    if pathlib.Path(r['comando'][0]).resolve() != exe.resolve():
        raise RuntimeError('Dispatcher aponta para outra instalação.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', required=True, type=pathlib.Path)
    p.add_argument('--instalacao', required=True, type=pathlib.Path)
    p.add_argument('--saida', required=True, type=pathlib.Path)
    p.add_argument('--qa', required=True, type=pathlib.Path)
    p.add_argument('--proveniencia', type=pathlib.Path,
                   help='Manifesto do build; padrão: proveniencia.json ao lado da pasta do pacote')
    args = p.parse_args()
    args.build_original = args.build.resolve()
    instalacao = args.instalacao.resolve()
    saida = args.saida.resolve()
    if (args.build_original == instalacao or args.build_original.is_relative_to(instalacao) or
            instalacao.is_relative_to(args.build_original) or saida.is_relative_to(instalacao) or
            saida.is_relative_to(args.build_original)):
        raise RuntimeError('Build, instalação e saída de evidências precisam estar separados.')
    args.proveniencia = args.proveniencia or args.build_original.parent / 'proveniencia.json'
    # A trava cobre preparo, cópia, validação e eventual reversão.
    with trava_instalacao(args.instalacao):
        args.saida = reservar_saida(args.saida)
        with tempfile.TemporaryDirectory(prefix='rubinot-entrega-') as tmp:
            inicial = hashes_produto(args.build_original)
            staging = pathlib.Path(tmp) / 'produto'
            shutil.copytree(args.build_original, staging)
            if inicial != hashes_produto(staging) or inicial != hashes_produto(args.build_original):
                raise RuntimeError('Pacote mudou durante a preparação da entrega.')
            args.build = staging
            executar(args)


def executar(args):
    build, instalacao, saida = (a.resolve() for a in (args.build, args.instalacao, args.saida))
    saida.mkdir(parents=True, exist_ok=True)
    qa = json.loads(args.qa.read_text(encoding='utf8'))
    from verificar import impressao_runtime
    atual = fontes(ROOT)
    runtime = impressao_runtime()
    validar_qa(qa, atual, runtime)
    proveniencia = json.loads(args.proveniencia.read_text(encoding='utf8'))
    validar_proveniencia(build, proveniencia, atual, runtime)
    if not (build / 'HuntAnalyzer.exe').is_file() or not (instalacao / 'HuntAnalyzer.exe').is_file():
        raise RuntimeError('Build ou instalação inválidos.')
    original = args.build_original
    if original == instalacao or original.is_relative_to(instalacao) or instalacao.is_relative_to(original):
        raise RuntimeError('Build e instalação precisam estar separados.')
    if ativos():
        raise RuntimeError('Aplicativo aberto: atualizar somente após a hunt encerrar.')
    sys.path.insert(0, str(ROOT / 'instalador'))
    import montar_pacote as pacote
    produto = {p.relative_to(build).as_posix(): p for p in build.rglob('*') if p.is_file()}
    hashes = hashes_produto(build)
    anteriores = {nome: sha(instalacao / nome) if (instalacao / nome).is_file() else None for nome in produto}
    for nome in produto:
        if pacote.PROIBIDO.search(nome) or pathlib.Path(nome).suffix in {'.py', '.pyc', '.pyw'} or pathlib.Path(nome).name in pacote.PESSOAIS:
            raise RuntimeError('Arquivo pessoal/fonte no build: ' + nome)
    pessoais = {p.relative_to(instalacao).as_posix(): sha(p) for p in instalacao.rglob('*')
                if p.is_file() and p.relative_to(instalacao).as_posix() not in produto}
    print(f'Pessoais identificados: {len(pessoais)}; conferindo build...', flush=True)
    validar(build / 'HuntAnalyzer.exe', saida)
    alterados = [nome for nome, fonte in produto.items() if not (instalacao / nome).is_file() or sha(fonte) != sha(instalacao / nome)]
    backup = saida / 'backup-instalacao'
    existentes = []
    for nome in alterados:
        antigo = instalacao / nome
        if antigo.is_file():
            destino = backup / nome; destino.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(antigo, destino)
            existentes.append(nome)
    manifesto = {'build': str(original), 'instalacao': str(instalacao), 'alterados': alterados,
                 'preexistentes': existentes, 'pessoais_antes': pessoais, 'estado': 'preparado',
                 'qa_id': qa['id'], 'qa_sha256': sha(args.qa), 'proveniencia_id': proveniencia['id'],
                 'fontes_sha256': atual['sha256'], 'runtime_sha256': runtime,
                 'produto_esperado': hashes, 'produto_anterior': anteriores,
                 'conferido_na_tela': False, 'beneficio_observado': False}
    (saida / 'qa-utilizado.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf8')
    (saida / 'proveniencia-utilizada.json').write_text(json.dumps(proveniencia, ensure_ascii=False, indent=2), encoding='utf8')
    (saida / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf8')
    if ativos():
        raise RuntimeError('Aplicativo abriu durante a preparação; instalação preservada.')
    validar_qa(qa, fontes(ROOT), impressao_runtime())
    if hashes != hashes_produto(build) or anteriores != {
            nome: sha(instalacao / nome) if (instalacao / nome).is_file() else None for nome in produto}:
        raise RuntimeError('Pacote ou instalação mudou durante a preparação; nada foi copiado.')
    print(f'Atualizando {len(alterados)} arquivos de produto...', flush=True)
    try:
        for nome in alterados:
            destino = instalacao / nome; destino.parent.mkdir(parents=True, exist_ok=True)
            tmp = destino.with_name('.' + destino.name + '.atualizacao')
            shutil.copy2(produto[nome], tmp)
            if sha(tmp) != hashes[nome]:
                raise RuntimeError('Cópia diverge do pacote validado: ' + nome)
            os.replace(tmp, destino)
        validar(instalacao / 'HuntAnalyzer.exe', saida)
        entregues = {nome: sha(instalacao / nome) for nome in produto}
        if entregues != hashes:
            raise RuntimeError('Produto instalado diverge do pacote validado.')
        depois = {nome: sha(instalacao / nome) for nome in pessoais}
        if depois != pessoais:
            raise RuntimeError('Hash pessoal divergente.')
        # Reversão demonstrada em instalação temporária, sem reverter dados atuais.
        reversao = saida / 'teste-reversao'
        for nome in produto:
            origem = instalacao / nome; destino = reversao / nome
            destino.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(origem, destino)
        for arquivo in (instalacao / 'ui').rglob('*'):
            if arquivo.is_file() and arquivo.name not in pacote.PESSOAIS:
                destino = reversao / arquivo.relative_to(instalacao)
                destino.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(arquivo, destino)
        for nome in existentes:
            shutil.copy2(backup / nome, reversao / nome)
        validar(reversao / 'HuntAnalyzer.exe', saida)
        manifesto.update({'estado': 'atualizado', 'pessoais_preservados': len(pessoais), 'reversao_autoteste': True,
                          'exe_sha256': sha(instalacao / 'HuntAnalyzer.exe'), 'produto_instalado': entregues})
    except BaseException:
        for nome in alterados:
            destino = instalacao / nome
            if nome in existentes:
                shutil.copy2(backup / nome, destino)
            else:
                destino.unlink(missing_ok=True)
        manifesto['estado'] = 'revertido_por_falha'
        raise
    finally:
        (saida / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf8')
    print('Instalação atualizada; pessoais preservados; reversão testada.', flush=True)


if __name__ == '__main__':
    main()
