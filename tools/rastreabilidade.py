"""Proveniência e exclusão mútua das ferramentas; nunca altera dados de hunts."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def identidade():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]


def sha(arquivo):
    h = hashlib.sha256()
    with Path(arquivo).open('rb') as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloco)
    return h.hexdigest()


def resumo(arquivos):
    return hashlib.sha256(json.dumps(arquivos, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf8')).hexdigest()


def fontes(raiz):
    raiz = Path(raiz)
    nomes = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                           cwd=raiz, capture_output=True, check=True).stdout.decode('utf8').split('\0')
    arquivos = {n: sha(raiz / n) for n in sorted(set(nomes)) if n and (raiz / n).is_file()}
    return {'sha256': resumo(arquivos), 'arquivos': arquivos}


def diferencas(antes, depois):
    return sorted(n for n in antes.keys() | depois.keys() if antes.get(n) != depois.get(n))


def produto(raiz):
    raiz = Path(raiz).resolve()
    arquivos = {}
    for p in sorted(raiz.rglob('*')):
        if p.is_symlink() or not p.resolve().is_relative_to(raiz):
            raise RuntimeError('Link não permitido no pacote: ' + str(p))
        if p.is_file():
            arquivos[p.relative_to(raiz).as_posix()] = sha(p)
    return arquivos


def reservar_saida(destino, marcador='execucao'):
    """Uma tentativa nunca sobrescreve evidências de outra, mesmo concorrente."""
    destino = Path(destino).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    try:
        with (destino / (marcador + '.json')).open('x', encoding='utf8') as f:
            json.dump({'id': identidade(), 'pid': os.getpid()}, f)
    except FileExistsError:
        return reservar_saida(destino / 'tentativas' / identidade(), marcador)
    # Também preserva diretórios produzidos por versões anteriores, sem marcador.
    if (destino / 'resultado.json').exists() or (destino / 'nativo.json').exists() or (destino / 'manifesto.json').exists():
        return reservar_saida(destino / 'tentativas' / identidade(), marcador)
    return destino


@contextmanager
def trava_instalacao(instalacao):
    """Trava do SO, liberada inclusive após crash; arquivo estável fora dos dados."""
    chave = hashlib.sha256(os.path.normcase(str(Path(instalacao).resolve())).encode()).hexdigest()
    pasta = Path(tempfile.gettempdir()) / 'rubinot-atualizacao-locks'
    pasta.mkdir(exist_ok=True)
    with (pasta / (chave + '.lock')).open('a+b') as f:
        if f.seek(0, 2) == 0:
            f.write(b'0'); f.flush()
        f.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as erro:
            raise RuntimeError('Outra atualização está em andamento nesta instalação.') from erro
        try:
            yield
        finally:
            f.seek(0)
            if os.name == 'nt':
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def emitir_proveniencia(build, destino, antes, depois, runtime_antes, runtime_depois):
    if antes != depois or runtime_antes != runtime_depois:
        raise RuntimeError('Fontes mudaram durante o build; pacote sem aprovação.')
    dados = {'schema': 1, 'id': identidade(), 'fontes_sha256': antes['sha256'],
             'runtime_sha256': runtime_antes, 'fontes': antes['arquivos'],
             'produto': produto(build)}
    if 'HuntAnalyzer.exe' not in dados['produto']:
        raise RuntimeError('Proveniência exige o executável compilado.')
    destino = Path(destino)
    historico = destino.parent / 'proveniencias'
    historico.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, indent=2)
    (historico / (dados['id'] + '.json')).write_text(texto, encoding='utf8')
    temporario = destino.with_name(destino.name + '.' + dados['id'] + '.tmp')
    temporario.write_text(texto, encoding='utf8')
    os.replace(temporario, destino)
    return dados


def validar_proveniencia(build, evidencia, fontes_atual, runtime_atual):
    if evidencia.get('schema') != 1 or not evidencia.get('id'):
        raise RuntimeError('Build sem proveniência verificável; recompile pelo fluxo documentado.')
    if (evidencia.get('fontes_sha256') != fontes_atual['sha256'] or
            evidencia.get('runtime_sha256') != runtime_atual or
            evidencia.get('fontes') != fontes_atual['arquivos']):
        raise RuntimeError('Build pertence a outra revisão das fontes/testes.')
    esperado = evidencia.get('produto', {})
    if 'HuntAnalyzer.exe' not in esperado or esperado != produto(build):
        raise RuntimeError('Pacote diverge da proveniência: executável, assets ou arquivos extras.')


def validar_qa(qa, atual, runtime):
    suites = qa.get('suites', [])
    if (qa.get('schema', 0) < 2 or not qa.get('id') or not qa.get('ok') or
            qa.get('perfil') not in ('completo', 'windows') or not suites or
            any(s.get('estado') != 'passou' for s in suites) or
            not {'python', 'e2e', 'integridade-fontes', 'incidentes'}.issubset(s.get('nome') for s in suites) or
            qa.get('fontes_sha256') != atual['sha256'] or
            qa.get('fontes_finais_sha256') != atual['sha256'] or
            qa.get('runtime_sha256') != runtime or qa.get('runtime_final_sha256') != runtime):
        raise RuntimeError('Harness completo ausente, inconclusivo ou de outra revisão das fontes/testes.')


def conferir_incidentes(catalogo, suites, testes, perfil, aceites_e2e=()):
    estados = {s['nome']: s['estado'] for s in suites}
    executados = {t['id']: t['estado'] for t in testes}
    casos = []
    for caso in catalogo:
        ausentes = [t for t in caso.get('python', []) if executados.get(t) != 'passou']
        exigidas = caso.get('suites', [])
        sem_navegador = perfil not in ('completo', 'windows')
        falhas = [s for s in exigidas if estados.get(s) != 'passou' and not (sem_navegador and s == 'e2e')]
        parcial = sem_navegador and 'e2e' in exigidas
        if not sem_navegador and caso.get('aceite_e2e') and caso['aceite_e2e'] not in aceites_e2e:
            falhas.append('aceite_e2e:' + caso['aceite_e2e'])
        estado = 'falhou' if ausentes or falhas else 'parcial' if parcial else 'passou'
        casos.append({'id': caso['id'], 'estado': estado, 'testes_pendentes': ausentes,
                      'suites_pendentes': falhas, 'criterio': caso['criterio']})
    return casos
