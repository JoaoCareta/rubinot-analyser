"""Leitor contínuo: mantém só o quadro recente; anúncios/offline viram lacuna.

Usa o leitor HLS do Streamlink, inclusive seu filtro de anúncios, antes do PyAV.
Nunca entrega a URL assinada para logs ou para o navegador.
"""
import threading
import time


class FluxoLeitura:
    """Adapta o StreamIO do Streamlink, cujo IOBase anuncia readable=False."""

    def __init__(self, fluxo):
        self.fluxo = fluxo

    def readable(self):
        return True

    def read(self, tamanho=-1):
        return self.fluxo.read(tamanho)

    def close(self):
        self.fluxo.close()


class Leitor:
    def __init__(self, canal):
        self.canal = canal
        self.parar = threading.Event()
        self.trava = threading.Lock()
        self.quadro = None
        self.recebido = 0
        self.sequencia = 0
        self.mensagem = 'Conectando à Twitch…'
        self.fluxo = None
        self.thread = threading.Thread(target=self._rodar, daemon=True)
        self.thread.start()

    def ultimo(self, depois=0):
        with self.trava:
            if self.quadro is None or time.monotonic() - self.recebido > 3 or self.sequencia <= depois:
                return None, self.sequencia
            return self.quadro.copy(), self.sequencia

    def estado(self):
        with self.trava:
            idade = round(time.monotonic() - self.recebido, 1) if self.recebido else None
            conectado = self.quadro is not None and idade <= 3
            return {'conectado': conectado, 'ultimo_quadro_s': idade,
                    'mensagem': 'Recebendo a live (há atraso da transmissão).' if conectado else self.mensagem,
                    'resolucao': list(self.quadro.size) if self.quadro is not None else None}

    def fechar(self):
        self.parar.set()
        fluxo = self.fluxo
        if fluxo:
            try:
                fluxo.close()
            except Exception:
                pass
        self.thread.join(timeout=12)

    def _rodar(self):
        espera = 2
        while not self.parar.is_set():
            sessao = container = fluxo = None
            try:
                import av
                import truststore
                from streamlink import Streamlink
                from streamlink.plugins.twitch import Twitch
                truststore.inject_into_ssl()
                sessao = Streamlink()
                sessao.set_option('http-timeout', 10)
                sessao.set_option('stream-timeout', 10)
                sessao.set_option('hls-live-edge', 2)
                streams = Twitch(sessao, 'https://www.twitch.tv/' + self.canal).streams()
                if 'best' not in streams:
                    raise RuntimeError('offline')
                fluxo = self.fluxo = FluxoLeitura(streams['best'].open())
                container = av.open(fluxo, mode='r')
                for frame in container.decode(video=0):
                    if self.parar.is_set():
                        break
                    img = frame.to_image()
                    with self.trava:
                        self.quadro = img
                        self.recebido = time.monotonic()
                        self.sequencia += 1
                    espera = 2
                self.mensagem = 'A live interrompeu. Tentando reconectar…'
            except ImportError:
                self.mensagem = 'Componentes de stream ausentes. Atualize o Hunt Analyzer.'
                return
            except Exception:
                # Exceções de rede podem conter tokens e URLs de segmentos.
                self.mensagem = 'Live offline, anúncio ou conexão indisponível. Tentando novamente…'
            finally:
                with self.trava:
                    self.quadro = None
                if container:
                    container.close()
                if fluxo:
                    fluxo.close()
                self.fluxo = None
                if sessao:
                    sessao.http.close()
            self.parar.wait(espera)
            espera = min(30, espera * 2)
