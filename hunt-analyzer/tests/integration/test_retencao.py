import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import ao_vivo
import auxiliares


class RetencaoTest(unittest.TestCase):
    def test_limpeza_nunca_apaga_gravacoes_nem_apos_consumo(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            for i, estado in enumerate(['pendente', 'falhou', 'coletando', 'numeros_persistidos', None]):
                s = raiz / f'session_20260101_01000{i}'; s.mkdir()
                (s / 'aprendizado_estado.json').write_text(json.dumps({'estado': estado}), encoding='utf8')
                (s / 'f_010001_000.png').write_bytes(b'quadro')
                (s / 'q_010001_000.png').write_bytes(b'original')
                (s / 'hunt.mp4').write_bytes(b'video')
                (s / 'laps.jsonl').write_text('{}\n', encoding='utf8')
            apagados, _ = ao_vivo.limpa_quadros(raiz=raiz)
            self.assertEqual(apagados, 0)
            self.assertEqual(len(list(raiz.glob('*/laps.jsonl'))), 5)
            self.assertEqual(len(list(raiz.glob('*/f_*.png'))), 5)
            self.assertEqual(len(list(raiz.glob('*/q_*.png'))), 5)
            self.assertEqual(len(list(raiz.glob('*/hunt.mp4'))), 5)

    def test_replay_preserva_lacunas_meia_noite_e_fallback(self):
        from rubinot.adapters import gravacoes
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            nome = 'session_20261014_230000'
            s = raiz / nome; s.mkdir()
            for arquivo in ['q_235959_000.png', 'f_235959_000.png', 'f_240020_000.png', 'q_240021_500.png', 'q_240022_000.tmp']:
                (s / arquivo).write_bytes(b'imagem')
            indice = gravacoes.indice(raiz, [nome, nome, 'session_20261015_010000'])
            qs = indice['trechos'][0]['quadros']
            self.assertEqual([q['t'] for q in qs], [86399, 86420, 86421.5])
            self.assertEqual(qs[0]['nome'], 'q_235959_000.png')
            self.assertEqual(indice['trechos'][1]['quadros'], [])
            self.assertEqual(gravacoes.quadro(raiz, nome, qs[0]['nome']), s / qs[0]['nome'])
            for sessao, quadro in [('../fora',qs[0]['nome']), (nome,'../segredo.png'), (nome,'calibracao.json'), (nome,'q_000001_000.png')]:
                self.assertIsNone(gravacoes.quadro(raiz,sessao,quadro))

    def test_historico_replay_inclui_todas_as_sessoes_agrupadas(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            nomes = ['session_20261014_060000','session_20261014_070000']
            for nome in nomes:
                (raiz/nome).mkdir()
                (raiz/nome/'q_070001_000.png').write_bytes(b'quadro')
            grupo = [(None,{'pasta':nome}) for nome in nomes]
            with patch.object(ao_vivo,'CAPTURAS',raiz), patch.object(ao_vivo,'_grupo_hist',return_value=grupo):
                self.assertEqual([t['sessao'] for t in ao_vivo.historico_gravacao('teste')['trechos']],nomes)
            with patch.object(ao_vivo,'_grupo_hist',return_value=None):
                self.assertIsNone(ao_vivo.historico_gravacao('invalido'))

    def test_um_apito_e_escudo_desconhecido(self):
        with patch.object(auxiliares, 'CONFIG', pathlib.Path('inexistente-qa.json')):
            u = auxiliares.Utamo(); u.som = False; u.agora = 1000
            self.assertIsNone(u.escudo())
            self.assertTrue(u._apita('vida'))
            self.assertFalse(u._apita('escudo', caiu=True))
            self.assertIn('sem apito', u.historico[0]['motivo'])
            u.agora += auxiliares.APITO_GAP_S
            self.assertTrue(u._apita('escudo', caiu=True))
