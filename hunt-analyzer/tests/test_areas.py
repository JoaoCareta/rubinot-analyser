import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from rubinot.hunt.areas import detectar, recortar


class AreasTest(unittest.TestCase):
    def pontos(self, andar, nomes, inicio=0):
        return [{'t': inicio+i*4, 'z': andar, 'especies': dict.fromkeys(nomes, 1)} for i in range(30)]

    def test_troca_exige_andar_e_monstros(self):
        a = self.pontos(10, ['lion hydra', 'bluebeak'])
        self.assertEqual(len(detectar(a+self.pontos(11, ['lion hydra', 'bluebeak'],120))),1)
        self.assertEqual(len(detectar(a+self.pontos(10, ['crusader'],120))),1)
        areas = detectar(a+self.pontos(11, ['crusader', 'headwalker'],120))
        self.assertEqual(len(areas),2)
        self.assertEqual(areas[-1]['inicio'],120)

    def test_passagem_nao_troca(self):
        a = self.pontos(10,['lion hydra'])
        a += self.pontos(11,['dog'],120)[:4]
        a += self.pontos(10,['lion hydra'],136)
        self.assertEqual(len(detectar(a)),1)

    def test_recorte_preserva_original_e_nao_rateia(self):
        areas=[{'inicio':0,'andar':10,'especies':['lion hydra']},{'inicio':120,'andar':11,'especies':['crusader']}]
        dados={'voltas':[{'ini':0,'fim':100},{'ini':100,'fim':300,'xp_raw':1000,'especies':{'lion hydra':3,'crusader':4}}]}
        r=recortar(dados,areas)
        self.assertEqual(len(r['voltas']),1)
        self.assertTrue(r['voltas'][0]['parcial'])
        self.assertIsNone(r['voltas'][0]['xp_raw'])
        self.assertEqual(dados['voltas'][1]['xp_raw'],1000)
        self.assertEqual(r['voltas'][0]['especies'],{'crusader':4})
        self.assertNotIn('parcial',dados['voltas'][1])

    def test_recorte_preserva_raro_posterior_sem_trazer_area_anterior(self):
        areas = [{'inicio': 0, 'andar': 15, 'especies': ['primal pack beast']},
                 {'inicio': 120, 'andar': 14, 'especies': ['undertaker']}]
        dados = {'voltas': [
            {'ini': 0, 'fim': 100, 'especies': {'primal pack beast': 3}},
            {'ini': 100, 'fim': 150, 'especies': {'primal pack beast': 2, 'undertaker': 4}},
            {'ini': 150, 'fim': 300, 'especies': {'undertaker': 6, 'plunder patriarch': 1}},
        ]}
        r = recortar(dados, areas)
        self.assertEqual(r['voltas'][0]['especies'], {'undertaker': 4})
        self.assertEqual(r['voltas'][1]['especies'], {'undertaker': 6, 'plunder patriarch': 1})
        self.assertNotIn('plunder patriarch', areas[-1]['especies'])
        self.assertEqual(len(dados['voltas']), 3)
        self.assertEqual(recortar(dados, areas[:1]), dados)

    def test_motor_reusa_quadros_e_persiste_fronteira(self):
        from rubinot.hunt.aplicacao import Gravacao
        from rubinot.hunt import aplicacao as motor
        with tempfile.TemporaryDirectory() as tmp:
            g=Gravacao.__new__(Gravacao)
            g.sessao=Path(tmp)
            g.hunt_comecou='12:00:00'
            pontos=self.pontos(10,['lion hydra'],43200)+self.pontos(11,['crusader'],43320)
            g.amostras=[[p['t'],p['z'],1,1,3] for p in pontos]
            frames=['b_'+motor.lw.fmt(p['t']).replace(':','')+'_000.png' for p in pontos]
            logs=[];g.registra=logs.append
            def ler(quadro,*args):
                png=list(quadro.glob('b_*.png'))[0]
                return {'lion hydra':3} if motor.lw.fsec(png.name)<43320 else {'crusader':3}
            with patch.object(motor.lw,'battle_especies',side_effect=ler) as leitura:
                g._areas(frames)
                quantidade=leitura.call_count
                g._areas(frames)
                self.assertEqual(leitura.call_count,quantidade)
            self.assertEqual(len(g.areas_hunt),2)
            self.assertTrue((g.sessao/'areas_observacoes.jsonl').exists())
            self.assertEqual(len(logs),1)
