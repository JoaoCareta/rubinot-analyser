import ast
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / 'tools'))
from arquitetura import grafo, ciclos, violacoes_dominio


class ArquiteturaTest(unittest.TestCase):
    def test_nenhum_ciclo_inclusive_imports_tardios(self):
        self.assertEqual(ciclos(grafo(pathlib.Path('.'))), [])

    def test_regra_detecta_ciclo_e_import_proibido(self):
        self.assertEqual(ciclos({'a': {'b'}, 'b': {'a'}}), [['a', 'b']])
        self.assertEqual(ciclos({'a': {'b'}, 'b': set()}), [])
        self.assertTrue(violacoes_dominio('import sqlite3\ndef conta():\n import capture\n'))
        self.assertTrue(violacoes_dominio('open("pessoal")'))
        self.assertEqual(violacoes_dominio('import math\ndef conta(x): return math.floor(x)'), [])

    def test_metricas_nao_importam_motor_ou_adaptadores(self):
        for nome in ('rubinot/hunt/metricas.py', 'rubinot/planejamento/avaliacao.py', 'rubinot/configuracao_combate/concordancia.py'):
            texto = pathlib.Path(nome).read_text(encoding='utf8')
            self.assertEqual(violacoes_dominio(texto), [], nome)
        for nome in ('rubinot/planejamento/registro.py', 'rubinot/planejamento/modelos.py'):
            arv = ast.parse(pathlib.Path(nome).read_text(encoding='utf8'))
            deps = [n.module for n in ast.walk(arv) if isinstance(n, ast.ImportFrom)]
            self.assertNotIn('ao_vivo', deps)
            self.assertNotIn('configuracoes', deps)

    def test_manifesto_classifica_todas_as_entradas_manuais(self):
        m = json.loads(pathlib.Path('runtime-manifest.json').read_text(encoding='utf8'))
        self.assertEqual(set(m['processos']), {'app', 'capture', 'lap_watch', 'ks'})
        classificados = set(m['fachadas']) | set(m['ferramentas']) | set(m['entradas']) | set(m['modulos_runtime'])
        fontes = {p.name for p in pathlib.Path('.').glob('*.py') if not p.name.startswith('test_')}
        self.assertEqual(fontes - classificados, set())
        for asset in m['assets']:
            self.assertNotIn(pathlib.Path(asset).name, m['dados_pessoais'])
            self.assertTrue(pathlib.Path(asset).is_file(), asset)
