"""Composição do leitor e observador; domínio não inicia captura."""
import threading
import time
import re
import os
import pathlib
from PIL import Image
import configuracoes

class Monitor:
    """Um consumidor: gravação compartilha f_; modo leve só captura o jogo à frente."""
    def __init__(self, sessao_de, ativo_de, fonte_de):
        self.sessao_de,self.ativo_de,self.fonte_de=sessao_de,ativo_de,fonte_de
        self.parar=threading.Event();self.leitor=configuracoes.Leitor()
        self.thread=threading.Thread(target=self._rodar,daemon=True)
        self.thread_rtc=threading.Thread(target=self._rodar_rtc,daemon=True)

    def iniciar(self):
        self.thread.start()
        self.thread_rtc.start()
    def fechar(self):
        self.parar.set()
        if self.thread.is_alive():self.thread.join(timeout=5)
        if self.thread_rtc.is_alive():self.thread_rtc.join(timeout=5)

    def _rodar(self):
        import capture
        import observacao_execucao
        observador=observacao_execucao.Observador()
        while not self.parar.is_set():
            try:
                if self.ativo_de():
                    sessao=self.sessao_de()
                    frames=self._quadros(sessao)
                    if frames and time.time()-frames[-1].stat().st_mtime<12:
                        layout=configuracoes._json(sessao/'layout.json');fonte=self.fonte_de();char=layout.get('char') or (fonte.get('char') if fonte.get('tipo')=='twitch' else None)
                        if not char:
                            info=capture.find_game_rect();char=self._char(info)
                        if char:
                            observador.processar(sessao,char,frames[-1])
                            observador.coletar_cura(sessao,char)
                elif self.fonte_de().get('tipo','janela')=='janela':
                    # Encerrar a gravação não abandona números pendentes. Retoma
                    # em lotes ao abrir o app, sem capturar ou alterar o jogo.
                    atual=self.sessao_de()
                    if atual:
                        for pasta in sorted(atual.parent.glob('session_*')):
                            if configuracoes._json(pasta/'coleta_cura.json').get('estado')=='pendente':
                                char_pendente=configuracoes._json(pasta/'layout.json').get('char')
                                if char_pendente:
                                    observador.coletar_cura(pasta,char_pendente)
                                    break
            except Exception as erro:
                configuracoes.ESTADO_LEITOR['erro_combate']=str(erro)
            self.parar.wait(1)

    def _rodar_rtc(self):
        import capture
        import ctypes
        import mss
        from rubinot.adapters.fila_rtc import consumir
        while not self.parar.is_set():
            try:
                atual=self.sessao_de()
                pastas=([atual] if atual else [])
                raiz=atual.parent if atual else pathlib.Path(os.environ.get('HUNT_CAPTURAS_RAIZ') or configuracoes.AQUI/'capture')
                pastas += [p for p in sorted(raiz.glob('session_*'),reverse=True) if p!=atual]
                for sessao in pastas:
                    layout=configuracoes._json(sessao/'layout.json')
                    fonte=self.fonte_de()
                    char=layout.get('char') or configuracoes._json(sessao/'contexto_hunt.json').get('char') or (fonte.get('char') if sessao==atual and fonte.get('tipo')=='twitch' else None)
                    if not char and sessao==atual and self.ativo_de():
                        char=self._char(capture.find_game_rect())
                    if char:
                        feitos=consumir(sessao,char,self.leitor,self._quadros(sessao),parar=self.parar)
                        if sessao==atual:
                            configuracoes.ESTADO_LEITOR['fila']=configuracoes._json(sessao/'coleta_rtc.json')
                        if feitos:
                            break
                if not self.ativo_de() and self.fonte_de().get('tipo','janela')=='janela':
                    info=capture.find_game_rect();char=self._char(info)
                    if info and char and ctypes.windll.user32.GetForegroundWindow()==info['hwnd']:
                        with mss.mss() as camera:
                            quadro=camera.grab(info['rect']);img=Image.frombytes('RGB',quadro.size,quadro.rgb)
                        self.leitor.processar_imagem(img,char)
            except Exception as erro:
                configuracoes.ESTADO_LEITOR.update(estado='falha de leitura',erro=str(erro))
            self.parar.wait(.1 if self.ativo_de() else 1)

    @staticmethod
    def _quadros(sessao):
        # q_ já contém a captura completa de cada tick; não criar outra captura
        # nem esperar os f_ espaçados. As provas aceitas são copiadas pelo leitor.
        return sorted([*sessao.glob('q_*.png'), *sessao.glob('f_*.png')],
                      key=lambda p: (p.name[2:], p.name[0]=='q')) if sessao else []

    @staticmethod
    def _char(info):
        if not info:return None
        titulo=info.get('title','');m=re.search(r'RubinOT Client\s*-\s*(.+)',titulo)
        return m[1].strip() if m else None
