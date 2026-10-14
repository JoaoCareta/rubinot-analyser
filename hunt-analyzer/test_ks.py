"""Regras de KS e união do histórico, com dados isolados."""
import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import ao_vivo
import ks
import atlas_build as ab
import numpy as np


class RegrasKS(unittest.TestCase):
    def test_lista_historico_reusa_party_e_ks_do_mesmo_relatorio(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ao_vivo,'HUNT_DATA',pathlib.Path(tmp)):
            p=pathlib.Path(tmp)/'hunt/sessoes/20261013_062400';p.mkdir(parents=True)
            (p/'resumo.json').write_text(json.dumps({'sessao':{'pt':'pt x3'},'voltas':[], 'totais':{},'fechada':True}))
            conflitos={'episodios':[{'id':'ks'}],'sessoes':[{'party':['A','B','C','D']}]}
            with patch.object(ao_vivo,'_ks_hist',return_value=conflitos) as leitura:
                s=ao_vivo.historico()[0]
                self.assertEqual(s['pt'],'pt x4');self.assertTrue(s['tem_ks'])
                self.assertEqual(s['ks_episodios'],1);leitura.assert_called_once()

    def test_ks_recuperado_com_prova_preserva_aliado_e_nao_duplica(self):
        ep=dict(id='real',origem='releitura_server_log',inicio='08:45:48',fim='08:45:48',
                prova_inicio=dict(sha256_log_original='prova'),
                dano=dict(party={},fora={'Hectera':dict(dano=1039,golpes=2)}))
        original=dict(sessao='qa',party=['Eu'],episodios=[],dano_hunt_observado=dict(party={},fora={}))
        d=dict(origem='usuario',aliados=['Aliado'],episodios_recuperados=[ep])
        r=ks.corrigir_relatorio(original,d)
        self.assertEqual([e['id'] for e in r['episodios']],['real'])
        self.assertEqual(len(ks.corrigir_relatorio(r,d)['episodios']),1)
        self.assertEqual(original['episodios'],[])
        self.assertEqual(ks.corrigir_relatorio(original,{**d,'episodios_recuperados':[{**ep,'prova_inicio':{}}]})['episodios'],[])

    def test_solo_prioriza_hunt_analyser_e_preserva_log_parcial(self):
        r = dict(party_paineis=[dict(t=1,solo=True,fonte_dano='Hunt Analyser',
            danos={'Druida':5823000},curas={'Druida':750669},profits={'Druida':None}),
            dict(t=2,solo=True,fonte_dano='Hunt Analyser',
                 danos={'Druida':None},curas={'Druida':760000},profits={})],
            dano_hunt_observado={'party':{'Druida':dict(dano=50,golpes=1,criticos=0)}})
        stats = ks.estatisticas_party([r])
        self.assertEqual(stats['fonte_dano'], 'Hunt Analyser')
        self.assertEqual(stats['total'], 5823000)
        self.assertEqual(stats['jogadores'][0]['cura'], 760000)
        self.assertEqual(stats['jogadores'][0]['dano_observado'], 50)

    def test_party_nao_e_substituida_pelo_solo_apos_sair(self):
        ps = [dict(t=1,danos={'Druida':1000,'Cavaleiro':2000},curas={},profits={}),
              dict(t=2,solo=True,fonte_dano='Hunt Analyser',danos={'Druida':5000},curas={},profits={})]
        stats = ks.estatisticas_party([dict(party_paineis=ps)])
        self.assertEqual(stats['total'], 3000)
        self.assertEqual(stats['fonte_dano'], 'Party Hunt')

    def test_reset_solo_depois_de_lacuna_preserva_segmentos(self):
        ps = [dict(t=t,solo=True,fonte_dano='Hunt Analyser',danos={'Druida':d},curas={},profits={})
              for t,d in [(1,1000),(2,None),(3,0),(4,200)]]
        stats = ks.estatisticas_party([dict(party_paineis=ps)])
        self.assertEqual(stats['total'],1200)
        self.assertEqual(stats['resets'],1)

    def test_variacao_espacos_do_painel_nao_duplica_acumulado(self):
        ps = [dict(t=1,danos={'Druida Um':1000},curas={},profits={}),
              dict(t=2,danos={'DruidaUm':1200},curas={},profits={})]
        stats = ks.estatisticas_party([dict(party_paineis=ps)])
        self.assertEqual(stats['total'],1200)
        self.assertEqual(len(stats['jogadores']),1)

    def test_party_formas_identifica_nome_sem_exigir_dano_legivel(self):
        nomes, danos, _, curas = ks.Leitor.blocos_party([
            'Druida', '1,000', '2?000', '400', 'Cavaleiro', '200', '3,000', '0'])
        self.assertEqual(nomes, ['Druida','Cavaleiro'])
        self.assertIsNone(danos['Druida'])
        self.assertEqual(curas['Druida'], 400)
        _, danos, _, _ = ks.Leitor.blocos_party([
            'Druida','? 1,000','? 2,000','? 400','Cavaleiro','? 200','? 3,00?','? 0'])
        self.assertEqual(danos['Druida'],2000)
        self.assertIsNone(danos['Cavaleiro'])

    def test_leitor_solo_publica_dano_cura_do_painel_pessoal(self):
        from PIL import Image
        p = self.sessao / 'f_000001_000.png'
        Image.new('RGB',(2000,1100)).save(p)
        with patch.object(self.d.leitor,'linhas',return_value=[]), \
             patch.object(ks.painel_stream,'recortar_painel',return_value=Image.new('RGB',(200,200))), \
             patch.object(ks.painel_stream,'linhas',return_value=[]), \
             patch.object(ks.painel_stream,'ler',return_value=({'Loot':0,'Supplies':0,'Balance':0},[])), \
             patch.object(ks.painel_stream,'ler_quadro',return_value=({'Damage':5823000,'Healing':750669},[])):
            painel = self.d.leitor.party(p,self.d.lay,'Druida')
        self.assertTrue(painel['solo'])
        self.assertEqual(painel['danos'], {'Druida':5823000})
        self.assertEqual(painel['curas'], {'Druida':750669})

    def test_ganhos_ks_usam_fronteiras_e_rejeitam_reset_ou_loot_type(self):
        ep = dict(inicio='00:00:10',ultimo_t=30)
        self.d.paineis = [dict(t=10,xp_raw=100,fonte_xp='XP Analyser',loot_periodo=200,fonte_loot='Party Hunt',tipo='Market'),
                          dict(t=30,xp_raw=140,fonte_xp='XP Analyser',loot_periodo=270,fonte_loot='Party Hunt',tipo='Market')]
        self.assertEqual(self.d.ganhos_painel(ep)['xp_raw'],40)
        self.assertEqual(self.d.ganhos_painel(ep)['loot'],70)
        self.d.paineis[0]['fonte_xp']='Hunt Analyser'
        self.assertIsNone(self.d.ganhos_painel(ep)['xp_raw'])
        self.assertEqual(self.d.ganhos_painel(ep)['loot'],70)
        self.d.paineis[0]['fonte_xp']='XP Analyser'
        self.d.paineis.insert(1,dict(t=20,xp_raw=10,fonte_xp='XP Analyser',loot_periodo=10,fonte_loot='Party Hunt',tipo='Market'))
        self.assertIsNone(self.d.ganhos_painel(ep)['xp_raw'])
        self.assertIsNone(self.d.ganhos_painel(ep)['loot'])
        self.d.paineis.pop(1);self.d.paineis[-1]['tipo']='Leader'
        self.assertIsNone(self.d.ganhos_painel(ep)['loot'])
        ep['ultimo_t']=40
        self.assertIsNone(self.d.ganhos_painel(ep)['xp_raw'])

    def test_house_com_gravacao_parada(self):
        g = ao_vivo.Gravacao()
        with patch.object(ao_vivo, 'house_player', return_value=dict(x=100,y=100,z=7,raio=3)):
            self.assertFalse(g.json_hunt()['estado']['gravando'])

    def test_house_ao_vivo_so_com_posicao_absoluta(self):
        import time
        g = ao_vivo.Gravacao()
        g.sessao, g.char, g.grava = self.sessao, 'Druida', False
        g.visto = g.t0 = time.time()
        g.hunt_comecou = None
        g.amostras = [[0,7,100,100,0]]
        with patch.object(ao_vivo, 'house_player', return_value=dict(x=100,y=100,z=7,raio=3)):
            self.assertEqual(g.json_hunt()['estado']['local'],'House do player')
            with patch.object(g, '_mapa_estado', return_value=dict(fonte='local',ancorado=False,planos=[])):
                self.assertNotEqual(g.json_hunt()['estado']['local'],'House do player')

    def test_house_pessoal_separa_periodo_e_andar(self):
        import sinais
        trechos = [dict(tipo='refil', inicio=0, fim=30, dur_s=30)]
        pontos = [dict(t=0,z=7,x=10,y=10),dict(t=10,z=7,x=100,y=100),
                  dict(t=20,z=8,x=100,y=100),dict(t=30,z=8,x=100,y=100)]
        res = sinais.identifica_house(trechos,pontos,dict(x=100,y=100,z=7,raio=3))
        self.assertEqual([(t['tipo'],t['dur_s']) for t in res],[('refil',10),('house',10),('refil',10)])

    def test_espacos_no_nome_e_troca_loot_nao_resetam_dano(self):
        r = dict(sessao='session_20261010_000000',party_paineis=[
            dict(t=1,danos={'SkysThe Limit':1000},supplies=100,tipo='Market'),
            dict(t=2,danos={'SkysThe Limit':1200},supplies=90,tipo='Leader')],
            dano_hunt_observado={'party':{'Skys The Limit':dict(dano=50,golpes=1,criticos=0)}})
        stats=ks.estatisticas_party([r])
        self.assertEqual(stats['total'],1200)
        self.assertEqual(stats['resets'],0)
        self.assertEqual(len(stats['jogadores']),1)
        self.assertEqual(stats['jogadores'][0]['golpes'],1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = pathlib.Path(self.tmp.name)
        self.sessao = self.raiz / 'session_20261008_000000'
        self.sessao.mkdir()
        self.patch = patch.object(ks, 'RAIZ', self.raiz / 'KS')
        self.patch.start()
        self.d = ks.Detector(self.sessao, 'Druida')
        self.d.monstros = {'undertaker'}
        self.d.party = ['Druida', 'Cavaleiro']
        def prova(e, tipo, ep):
            p = self.d.pasta / ep['id'] / (tipo + '.png')
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'original')
            return {'print': p.relative_to(ks.RAIZ).as_posix(), 'evento': e}
        self.d.prova = prova

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def golpe(self, t, ator, valor=100):
        e = {'t': t, 'ts': f'{t // 3600:02d}:{t // 60 % 60:02d}:{t % 60:02d}',
             'kind': 'damage_dealt_player', 'actor': ator, 'target': 'undertaker', 'value': valor}
        self.d.evento(e, self.d.party)

    def test_party_proc_e_roster_ausente_nao_sao_ks(self):
        self.golpe(10, 'Cavaleiro (Onslaught)')
        self.assertFalse(self.d.episodios)
        self.d.evento({'kind': 'damage_dealt_player', 'target': 'undertaker'}, None)
        self.assertFalse(self.d.episodios)

    def test_duas_voltas_fim_no_ultimo_golpe_e_sem_dano_depois(self):
        voltas = [{'inicio': '00:00:00', 'fim': '00:02:00', 'dur_s': 120},
                  {'inicio': '00:02:00', 'fim': '00:05:00', 'dur_s': 180}]
        (self.sessao / 'laps.jsonl').write_text('\n'.join(json.dumps(v) for v in voltas), encoding='utf-8')
        self.assertEqual(self.d.silencio_da_hunt(301), 300)
        self.golpe(400, 'Adversario')
        self.golpe(410, 'Cavaleiro', 70)
        self.golpe(420, 'Adversario', 200)
        self.golpe(500, 'Cavaleiro', 90)
        self.d.fecha(719)
        self.assertIsNotNone(self.d.atual)
        self.d.fecha(720)
        ep = self.d.episodios[0]
        self.assertEqual(ep['fim'], '00:07:00')
        self.assertEqual(ep['dano']['fora']['Adversario']['dano'], 300)
        self.assertEqual(ep['dano']['party']['Cavaleiro']['dano'], 70)
        self.assertTrue((ks.RAIZ / ep['prova_fim']['print']).exists())

    def test_encerrar_gravacao_fecha_no_ultimo_dano_sem_esperar_voltas(self):
        self.golpe(400, 'Adversario')
        self.golpe(420, 'Adversario', 200)
        self.golpe(500, 'Cavaleiro', 90)
        self.d.fecha(600, encerrar=True)
        ep = self.d.salva()['episodios'][0]
        self.assertFalse(ep['aberto'])
        self.assertEqual(ep['fim'], '00:07:00')
        self.assertEqual(ep['motivo_fim'], 'gravacao_encerrada')
        self.assertEqual(ep['prova_fim']['evento']['ts'], '00:07:00')
        self.assertEqual(ep['dano']['fora']['Adversario']['dano'], 300)
        self.assertNotIn('Cavaleiro', ep['dano']['party'])
        self.assertIsNone(self.d.atual)

    def test_historico_encerrado_consolida_ks_antigo_sem_alterar_prova(self):
        self.golpe(420, 'Adversario')
        self.d.salva()
        registro = dict(pasta=self.sessao.name, fechada=True)
        with patch.object(ao_vivo, 'CAPTURAS', self.raiz):
            resultado = ao_vivo._ks_hist([(self.sessao / 'resumo.json', registro)])
            ep = resultado['episodios'][0]
            self.assertFalse(ep['aberto'])
            self.assertEqual(ep['fim'], '00:07:00')
            self.assertEqual(ep['prova_fim'], ep['prova_ultimo'])
            registro['fechada'] = False
            ativo = ao_vivo._ks_hist([(self.sessao / 'resumo.json', registro)])
            self.assertTrue(ativo['episodios'][0]['aberto'])
        self.assertTrue(json.loads((self.sessao / 'ks.json').read_text(encoding='utf-8'))['episodios'][0]['aberto'])

    def test_sem_volta_nao_inventa_timeout(self):
        self.golpe(400, 'Adversario')
        self.d.fecha(10000)
        self.assertIsNotNone(self.d.atual)

    def test_prova_preserva_tela_inteira_e_separa_log(self):
        from PIL import Image
        tela = Image.new('RGB', (1600, 900), '#123456')
        tela.save(self.sessao / 'f_000011_000.png')
        Image.new('RGB', (586, 62), '#555555').save(self.sessao / 'c_000010_000.png')
        e = {'ts': '00:00:10', 'capturado_t': 10, 'frame': 'c_000010_000.png', 'y0': 20, 'y1': 31}
        prova = ks.Detector.prova(self.d, e, 'inicio', {'id': '001'})
        with Image.open(ks.RAIZ / prova['print']) as saida:
            self.assertEqual(saida.crop((0, 0, 1600, 900)).tobytes(), tela.tobytes())
            self.assertGreater(saida.height, tela.height)
        self.assertEqual(prova['defasagem_contexto_s'], 1)
        self.assertEqual(prova['formato'], 'tela_inteira_com_log_separado')
        self.assertTrue((ks.RAIZ / prova['log_destacado']).exists())

    def test_prova_sincronizada_destaca_linha_na_janela(self):
        from PIL import Image
        import capture
        self.d.lay['chat'] = {'left': 200, 'top': 500, 'width': 586, 'height': 62}
        tela = Image.new('RGB', (1000, 700), '#123456')
        capture.salva_quadro(tela, self.sessao / 'q_000010_000.png')
        capture.salva_quadro(capture.recorta(tela, self.d.lay['chat']), self.sessao / 'c_000010_000.png')
        e = {'ts': '00:00:10', 'capturado_t': 10, 'frame': 'c_000010_000.png', 'y0': 20, 'y1': 31}
        prova = ks.Detector.prova(self.d, e, 'inicio', {'id': '001'})
        self.assertEqual((ks.RAIZ / prova['print']).parent, self.d.pasta)
        self.assertEqual((ks.RAIZ / prova['original']).parent, self.d.logs)
        self.assertFalse(any(p.is_dir() and p.name.isdigit() for p in self.d.pasta.iterdir()))
        self.assertTrue(prova['sincronizado'])
        self.assertEqual(prova['defasagem_contexto_s'], 0)
        with Image.open(ks.RAIZ / prova['print']) as saida:
            self.assertEqual(saida.size, tela.size)
            self.assertEqual(saida.getpixel((200, 519)), (255, 85, 85))
            self.assertEqual(saida.crop((0, 0, 1000, 500)).tobytes(), tela.crop((0, 0, 1000, 500)).tobytes())
        # Um recorte de outro momento jamais é inserido na tela.
        Image.new('RGB', (586, 62), '#ffffff').save(self.sessao / e['frame'])
        prova = ks.Detector.prova(self.d, e, 'ultimo', {'id': '001'})
        self.assertFalse(prova['sincronizado'])

    def test_party_parcial_nao_transforma_aliado_em_ks(self):
        p = self.sessao / 'f_000010_000.png'
        self.d.leitor.party = lambda *args: {'nomes': ['Druida', 'Novo'], 'danos': {}, 'frame': p.name, 't': 10}
        self.d.processa(p)
        self.d.processa(p)
        self.assertIn('Cavaleiro', self.d.party)
        self.assertIn('Novo', self.d.party)
        self.golpe(12, 'Cavaleiro')
        self.assertFalse(self.d.episodios)

    def test_lacuna_nao_conta_como_silencio(self):
        self.d.silencio = 300
        self.golpe(100, 'Adversario')
        self.d.atual['silencio_desde'] = 1000
        self.d.fecha(1299)
        self.assertIsNotNone(self.d.atual)
        self.d.fecha(1300)
        self.assertIsNone(self.d.atual)


