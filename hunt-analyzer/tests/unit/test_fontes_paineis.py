import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import painel_stream
import pt_card
from rubinot.assistencia.utamo import Utamo


class FontesPaineisTest(unittest.TestCase):
    def test_vida_exige_barra_inteira_nao_cauda_colorida(self):
        import numpy as np
        from rubinot.observacao.execucao import vida_nameplate
        arr = np.full((30,100,3),45,dtype=np.uint8)
        arr[10:14,30:61] = 0
        arr[11:13,31:55] = (96,192,96)
        self.assertAlmostEqual(vida_nameplate(arr,51,17),24/29*100)
        arr[10,30:61] = 45
        self.assertIsNone(vida_nameplate(arr,51,17))

    def test_releitura_nao_altera_cache_nem_inventa_valor(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'xp_releituras.json'
            p.write_text(json.dumps({'qa': {'voltas': {'1|10|20': {
                'xp_origem': 'XP Analyser', 'xp_raw': 0, 'provas': ['quadro']}}}}))
            card = {'xp_raw_painel': None}
            L = dict(volta=1, inicio='00:00:10', fim='00:00:20')
            with patch.object(pt_card, 'RELEITURAS_XP', p):
                self.assertEqual(pt_card.aplicar_releitura_xp(Path('qa'), L, card)['xp_raw_painel'], 0)
                self.assertIs(pt_card.aplicar_releitura_xp(Path('outra'), L, card), card)
            self.assertIsNone(card['xp_raw_painel'])

    def test_xp_borda_da_seta_nao_e_digito(self):
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/leitores/xp-scrollbar.png'
        with Image.open(fixture) as img:
            com_seta, _ = painel_stream.ler(img)
            sem_seta, _ = painel_stream.ler(img.crop((0, 0, 157, img.height)))
        self.assertNotIn('RawXPGain', com_seta)
        self.assertEqual(sem_seta['RawXPGain'], 29892422)
        self.assertEqual(sem_seta['XPGain'], 156433733)
        self.assertNotIn('RawXPGain', painel_stream.campos(['Raw XP Gain:29,892,42?']))

    def test_historico_antigo_preserva_xp_com_origem_sem_regravar(self):
        import ao_vivo
        with tempfile.TemporaryDirectory() as tmp, patch.object(ao_vivo,'HUNT_DATA',Path(tmp)):
            p=Path(tmp)/'hunt'/'sessoes'/'20261012_0600';p.mkdir(parents=True)
            arquivo=p/'resumo.json'
            arquivo.write_text(json.dumps({'sessao':{},'voltas':[{'xp_raw':1000,'dur':100}],'totais':{'xp_raw':1000}}))
            antes=arquivo.read_bytes();r=ao_vivo._grupos_historico()[0][0][1]
            self.assertEqual(r['voltas'][0]['xp_raw'],1000)
            self.assertEqual(r['voltas'][0]['xp_origem'],'Registro antigo')
            self.assertEqual(arquivo.read_bytes(),antes)

    def test_historico_releitura_prioritaria_e_lacuna_atual(self):
        import ao_vivo
        with tempfile.TemporaryDirectory() as tmp, patch.object(ao_vivo,'HUNT_DATA',Path(tmp)):
            revisoes = Path(tmp)/'xp.json'
            revisoes.write_text(json.dumps({'session_20261012_060000': {'voltas': {
                '1|100|200': {'xp_raw':0,'xp_origem':'XP Analyser','provas':['quadro']},
                '2|200|300': {'xp_raw':999,'xp_origem':'XP Analyser','provas':[]}}}}))
            for dia in ['20261012','20261014']:
                p=Path(tmp)/'hunt'/'sessoes'/f'{dia}_0600';p.mkdir(parents=True)
                (p/'resumo.json').write_text(json.dumps({'pasta':f'session_{dia}_060000','sessao':{},
                    'voltas':[{'n':1,'ini':100,'fim':200,'dur':100,'xp_raw':1000},
                              {'n':2,'ini':200,'fim':300,'dur':100,'xp_raw':2000}]}))
            with patch.object(pt_card,'RELEITURAS_XP',revisoes):
                grupos=ao_vivo._grupos_historico()
            antigo, atual = [g[0][1] for g in grupos]
            self.assertEqual(antigo['totais']['xp_raw'],2000)
            self.assertEqual(antigo['voltas'][0]['xp_origem'],'XP Analyser')
            self.assertEqual(antigo['voltas'][1]['xp_raw'],2000)
            self.assertIsNone(atual['totais']['xp_raw'])
            self.assertTrue(all(v['xp_raw'] is None for v in atual['voltas']))

    def test_xp_jamais_volta_ao_hunt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with patch.object(painel_stream,'ler',return_value=({'RawXPGain':999,'Supplies':20},[])):
                dados,_=painel_stream.ler_quadro(Image.new('RGB',(100,100)),p,(0,0,90,90),90)
            self.assertNotIn('RawXPGain',dados)
            self.assertEqual(dados['Supplies'],20)

    def test_xp_zero_e_fonte_separada(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'calibracao.json').write_text(json.dumps({'regioes':{'xp':{'left':10,'top':0,'width':30,'height':20}}}))
            with patch.object(painel_stream,'ler',return_value=({'RawXPGain':0,'XPGain':200,'Supplies':999},[])):
                self.assertEqual(painel_stream.ler_xp(Image.new('RGB',(100,100)),p),{'RawXPGain':0,'XPGain':200})

    def test_input_nao_confunde_total_de_cura_e_conserva_tipos(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'calibracao.json').write_text(json.dumps({'regioes':{'input':{'left':0,'top':0,'width':160,'height':200}}}))
            with patch.object(painel_stream,'linhas',return_value=['Received Damage','Total: 1,000','Max-DPS: 30','Damage Types','? 700 (70.0%)','Received Healing','Total: 9,000']):
                r=painel_stream.ler_input(Image.new('RGB',(200,220)),p)
            self.assertEqual(r['total'],1000);self.assertEqual(r['max_dps'],30)
            self.assertEqual(r['tipos'][0]['valor'],700);self.assertIsNone(r['tipos'][0]['tipo'])

    def test_utamo_prioriza_delta_input_e_rejeita_reset(self):
        u=Utamo();u.agora=100;u.eventos.append((100,'damage_taken',100,'bicho'))
        u.input_danos.extend([(92,1000),(96,1500),(100,3000)])
        self.assertEqual(u.sinais()['dano'],2000)
        self.assertEqual(u.sinais()['dano_origem'],'Input Analyser')
        u.input_danos[-1]=(100,100)
        self.assertEqual(u.sinais()['dano_origem'],'log_parcial')

    def test_volta_xp_ausente_nao_usa_hunt_e_dano_recebido_e_input(self):
        l={'inicio':'00:00:00','fim':'00:00:20','volta':1}
        with tempfile.TemporaryDirectory() as tmp, patch.object(pt_card,'leia',return_value={'raw':999,'xpg':9999,'sup':0,'bal':0,'membros':0}), patch.object(pt_card,'leia_xp',return_value={}), patch.object(pt_card,'leia_input',side_effect=[{'total':100},{'total':600}]):
            r=pt_card.volta(Path(tmp),None,None,l)
        self.assertIsNone(r['xp_raw_painel']);self.assertEqual(r['dmg_in_painel'],500)


if __name__=='__main__': unittest.main()
