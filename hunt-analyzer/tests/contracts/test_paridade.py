import json
import random
import subprocess
import unittest
from rubinot.hunt.metricas import taxas, especies, pressao, consumo_itens, variacoes_estoque, balanco_cura, resumo_vida, permanencia_vida


class ParidadeTest(unittest.TestCase):
    def test_permanencia_fronteiras_lacunas_sem_extrapolar(self):
        def serie(pares):
            return [dict(t=t, percentual=p) for t, p in pares]
        casos = [[], serie([(1, 0), (7, 30), (9, 50), (10, 70), (12, 90), (13, 100), (14, 100)]),
                 serie([(0, 90), (7, 90)]), serie([(1, 20), (2, None), (3, 20)]),
                 serie([(1, 50), (2, True), (3, '50'), (4, -1), (5, 101)]),
                 serie([(19, 100)]), serie([(-1, 90), (1, 40), (1, 100), (3, 90), (21, 100)]),
                 serie([(3.5, 100), (1.5, 90), (2.5, 70)])]
        js = "const m=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(x=>m.permanenciaVida(x,0,20)))));"
        r = subprocess.run(['node', '-e', js], input=json.dumps(casos), text=True, encoding='utf8', capture_output=True, check=True, timeout=30)
        resultados = [permanencia_vida(v, 0, 20) for v in casos]
        self.assertEqual(json.loads(r.stdout), resultados)
        self.assertEqual([f['tempo_s'] for f in resultados[1]['faixas']], [6, 2, 1, 2, 2])
        self.assertEqual(resultados[1]['tempo_sem_leitura_s'], 7)
        for i in (0, 2, 3, 4, 5):
            self.assertEqual(resultados[i]['tempo_sem_leitura_s'], 20)
            self.assertTrue(all(f['tempo_s'] is None for f in resultados[i]['faixas']))
        for r in resultados:
            self.assertEqual(r['tempo_identificado_s'] + r['tempo_sem_leitura_s'], 20)

    def test_vida_fronteiras_zero_lacunas_e_tipos(self):
        casos = [[], [None, True, '50', -1, 101], [0, 29.99, 30, 50, 70, 90, 100], [80, 80, 90]]
        js = "const m=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(m.resumoVida))));"
        r = subprocess.run(['node', '-e', js], input=json.dumps(casos), text=True, encoding='utf8', capture_output=True, check=True, timeout=30)
        self.assertEqual(json.loads(r.stdout), [resumo_vida(v) for v in casos])
        self.assertIsNone(resumo_vida([])['minima'])
        self.assertEqual(resumo_vida([0])['minima'], 0)
        self.assertEqual([f['leituras'] for f in resumo_vida(casos[2])['faixas']], [2, 1, 1, 1, 2])

    def test_balanco_sio_mesmo_intervalo_zero_e_lacunas(self):
        casos = [[], [dict(inicio=0,fim=2,dano_hp=3000,sio_hp=2000,outras_hp=1200,cobertura_completa=False),
                      dict(inicio=2,fim=4,dano_hp=None,sio_hp=0),
                      dict(inicio=4,fim=6,dano_hp=0,sio_hp=0,outras_hp=0,cobertura_completa=True)],
                 [dict(inicio=0,fim=0,dano_hp=3,sio_hp=4),dict(inicio=0,fim=2,dano_hp=True,sio_hp=4)]]
        js="const m=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(m.balancoCura))));"
        r=subprocess.run(['node','-e',js],input=json.dumps(casos),text=True,encoding='utf8',capture_output=True,check=True,timeout=30)
        self.assertEqual(json.loads(r.stdout),[balanco_cura(v) for v in casos])
        b=balanco_cura(casos[1]);self.assertEqual(b['deficits'],1);self.assertEqual(b['lacunas'],1)
        self.assertEqual(b['janelas'][0]['saldo_total_hp'],200)
        self.assertIsNone(b['janelas'][1]['razao_sio_dano'])

    def test_estoque_precos_refis_e_lacunas(self):
        rows=[dict(t=t,valor=v,char='QA',item='mana',serie='s',origem='estoque_hotkey',
                   unidade='unidades',local=[1,2],prova=str(t),preco_observado={'gold':488,'origem':'NPC'})
              for t,v in [(0,2055),(2,2053),(4,2053),(6,2060),(30,2050)]]
        js="const m=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(m.variacoesEstoque(JSON.parse(s)))));"
        r=subprocess.run(['node','-e',js],input=json.dumps(rows),text=True,encoding='utf8',capture_output=True,check=True,timeout=30)
        self.assertEqual(json.loads(r.stdout),variacoes_estoque(rows))

    def test_pressao_consumo_e_lacunas(self):
        casos = [[], [{'t': i, 'combate': True, 'vida': {'percentual': p},
                      'escudo': [True, False, None][i % 3]}
                     for i, p in enumerate([90, 45, 49, 72, 69, 75, 76, 80])],
                 [{'t': 0, 'combate': True, 'vida': {'percentual': 20}},
                  {'t': 30, 'combate': True, 'vida': {'percentual': 100}}]]
        itens = [{'t': t, 'char': 'QA', 'item': 'mana', 'serie': 's',
                  'unidade': 'unidades', 'valor': n, 'origem': 'contador_uso',
                  'continuidade': True} for t, n in [(0, 10), (90, 40), (120, 1), (180, 1)]]
        js = "const m=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{const d=JSON.parse(s);console.log(JSON.stringify([d[0].map(x=>m.pressao(x)),m.consumoItens(d[1])]))});"
        r = subprocess.run(['node', '-e', js], input=json.dumps([casos, itens]), text=True,
                           capture_output=True, timeout=30, check=True)
        self.assertEqual(json.loads(r.stdout), [[pressao(v) for v in casos], consumo_itens(itens)])
        self.assertEqual(len(pressao(casos[1])['episodios']), 1)
        self.assertEqual(pressao(casos[2])['vida_cobertura_s'], 0)
        self.assertEqual(consumo_itens(itens)[0]['por_minuto'], 20)
        self.assertEqual(consumo_itens(itens)[1]['quantidade'], 0)
        self.assertEqual(consumo_itens([{**v, 'origem': 'inventario'} for v in itens]), [])

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
