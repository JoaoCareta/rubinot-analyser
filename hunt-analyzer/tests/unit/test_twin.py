import copy
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import configuracoes as c
from rubinot.adapters.fila_rtc import consumir
from rubinot.configuracao_combate.concordancia import comparar
from rubinot.hunt.metricas import taxas_intervalos
from rubinot.planejamento.registro import Registro
from rubinot.planejamento import twin


def fase(limiar=5,raw=20000000,inicio=100,fim=200,sessao='referencia'):
    return {'twin':limiar,'inicio':inicio,'fim_observado':fim,'sessao':sessao,
        'contexto':dict(char='QA',hunt='cave',pt=4,membros=['QA','EK','RP','MS'],hazard=6,roda='r',rota='rota',interferencias=[]),
        'voltas':3,'cobertura':1,'uso_confirmado':True,'seguranca':True,
        'raw_por_volta':[raw]*3,'taxas':{'raw':{'por_h':raw},'dano_pt':{'por_h':90000000}}}


class TwinTest(unittest.TestCase):
    def test_xp_primeiro_e_variacao_mantem_referencia(self):
        e=twin.propor(fase(),[],201)
        self.assertEqual(len(e['ajustes']),1)
        depois=fase(4,19000000,300,400,'depois')
        depois['taxas']['dano_pt']['por_h']=120000000
        self.assertEqual(twin.avaliar(e,depois)['estado'],'pior')
        depois=fase(4,20100000,300,400,'depois')
        self.assertEqual(twin.avaliar(e,depois)['estado'],'inconclusivo')
        for campo,valor in [('cobertura',0.79),('uso_confirmado',False),('seguranca',False),('voltas',2)]:
            f=fase();f[campo]=valor
            self.assertIsNone(twin.propor(f,[],201))
        f=fase();f['contexto']['membros'].pop()
        self.assertIsNone(twin.propor(f,[],201),'PT x4 não pode avaliar segurança de somente três integrantes')

    def test_validacao_exige_outra_hunt_posterior(self):
        e=twin.propor(fase(),[],201)
        d=fase(4,23000000,300,400,'d1')
        a=twin.avaliar(e,d)
        self.assertEqual(a['estado'],'promissor')
        self.assertFalse(a['promover'])
        self.assertFalse(twin.avaliar(e,d,[a])['promover'])
        self.assertTrue(twin.avaliar(e,fase(4,23000000,500,600,'d2'),[a])['promover'])
        alterada=fase(4,23000000,500,600,'d2');alterada['contexto']['hazard']=5
        self.assertFalse(twin.avaliar(e,alterada,[a])['promover'])
        controle=twin.propor({**fase(),'configuracoes':{'cura':{'slots':[{'id':'mass_healing','vida_percent':75}]}}},[],201)
        alterada=fase(4,23000000,500,600,'d2');alterada['configuracoes']={'cura':{'slots':[{'id':'mass_healing','vida_percent':95}]}}
        self.assertEqual(twin.avaliar(controle,alterada)['estado'],'inconclusivo','cura alterada não vira ganho exclusivo da Twin')
        self.assertIsNone(twin.propor(fase(),[e],201))
        anterior={**e,'estado':'inconclusivo'}
        self.assertIsNotNone(twin.propor(fase(inicio=500,fim=600,sessao='nova_referencia'),[anterior],601))

    def test_comparacao_twin_independe_roda_e_cura(self):
        s={'rtc':{'linhas':[dict(id='ice_burst',tipo='magia',slot=1,creatures=5,prioridade=2,mana_percent=5)]},'roda':{'pontos':{'a':25}}}
        obs={'rtc':{'slots':[dict(id='ice_burst',tipo='magia',slot=1,creatures=5,prioridade=2,mana_percent=5,instante=10)]}}
        cmp=comparar(s,obs,{})
        self.assertEqual(cmp['campos'][0]['estado'],'confere')
        self.assertEqual(cmp['componentes']['rtc']['estado'],'confere')
        self.assertEqual(cmp['campos'][0]['uso_automatico'],'uso_desconhecido')
        obs['rtc']['slots'][0]['creatures']=None
        self.assertEqual(comparar(s,obs,{})['campos'][0]['estado'],'parcial')

    def test_fronteira_incerta_exclui_volta_sem_rateio(self):
        leituras=[dict(tipo='rtc',instante=t,slots=[dict(id='ice_burst',creatures=n)],campos={}) for t,n in [(10,5),(20,5),(40,2)]]
        fs=twin.periodos(leituras,[])
        self.assertEqual(len(fs),2)
        self.assertEqual(fs[1]['fronteira']['inicio'],20)
        self.assertEqual(twin.fase_intervalo(fs,10,20),0)
        self.assertIsNone(twin.fase_intervalo(fs,15,30))
        self.assertEqual(twin.fase_intervalo(fs,40,50),1)

    def test_retrospectiva_deltas_e_paridade(self):
        rows=[dict(inicio=0,fim=7425.733,raw=39514532,dano_proprio=23012074),
              dict(inicio=8000,fim=11955.589,raw=22242184,dano_proprio=12958304)]
        for r in rows:r['fontes']={'raw':'XP Analyser','dano_proprio':'Party Hunt'}
        r=taxas_intervalos(rows)
        self.assertAlmostEqual(r['raw']['por_h']/1e6,19.534,places=3)
        self.assertAlmostEqual(r['dano_proprio']['por_h']/1e6,11.378,places=3)
        casos=[[],rows,[dict(inicio=0,fim=1,raw=0,fontes={'raw':'XP Analyser'})],
               [dict(inicio=0,fim=1,raw=10,reset=True,fontes={'raw':'XP Analyser'})],
               [dict(inicio=0,fim=1,raw=True,fontes={'raw':'XP Analyser'})],
               [dict(inicio=0,fim=1,raw=10,mista=True,fontes={'raw':'XP Analyser'})]]
        js="const m=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(m.taxasIntervalos))));"
        p=subprocess.run(['node','-e',js],input=json.dumps(casos),text=True,capture_output=True,check=True,timeout=30)
        self.assertEqual(json.loads(p.stdout),[taxas_intervalos(r) for r in casos])

    def test_battle_nao_produz_dano_twin_nem_media_acertos(self):
        recursos=[{'instante':t,'battle':20,'contexto_twin':{'char':'QA'}} for t in (10,20)]
        p=twin.medir([dict(tipo='rtc',instante=10,slots=[dict(id='ice_burst',creatures=5)])],recursos,[])
        self.assertTrue(all(f['taxas']['raw']['por_h'] is None for f in p))
        self.assertTrue(all('alvos_atingidos' not in f for f in p))

    def test_fila_reinicio_falha_quadro_tardio_e_retencao(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessao=pathlib.Path(tmp)/'session_20261014_060000';sessao.mkdir()
            ps=[sessao/n for n in ('q_060000_000.png','q_060001_000.png','q_060002_000.png')]
            for p in ps:p.write_bytes(b'prova')
            l=type('Leitor',(),{})();vistos=[]
            l.processar=lambda p,*args: vistos.append(p.name)
            self.assertEqual(consumir(sessao,'QA',l,ps,limite=1),1)
            def falhar(*args):
                raise ValueError('quadro em escrita')
            l.processar=falhar
            with self.assertRaises(ValueError):consumir(sessao,'QA',l,ps)
            self.assertEqual(json.loads((sessao/'coleta_rtc.json').read_text())['pendentes'],2)
            l.processar=lambda p,*args: vistos.append(p.name)
            self.assertEqual(consumir(sessao,'QA',l,ps),2)
            self.assertEqual(consumir(sessao,'QA',l,ps),0)
            tarde=sessao/'f_055959_000.png';tarde.write_bytes(b'antigo')
            self.assertEqual(consumir(sessao,'QA',l,[tarde,*ps]),1)
            self.assertEqual(len(list(sessao.glob('*.png'))),4)
            self.assertEqual(vistos,[p.name for p in ps]+[tarde.name])

    def test_snapshot_repetido_antigo_e_provas_preservadas(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c,'RAIZ',pathlib.Path(tmp)/'cfg'), patch.dict(os.environ,{'HUNT_APRENDIZADO_RAIZ':str(pathlib.Path(tmp)/'aprendizado')}):
            img=Image.new('RGB',(10,10))
            def ler(n,t):
                with patch.object(c,'rtc_da_imagem',return_value=({},[dict(id='ice_burst',creatures=n,tipo='magia',slot=1)])):
                    return c.observar('rtc',img,'QA','session_20261014_060000',[],capturado_em=t)
            a=ler(5,10);b=ler(5,20)
            self.assertEqual(a['snapshot']['id'],b['snapshot']['id'])
            self.assertEqual(b['snapshot']['visto_por_ultimo_em'],20)
            nova=ler(2,30);antiga=ler(9,15);ler(9,15)
            self.assertTrue(antiga['quadro_antigo'])
            pasta=c.pasta_personagem('QA')
            self.assertEqual(c.ler_json(pasta/'rtc_atual.json')['id'],nova['snapshot']['id'])
            self.assertEqual(len(list(pasta.glob('*.png'))),3)
            reg=Registro(c.raiz_aprendizado())
            self.assertEqual(len(reg.ler('session_20261014_060000','configuracao_leitura')),4)
            self.assertEqual([r['slots'][0]['creatures'] for r in reg.ler('session_20261014_060000','configuracao_leitura')],[5,9,5,2])
            with patch.object(c,'rtc_da_imagem',return_value=({},[dict(id='ice_burst',creatures=6,tipo='magia',slot=1)])):
                outra=c.observar('rtc',img,'QA','session_20261013_060000',[],capturado_em=5)
            self.assertTrue(outra['quadro_antigo'])
            self.assertEqual(c.ler_json(pasta/'rtc_atual.json')['id'],nova['snapshot']['id'])
            historico=c.consultar('QA','session_20261013_060000',historico=True)
            self.assertEqual(historico['rtc']['slots'][0]['creatures'],6)

    def test_contexto_roda_cura_hazard_abrem_fases(self):
        leituras=[dict(tipo='rtc',instante=10,slots=[dict(id='ice_burst',creatures=5)]),
                  dict(tipo='roda',instante=10,campos={'pontos':{'valor':10}}),
                  dict(tipo='cura',instante=30,slots=[dict(id='heal_friend',vida_percent=90)])]
        ctx=fase()['contexto'];outro=copy.deepcopy(ctx);outro['hazard']=5
        recursos=[dict(instante=10,contexto_twin=ctx),dict(instante=20,contexto_twin=ctx),dict(instante=40,contexto_twin=outro)]
        fs=twin.periodos(leituras,recursos)
        self.assertEqual(fs[-1]['contexto']['hazard'],5)
        self.assertIsNone(twin.fase_intervalo(fs,15,45))

    def test_abertura_breve_real_recuperada_apos_fechamento(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c,'RAIZ',pathlib.Path(tmp)/'cfg'), patch.dict(os.environ,{'HUNT_APRENDIZADO_RAIZ':str(pathlib.Path(tmp)/'aprendizado')}):
            sessao=pathlib.Path(tmp)/'session_20261014_060000';sessao.mkdir()
            aberta=sessao/'q_060000_000.png';fechada=sessao/'q_060001_000.png'
            with Image.open('tests/fixtures/leitores/01-rtc-configurado.png') as im:
                im.save(aberta)
                Image.new('RGB',im.size).save(fechada)
            consumir(sessao,'QA',c.Leitor(),[aberta,fechada],limite=1)
            consumir(sessao,'QA',c.Leitor(),[aberta,fechada])
            atual=c.ler_json(c.pasta_personagem('QA')/'rtc_atual.json')
            self.assertTrue(atual['slots'])
            self.assertTrue((c.RAIZ/atual['prova']).is_file())
            self.assertFalse(atual['aplicado_confirmado'])
            self.assertEqual(consumir(sessao,'QA',c.Leitor(),[aberta,fechada]),0)

    def test_registro_proposta_usa_contexto_da_hunt_e_nao_contexto_de_cura(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Registro(pathlib.Path(tmp));s='session_20261014_060000';f=fase()
            r.guardar(s,'estudo_twin',[{'id':'referencia','instante':200,'periodos':[f]}])
            e=r.propor_twin(s,'QA',4,201)
            r.guardar(s,'recurso',[{'id':'quadro','instante':200,'contexto_twin':f['contexto']}])
            resumo=r.resumo_twin(s,'QA',{'char':'QA','sessao':s,'cura':{}})
            self.assertEqual(resumo['proposta']['id'],e['id'])
            self.assertEqual(resumo['proposta']['candidato'],4)
            with self.assertRaises(ValueError):r.propor_twin(s,'QA',6,202)

    def test_estudo_repetido_e_leitura_tardia_reconstroi_sem_regravar(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Registro(pathlib.Path(tmp));s='session_20261014_060000'
            r.guardar(s,'recurso',[{'id':'r','instante':20,'contexto_twin':fase()['contexto']}])
            a=r.estudar_twin(s,'QA',{})
            self.assertEqual(r.estudar_twin(s,'QA',{})['id'],a['id'])
            r.guardar(s,'configuracao_leitura',[{'id':'q','instante':10,'char':'QA','tipo':'rtc','slots':[{'id':'ice_burst','creatures':4}]}])
            b=r.estudar_twin(s,'QA',{})
            self.assertNotEqual(a['id'],b['id'])
            self.assertEqual(r.resumo_twin(s,'QA')['periodo']['inicio'],20)
            self.assertEqual(len(r.ler(s,'estudo_twin')),2)
            self.assertEqual(r.estudar_twin(s,'QA',{})['id'],b['id'])


if __name__=='__main__':
    unittest.main()