class Historico(unittest.TestCase):
    def test_correcao_declarada_preserva_original_e_intrusos_sem_ledger(self):
        r = dict(sessao='qa', party=['Eu'], episodios=[
            dict(id='1', inicio='00:00:10', ultimo_t=10, aberto=False,
                 dano={'party': {}, 'fora': {'Aliado': {'dano': 10}}}),
            dict(id='2', inicio='00:00:20', ultimo_t=20, aberto=False,
                 dano={'party': {}, 'fora': {'Intruso': {'dano': 20}}})])
        antes = copy.deepcopy(r)
        d = dict(origem='usuario', aliados=['Aliado'])
        corrigido = ks.corrigir_relatorio(r, d)
        self.assertEqual(r, antes)
        self.assertEqual([e['id'] for e in corrigido['episodios']], ['2'])
        self.assertEqual(corrigido['episodios_reclassificados'][0]['id'], '1')
        self.assertEqual(len(ks.corrigir_relatorio(corrigido, d)['episodios_reclassificados']), 1)
        self.assertIs(ks.corrigir_relatorio(r, dict(origem='inferido', aliados=['Aliado'])), r)

    def test_intervalo_personagem_dia_e_taxa_unica(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ao_vivo, 'HUNT_DATA', pathlib.Path(tmp)):
            def salva(nome, inicio, fim, char='Druida', data='08/10/2026'):
                p = pathlib.Path(tmp) / 'hunt' / 'sessoes' / nome
                p.mkdir(parents=True)
                r = {'sessao': {'inicio': inicio, 'fim': fim, 'char': char, 'data': data, 'pt': 'pt x4'},
                     'voltas': [{'n': 1, 'ini': 0, 'fim': 100, 'dur': 100, 'xp_raw': 1000, 'xp_origem':'XP Analyser', 'bichos': 10}],
                     'totais': {'voltas': 1, 'dur_s': 100, 'xp_raw': 1000}, 'fechada': True}
                (p / 'resumo.json').write_text(json.dumps(r), encoding='utf-8')
                return p / 'resumo.json'
            original = salva('20261008_0600', '06:00:00', '07:00:00')
            antes = original.read_bytes()
            salva('20261008_0730', '07:30:00', '08:00:00')
            salva('20261008_0900', '09:00:00', '09:30:00')  # exatamente 1 h não une
            salva('20261008_0940', '09:40:00', '10:00:00', char='Outro')
            grupos = ao_vivo._grupos_historico()
            self.assertEqual([len(g) for g in grupos], [2, 1, 1])
            r = ao_vivo._mescla_historico(grupos[0])
            self.assertEqual([v['n'] for v in r['voltas']], [1, 2])
            self.assertEqual(ao_vivo.taxas(r['voltas'])['raw_h'], 36000)
            self.assertEqual(ao_vivo.taxas(r['voltas'])['dur_s'], 200)
            self.assertEqual(original.read_bytes(), antes)
            # outro dia nunca agrega
            salva('20261009_0600', '06:00:00', '07:00:00', data='09/10/2026')
            self.assertEqual([len(g) for g in ao_vivo._grupos_historico()], [2, 1, 1, 1])


