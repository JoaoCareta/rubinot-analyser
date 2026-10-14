import pathlib
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import configuracoes as c
from rubinot.planejamento.registro import Registro, absoluto, vincular_voltas


class UsoDetectadoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = pathlib.Path(self.tmp.name)
        p = patch.object(c, 'RAIZ', self.raiz / 'config')
        p.start(); self.addCleanup(p.stop)
        self.img = Image.new('RGB', (200, 100), 'black')

    def ler(self, preset='um', sessao='s1', instante=10):
        return c.observar('rtc', self.img, 'QA', sessao,
            [{'texto': 'Preset: '+preset, 'y': 2}], capturado_em=instante)['snapshot']

    def test_sem_leitura_nao_confirma(self):
        with self.assertRaises(ValueError):
            c.declarar_uso('QA', 's1', {'rtc': 'ausente'}, 'uso_confirmado')

    def test_parcial_sem_roda_e_sem_sugestao(self):
        s = self.ler()
        d = c.declarar_uso('QA', 's1', {'rtc': s['id']}, 'uso_confirmado')
        obs = c.consultar('QA', 's1')
        self.assertTrue(obs['elegibilidade_aprendizado']['cadencia_ataque'])
        self.assertFalse(obs['elegibilidade_aprendizado']['cura'])
        self.assertFalse(obs['elegibilidade_aprendizado']['efeitos_roda'])
        self.assertFalse(obs['rtc']['aplicado_confirmado'])
        self.assertIn('rtc', d['lacunas'])
        self.assertEqual(d, c.declarar_uso('QA', 's1', {'rtc': s['id']}, 'uso_confirmado'))
        self.assertFalse(c.consultar('QA', 's2')['elegibilidade_aprendizado']['cadencia_ataque'])

    def test_revisao_obsoleta_e_negativa(self):
        s = self.ler(); c.declarar_uso('QA', 's1', {'rtc': s['id']}, 'uso_confirmado')
        nova = self.ler('dois', instante=20)
        self.assertFalse(c.consultar('QA', 's1')['elegibilidade_aprendizado']['cadencia_ataque'])
        with self.assertRaises(ValueError):
            c.declarar_uso('QA', 's1', {'rtc': s['id']}, 'uso_confirmado')
        d = c.declarar_uso('QA', 's1', {'rtc': nova['id']}, 'rtc_desligado')
        self.assertTrue(d['substitui'])
        self.assertEqual(c.consultar('QA', 's1')['uso_componentes']['rtc']['estado'], 'rtc_desligado')
        self.assertEqual(len(list(c.RAIZ.rglob('uso_*.json'))), 3)

    def test_frescor_sem_fase_duplicada_ou_confirmacao_retroativa(self):
        s = self.ler(instante=10)
        d = c.declarar_uso('QA', 's1', {'rtc': s['id']}, 'uso_confirmado')
        nova = self.ler(instante=20)
        self.assertEqual(s['id'], nova['id'])
        self.assertEqual(nova['instante'], 10)
        self.assertEqual(nova['visto_por_ultimo_em'], 20)
        reg = Registro(self.raiz / 'db')
        obs = c.consultar('QA', 's1')
        antes = reg.fase('s1', 'QA', obs, d['confirmado_em']-1)
        depois = reg.fase('s1', 'QA', obs, d['confirmado_em'])
        self.assertEqual(antes['revisoes']['rtc']['estado'], 'observado_sem_aplicacao')
        self.assertEqual(depois['revisoes']['rtc']['estado'], 'uso_declarado')
        self.assertEqual(depois['id'], reg.fase('s1', 'QA', obs, d['confirmado_em']+1)['id'])
        self.assertEqual(len(reg.ler('s1', 'fase')), 2)

    def test_calibracao_revalidada_para_sessao(self):
        s = self.ler(sessao='calibracao')
        c.declarar_uso('QA', 's1', {'rtc': s['id']}, 'uso_confirmado')
        self.assertTrue(c.consultar('QA', 's1')['elegibilidade_aprendizado']['cadencia_ataque'])
        self.assertFalse(c.consultar('QA', 's2')['elegibilidade_aprendizado']['cadencia_ataque'])

    def test_observacao_leve_pode_ser_associada_explicitamente(self):
        s = self.ler(sessao='observacao')
        self.assertEqual(c.consultar('QA', 's1')['rtc']['id'], s['id'])
        self.assertFalse(c.consultar('QA', 's1')['elegibilidade_aprendizado']['cadencia_ataque'])
        c.declarar_uso('QA', 's1', {'rtc':s['id']}, 'uso_confirmado')
        self.assertTrue(c.consultar('QA', 's1')['elegibilidade_aprendizado']['cadencia_ataque'])
        self.assertFalse(c.consultar('QA', 's2')['elegibilidade_aprendizado']['cadencia_ataque'])

    def test_quadro_atrasado_nao_substitui_leitura_vigente(self):
        s = self.ler(instante=10)
        self.ler(instante=50)
        r = self.ler('antigo', instante=30)
        self.assertEqual(r['id'], s['id'])
        self.assertEqual(c.consultar('QA', 's1')['rtc']['id'], s['id'])
        self.assertTrue(any(c.ler_json(p).get('estado') == 'quadro_antigo_preservado'
                            for p in c.RAIZ.rglob('*_rtc.json')))

    def test_volta_mista_sem_rateio(self):
        sessao = 'session_20261012_142757'
        fases = [{'id':'antes', 'instante':absoluto(sessao, 0),
                  'revisoes':{'rtc':{'estado':'observado_sem_aplicacao'}}},
                 {'id':'depois', 'instante':absoluto(sessao, 100),
                  'revisoes':{'rtc':{'estado':'uso_declarado'}}}]
        voltas = [{'n':9,'ini':90,'fim':110,'xp_raw':200}, {'n':10,'ini':110,'fim':130,'xp_raw':300}]
        r = vincular_voltas(sessao, voltas, fases)
        self.assertEqual(r[0]['estado'], 'mista')
        self.assertEqual(r[1]['estado'], 'completa_com_uso_declarado')
        self.assertFalse(r[0]['totais_rateados'])
        self.assertEqual(voltas[0]['xp_raw'], 200)
