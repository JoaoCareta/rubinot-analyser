"""Publicação de sessão: geração completa antes do resumo visível.

Leitores legados continuam vendo resumo.json; leitores atuais usam arquivos
da geração indicada nesse resumo, inclusive durante outra publicação.
"""
import hashlib
import pathlib
import re
import uuid
from .arquivos import gravar_bytes, gravar_json


def chave_sessao(nome, personagem=''):
    m = re.search(r'(\d{8}_\d{6})(?:_[a-f0-9]{8})?$', nome)
    if not m:
        raise ValueError('Identidade de sessão inválida.')
    sufixo = hashlib.sha256((nome + '\0' + personagem).encode('utf8')).hexdigest()[:8]
    return m[1] + '_' + sufixo


def publicar(pasta, resumo, arquivos):
    pasta = pathlib.Path(pasta)
    geracao = '_geracoes/' + uuid.uuid4().hex
    for nome, conteudo in arquivos.items():
        if pathlib.PurePosixPath(nome).name != nome:
            raise ValueError('Nome de arquivo inválido.')
        gravar_bytes(pasta / geracao / nome, conteudo)
    publicado = {**resumo, 'historico_schema': 2, 'geracao': geracao}
    gravar_json(pasta / geracao / 'resumo.json', publicado)
    # Compatibilidade com ferramentas que abrem arquivos pelo nome antigo.
    # O leitor atual usa a geração: uma falha aqui conserva a anterior inteira.
    for nome, conteudo in arquivos.items():
        gravar_bytes(pasta / nome, conteudo)
    gravar_json(pasta / 'resumo.json', publicado)
    return publicado


def arquivo_publicado(pasta, resumo, nome):
    pasta = pathlib.Path(pasta)
    geracao = resumo.get('geracao')
    if geracao:
        if not re.fullmatch(r'_geracoes/[a-f0-9]{32}', geracao):
            raise ValueError('Geração inválida.')
        return pasta / geracao / nome
    return pasta / nome


def reservar_sessao(raiz, agora):
    raiz=pathlib.Path(raiz);raiz.mkdir(parents=True,exist_ok=True)
    candidato=raiz / agora.strftime('session_%Y%m%d_%H%M%S')
    while True:
        try:
            candidato.mkdir()
            return candidato
        except FileExistsError:
            candidato=raiz / (agora.strftime('session_%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
