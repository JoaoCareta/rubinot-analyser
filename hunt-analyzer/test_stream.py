"""Regressões da entrada Twitch. Não acessa a rede nem as sessões pessoais."""
import contextlib
import io
import json
import pathlib
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
import fontes
import painel_stream
import stream_twitch


class FontesTest(unittest.TestCase):
    def test_dano_cura_pessoal_nao_confunde_dano_por_hora(self):
        v = painel_stream.campos(['Damage: 5,823k','Damage/h: 945,885','Healing: 750,669'])
        self.assertEqual(v['Damage'], 5823000)
        self.assertEqual(v['Healing'], 750669)
        self.assertNotIn('Damage', painel_stream.campos(['Damage: 5,?23k']))
        with Image.open('tests/fixtures/leitores/hunt-cura.png') as img:
            v, _ = painel_stream.ler(img)
        self.assertEqual(v['Healing'], 750669)

    def test_urls_e_personagem(self):
        f = fontes.normalizar({'tipo':'twitch', 'canal':'https://www.twitch.tv/9Dude', 'char':'Traps the cat'})
        self.assertEqual(f['canal'], '9dude')
        for canal in ['https://evil.test/9dude', 'https://twitch.tv@evil.test/x', 'file:///x', '../abc', 'https://twitch.tv/a/videos', 'https://twitch.tv/abc?token=x']:
            with self.assertRaises(ValueError):
                fontes.normalizar({**f, 'canal':canal})

    def test_isolamento_preserva_janela(self):
        with tempfile.TemporaryDirectory() as d, patch.object(fontes, 'PASTA', pathlib.Path(d)), patch.object(fontes, 'CONFIG', pathlib.Path(d)/'fonte.json'):
            local, _ = fontes.caminhos()
            local.write_text('{"original":true}', encoding='utf-8')
            a = fontes.salvar({'tipo':'twitch','canal':'9dude','char':'Traps the cat'})
            ca, pa = fontes.caminhos()
            fontes.grava_json(ca, {'a':1})
            b = fontes.salvar({**a, 'canal':'outro'})
            self.assertNotEqual(fontes.caminhos()[0], ca)
            self.assertNotEqual(fontes.caminhos({**a, 'char':'Outro nome'})[0], ca)
            fontes.salvar({'tipo':'janela'})
            self.assertEqual(fontes.caminhos()[0], local)
            self.assertEqual(json.loads(local.read_text()), {'original':True})
            self.assertEqual(json.loads(ca.read_text()), {'a':1})

    def test_frames_nao_repetem_e_expiram(self):
        r = stream_twitch.Leitor.__new__(stream_twitch.Leitor)
        r.trava = threading.Lock(); r.quadro = Image.new('RGB',(20,10))
        r.recebido = time.monotonic(); r.sequencia = 7; r.mensagem = 'Lacuna'
        self.assertIsNotNone(r.ultimo(6)[0])
        self.assertIsNone(r.ultimo(7)[0])
        r.recebido -= 4
        self.assertIsNone(r.ultimo()[0])
        self.assertFalse(r.estado()['conectado'])

    def test_numeros_nao_truncam_e_balance_confere(self):
        for ruim in ['9?', '94,18', '1,2,345', '12 345', '?123', '123?']:
            self.assertIsNone(painel_stream.numero(ruim))
        self.assertEqual(painel_stream.numero('11,529k'), 11529000)
        self.assertEqual(painel_stream.numero('-329'), -329)
        self.assertEqual(painel_stream.numero('0'), 0)
        l = ['Loot: 96,748', 'Supplies: 2,564', 'Balance: 9']
        self.assertNotIn('Balance', painel_stream.campos(l))
        self.assertEqual(painel_stream.campos(l[:2]+['Balance: 94,184'])['Balance'],94184)
        self.assertEqual(painel_stream.campos(['Loot: 0','Supplies: 329','Balance: -329'])['Balance'],-329)
        self.assertNotIn('Balance', painel_stream.campos(['Balance: 94,184']))

    def test_captura_stream_sem_jogo(self):
        import capture
        import layout
        f = {'tipo':'twitch','canal':'9dude','char':'Teste'}
        r = {'left':20,'top':20,'width':300,'height':200}
        c = {'regioes':{k:dict(r) for k in layout.REGIOES_OBRIGATORIAS}, 'janela':{'largura':640,'altura':480}}
        class Fake:
            def __init__(self,*a): self.n=0; self.fechou=False
            def ultimo(self,*a): self.n+=1; return Image.new('RGB',(640,480)),self.n
            def estado(self): return {'conectado':True}
            def fechar(self): self.fechou=True
        leitor = Fake()
        with tempfile.TemporaryDirectory() as d, contextlib.ExitStack() as st:
            base=pathlib.Path(d); cp=base/'cal.json'; fontes.grava_json(cp,c)
            session=base/'session_20261009_000000'
            session.mkdir()
            # Mesmo consumidos e anteriores ao antigo buffer de 60 s, não expiram.
            antigos = [session/f'q_000000_{n:03d}.png' for n in range(121)]
            for antigo in antigos:
                antigo.write_bytes(b'prova anterior')
            fontes.grava_json(session/'coleta_cura.json', {'estado':'numeros_persistidos','ultimo':'q_999999_999.png'})
            st.enter_context(patch.object(capture.sys,'argv',['capture',str(session)]))
            st.enter_context(patch.object(fontes,'atual',return_value=f))
            st.enter_context(patch.object(fontes,'caminhos',return_value=(cp,base/'print.png')))
            st.enter_context(patch.object(capture,'pouco_disco',return_value=False))
            st.enter_context(patch.object(capture,'find_game_rect',side_effect=AssertionError('Não pode abrir o jogo')))
            st.enter_context(patch.object(stream_twitch,'Leitor',return_value=leitor))
            st.enter_context(patch.object(capture,'MAX_HOURS',0.5/3600))
            with contextlib.redirect_stdout(io.StringIO()): capture.main()
            for prefix in ['c','m','f','q']:
                paths=[p for p in session.glob(prefix+'_*.png') if p not in antigos]; self.assertEqual(len(paths),1)
                with Image.open(paths[0]) as img: img.verify()
            self.assertTrue(all(p.read_bytes() == b'prova anterior' for p in antigos))
            # Quadro preto não identifica Battle List: ausência nunca vira lista vazia.
            self.assertEqual(list(session.glob('b_*.png')), [])
            self.assertTrue(leitor.fechou)
            self.assertEqual(fontes.da_sessao(session),f)
            self.assertEqual(json.loads((session/'calibracao.json').read_text())['janela'],c['janela'])

    def test_api_recusa_troca_durante_gravacao(self):
        import app
        with patch.object(app.ao_vivo, 'ativo', return_value=True), patch.object(fontes, 'salvar') as salvar:
            self.assertFalse(app.muda_fonte({'tipo':'janela'})['ok'])
            salvar.assert_not_called()

    def test_captura_local_preserva_fluxo(self):
        import capture
        import layout
        r={'left':20,'top':20,'width':300,'height':200}
        c={'regioes':{k:dict(r) for k in layout.REGIOES_OBRIGATORIAS},'janela':{'largura':640,'altura':480}}
        class MSS:
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def grab(self,rect):
                class Shot:
                    size=(640,480)
                    rgb=bytes(640*480*3)
                return Shot()
        with tempfile.TemporaryDirectory() as d, contextlib.ExitStack() as st:
            base=pathlib.Path(d); cp=base/'cal.json'; fontes.grava_json(cp,c)
            session=base/'session_20261009_000000'
            st.enter_context(patch.object(capture.sys,'argv',['capture',str(session)]))
            st.enter_context(patch.object(fontes,'atual',return_value={'tipo':'janela'}))
            st.enter_context(patch.object(fontes,'caminhos',return_value=(cp,base/'print.png')))
            st.enter_context(patch.object(capture,'pouco_disco',return_value=False))
            st.enter_context(patch.object(capture,'find_game_rect',return_value={'title':'RubinOT Client - Teste','rect':{'left':0,'top':0,'width':640,'height':480}}))
            st.enter_context(patch.object(capture.mss,'MSS',MSS))
            stream=st.enter_context(patch.object(stream_twitch,'Leitor'))
            st.enter_context(patch.object(capture,'MAX_HOURS',0.5/3600))
            with contextlib.redirect_stdout(io.StringIO()): capture.main()
            self.assertEqual(len(list(session.glob('f_*.png'))),1)
            stream.assert_not_called()

    def test_api_troca_carrega_e_restaura_calibracao(self):
        import app
        original = app.CALIB, app.PRINT
        try:
            with tempfile.TemporaryDirectory() as d, patch.object(fontes,'PASTA',pathlib.Path(d)), patch.object(fontes,'CONFIG',pathlib.Path(d)/'fonte.json'), patch.object(app.ao_vivo,'ativo',return_value=False):
                local, _ = fontes.caminhos()
                fontes.grava_json(local,{'regioes':{'hunt':{'left':1}},'char':'Local'})
                r=app.muda_fonte({'tipo':'twitch','canal':'9dude','char':'Teste'})
                self.assertTrue(r['ok'])
                self.assertEqual(app.carregar()['regioes'],{})
                self.assertFalse(app.carregar()['tem_print'])
                self.assertFalse(app.salvar({'regioes':{}})['ok'])
                app.muda_fonte({'tipo':'janela'})
                self.assertEqual(app.carregar()['regioes'],{'hunt':{'left':1}})
        finally:
            app.CALIB, app.PRINT = original

    def test_quadros_preservados_com_moeda(self):
        # A evidência JPEG não é idêntica ao frame original; este é um replay separado.
        with Image.open('tests/fixtures/leitores/hunt-moeda.png') as img: v,_=painel_stream.ler(img)
        self.assertEqual(v['Loot'],185149)
        self.assertEqual(v['Supplies'],5998)
        self.assertEqual(v['Balance'],179151)
        self.assertEqual(v['RawXPGain'],958373)

    def test_resolucao_diferente_nao_publica_png(self):
        import capture
        import layout
        r = {'left':20,'top':20,'width':300,'height':200}
        c = {'regioes':{k:dict(r) for k in layout.REGIOES_OBRIGATORIAS}, 'janela':{'largura':640,'altura':480}}
        class Fake:
            def ultimo(self,*a): return Image.new('RGB',(800,600)),1
            def estado(self): return {'conectado':True}
            def fechar(self): pass
        with tempfile.TemporaryDirectory() as d, contextlib.ExitStack() as st:
            base=pathlib.Path(d); cp=base/'cal.json'; fontes.grava_json(cp,c)
            session=base/'session_20261009_000000'
            st.enter_context(patch.object(capture.sys,'argv',['capture',str(session)]))
            st.enter_context(patch.object(fontes,'atual',return_value={'tipo':'twitch','canal':'9dude','char':'Teste'}))
            st.enter_context(patch.object(fontes,'caminhos',return_value=(cp,base/'print.png')))
            st.enter_context(patch.object(capture,'pouco_disco',return_value=False))
            st.enter_context(patch.object(stream_twitch,'Leitor',return_value=Fake()))
            st.enter_context(patch.object(capture.time,'sleep',side_effect=KeyboardInterrupt))
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt): capture.main()
            self.assertEqual(list(session.glob('*.png')),[])
            estado=json.loads((session/'stream_estado.json').read_text(encoding='utf-8'))
            self.assertFalse(estado['conectado'])
            self.assertIn('resolução',estado['mensagem'])

    def test_retoma_nao_mistura_fontes(self):
        import ao_vivo
        import layout
        with tempfile.TemporaryDirectory() as d, patch.object(fontes,'atual',return_value={'tipo':'twitch','canal':'9dude','char':'Teste'}), patch.object(layout,'atual',return_value=layout.LEGADO):
            root=pathlib.Path(d); s=root/'session_20261009_000000'; s.mkdir()
            (s/'m_000000_000.png').touch()
            (s/'lap_state.json').write_text('{}')
            self.assertIsNone(ao_vivo.retomavel(raiz=root))
            fontes.grava_json(s/'fonte.json',fontes.atual())
            self.assertEqual(ao_vivo.retomavel(raiz=root),s)

    def test_reconexao_e_fechamento_do_leitor(self):
        import av
        import numpy as np
        from streamlink.plugins.twitch import Twitch
        gate=threading.Event(); recebeu=threading.Event()
        class Container:
            def decode(self, **kwargs):
                yield av.VideoFrame.from_ndarray(np.zeros((10,20,3),dtype='uint8'),format='rgb24')
                recebeu.set(); gate.wait(5)
            def close(self): pass
        class Fluxo(io.BytesIO):
            def close(self): gate.set(); super().close()
        fluxo=Fluxo()
        class Stream:
            def open(self): return fluxo
        # A primeira abertura falha. A segunda recebe vídeo; fechar libera o fluxo.
        with patch.object(Twitch,'streams',side_effect=[RuntimeError('offline'),{'best':Stream()}]), patch.object(av,'open',return_value=Container()):
            leitor=stream_twitch.Leitor('9dude')
            try:
                self.assertTrue(recebeu.wait(5))
                self.assertEqual(leitor.ultimo()[0].size,(20,10))
            finally: leitor.fechar()
            self.assertTrue(fluxo.closed)
            self.assertFalse(leitor.thread.is_alive())

    def test_streamio_real_legivel_no_av(self):
        import av
        import numpy as np
        # Streamlink implementa read(), mas herda readable() == False de IOBase.
        video = io.BytesIO()
        with av.open(video, mode='w', format='mpegts') as container:
            stream = container.add_stream('mpeg2video', rate=25)
            stream.width, stream.height = 32, 32
            stream.pix_fmt = 'yuv420p'
            frame = av.VideoFrame.from_ndarray(np.zeros((32,32,3), dtype='uint8'), format='rgb24')
            for packet in list(stream.encode(frame)) + list(stream.encode(None)):
                container.mux(packet)
        class Fluxo(io.IOBase):
            def __init__(self): self.dados = io.BytesIO(video.getvalue())
            def read(self, tamanho=-1): return self.dados.read(tamanho)
            def close(self): self.dados.close(); super().close()
        fluxo = Fluxo()
        self.assertFalse(fluxo.readable())
        leitura = stream_twitch.FluxoLeitura(fluxo)
        try:
            with av.open(leitura, mode='r', format='mpegts') as container:
                self.assertEqual(next(container.decode(video=0)).width, 32)
        finally:
            leitura.close()
        self.assertTrue(fluxo.closed)

    def test_retorno_trilha_sem_deriva_sem_troca_de_andar(self):
        import lap_watch
        pontos = [{'t':100, 'x':33232.5, 'y':31100, 'z':14},
                  {'t':200, 'x':33300, 'y':31100, 'z':14},
                  {'t':310, 'x':33223.5, 'y':31098, 'z':14},
                  {'t':312, 'x':33232.5, 'y':31100, 'z':13}]
        self.assertIsNone(lap_watch.posicao_da_trilha(pontos, 99))
        p, piso = lap_watch.posicao_da_trilha(pontos, 310)
        self.assertTrue(piso)
        self.assertLess((p[0]**2+p[1]**2)**.5, lap_watch.NEAR_TILES)
        self.assertFalse(lap_watch.posicao_da_trilha(pontos, 312)[1])
        self.assertIsNone(lap_watch.posicao_da_trilha(pontos, 316))


if __name__ == '__main__':
    unittest.main()
