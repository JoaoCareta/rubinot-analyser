"""Composição do leitor e observador; domínio não inicia captura."""
import threading
import time
import re
from PIL import Image
import configuracoes

class Monitor:
    """Um consumidor: gravação compartilha f_; modo leve só captura o jogo à frente."""
    def __init__(self, sessao_de, ativo_de, fonte_de):
        self.sessao_de,self.ativo_de,self.fonte_de=sessao_de,ativo_de,fonte_de
        self.parar=threading.Event();self.leitor=configuracoes.Leitor(estabilizar=True)
        self.thread=threading.Thread(target=self._rodar,daemon=True)

    def iniciar(self):self.thread.start()
    def fechar(self):
        self.parar.set()
        if self.thread.is_alive():self.thread.join(timeout=5)

    def _rodar(self):
        import capture
        import ctypes
        import mss
        import observacao_execucao
        observador=observacao_execucao.Observador()
        while not self.parar.is_set():
            try:
                if self.ativo_de():
                    sessao=self.sessao_de()
                    frames=sorted(sessao.glob('f_*.png')) if sessao else []
                    if frames and time.time()-frames[-1].stat().st_mtime<12:
                        layout=configuracoes._json(sessao/'layout.json');fonte=self.fonte_de();char=layout.get('char') or (fonte.get('char') if fonte.get('tipo')=='twitch' else None)
                        if not char:
                            info=capture.find_game_rect();char=self._char(info)
                        self.leitor.processar(frames[-1],char,sessao.name)
                        if char:observador.processar(sessao,char,frames[-1])
                    else:configuracoes.ESTADO_LEITOR.update({'estado':'aguardando quadro atual','janelas':[]})
                elif self.fonte_de().get('tipo','janela')=='janela':
                    info=capture.find_game_rect()
                    char=self._char(info)
                    if info and char and ctypes.windll.user32.GetForegroundWindow()==info['hwnd']:
                        with mss.mss() as camera:
                            quadro=camera.grab(info['rect']);img=Image.frombytes('RGB',quadro.size,quadro.rgb)
                        self.leitor.processar_imagem(img,char)
                    else:configuracoes.ESTADO_LEITOR.update({'estado':'aguardando jogo em primeiro plano','janelas':[]})
            except Exception as erro:
                configuracoes.ESTADO_LEITOR.update({'estado':'aguardando leitura','erro':str(erro),'janelas':[]})
            self.parar.wait(4)

    @staticmethod
    def _char(info):
        if not info:return None
        titulo=info.get('title','');m=re.search(r'RubinOT Client\s*-\s*(.+)',titulo)
        return m[1].strip() if m else None
