import json
import pathlib
import tempfile
import unittest

from rubinot.planejamento.sio import estudar
from rubinot.planejamento.registro import Registro


class SioTest(unittest.TestCase):
    def setUp(self):
        self.ctx={'char':'ED QA','sessao':'session_20261013_000000','hunt':'QA','hazard':5}
        self.party=[{'nome':'EK QA','vocacao':'EK','identidade_confirmada':True}]

    def eventos(self, n=36):
        rows=[]
        for i in range(n+1):
            t=i*4
            rows.extend([dict(id=f'c{i}',t=t,kind='cast',magia_id='heal_friend',ator='ED QA',alvo='EK QA',qualidade='identificada',fase_id='f'),
                         dict(id=f'h{i}',t=t,kind='heal_other',value=2000,ator='ED QA',alvo='EK QA'),
                         dict(id=f'd{i}',t=t+2,kind='damage_taken_player',value=3000,alvo='EK QA')])
        return rows

    def test_deficit_associacao_destino_e_outras_curas(self):
        es=self.eventos();es.extend([dict(id='autocura',t=1,kind='heal_self_player',value=1200,alvo='EK QA'),
            dict(id='duplicada',t=0,kind='healed_player',value=2000,alvo='EK QA')])
        rs=[{'t':2,'aliados':{'EK QA':{'percentual':69,'identidade_confirmada':True}},'origem':'prova'}]
        r=estudar(es,rs,self.ctx,self.party,{'EK QA':{'sio_percent':80}})
        m=r['membros'][0];b=m['balanco'];self.assertEqual(b['comparaveis'],36)
        self.assertEqual(b['janelas'][0]['saldo_sio_hp'],-1000)
        self.assertEqual(b['janelas'][0]['saldo_total_hp'],200)
        self.assertFalse(b['cobertura_completa']);self.assertEqual(r['sugestoes'][0]['vida_percent'],90)
        self.assertNotIn('nature_s_embrace',[s['id']for s in r['sugestoes']])
        self.assertEqual(m['modelo']['estado'],'validado_descritivo_parcial')
        p=m['modelo']['perfis'][0];self.assertLessEqual(p['treino_ate'],p['teste_desde'])
        self.assertFalse(set(p['treino_ids'])&set(p['teste_ids']))

    def test_ambiguidade_critico_lacuna_e_identidade(self):
        es=self.eventos(2);es.append(dict(id='mas',t=0,kind='cast',magia_id='mass_healing',ator='ED QA',qualidade='identificada'))
        es.append(dict(id='externo',t=4,kind='heal_other',value=9000,ator='outro ED',alvo='EK QA'))
        r=estudar(es,[],self.ctx,self.party);b=r['membros'][0]['balanco']
        self.assertEqual(b['lacunas'],1);self.assertEqual(b['sio_hp'],2000);self.assertEqual(r['sugestoes'],[])
        self.assertEqual(estudar(es,[],self.ctx,[{'nome':'EK QA','vocacao':'EK'}])['membros'],[])
        qa=[{**e,'qa':True}for e in es];self.assertEqual(estudar(qa,[],self.ctx,self.party)['membros'][0]['balanco']['comparaveis'],0)

    def test_barra_integral_com_party_confirmada_nao_aceita_recorte_antigo(self):
        def recurso(origem):
            return [{'t':2,'aliados':{'EK QA':{'percentual':69,'origem':origem}}}]
        a=estudar(self.eventos(),recurso('barra_nameplate_integral'),self.ctx,self.party,{'EK QA':{'sio_percent':80}})
        b=estudar(self.eventos(),recurso('barra_nameplate'),self.ctx,self.party,{'EK QA':{'sio_percent':80}})
        self.assertEqual(len(a['sugestoes']),1);self.assertEqual(b['sugestoes'],[])

    def test_preservacao_idempotencia_e_revisao_sem_apagar_original(self):
        with tempfile.TemporaryDirectory()as d:
            reg=Registro(pathlib.Path(d));sessao=self.ctx['sessao'];reg.guardar(sessao,'evento',self.eventos())
            original={'id':'original','t':2,'aliados':{'EK QA':{'percentual':16,'identidade_confirmada':False}}}
            reg.guardar(sessao,'recurso',[original])
            rev={'id':'revisao','t':2,'revisao':'moldura_integral','aliados':{'EK QA':{'percentual':69,'identidade_confirmada':True}},'prova':'p'}
            a=reg.estudar_sio(sessao,self.ctx,self.party,{'EK QA':{'sio_percent':80}},[rev])
            b=reg.estudar_sio(sessao,self.ctx,self.party,{'EK QA':{'sio_percent':80}})
            self.assertEqual(a['id'],b['id']);self.assertEqual(reg.ler(sessao,'recurso'),[original])
            self.assertEqual(len(reg.ler(sessao,'estudo_sio')),1);self.assertEqual(len(reg.ler(sessao,'amostra_sio')),36)
            self.assertEqual(a['membros'][0]['vida_minima'],69)

