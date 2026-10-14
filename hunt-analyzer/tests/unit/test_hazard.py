import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rubinot.hunt.hazard import area, nivel, regras, trecho
from rubinot.planejamento.registro import Registro, absoluto


class Hazard(unittest.TestCase):
    def test_regra_atual_nao_inventa_coeficientes(self):
        self.assertEqual(area('Carrinho 1'),area('Monster Graveyard'))
        self.assertIsNone(nivel(True)); self.assertIsNone(nivel(-1))
        self.assertEqual(nivel(0),0)
        r=regras(datetime.datetime(2026,10,12).timestamp())
        self.assertEqual(r['loot_bonus_por_hazard'],0)
        self.assertIsNone(r['dano_por_hazard'])
        self.assertIsNone(regras(datetime.datetime(2025,1,1).timestamp())['loot_bonus_por_hazard'])

    def test_mudanca_gap_e_nome_impedem_rotular_volta(self):
        rows=[{'instante':t,'hazard':{'nivel':4,'char':'ED','prova':'a.png'}} for t in range(0,31,5)]
        self.assertEqual(trecho(rows,0,30,'ED')['nivel'],4)
        self.assertIsNone(trecho(rows,0,30,'outro')['nivel'])
        self.assertIsNone(trecho(rows[::3],0,30,'ED')['nivel'])
        rows[3]['hazard']['nivel']=5
        self.assertEqual(trecho(rows,0,30,'ED')['estado'],'misto')

    def test_icone_real_numero_nome_e_ambiguidade(self):
        import atlas_build, nameplates
        from PIL import Image
        from rubinot.observacao.hazard import ler
        im=Image.new('RGB',(120,100)); im.paste(Image.open('tests/fixtures/leitores/hazard-8.png'),(40,50))
        ref=json.loads(Path('ui/hazard_referencias.json').read_text())
        indice=nameplates.shape_index(atlas_build.load_atlas()[0])
        nome={'nome':'ED','tipo':'jogador','px':(35,25)}
        with patch('nameplates.nameplates',return_value=[nome]):
            self.assertEqual(ler(im,'ED',(0,0,120,100),ref,indice)['nivel'],8)
            duplo=im.copy()
            duplo.paste(im.crop((53,52,59,60)),(61,52))
            self.assertEqual(ler(duplo,'ED',(0,0,120,100),ref,indice)['nivel'],88)
            self.assertIsNone(ler(im,'outro',(0,0,120,100),ref,indice)['nivel'])
            self.assertEqual(ler(im,'outro',(0,0,120,100),ref,indice)['visiveis'],[])
            grupo=ler(im,'outro',(0,0,120,100),ref,indice,integrantes=['ED'])
            self.assertEqual(grupo['nivel'],8)
            self.assertEqual(grupo['integrantes_observados'],['ED'])
            sem_icone=im.copy();sem_icone.paste((0,0,0),(40,50,52,62))
            self.assertIsNone(ler(sem_icone,'ED',(0,0,120,100),ref,indice)['nivel'])
        with patch('nameplates.nameplates',return_value=[nome,{**nome,'nome':'outro'}]):
            self.assertIsNone(ler(im,'ED',(0,0,120,100),ref,indice)['nivel'])
        dois=Image.new('RGB',(180,100));dois.paste(im,(0,0));dois.paste(duplo.crop((40,50,78,62)),(95,50))
        estranho={'nome':'KS','tipo':'jogador','px':(90,25)}
        with patch('nameplates.nameplates',return_value=[nome,estranho]):
            leitura=ler(dois,'ED',(0,0,180,100),ref,indice,integrantes=['ED','RP'])
            self.assertEqual(leitura['nivel'],8)
            self.assertEqual(leitura['integrantes_observados'],['ED'])
            conflito=ler(dois,'ED',(0,0,180,100),ref,indice,integrantes=['ED','KS'])
            self.assertIsNone(conflito['nivel'])

    def test_previsao_separa_hazard_sem_reescrever_original(self):
        with tempfile.TemporaryDirectory() as p:
            r=Registro(p); s='session_20261012_100000'
            resumo={'sessao':{'char':'ED','hunt':'Carrinho 1','pt':'pt x4'},'voltas':[
                {'n':1,'ini':36000,'fim':36030,'dur':30},
                {'n':2,'ini':36030,'fim':36060,'dur':30},
                {'n':3,'ini':36060,'fim':36120,'dur':60}]}
            recursos=[{'id':str(t),'instante':absoluto(s,t),'hazard':{'nivel':4 if t<36060 else 5,'char':'ED'}} for t in range(36000,36121,5)]
            r.guardar(s,'recurso',recursos)
            estudos=r.estudar_voltas(s,resumo,True)['comparacoes']
            dur=[e for e in estudos if e['metrica']=='duracao_s']
            self.assertEqual(dur[1]['previsto'],30)
            self.assertEqual(dur[2]['contexto']['hazard'],5)
            self.assertIsNone(dur[2]['previsto'])
            self.assertEqual(estudos,r.estudar_voltas(s,resumo,True)['comparacoes'])


if __name__=='__main__': unittest.main()
