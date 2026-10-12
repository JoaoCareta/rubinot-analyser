import json
import random
import subprocess
import unittest
from rubinot.hunt.metricas import taxas, especies


class ParidadeTest(unittest.TestCase):
    def test_matriz_sintetica_python_javascript(self):
        rng = random.Random(3312)
        conjuntos = [[], [{'dur': 120, 'xp_raw': 0, 'profit': 0}]]
        for _ in range(100):
            conjuntos.append([{'dur': rng.choice([0, 1, 120, 359, 360, 600]),
                'parcial': rng.choice([False, False, True]), 'tipo': rng.choice(['volta', 'volta', 'refil']),
                'xp_raw': rng.choice([None, 0, 123456]), 'xp_raw_15min': rng.choice([None, 0, 150000]),
                'profit': rng.choice([None, 0, -500, 10000]), 'sup_pt': rng.choice([None, 0, 100]),
                'sup_eu': rng.choice([None, 0, 5]), 'bichos': rng.choice([None, 0, 12]),
                'especies': {'Livro': rng.randrange(5)}} for _ in range(rng.randrange(10))])
        js = "const t=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(v=>[t.taxasDe(v),t.especiesDe(v)]))));"
        r = subprocess.run(['node', '-e', js], input=json.dumps(conjuntos), text=True, capture_output=True, timeout=30, check=True)
        self.assertEqual(json.loads(r.stdout), [[taxas(v), especies(v)] for v in conjuntos])