class ConsoleAlto(unittest.TestCase):
    def test_leitura_abaixo_da_antiga_altura_limite(self):
        glyphs, gap = ab.load_atlas()
        key, char = next((k, ch) for k, ch in glyphs.items()
                         if len(ch) == 1 and ch.isalpha() and json.loads(k)[0] == 0
                         and 6 <= len(json.loads(k)[2]) <= 15)
        top, w, rows = json.loads(key)
        letra = np.array([[(r >> (w - 1 - x)) & 1 for x in range(w)] for r in rows], dtype=bool)
        tela = np.zeros((500, w + 4), dtype=bool)
        for y in (20, 350):
            tela[y:y + len(letra), 2:2 + w] = letra
        self.assertEqual(ab.decode_binary(tela, glyphs, gap), [char])
        self.assertEqual(ab.decode_binary(tela, glyphs, gap, input_top=None), [char, char])


class EstatisticasParty(unittest.TestCase):
    def test_painel_inclui_baseline_e_nao_duplica_gravacoes(self):
        a = {'nomes':['Druida','EK'], 'danos':{'Druida':900,'EK':1200}, 't':10, 'frame':'f_a',
             'profits':{'Druida':-30,'EK':130}, 'curas':{'Druida':500,'EK':40},
             'loot':150,'supplies':50,'profit':100}
        b = dict(a, danos={'Druida':1000,'EK':1500}, t=20, frame='f_b')
        r = ks.estatisticas_party([{'sessao':'session_20261010_000000','party_paineis':[a,b]},
                                  {'sessao':'session_20261010_000015','party_paineis':[b]}])
        self.assertEqual(r['total'], 2500)
        self.assertEqual(r['loot'],150)
        self.assertEqual(r['profit'],100)
        self.assertEqual(r['jogadores'][0]['participacao'],60)
        self.assertIsNone(r['jogadores'][0]['criticos'])

    def test_reset_soma_periodos_comprovados(self):
        ps = [{'t':10,'frame':'a','danos':{'Druida':1000},'supplies':100},
              {'t':20,'frame':'b','danos':{'Druida':10},'supplies':1},
              {'t':30,'frame':'c','danos':{'Druida':90},'supplies':10}]
        r = ks.estatisticas_party([{'party_paineis':ps}])
        self.assertEqual(r['total'],1090)
        self.assertEqual(r['resets'],1)
        self.assertEqual(r['supplies'],110)

    def test_aliado_convertido_na_hunt_inteira_e_ks_retido_so_de_outros(self):
        with tempfile.TemporaryDirectory() as temp:
            s=pathlib.Path(temp)/'session_20261010_000000'; s.mkdir()
            with patch.object(ks,'RAIZ',pathlib.Path(temp)/'KS'):
                d=ks.Detector(s,'Druida'); d.monstros={'undertaker'}
                d.party=['Druida']; d.prova=lambda e,t,ep: {'evento':e}
                def golpe(nome,t):
                    d.evento(dict(kind='damage_dealt_player',actor=nome,target='undertaker',
                                  t=t,ts=f'00:00:{t:02d}',value=100),d.party)
                golpe('Novo',10); d.salva(); d.confirma_party(['Druida','Novo'],15)
                self.assertFalse(d.episodios)
                self.assertEqual(d.dano_hunt['party']['Novo']['dano'],100)
                self.assertNotIn('Novo',d.dano_hunt['fora'])
                golpe('Intruso',20); golpe('Novo',21)
                d.confirma_party(['Druida','Novo','MaisUm'],22)
                self.assertEqual(len(d.episodios),1)
                self.assertEqual(set(d.episodios[0]['dano']['fora']),{'Intruso'})
                d.salva()
                ledger=[json.loads(l) for l in d.dano_path.read_text(encoding='utf-8').splitlines()]
                self.assertTrue(all(e['grupo']=='party' for e in ledger if e['actor']=='Novo'))

    def test_fatal_antes_e_depois_do_ponto_e_critico_simultaneo(self):
        import events_build as ev
        pessoas = {}
        for body in ('A undertaker loses 200 hitpoints due to your critical attack. (Onslaught)',
                     'A undertaker loses 300 hitpoints due to an attack by Cavaleiro (Onslaught).'):
            kind, e = ev.classify(body)
            self.assertTrue(e['fatal'])
            e.setdefault('actor', 'Druida')
            ks.Detector.soma(pessoas, e)
        self.assertEqual(set(pessoas), {'Druida', 'Cavaleiro'})
        self.assertEqual(pessoas['Druida']['criticos'], 1)
        self.assertEqual(pessoas['Druida']['fatais'], 1)
        self.assertEqual(pessoas['Cavaleiro']['dano_fatal'], 300)
        self.assertEqual(pessoas['Cavaleiro']['maior_golpe'], 300)

    def test_sessoes_reunidas_somam_e_lacunas_antigas_nao_viram_zero(self):
        novo = {}
        ks.Detector.soma(novo, dict(actor='Druida', target='undertaker', value=200, crit=True, fatal=True))
        antigo = {'druida': {'dano': 100, 'golpes': 2, 'criticos': 0}}
        r = ks.estatisticas_party([{'dano_hunt_observado': {'party': novo}},
                                  {'dano_hunt_observado': {'party': antigo}}])
        self.assertIsNone(r['total'])  # log não substitui o painel
        self.assertEqual(len(r['jogadores']), 1)
        p = r['jogadores'][0]
        self.assertIsNone(p['participacao'])
        self.assertEqual(p['dano_observado'], 300)
        self.assertAlmostEqual(p['criticos_pct'], 100 / 3)
        self.assertIsNone(p['fatais'])
        self.assertIsNone(p['maior_golpe'])

    def test_conta_sem_ks_e_persiste_sem_quadros(self):
        with tempfile.TemporaryDirectory() as temp:
            pasta = pathlib.Path(temp) / 'session_20261010_000000'
            pasta.mkdir()
            d = ks.Detector(pasta, 'Druida')
            d.monstros = {'undertaker'}
            d.evento(dict(kind='damage_dealt', target='undertaker', value=50,
                          ts='00:00:10', t=10), ['Druida', 'Cavaleiro'])
            r = d.salva()
            self.assertFalse(r['episodios'])
            self.assertIsNone(r['estatisticas_party']['total'])
            self.assertEqual(r['estatisticas_party']['jogadores'][0]['dano_observado'], 50)
            self.assertEqual(json.loads((pasta / 'ks.json').read_text(encoding='utf-8'))['estatisticas_party'], r['estatisticas_party'])

    def test_releitura_party_com_prova_recupera_ultima_linha_sem_alterar_original(self):
        original = {'party':['Druida'],'episodios':[],'party_paineis':[],
                    'dano_hunt_observado':{'party':{},'fora':{}}}
        releitura = {'origem':'releitura_paineis_e_console','provas':['quadro'],
                     'party_paineis':[{'t':20,'nomes':['Druida','Aliado'],
                       'danos':{'Druida':100,'Aliado':200},'profits':{},'curas':{},
                       'fonte_dano':'Party Hunt'}],
                     'dano_hunt_observado':{'party':{},'fora':{}}}
        declaracao = {'origem':'usuario','aliados':['Aliado'],'relatorio_releitura':releitura}
        r = ks.corrigir_relatorio(original,declaracao)
        aliado = next(p for p in r['estatisticas_party']['jogadores'] if p['nome']=='Aliado')
        self.assertEqual(aliado['dano'],200)
        self.assertIsNone(aliado['golpes'])
        self.assertEqual(original['party_paineis'],[])
        releitura['provas']=[]
        self.assertEqual(ks.corrigir_relatorio(original,declaracao)['party_paineis'],[])

if __name__ == '__main__':
    unittest.main()

