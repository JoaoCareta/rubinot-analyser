"""Executa todas as regressões isoladas e registra testes ignorados."""
import json
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path.cwd()))
loader = unittest.TestLoader()
suite = unittest.TestSuite([loader.discover('.', pattern='test_*.py'), loader.discover('tests', pattern='test_*.py', top_level_dir='.')])
# A descoberta da raiz já percorre tests quando é pacote: elimina nomes repetidos.
def folhas(grupo):
    for item in grupo:
        if isinstance(item, unittest.TestSuite):
            yield from folhas(item)
        else:
            yield item
unicos = {item.id(): item for item in folhas(suite)}
class Resultado(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.registros.append({'id': test.id(), 'estado': 'iniciado'})

    def stopTest(self, test):
        problemas = {t.id() for t, _ in self.failures + self.errors + self.skipped}
        problemas.update(t.id() for t in self.unexpectedSuccesses)
        problemas.update(t.id() for t, _ in self.expectedFailures)
        # Falhas em subTest pertencem ao teste pai.
        ruim = any(n == test.id() or n.startswith(test.id() + ' ') for n in problemas)
        self.registros[-1]['estado'] = 'falhou' if ruim else 'passou'
        super().stopTest(test)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registros = []


r = unittest.TextTestRunner(verbosity=1, resultclass=Resultado).run(unittest.TestSuite(unicos.values()))
if os.environ.get('HUNT_QA_SAIDA'):
    (pathlib.Path(os.environ['HUNT_QA_SAIDA']) / 'python-testes.json').write_text(
        json.dumps(r.registros, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'executados': r.testsRun, 'falhas': len(r.failures), 'erros': len(r.errors),
                  'ignorados': [{'teste': t.id(), 'motivo': m} for t, m in r.skipped]}, ensure_ascii=False))
sys.exit(0 if r.wasSuccessful() and not r.skipped and not r.expectedFailures else 1)
