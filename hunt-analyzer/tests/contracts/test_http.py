import io
import unittest
from rubinot.adapters.http import EntradaInvalida, ler_objeto, LIMITE_JSON


class HttpTest(unittest.TestCase):
    def test_json_invalido_tipo_e_limite(self):
        for corpo in (b'{', b'[]', b'null', b'"texto"'):
            with self.assertRaises(EntradaInvalida) as erro:
                ler_objeto({'Content-Length': str(len(corpo))}, io.BytesIO(corpo))
            self.assertEqual(erro.exception.status, 400)
        with self.assertRaises(EntradaInvalida) as erro:
            ler_objeto({'Content-Length': str(LIMITE_JSON + 1)}, io.BytesIO())
        self.assertEqual(erro.exception.status, 413)

    def test_utf8_e_corpo_incompleto(self):
        corpo = '{"nome":"ação"}'.encode('utf8')
        self.assertEqual(ler_objeto({'Content-Length': str(len(corpo))}, io.BytesIO(corpo))['nome'], 'ação')
        with self.assertRaises(EntradaInvalida):
            ler_objeto({'Content-Length': '100'}, io.BytesIO(b'{}'))
