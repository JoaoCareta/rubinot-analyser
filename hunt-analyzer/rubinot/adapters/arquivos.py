"""Persistência de documentos: substituição atômica, temporários únicos."""
import json
import os
import pathlib
import tempfile
import threading
import time

_SUBSTITUICAO = threading.RLock()


def ler_json(caminho, padrao=None):
    try:
        return json.loads(pathlib.Path(caminho).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {} if padrao is None else padrao


def gravar_bytes(caminho, conteudo):
    caminho = pathlib.Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix='.' + caminho.name + '-', suffix='.tmp', dir=caminho.parent)
    try:
        with os.fdopen(fd, 'wb') as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        with _SUBSTITUICAO:
            # Windows/antivírus podem segurar o destino por poucos milissegundos.
            for tentativa in range(6):
                try:
                    os.replace(temporario, caminho)
                    break
                except PermissionError:
                    if tentativa == 5:
                        raise
                    time.sleep(0.01 * 2 ** tentativa)
    finally:
        pathlib.Path(temporario).unlink(missing_ok=True)


def gravar_json(caminho, dados):
    gravar_bytes(caminho, json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False).encode('utf8'))
