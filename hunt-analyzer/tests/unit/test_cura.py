import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rubinot.planejamento.cura import estudar
from rubinot.planejamento.registro import Registro


class CuraTest(unittest.TestCase):
    def test_fonte_do_nome_exata_sem_completar_identidade(self):
        import atlas_build, nameplates, numpy as np
        indice=nameplates.shape_index(atlas_build.load_atlas()[0])
        f=np.array([[c=='1' for c in f'{row:05b}'] for row in [7,12,31,12,12,12,12,12]])
        self.assertEqual(nameplates.decode_shape(f,indice),'f')
        f[3,1]=False
        self.assertEqual(nameplates.decode_shape(f,indice),'?')

    def test_aliado_conhecido_com_nome_vermelho_mantem_vida(self):
        from PIL import Image
        from rubinot.observacao.execucao import Observador
        nomes=[{'nome':'Knight','tipo':'alvo','px':(30,30),'dist_tiles':2},
               {'nome':'Creature','tipo':'alvo','px':(80,30),'dist_tiles':3}]
        with patch('layout.da_sessao',return_value={}),patch('nameplates.nameplates',return_value=nomes),patch('rubinot.observacao.execucao.vida_nameplate',return_value=20):
            r=Observador._aliados(Image.new('RGB',(100,60)),Path('x'),'ED',['Knight'])
        self.assertEqual(r['aliados']['Knight']['percentual'],20)
        self.assertNotIn('Creature',r['aliados'])
        self.assertEqual(r['criaturas'],1)

    def test_le_vida_mesmo_sem_barra_verde(self):
        from PIL import Image
        import numpy as np
        from rubinot.observacao.execucao import recursos
        with Image.open('tests/fixtures/leitores/cura.png') as im:
            arr=np.asarray(im.convert('RGB')).copy()
        topo=arr[:90];g=(topo[:,:,1].astype(int)-topo[:,:,0]>20)&(topo[:,:,1].astype(int)-topo[:,:,2]>20)&(topo.min(2)<170)
        topo[g]=[190,30,30]
        r=recursos(Image.fromarray(arr),rapido=True)
        self.assertEqual(r['vida']['atual'],5855)
        self.assertEqual(r['mana']['maxima'],32610)

    def setUp(self):
        self.ctx = {'char':'ED','sessao':'session_20261014_100000'}
        self.party = [{'nome':'Knight','vocacao':'EK','identidade_confirmada':True}]
        self.slots = [{'id':'mass_healing','tipo':'autocura','vida_percent':75},
                      {'id':'ultimate_healing','tipo':'autocura','vida_percent':70},
                      {'id':'restoration','tipo':'autocura','vida_percent':60},
                      {'id':'heal_friend','tipo':'party','vocacao_destino':'EK','vida_percent':80}]
        self.eventos=[];self.recursos=[]
        for i in range(60):
            t=i*8
            self.eventos.append({'kind':'cast','ator':'ED','magia_id':'heal_friend',
                                 'qualidade':'identificada','t':t})
            for dt in (0,1):
                self.recursos.append({'id':f'{i}-{dt}','t':t+dt,'fase_id':'fase1','prova':f'frame-{i}-{dt}',
                    'vida':{'percentual':72-dt},'aliados':{'Knight':{'percentual':45-dt}},'hazard':{'nivel':5}})

    def estudar(self, recursos=None, party=None):
        return estudar(self.eventos,self.recursos if recursos is None else recursos,self.ctx,
                       self.party if party is None else party,self.slots)

    def test_sugere_menos_disputa_sem_imitar_percentual(self):
        antes=copy.deepcopy(self.slots)
        r=self.estudar()
        self.assertEqual(r['estado'],'sugestao_para_testar')
        self.assertEqual(len(r['sugestoes']),1)
        s=r['sugestoes'][0]
        self.assertEqual((s['id'],s['anterior'],s['vida_percent']),('mass_healing',75,70))
        self.assertFalse(s['beneficio_real_validado'])
        self.assertLess(r['avaliacao']['treino_ate'],r['avaliacao']['teste_desde'])
        self.assertEqual(self.slots,antes)

    def test_perigo_proprio_posterior_rejeita_reducao(self):
        rs=copy.deepcopy(self.recursos)
        for i,q in enumerate(rs):
            if i>=90 and i%2:q['vida']['percentual']=20
        r=self.estudar(rs)
        self.assertEqual(r['estado'],'sem_melhoria_demonstrada')
        self.assertEqual(r['sugestoes'],[])

    def test_queda_do_ek_pede_antecipar_sio(self):
        rs=copy.deepcopy(self.recursos)
        for i,q in enumerate(rs):
            q['vida']['percentual']=100
            q['aliados']['Knight']['percentual']=85 if i%2==0 else 25
        r=self.estudar(rs)
        s=r['sugestoes'][0]
        self.assertEqual((s['id'],s['anterior'],s['vida_percent']),('heal_friend',80,85))

    def test_lacunas_identidade_fase_qa_e_provas_nao_viram_seguranca(self):
        variantes=[]
        for campo,valor in [('fase_id',None),('vigencia_inconclusiva',True),('qa',True),('prova',None),('hazard',{'nivel':None})]:
            variantes.append([{**q,campo:valor} for q in self.recursos])
        variantes.append([{**q,'t':q['t']*4} for q in self.recursos])
        variantes.append([{**q,'aliados':{'Kn?ght':q['aliados']['Knight']}} for q in self.recursos])
        for rs in variantes:
            with self.subTest(variante=rs[0]):
                r=self.estudar(rs);self.assertEqual(r['estado'],'dados_insuficientes');self.assertFalse(r['sugestoes'])
        self.assertEqual(self.estudar(party=[])['estado'],'dados_insuficientes')

    def test_fases_nao_sao_somadas_para_validar(self):
        rs=[{**q,'fase_id':str(i//40)} for i,q in enumerate(self.recursos)]
        self.assertEqual(self.estudar(rs)['estado'],'dados_insuficientes')

    def test_regra_do_rp_sem_identidade_bloqueia_ajuste_parcial(self):
        self.slots.append({'id':'heal_friend','tipo':'party','vocacao_destino':'RP','vida_percent':85})
        r=self.estudar()
        self.assertEqual(r['estado'],'dados_insuficientes')
        self.assertTrue(any('cada regra' in l for l in r['lacunas']))
        repetido=estudar(self.eventos,self.recursos,self.ctx,r['party'],r['configuracao_referencia'])
        self.assertEqual(repetido['estado'],'dados_insuficientes')

    def test_registro_historico_independente_da_sessao_atual(self):
        import configuracoes as c
        with tempfile.TemporaryDirectory() as td, patch.object(c,'RAIZ',Path(td)/'conf'):
            reg=Registro(c.raiz_aprendizado())
            reg.guardar(self.ctx['sessao'],'recurso_cura',self.recursos)
            reg.guardar(self.ctx['sessao'],'evento',[dict(e,id=str(i)) for i,e in enumerate(self.eventos)])
            estudo=reg.estudar_cura(self.ctx['sessao'],self.ctx,self.party,self.slots)
            r=c.consultar('ED',self.ctx['sessao'],historico=True)
            self.assertEqual(r['estudo_cura']['id'],estudo['id'])
            # A mesma série pode ganhar uma correção de configuração depois.
            # A consulta precisa mostrar a revisão mais recente, não o maior hash.
            self.slots[0]['vida_percent']=70
            with patch('rubinot.planejamento.registro.time.time',return_value=estudo['instante']+1):
                novo=reg.estudar_cura(self.ctx['sessao'],self.ctx,self.party,self.slots)
            self.assertEqual(c.consultar('ED',self.ctx['sessao'],historico=True)['estudo_cura']['id'],novo['id'])

    def test_coleta_drena_intermediarios_e_cursor_so_depois_de_guardar(self):
        from PIL import Image
        from rubinot.observacao.execucao import Observador
        import configuracoes as c
        with tempfile.TemporaryDirectory() as td, patch.object(c,'RAIZ',Path(td)/'conf'):
            sessao=Path(td)/self.ctx['sessao'];sessao.mkdir()
            for segundo in range(3):Image.new('RGB',(4,4)).save(sessao/f'q_10000{segundo}_000.png')
            reg=Registro(Path(td)/'db');o=Observador(registro_de=lambda _:reg)
            with patch('rubinot.observacao.execucao.recursos',return_value={'vida':{'percentual':42}}),patch.object(Observador,'_aliados',return_value={}):
                self.assertEqual(o.coletar_cura(sessao,'ED',limite=2),2)
                self.assertEqual(c.ler_json(sessao/'coleta_cura.json')['estado'],'pendente')
                self.assertEqual(o.coletar_cura(sessao,'ED'),1)
                self.assertEqual(o.coletar_cura(sessao,'ED'),0)
                self.assertEqual(len(reg.ler(sessao.name,'recurso_cura')),3)
                self.assertTrue(all(Path(q['prova']).exists() for q in reg.ler(sessao.name,'recurso_cura')))

    def test_falha_de_leitura_preserva_cursor_e_quadro(self):
        from PIL import Image
        from rubinot.observacao.execucao import Observador
        import configuracoes as c
        with tempfile.TemporaryDirectory() as td, patch.object(c,'RAIZ',Path(td)/'conf'):
            sessao=Path(td)/self.ctx['sessao'];sessao.mkdir();p=sessao/'q_100000_000.png'
            Image.new('RGB',(4,4)).save(p)
            reg=Registro(Path(td)/'db');o=Observador(registro_de=lambda _:reg)
            with patch('rubinot.observacao.execucao.recursos',side_effect=ValueError('ilegível')):
                with self.assertRaises(ValueError):o.coletar_cura(sessao,'ED')
            self.assertTrue(p.exists());self.assertFalse((sessao/'coleta_cura.json').exists())
