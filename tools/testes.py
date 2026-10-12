"""Executa todas as regressões isoladas e registra testes ignorados."""
import json
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
r = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(unicos.values()))
print(json.dumps({'executados': r.testsRun, 'falhas': len(r.failures), 'erros': len(r.errors),
                  'ignorados': [{'teste': t.id(), 'motivo': m} for t, m in r.skipped]}, ensure_ascii=False))
sys.exit(0 if r.wasSuccessful() and not r.skipped else 1)
