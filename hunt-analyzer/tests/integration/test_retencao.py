import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import ao_vivo
import auxiliares


class RetencaoTest(unittest.TestCase):
    def test_limpeza_preserva_consumidor_pendente_e_numeros(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            for i, estado in enumerate(['pendente', 'falhou', 'coletando', 'numeros_persistidos']):
                s = raiz / f'session_20260101_01000{i}'; s.mkdir()
                (s / 'aprendizado_estado.json').write_text(json.dumps({'estado': estado}), encoding='utf8')
                (s / 'f_010001_000.png').write_bytes(b'quadro')
                (s / 'laps.jsonl').write_text('{}\n', encoding='utf8')
            apagados, _ = ao_vivo.limpa_quadros(raiz=raiz)
            self.assertEqual(apagados, 1)
            self.assertEqual(len(list(raiz.glob('*/laps.jsonl'))), 4)
            self.assertEqual(len(list(raiz.glob('*/f_*.png'))), 3)

    def test_um_apito_e_escudo_desconhecido(self):
        with patch.object(auxiliares, 'CONFIG', pathlib.Path('inexistente-qa.json')):
            u = auxiliares.Utamo(); u.som = False; u.agora = 1000
            self.assertIsNone(u.escudo())
            self.assertTrue(u._apita('vida'))
            self.assertFalse(u._apita('escudo', caiu=True))
            self.assertIn('sem apito', u.historico[0]['motivo'])
            u.agora += auxiliares.APITO_GAP_S
            self.assertTrue(u._apita('escudo', caiu=True))
