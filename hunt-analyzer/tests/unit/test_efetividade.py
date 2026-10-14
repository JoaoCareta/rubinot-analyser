import unittest
from rubinot.planejamento.efetividade import avaliar_ajuste, dividir_temporal, contribuicao_bonus
from rubinot.planejamento.oportunidades import reconstruir


class EfetividadeTest(unittest.TestCase):
    def test_pacote_nao_atribui_cada_perk(self):
        recomendacao = {'id': 'r', 'alteracoes': ['mana_leech', 'dano'],
                        'objetivo_declarado': 'dano', 'adocao': {'uso_confirmado': True}}
        antes = {'contexto': {'char': 'QA', 'area': 'A'}, 'fim': 10,
                 'exposicao_s': 300, 'medidas': {'producao': 100}}
        depois = {'contexto': antes['contexto'], 'inicio': 20, 'exposicao_s': 300,
                  'medidas': {'producao': 120}, 'seguranca': 'avaliada_sem_piora',
                  'intervalo_ganho': [10, 30]}
        politica = {'definida_em': 15, 'exposicao_min_s': 200, 'medida': 'producao', 'margem_pratica': 5}
        r = avaliar_ajuste(recomendacao, antes, depois, politica)
        self.assertEqual(r['estado'], 'beneficio_relevante')
        self.assertEqual(r['unidade_avaliada'], 'pacote')
        self.assertIn('alteracoes_simultaneas_sem_atribuicao_individual', r['limites_atribuicao'])
        for falta in ({'exposicao_s': 10}, {'seguranca': 'inconclusiva'}, {'intervalo_ganho': [-20,30]}):
            self.assertEqual(avaliar_ajuste(recomendacao, antes, {**depois, **falta}, politica)['estado'], 'inconclusivo')
        self.assertEqual(avaliar_ajuste(recomendacao, antes, {**depois, 'intervalo_ganho': [-1,1]}, politica)['estado'], 'sem_ganho_relevante_detectavel')

    def test_copias_e_sobreposicao_nao_vazam_no_teste(self):
        rows = [{'origem_id':str(i), 'inicio':i*10, 'fim':i*10+5} for i in range(8)]
        r = dividir_temporal(rows+rows)
        self.assertEqual([len(r[k]) for k in ('treino','selecao','teste')], [4,2,2])
        self.assertEqual(dividir_temporal([{**x,'fim':999} for x in rows])['estado'], 'inconclusivo_sobreposicao')

    def test_bonus_sem_confundir_dano_total(self):
        cast = {'id':'a','kind':'cast','qualidade':'identificada','magia_id':'wave','bonus_elegivel':True,'dano_total':5000}
        r = contribuicao_bonus([cast,cast], {'magia_id':'wave','tipo':'passivo'})
        self.assertEqual(r['casts_identificados'], 1)
        self.assertEqual(r['aplicacoes_identificadas_ou_derivadas'], 1)
        self.assertIsNone(r['contribuicao_incremental'])
        r = contribuicao_bonus([cast], {'magia_id':'wave','tipo':'condicional'})
        self.assertEqual(r['aplicacoes_identificadas_ou_derivadas'], 0)

    def test_oportunidade_tem_bloqueios_e_lacunas(self):
        eventos = [{'id':str(i),'kind':'cast','qualidade':'identificada','magia_id':'wave','t':t,'instante':t} for i,t in enumerate([10,12])]
        slots = [{'id':'wave','creatures':2,'mana_percent':5}, {'id':'fork','creatures':3,'mana_percent':5}]
        cat = [{'id':'wave','cd':4,'grupo':2}, {'id':'fork','cd':6,'grupo':2}]
        recursos = [{'t':12,'mana':{'percentual':2},'criaturas':2}]
        r = reconstruir(eventos,recursos,slots,cat,0)
        self.assertIn('geometria',r[0]['candidatas'][0]['desconhecidas'])
        self.assertIn('cooldown_individual',r[1]['candidatas'][0]['bloqueios'])
        self.assertIn('mana_percent',r[1]['candidatas'][1]['bloqueios'])
        self.assertIn('creatures',r[1]['candidatas'][1]['bloqueios'])
