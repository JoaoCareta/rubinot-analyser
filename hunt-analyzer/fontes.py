"""Configuração de entrada e calibrações isoladas, preservando a janela legada."""
import hashlib
import json
import pathlib
import re
from urllib.parse import urlsplit

PASTA = pathlib.Path(__file__).resolve().parent
CONFIG = PASTA / 'fonte.json'


def normalizar(dados):
    tipo = dados.get('tipo', 'janela')
    if tipo == 'janela':
        return {'tipo': 'janela'}
    if tipo != 'twitch':
        raise ValueError('Escolha Janela do RubinOT ou Live da Twitch.')
    canal = str(dados.get('canal', '')).strip()
    if '/' in canal or '.' in canal:
        u = urlsplit(canal if '://' in canal else 'https://' + canal)
        if u.scheme != 'https' or u.netloc.lower() not in ('twitch.tv', 'www.twitch.tv') or u.query or u.fragment:
            raise ValueError('Informe o canal ou um link https://www.twitch.tv/canal.')
        canal = u.path.strip('/')
    if not re.fullmatch(r'[A-Za-z0-9_]{3,25}', canal):
        raise ValueError('Canal Twitch inválido. Informe somente o nome do canal ou seu link.')
    char = str(dados.get('char', '')).strip()
    if not re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '\-]{1,39}", char):
        raise ValueError('Informe o nome do personagem mostrado na live.')
    return {'tipo': tipo, 'canal': canal.lower(), 'char': char}


def atual():
    return normalizar(json.loads(CONFIG.read_text(encoding='utf-8'))) if CONFIG.exists() else {'tipo': 'janela'}


def grava_json(path, dados):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def salvar(dados):
    fonte = normalizar(dados)
    grava_json(CONFIG, fonte)
    return fonte


def caminhos(fonte=None):
    f = fonte or atual()
    if f['tipo'] == 'janela':
        return PASTA / 'calibracao.json', PASTA / 'calibracao_print.png'
    chave = hashlib.sha256(f['char'].encode('utf-8')).hexdigest()[:12]
    pasta = PASTA / 'fontes' / f['canal'] / chave
    return pasta / 'calibracao.json', pasta / 'calibracao_print.png'


def da_sessao(sessao):
    p = pathlib.Path(sessao) / 'fonte.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'tipo': 'janela'}
