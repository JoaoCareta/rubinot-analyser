"""Consulta somente leitura da sequência visual preservada em capture/."""
import re

SESSAO = re.compile(r'session_\d{8}_\d{6}(?:_[a-f0-9]{8})?')
QUADRO = re.compile(r'[qf]_(\d{2,})(\d{2})(\d{2})_(\d{3})\.png')


def pasta(raiz, sessao):
    if not isinstance(sessao, str) or not SESSAO.fullmatch(sessao):
        return None
    p = raiz / sessao
    return p if p.resolve().is_relative_to(raiz.resolve()) and p.is_dir() else None


def quadro(raiz, sessao, nome):
    p = pasta(raiz, sessao)
    if p is None or not isinstance(nome, str) or not QUADRO.fullmatch(nome):
        return None
    arquivo = p / nome
    return arquivo if arquivo.resolve().is_relative_to(p.resolve()) and arquivo.is_file() else None


def indice(raiz, sessoes):
    trechos = []
    for sessao in dict.fromkeys(sessoes):
        p = pasta(raiz, sessao)
        # q_ e f_ podem coexistir; os f_ antigos também são evidência útil.
        por_instante = {}
        if p:
            for arq in p.iterdir():
                m = QUADRO.fullmatch(arq.name)
                if not m or not arq.is_file() or not arq.resolve().is_relative_to(p.resolve()):
                    continue
                h, minuto, segundo, ms = map(int, m.groups())
                t = h * 3600 + minuto * 60 + segundo + ms / 1000
                if t not in por_instante or arq.name.startswith('q_'):
                    por_instante[t] = arq.name
        trechos.append({'sessao': sessao, 'quadros': [
            {'nome': nome, 't': t} for t, nome in sorted(por_instante.items())]})
    return {'retencao': 'somente_exclusao_solicitada', 'trechos': trechos,
            'limite': 'Sequência de imagens capturadas, sem áudio. Cadência alvo: 0,5 s; '
                      'intervalos maiores são lacunas, não vídeo contínuo. '
                      'Quadros antigos já apagados não são recuperados.'}
