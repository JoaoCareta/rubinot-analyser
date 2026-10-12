import datetime
import tempfile
import unittest
from pathlib import Path

import rtc_ml as ml


class AprendizadoRTC(unittest.TestCase):
    def setUp(self):
        self.rtc = {'char': 'QA', 'sessao': 's1', 'preset': 'ice', 'instante': datetime.datetime(2026, 10, 12, 9).timestamp(),
                    'slots': [{'id': 'fork', 'tipo': 'magia', 'slot': 2, 'prioridade': 1, 'creatures': 2, 'mana_percent': 5, 'icone_hash': 'f'}]}
        self.magias = [{'id': 'fork', 'tipo': 'ofensiva', 'cd': 6, 'grupo': 2}]
        self.eventos = [{'id': str(i), 't': 32401+4*i, 'kind': 'cast', 'magia_id': 'fork', 'qualidade': 'identificada', 'ator': 'QA'} for i in range(150)]

    def test_aprende_e_valida_no_futuro(self):
        rows = ml.exemplos('QA', 's1', self.eventos, self.magias, self.rtc, [[32400, 33100]])
        r = ml.treinar(rows, rows, self.rtc)
        self.assertEqual(r['estado'], 'aprendizado_validado')
        self.assertEqual(r['intervalos_efetivos']['fork']['segundos'], 4)
        self.assertLess(r['treino_ate'], r['teste_desde'])
        self.assertGreater(len(r['coeficientes']), 0)
        self.assertLess(r['validacao']['fork']['perda_depois'], r['validacao']['fork']['perda_antes'])

    def test_rejeita_quando_validacao_piora(self):
        rows = ml.exemplos('QA', 's1', self.eventos, self.magias, self.rtc, [[32400, 33100]])
        for r in rows[-40:]:
            r['gap'] = 6
        r = ml.treinar(rows, rows, self.rtc)
        self.assertFalse(r['intervalos_efetivos'])

    def test_nao_inventa_negativos_e_nao_mistura_fase(self):
        self.assertEqual(ml.exemplos('outro', 's1', self.eventos, self.magias, self.rtc, [[32400, 33100]]), [])
        self.assertEqual(ml.exemplos('QA', 'outra', self.eventos, self.magias, self.rtc, [[32400, 33100]]), [])
        self.assertEqual(ml.exemplos('QA', 's1', self.eventos, self.magias, self.rtc, []), [])
        self.assertEqual(ml.treinar([], [], self.rtc)['estado'], 'coletando')
        eventos = [dict(e, qualidade='parcial') for e in self.eventos]
        self.assertEqual(ml.exemplos('QA', 's1', eventos, self.magias, self.rtc, [[32400, 33100]]), [])

    def test_dados_duraveis_sem_duplicacao(self):
        with tempfile.TemporaryDirectory() as p:
            pasta = Path(p)
            a = ml.atualizar(pasta, 'QA', 's1', self.eventos, self.magias, self.rtc, [[32400, 33100]])
            b = ml.atualizar(pasta, 'QA', 's1', self.eventos, self.magias, self.rtc, [[32400, 33100]])
            self.assertEqual(a['amostras'], b['amostras'])
            self.assertEqual(a['coeficientes'], b['coeficientes'])
            self.assertTrue((pasta/'rtc_ml_dados.json').is_file())

    def test_roda_separa_estagios_e_preserva_desconhecidos(self):
        catalogo={'conviction':{'31':{'Name':'Aug. Strong Ice Wave'}},'revelation':{'10':{'Name':'Twin Bursts'}}}
        roda={'campos':{'conviction.Aug. Strong Ice Wave':{'valor':'II','qualidade':'texto_integral'},'revelation.Twin Bursts':{'valor':'Stage 2','qualidade':'texto_integral'}}}
        ref=ml.referencia_roda(roda,catalogo)
        self.assertEqual(ref['fatias'], {})
        self.assertEqual(ml.estado_magia({'id':'strong_ice_wave'},ref)['chave'],'strong_ice_wave|area:1|extra:0|twin:0')
        self.assertEqual(ml.estado_magia({'id':'ice_burst','familia':'bursts'},ref)['twin_estagio'],2)
        self.assertIsNone(ml.estado_magia({'id':'terra_wave'},ref))

    def test_rendimento_validado_e_sem_leakage(self):
        rows=[{'id':str(i),'instante':i,'regras_versao':'QA','estado_magia':'ice|area:1|extra:0|twin:0',
               'magia_id':'ice','criaturas':2+i%5,'rendimento':20*(2+i%5)**.4,'roda_chave':'atual','sessao':'s'} for i in range(100)]
        r=ml.treinar_combate(rows,{'char':'QA','id':'atual'},'QA')
        p=next(iter(r['perfis'].values()))
        self.assertLess(p['treino_ate'],p['teste_desde'])
        self.assertLess(p['erro_depois'],p['erro_antes'])
        self.assertFalse(r['cobertura_completa'])
        self.assertEqual(ml.treinar_combate(rows,{'char':'QA'},'outra')['amostras'],0)

    def test_cadencia_separa_roda_com_mesmo_rtc(self):
        a=ml.exemplos('QA','s1',self.eventos,self.magias,{**self.rtc,'roda_efeitos':{'ranks':{'31':1}}},[[32400,33100]])
        b=ml.exemplos('QA','s1',self.eventos,self.magias,{**self.rtc,'roda_efeitos':{'ranks':{'31':2}}},[[32400,33100]])
        self.assertNotEqual(a[0]['fase'],b[0]['fase'])
        self.assertNotEqual(a[0]['id'],b[0]['id'])

    def test_associacao_rejeita_ambiguidade_critico_e_lacuna(self):
        magia={'id':'strong_ice_wave','tipo':'ofensiva','elemento':'gelo','bp':140}
        rtc={**self.rtc,'slots':[{'id':'strong_ice_wave'}]}
        roda={**self.rtc,'campos':{'conviction.Aug. Strong Ice Wave':{'valor':'II','qualidade':'texto_integral'}}}
        cat={'versao':'QA','conviction':{'31':{'Name':'Aug. Strong Ice Wave'}},'revelation':{}}
        cast={'id':'cast','t':32410,'kind':'cast','magia_id':'strong_ice_wave','qualidade':'identificada','ator':'QA'}
        dano={'id':'dano','t':32410,'kind':'damage_dealt','ator':'QA','target':'bicho','value':1484}
        def coletar(es,intervalos=((32400,32500),)):
            return ml.exemplos_combate('QA','s1',es,[magia],[rtc],[roda],[{'t':32410,'battle':4}],intervalos,cat,{'bicho':{'toma':{'gelo':100}}})
        r=coletar([cast,dano])
        self.assertEqual(len(r),1);self.assertAlmostEqual(r[0]['rendimento'],10)
        self.assertFalse(r[0]['cobertura_completa'])
        self.assertEqual(coletar([cast,{**dano,'crit':True}]),[])
        self.assertEqual(coletar([cast,{**dano,'tag':'prey'}]),[])
        self.assertEqual(coletar([cast,dano,{**cast,'id':'outra','t':32409}]),[])
        self.assertEqual(coletar([cast,dano],()),[])
        self.assertEqual(coletar([cast,{**dano,'target':'desconhecido'}]),[])


if __name__ == '__main__':
    unittest.main()
