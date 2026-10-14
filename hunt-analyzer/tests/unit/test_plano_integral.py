import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from rubinot.observacao.telemetria import contadores, prontidao, identificar_icones, escudo_certificado, transicoes_escudo
from rubinot.planejamento.validacao import validar_execucao, calibrar_politica, classificar_pressao
from rubinot.planejamento.registro import Registro
from rubinot.planejamento.efetividade import contraste_temporal, uso_bonus_por_magia


class PlanoIntegral(unittest.TestCase):
    def test_consumo_exige_item_e_contador_e_nao_gold(self):
        textos = [{'texto':'Supply Analyser','x':20,'y':10},
                  {'texto':'Ultimate Mana Potion','x':20,'y':40},
                  {'texto':'120x','x':200,'y':40}, {'texto':'Gold Value','x':20,'y':60},
                  {'texto':'100,000','x':200,'y':60}]
        r = contadores(textos,'QA',100,'q.png','s')
        self.assertEqual(len(r),1); self.assertEqual(r[0]['valor'],120)
        self.assertEqual(r[0]['familia'],'mana'); self.assertFalse(r[0]['continuidade'])
        self.assertFalse(contadores(textos[1:],'QA',100,'q.png','s'))
        self.assertFalse(contadores(textos+[{'texto':'121x','x':210,'y':40}],'QA',100,'q.png','s'))

    def test_prontidao_nao_infere_cast_ou_cd_por_icone(self):
        icones = [{'id':'wave','regiao':[20,20,32,32]}]
        r = prontidao([],icones,3,'q')
        self.assertIsNone(r['wave']['pronta'])
        r = prontidao([{'texto':'4s','x':22,'y':24}],icones,3,'q')
        self.assertFalse(r['wave']['pronta']); self.assertEqual(r['wave']['restante_s'],4)
        self.assertTrue(prontidao([{'texto':'0s','x':22,'y':24}],icones,7,'q')['wave']['pronta'])

    def test_pixel_icone_real_ambiguidade_e_regiao_oculta(self):
        # Asset do produto, sem rede ou capturar o jogo; dois matches são ambíguos.
        with Image.open('ui/magia_avalanche_rune.png') as im:
            ref = np.asarray(im.convert('RGB'))
        quadro = Image.new('RGB',(300,100),'black'); quadro.paste(Image.fromarray(ref),(20,20))
        self.assertEqual(len(identificar_icones(quadro,{'avalanche':ref})),1)
        quadro.paste(Image.fromarray(ref),(140,20))
        self.assertFalse(identificar_icones(quadro,{'avalanche':ref}))
        self.assertIsNone(escudo_certificado(quadro,False,{}))
        anchors = [{'regiao':[x,0,2,2],'pixels':np.asarray(quadro)[0:2,x:x+2].tolist()} for x in (0,10)]
        self.assertFalse(escudo_certificado(quadro,False,{'certificada':True,'ancoras':anchors}))
        anchors[0]['pixels'][0][0] = [255,255,255]
        self.assertIsNone(escudo_certificado(quadro,False,{'certificada':True,'ancoras':anchors}))

    def test_escudo_censurado_no_inicio_fim_e_gap(self):
        r = transicoes_escudo([{'t':t,'escudo':e} for t,e in [(1,True),(2,True),(3,False),(4,True),(20,True)]])
        self.assertTrue(r[0]['inicio_censurado']); self.assertIsNone(r[0]['duracao_integral_s'])
        self.assertTrue(r[1]['fim_censurado']); self.assertTrue(r[-1]['fim_censurado'])
        r = transicoes_escudo([{'t':t,'escudo':e} for t,e in [(1,False),(2,True),(3,True),(4,False)]])
        self.assertEqual(r[0]['duracao_integral_s'],2)

    def episodios(self):
        rows = []
        for i in range(12):
            oportunidades = [{'escolhida':'a' if n%2==0 else 'b','origem_execucao':'rtc_declarado',
                'cobertura_completa':True,'candidatas':[{'id':'a','tipo':'magia','slot':1,'prioridade':1,
                    'bloqueios':[] if n%2==0 else ['cooldown'],'desconhecidas':[]},
                    {'id':'b','tipo':'runa','slot':1,'prioridade':1,'bloqueios':[],'desconhecidas':[]}]} for n in range(10)]
            rows.append({'origem_id':str(i),'inicio':100+i*20,'fim':115+i*20,
                         'oportunidades':oportunidades})
        return rows

    def test_execucao_holdout_copias_anterior_e_rejeicao(self):
        rows = self.episodios()
        r = validar_execucao(rows+rows,{'char':'QA'},90)
        self.assertTrue(r['promover']); self.assertEqual(r['teste_n'],30)
        self.assertEqual(r['teste_erro'],0); self.assertEqual(r['hipotese'],'magia_desempata')
        self.assertFalse(validar_execucao(rows,{},999)['promover'])
        self.assertFalse(validar_execucao(rows,{},90,{'hipotese':'magia_desempata'})['promover'])
        for e in rows[-3:]:
            for o in e['oportunidades']: o['escolhida']='impossivel'
        self.assertFalse(validar_execucao(rows,{},90)['promover'])

    def test_ambiguidade_hotkey_e_geometria_nao_promovem(self):
        rows = self.episodios()
        for e in rows:
            for o in e['oportunidades']: o['origem_execucao']='rtc_declarado_com_hotkey_nao_excluida'
        self.assertFalse(validar_execucao(rows,{},90)['promover'])

    def test_politica_usa_provas_reservadas_nao_rotulos_proprios(self):
        rows = [{'origem_id':str(i),'inicio':100+i*20,'fim':115+i*20,
                 'rotulo_origem':'auditoria_provas','rotulo':['tranquila','controlada','pouca_margem'][i%3],
                 'vida_minima':[90,70,25][i%3],'esforco_por_min':[1,20,30][i%3]} for i in range(12)]
        p = calibrar_politica(rows,90); self.assertTrue(p['promover'])
        r = classificar_pressao({'eu':{'cobertura_s':100,'fracao_coberta':1,
             'minimo_observado':90,'mana_minima':80,'esforco_por_min':20}},p,['eu'])
        self.assertEqual(r['classificacao'],'pressionada_mas_controlada')
        r = classificar_pressao(r['por_membro']['eu']['medidas'] and {'eu':r['por_membro']['eu']['medidas']},p,['eu','EK'])
        self.assertEqual(r['classificacao'],'inconclusiva')
        rows[-1]['rotulo']='tranquila'; self.assertFalse(calibrar_politica(rows,90)['promover'])
        rows[0]['rotulo_origem']='regra_propria'; self.assertFalse(calibrar_politica(rows,90)['promover'])

    def test_adocao_exige_pacote_detectado_e_nao_intencao(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(Path(tmp)); obs = {'sugestao':{'id':'s'},'declaracao_uso':
                {'id':'d','resposta':'uso_confirmado','confirmado_em':100,'revisoes':{'rtc':'r'}},
                'concordancia':{'estado':'confere'},'uso_componentes':{'rtc':{'uso_confirmado':True}}}
            self.assertIsNone(reg.acompanhar_adocao('x',obs))
            obs['uso_componentes'].update({k:{'uso_confirmado':True} for k in ('cura','roda')})
            reg.acompanhar_adocao('x',obs); reg.acompanhar_adocao('x',obs)
            self.assertEqual(len(reg.ler('x','adocao')),1)
            obs['concordancia']['estado']='divergente'; self.assertIsNone(reg.acompanhar_adocao('x',obs))

    def test_reserva_persistida_e_configuracao_mudou(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(tmp)
            reg.validar_execucao('x',{'rtc_chave':'a'},90)
            reg.validar_execucao('x',{'rtc_chave':'a'},100)
            reg.validar_execucao('x',{'rtc_chave':'b'},101)
            self.assertEqual(len(reg.ler('x','reserva_avaliacao')),2)
            self.assertEqual(reg.ler('x','reserva_avaliacao')[0]['definida_em'],90)

    def test_contraste_entre_hunts_nao_copias_ou_contextos_diferentes(self):
        antes = [{'origem_id':str(i),'inicio':i*20+1,'fim':i*20+10,'contexto':{'area':'A'},
                  'medidas':{'mana':100}} for i in range(3)]
        depois = [{'origem_id':str(i+3),'inicio':100+i*20,'fim':110+i*20,'contexto':{'area':'A'},
                   'medidas':{'mana':80}} for i in range(3)]
        self.assertEqual(contraste_temporal(antes,depois,'mana',-1)['ganho'],20)
        self.assertIsNone(contraste_temporal(antes,antes,'mana')['intervalo_ganho'])
        depois[0]['contexto']['area']='B'
        self.assertIsNone(contraste_temporal(antes,depois,'mana')['intervalo_ganho'])

    def test_bonus_passivo_derivado_sem_dano_total_incremental(self):
        casts = [{'id':'a','kind':'cast','qualidade':'identificada','magia_id':'wave',
                  'declaracao_uso_id':'d','dano_total':9000},
                 {'id':'b','kind':'cast','qualidade':'identificada','magia_id':'wave','declaracao_uso_id':'anterior'}]
        r = uso_bonus_por_magia(casts,[{'magia_id':'wave','tipo':'passivo','modificador':.06}], 'd')
        self.assertEqual(r[0]['casts_identificados'],1)
        self.assertEqual(r[0]['usos_elegiveis'],1)
        self.assertIsNone(r[0]['contribuicao_incremental'])

    def test_fechamento_automatico_avalia_so_adocao_confirmada(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(tmp)
            rec = {'id':'r','instante':50,'contexto':{'char':'QA','hunt':'A','pt':'solo'},
                   'alteracoes':[{'campo':'prioridade','antes':2,'depois':1}], 'objetivo_declarado':'dano'}
            reg.registrar_recomendacao('antes',rec)
            resultado = {'sessao':'depois','contexto':{'char':'QA','hunt':'A','pt':'solo'},
                         'periodo':{'fim':150},'taxas':{'raw_h':120},'pressao':{'combate_observavel_s':100},'fases':[]}
            self.assertFalse(reg.avaliar_resultado_posterior('depois',resultado))
            reg.guardar('depois','adocao',[{'id':'a','instante':100,'recomendacao_id':'r','uso_confirmado':True}])
            r = reg.avaliar_resultado_posterior('depois',resultado)
            self.assertEqual(r[0]['estado'],'inconclusivo')
            self.assertEqual(len(reg.ler('depois','resultado_adotado')),1)
            self.assertEqual(len(reg.ler('depois','efetividade')),1)
