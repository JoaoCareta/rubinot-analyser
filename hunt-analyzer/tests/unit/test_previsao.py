import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rubinot.planejamento.previsao import prever, comparar
from rubinot.planejamento.registro import Registro, absoluto


class Previsao(unittest.TestCase):
    def test_estudo_disponivel_na_consulta_historica(self):
        import configuracoes as c
        with tempfile.TemporaryDirectory() as pasta:
            raiz=Path(pasta)/'configuracoes'
            with patch.object(c,'RAIZ',raiz):
                Registro(c.raiz_aprendizado()).guardar('session_20261012_100000','estudo_previsto',[
                    {'id':'original','previsto':10,'observado':12,'erro':2}])
                consulta=c.consultar('Teste','session_20261012_100000',historico=True)
            self.assertEqual(consulta['estudo_previsto'][0]['previsto'],10)

    def test_relogio_legado_sem_fabricar_instante(self):
        self.assertEqual(absoluto('session_20261012_100000','25:00:00'),absoluto('session_20261012_100000',90000))
        self.assertIsNone(absoluto('session_20261012_100000','ilegível'))
        self.assertIsNone(absoluto('session_20261012_100000','10:99:00'))

    def test_replay_recursos_idempotente_e_escudo_desconhecido(self):
        from PIL import Image
        from rubinot.observacao.execucao import reprocessar_recursos
        with tempfile.TemporaryDirectory() as pasta:
            sessao=Path(pasta)/'session_20261012_100000';sessao.mkdir()
            Image.new('RGB',(4,4)).save(sessao/'q_100001_000.png')
            r=Registro(Path(pasta)/'db')
            with patch('rubinot.observacao.execucao.recursos',return_value={}), patch('rubinot.observacao.execucao.Observador._aliados',return_value={}), patch('configuracoes.linhas',return_value=[]):
                self.assertEqual(reprocessar_recursos(sessao,'Teste',r)['recursos_novos'],1)
                self.assertEqual(reprocessar_recursos(sessao,'Teste',r)['recursos_novos'],0)
            self.assertIsNone(r.ler(sessao.name,'recurso')[0]['escudo'])

    def test_replay_console_preserva_prova_sem_atribuir_rtc(self):
        from rubinot.observacao.execucao import reprocessar_consoles
        with tempfile.TemporaryDirectory() as pasta:
            sessao=Path(pasta)/'session_20261012_100000';sessao.mkdir()
            (sessao/'s_100001_000.png').touch()
            r=Registro(Path(pasta)/'db')
            with patch('atlas_build.load_atlas',return_value=({},1)), patch('events_build.frame_messages',return_value=[('10:00:01','exevo gran frigo hur')]), patch('events_build.classify',return_value=('cast',{'words':'exevo gran frigo hur'})):
                a=reprocessar_consoles(sessao,'Teste',r)
                b=reprocessar_consoles(sessao,'Teste',r)
            self.assertEqual(a['eventos_novos'],1);self.assertEqual(b['eventos_novos'],0)
            e=r.ler(sessao.name,'evento')[0]
            self.assertIsNone(e['configuracao_aplicada']);self.assertIsNone(e['fase_id'])
            self.assertEqual(e['magia_id'],'strong_ice_wave');self.assertTrue(e['prova'].endswith('.png'))

    def test_lacuna_e_zero(self):
        self.assertIsNone(prever([])['previsto'])
        self.assertEqual(prever([0])['previsto'],0)
        self.assertIsNone(comparar(prever([1]),None)['erro'])
        self.assertIsNone(comparar(prever([1]),0)['erro_percentual'])

    def test_adaptacao_so_por_erros_passados(self):
        p=prever([10]*30+[100]*25)
        self.assertIn('mediana_recente',p['modelo'])
        self.assertEqual(p['previsto'],100)
        self.assertLess(p['erro_modelo_medio'],p['erro_anterior_medio'])

    def test_replay_idempotente_sem_futuro_e_congelado(self):
        with tempfile.TemporaryDirectory() as pasta:
            r=Registro(pasta);s='session_20261012_100000'
            resumo={'sessao':{'char':'Teste','hunt':'Fire','pt':2},'voltas':[
                {'n':1,'ini':36000,'fim':36100,'dur':100},
                {'n':2,'ini':36100,'fim':36200,'dur':100},
                {'n':3,'ini':36200,'fim':36400,'dur':200}]}
            a=r.estudar_voltas(s,resumo,True)['comparacoes']
            dur=[e for e in a if e['metrica']=='duracao_s']
            self.assertIsNone(dur[0]['previsto'])
            self.assertEqual(dur[2]['previsto'],100)
            self.assertEqual(dur[2]['erro'],100)
            resumo['voltas'][-1]['dur']=300
            self.assertEqual(a,r.estudar_voltas(s,resumo,True)['comparacoes'])

    def test_prospectiva_antes_do_inicio_e_contexto_separado(self):
        with tempfile.TemporaryDirectory() as pasta:
            r=Registro(pasta);s='session_20261012_100000'
            resumo={'sessao':{'char':'Teste','hunt':'Fire','pt':2},'voltas':[
                {'n':1,'ini':36000,'fim':36100,'dur':100}]}
            with patch('rubinot.planejamento.registro.time.time',return_value=absoluto(s,36100)):
                r.estudar_voltas(s,resumo)
            resumo['voltas'].append({'n':2,'ini':36101,'fim':36221,'dur':120})
            dados=r.estudar_voltas(s,resumo)['comparacoes']
            linha=next(e for e in dados if e['volta']==2 and e['metrica']=='duracao_s')
            self.assertEqual(linha['modo'],'prospectivo');self.assertEqual(linha['previsto'],100)
            resumo['sessao']['pt']=3
            outra=r.estudar_voltas('session_20261013_100000',resumo,True)['comparacoes'][0]
            self.assertIsNone(outra['previsto'])


if __name__=='__main__':
    unittest.main()
