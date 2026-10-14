"""Rastreia conexão e leitura HTTP do smoke sem esconder erros ou repetir rotas."""
from contextlib import contextmanager
import json
import http.client
import time
import urllib.parse
import urllib.request


class Resposta:
    def __init__(self, resposta, registro, salvar):
        self.resposta = resposta
        self.registro = registro
        self.salvar = salvar

    def __getattr__(self, nome):
        return getattr(self.resposta, nome)

    def _ler(self, metodo, *args):
        self.registro['fase'] = 'leitura'
        self.salvar()
        dados = getattr(self.resposta, metodo)(*args)
        self.registro['bytes'] += len(dados)
        self.salvar()
        return dados

    def read(self, *args):
        return self._ler('read', *args)

    def read1(self, *args):
        return self._ler('read1', *args)


class DiagnosticoHTTP:
    def __init__(self, arquivo, processo):
        self.arquivo = arquivo
        self.processo = processo
        self.registros = []

    def salvar(self):
        self.arquivo.write_text(json.dumps({'pid': self.processo.pid,
            'codigo_processo': self.processo.poll(), 'requisicoes': self.registros},
            ensure_ascii=False, indent=2), encoding='utf8')

    @contextmanager
    def abrir(self, requisicao, timeout, persistente=False):
        url = requisicao.full_url if isinstance(requisicao, urllib.request.Request) else requisicao
        registro = {'url': url, 'timeout_s': timeout, 'persistente': persistente, 'fase': 'conexao', 'bytes': 0,
                    'estado': 'executando', 'inicio_unix': time.time()}
        self.registros.append(registro)
        inicio = time.monotonic()
        self.salvar()
        conexao = None
        try:
            if persistente:
                endereco = urllib.parse.urlsplit(url)
                if endereco.scheme != 'http' or endereco.hostname not in ('127.0.0.1', 'localhost'):
                    raise ValueError('Conexão persistente do smoke exige HTTP local.')
                conexao = http.client.HTTPConnection(endereco.hostname, endereco.port, timeout=timeout)
                pedido = requisicao if isinstance(requisicao, urllib.request.Request) else urllib.request.Request(url)
                conexao.request(pedido.get_method(), endereco.path + ('?' + endereco.query if endereco.query else ''),
                                body=pedido.data, headers=dict(pedido.header_items()))
                resposta = conexao.getresponse()
            else:
                resposta = urllib.request.urlopen(requisicao, timeout=timeout)
            with resposta:
                registro.update(status=resposta.status, conexao_s=round(time.monotonic()-inicio, 3),
                                tamanho_declarado=resposta.headers.get('Content-Length'))
                self.salvar()
                yield Resposta(resposta, registro, self.salvar)
            registro['estado'] = 'passou'
        except Exception as erro:
            registro.update(estado='falhou', erro=type(erro).__name__ + ': ' + str(erro),
                            status=getattr(erro, 'code', registro.get('status')))
            raise
        finally:
            if conexao is not None:
                conexao.close()
            registro['duracao_s'] = round(time.monotonic()-inicio, 3)
            self.salvar()
