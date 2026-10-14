import datetime
import tempfile
import unittest
from pathlib import Path
import json
from unittest.mock import patch

import aprendizado_hunt as ah


class AprendizadoHunt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.r = ah.Registro(self.raiz/'registro')

    def test_retomada_e_deduplicacao(self):
        e = {'id':'cast','t':90000,'instante':ah.absoluto('session_20261012_230000',90000),'kind':'cast'}
        for _ in range(2): self.r.guardar('s','evento',[e])
        self.assertEqual(len(ah.Registro(self.raiz/'registro').ler('s','evento')),1)
        d = datetime.datetime.fromtimestamp(e['instante'])
        self.assertEqual((d.day,d.hour),(13,1))

    def test_fases_nao_aplicam_editor_ou_configuracao_antiga(self):
        obs={'rtc':{'id':'r1','sessao':'s','instante':10,'completo':True}}
        f = self.r.fase('s','char',obs,20)
        self.assertEqual(f['revisoes']['rtc']['estado'],'observado_sem_aplicacao')
        self.assertEqual(self.r.fase('s','char',obs,25)['id'],f['id'])
        obs['rtc']['id']='r2'
        self.r.fase('s','char',obs,30)
        self.assertEqual(len(self.r.ler('s','fase')),2)
        self.assertIsNone(self.r.fase('outra','char',obs,30)['revisoes']['rtc']['revisao'])

    def test_evento_anterior_nao_recebe_configuracao_futura(self):
        self.r.observar('s','char',{},[{'id':'a','instante':10}],[],[])
        self.assertIsNone(self.r.ler('s','evento')[0]['fase_id'])

    def test_inventario_copias_e_taxas_oficiais(self):
        from ao_vivo import taxas
        v={'dur':120,'tipo':'volta','xp_raw':1000,'xp_origem':'XP Analyser','profit':None,'sup_pt':None,'sup_eu':10,'bichos':2}
        resumo={'pasta':'session_20261012_060001','sessao':{'char':'char','hunt':'Hunt'},'voltas':[v]}
        for root in ('workspace','instalacao'):
            p=self.raiz/root/'hunt_data'/'hunt'/'sessoes'/'20261012_0600'
            p.mkdir(parents=True)
            (p/'resumo.json').write_text(json.dumps(resumo),encoding='utf8')
        roots=[self.raiz/'workspace',self.raiz/'instalacao']
        a=self.r.inventariar(roots);b=self.r.inventariar(roots)
        self.assertEqual((a['sessoes'],a['copias']),(1,1))
        self.assertEqual(a,b)
        self.assertEqual(a['inventario'][0]['taxas'],taxas([v]))
        self.assertIsNone(a['inventario'][0]['configuracoes'])

    def test_lacunas_e_identidade_nao_viram_saude(self):
        qs=[{'instante':1,'vida':{'percentual':20},'aliados':{'player':{'percentual':10}}},
            {'instante':20,'vida':{'percentual':100}}]
        s=ah.saude_party(qs,[],{'versao':'qa','por_membro':{'eu':{'critico_pct':30}}})
        self.assertNotIn('player',s)
        self.assertEqual(s['eu']['cobertura_s'],0)
        self.assertEqual(s['eu']['critico_s'],0)
        self.assertEqual(s['eu']['seguranca'],'inconclusiva')

    def test_raw_maior_nao_libera_risco(self):
        a={'saude':{'RP':{'critico_s':1,'cobertura_s':100,'politica_versao':'qa'}}}
        b={'saude':{'RP':{'critico_s':20,'cobertura_s':100,'politica_versao':'qa'}}}
        c=ah.comparar_resultados(a,b,{'risco':.01})
        self.assertEqual(c['estado'],'resultado_misto');self.assertFalse(c['promover'])

    def test_limpeza_preserva_extração_pendente(self):
        import ao_vivo
        p=self.raiz/'session_20261012_060000';p.mkdir()
        (p/'c_060000_000.png').write_bytes(b'qa')
        (p/'aprendizado_estado.json').write_text('{"estado":"pendente"}',encoding='utf8')
        self.assertEqual(ao_vivo.limpa_quadros(raiz=self.raiz),(0,0))

    def test_coleta_independe_da_confirmacao(self):
        import configuracoes as c
        import observacao_execucao as o
        sessao=self.raiz/'session_20261012_000000';sessao.mkdir()
        f=sessao/'c_000001_000.png';f.touch()
        obs={}
        def mensagens(p,*args):
            return [('00:00:01' if p.name==f.name else '00:00:02','You gained 10 mana.')]
        with patch.object(c,'AQUI',self.raiz),patch.object(c,'RAIZ',self.raiz/'configuracoes_player'), \
             patch.object(c,'consultar',side_effect=lambda *args:obs), \
             patch('atlas_build.load_atlas',return_value=({},0)),patch('events_build.frame_messages',side_effect=mensagens):
            leitor=o.Observador(registro_de=lambda _:ah.Registro(self.raiz/'hunt_data'/'_aprendizado'));leitor.processar(sessao,'QA')
            obs['confirmacao']={'valida':True,'sugestao_id':'nova','instante':9999999999}
            (sessao/'c_000002_000.png').touch()
            leitor.processar(sessao,'QA')
        pasta=self.raiz/'configuracoes_player'/c._chave('QA')/'execucao'/sessao.name
        self.assertEqual([p.name for p in pasta.iterdir()],['observacao'])
        self.assertEqual(len(list(ah.linhas(pasta/'observacao'/'eventos.jsonl'))),2)
        self.assertEqual(len(ah.Registro(self.raiz/'hunt_data'/'_aprendizado').ler(sessao.name,'evento')),2)


if __name__=='__main__':unittest.main()
