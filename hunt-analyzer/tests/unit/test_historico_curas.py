import tempfile
import unittest

from rubinot.adapters.curas import projetar, segundos
from rubinot.planejamento.registro import Registro


class HistoricoCurasTest(unittest.TestCase):
    def test_faixas_contabilizam_tempo_e_curas_sem_perder_lacunas(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(tmp)
            party = [dict(nome='Tank', vocacao='EK', identidade_confirmada=True)]
            reg.guardar('s', 'recurso', [dict(id=str(t), t=t, aliados={
                'Tank': dict(percentual=p, identidade_confirmada=confirmada)})
                for t, p, confirmada in [(1, 0, True), (3, 30, True), (5, 90, True),
                                         (7, 100, True), (8, 100, False), (9, 100, True), (18, 90, True)]])
            reg.guardar('s', 'evento', [dict(id=str(t), t=t, kind='cast', ator='ED', alvo='Tank',
                qualidade='identificada', magia_id=magia) for t, magia in
                [(2, 'heal_friend'), (4, 'heal_friend'), (6, 'nature_s_embrace'),
                 (10, 'heal_friend'), (15, 'heal_friend')]])
            m = projetar(reg, 's', 'ED', party, 0, 20)['membros'][0]
            p = m['permanencia']
            self.assertEqual([f['tempo_s'] for f in p['faixas']], [2, 2, 0, 0, 2])
            self.assertEqual(p['sem_vida'], dict(tempo_s=14, sio=1, gran_sio=0))
            self.assertEqual([f['sio'] for f in p['faixas']], [1, 1, 0, 0, 1])
            self.assertEqual(p['faixas'][-1]['gran_sio'], 1)
            for magia in ('sio', 'gran_sio'):
                self.assertEqual(sum(f[magia] for f in p['faixas']) + p['sem_vida'][magia], m[magia])

    def test_todos_os_jogadores_sem_inferir_destino_ou_vocacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(tmp)
            party = [dict(nome=n, identidade_confirmada=True) for n in ('Druid', 'Mage', 'Tank')]
            party.append(dict(nome='Nome incerto'))
            reg.guardar('s', 'evento', [
                dict(kind='cast', ator='Druid', alvo='Mage', qualidade='identificada', magia_id='heal_friend', t=5),
                dict(kind='cast', ator='Druid', alvo='Mage', qualidade='identificada', magia_id='nature_s_embrace', t=6),
                dict(kind='cast', ator='Druid', alvo='Nome incerto', qualidade='identificada', magia_id='heal_friend', t=7),
                dict(kind='cast', ator='Druid', qualidade='identificada', magia_id='heal_friend', t=8)])
            membros = {m['nome']: m for m in projetar(reg, 's', 'Druid', party, 0, 300)['membros']}
            self.assertEqual(set(membros), {'Druid', 'Mage', 'Tank'})
            self.assertEqual((membros['Mage']['sio'], membros['Mage']['gran_sio']), (1, 1))
            self.assertEqual(membros['Tank']['sio'], 0)
            self.assertIsNone(membros['Mage']['vocacao'])
            self.assertIsNone(membros['Mage']['vida']['minima'])

    def test_revisoes_destinos_fronteiras_e_lacunas(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(tmp)
            party = [dict(nome='Tank', vocacao='EK', identidade_confirmada=True),
                     dict(nome='Archer', vocacao='RP', identidade_confirmada=True)]
            def recurso(t, p, nome='Tank', **kw):
                return dict(id=str(t)+nome, t=t, aliados={nome:dict(percentual=p, origem='barra_nameplate_integral')}, **kw)
            reg.guardar('s', 'recurso', [recurso(0, 100), recurso(1, 10), recurso(3, 60),
                recurso(600, 0), recurso(601, 100), recurso(2, 90, 'Archer'), recurso(4, 1, 'T?nk'),
                recurso(5, 1, qa=True), recurso(6, 1, sintetico=True)])
            reg.guardar('s', 'recurso_cura', [recurso(1, 80)])
            cast = dict(kind='cast', ator='Druid', alvo='Tank', qualidade='identificada', magia_id='heal_friend')
            reg.guardar('s', 'evento', [{**cast, 't':2, 'id':'a'}, {**cast, 't':2, 'id':'duplicado'},
                {**cast, 't':10, 'id':'longe'}, {**cast, 't':3, 'id':'rp', 'alvo':'Archer'},
                {**cast, 't':300, 'id':'gran', 'magia_id':'nature_s_embrace'},
                {**cast, 't':1, 'id':'outro', 'ator':'Outro'}, {**cast, 't':4, 'id':'qa', 'qa':True},
                {**cast, 't':5, 'id':'parcial', 'qualidade':'parcial'}, {**cast, 't':601, 'id':'fora'}])
            antes = len(reg.ler('s', 'recurso'))
            r = projetar(reg, 's', 'Druid', party, 1, 600)
            ek, rp = r['membros']
            self.assertEqual(ek['vida']['leituras'], 3)
            self.assertEqual((ek['vida']['minima'], ek['vida']['maxima']), (0, 80))
            self.assertEqual((ek['sio'], ek['gran_sio'], rp['sio']), (2, 1, 1))
            self.assertEqual(ek['trechos'][0]['curas'][0]['vida_antes'], 80)
            self.assertIsNone(ek['trechos'][0]['curas'][1]['vida_antes'])
            self.assertEqual(rp['trechos'][1]['vida']['minima'], None)
            self.assertEqual(len(reg.ler('s', 'recurso')), antes)
            self.assertNotIn('prova', str(r))
            self.assertNotIn('modelo', str(r))

    def test_sem_periodo_sem_identidade_e_meia_noite(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registro(tmp)
            self.assertEqual(projetar(reg, 's', 'ED', [], 0, 600)['membros'], [])
            self.assertFalse(projetar(reg, 's', 'ED', [], None, 600)['periodo_disponivel'])
            self.assertEqual(segundos('24:01:02'), 86462)
            self.assertIsNone(segundos('01:70:00'))
            self.assertIsNone(segundos(True))
            reg.guardar('s', 'evento', [dict(kind='player_info', target='Tank', vocation='elite knight', t=86401)])
            r = projetar(reg, 's', 'ED', [{'nome':'Tank'}], 86400, 87001)
            self.assertEqual(len(r['membros'][0]['trechos']), 3)
            self.assertTrue(all(t['vida']['minima'] is None for t in r['membros'][0]['trechos']))

