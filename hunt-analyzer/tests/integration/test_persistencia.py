import json
import contextlib
import datetime
import pathlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from rubinot.adapters.arquivos import gravar_json, ler_json
from rubinot.adapters.historico import publicar, arquivo_publicado, chave_sessao, reservar_sessao
from aprendizado_hunt import Registro


class PersistenciaTest(unittest.TestCase):
    def test_plunder_no_historico_sem_alterar_registros(self):
        import ao_vivo
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            for dia, qtd in ((1, 7), (2, 0), (3, None)):
                pasta = raiz / 'qa' / 'sessoes' / f'2026010{dia}_010000'
                publicar(pasta, {'pasta': f'session_2026010{dia}_010000',
                    'sessao': {'hunt': 'QA', 'char': 'QA', 'data': f'0{dia}/01/2026',
                               'inicio': '01:00:00', 'fim': '01:05:00'},
                    'fechada': True, 'especies': {'undertaker': 100},
                    'voltas': [{'n': 1, 'especies': {'Plunder Patriarch': qtd}}]}, {})
            antes = {p: p.read_bytes() for p in raiz.rglob('*') if p.is_file()}
            with patch.object(ao_vivo, 'HUNT_DATA', raiz), \
                 patch.object(ao_vivo, '_ks_hist', return_value={'episodios': [], 'party': []}):
                lista = ao_vivo.historico()
            self.assertEqual([s['tem_plunder'] for s in lista], [False, False, True])
            self.assertEqual(antes, {p: p.read_bytes() for p in antes})
            self.assertTrue(ao_vivo._plunder_avistado({'especies': {' plunder   patriarch ': 1}}))
            self.assertFalse(ao_vivo._plunder_avistado({}))
            self.assertFalse(ao_vivo._plunder_avistado({'especies': {'plunder': 1, 'plunder patriarch': -1}}))
            grupos = [(pathlib.Path('qa/sessoes/a/resumo.json'), {'sessao': {}, 'voltas': []}),
                      (pathlib.Path('qa/sessoes/b/resumo.json'), {'sessao': {},
                       'voltas': [{'especies': {'plunder patriarch': 2}}]})]
            self.assertTrue(ao_vivo._plunder_avistado(ao_vivo._mescla_historico(grupos)))

    def test_reserva_duas_capturas_no_mesmo_segundo(self):
        with tempfile.TemporaryDirectory() as d:
            agora = datetime.datetime(2026, 1, 1, 1, 0, 1)
            a, b = reservar_sessao(d, agora), reservar_sessao(d, agora)
            self.assertNotEqual(a, b)
            self.assertNotEqual(chave_sessao(a.name), chave_sessao(b.name))
            from aprendizado_hunt import identidade
            self.assertNotEqual(identidade(a), identidade(b))

    def test_sessoes_no_mesmo_minuto_e_personagens(self):
        chaves = {chave_sessao('session_20261012_0700' + segundo, char)
                  for segundo in ('01', '02') for char in ('QA A', 'QA B')}
        self.assertEqual(len(chaves), 4)

    def test_escritores_concorrentes_sem_tmp_compartilhado(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'estado.json'
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda n: gravar_json(p, {'n': n, 'texto': 'ação'}), range(30)))
            self.assertIn(ler_json(p)['n'], range(30))
            self.assertEqual(list(pathlib.Path(d).glob('*.tmp')), [])

    def test_crash_preserva_geracao_anterior_completa(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            anterior = publicar(p, {'voltas': [1]}, {'mapa_z13.png': b'antigo', 'laps.jsonl': b'1\n'})
            from rubinot.adapters import historico
            original = historico.gravar_bytes
            def falhar(caminho, dados):
                if caminho.name == 'laps.jsonl':
                    raise OSError('falha injetada')
                original(caminho, dados)
            with patch.object(historico, 'gravar_bytes', side_effect=falhar):
                with self.assertRaises(OSError):
                    publicar(p, {'voltas': [2]}, {'mapa_z13.png': b'novo', 'laps.jsonl': b'2\n'})
            visivel = ler_json(p / 'resumo.json')
            self.assertEqual(visivel, anterior)
            self.assertEqual(arquivo_publicado(p, visivel, 'mapa_z13.png').read_bytes(), b'antigo')

    def test_sqlite_rollback_backup_e_fechamento(self):
        with tempfile.TemporaryDirectory() as d:
            reg = Registro(pathlib.Path(d) / 'origem')
            with self.assertRaises(RuntimeError):
                with reg.conexao() as con:
                    con.execute('INSERT INTO sessoes VALUES (?,?)', ('QA', '{}'))
                    raise RuntimeError('rollback')
            with reg.conexao() as con:
                self.assertEqual(con.execute('SELECT count(*) FROM sessoes').fetchone()[0], 0)
            reg.guardar('s', 'evento', [{'id': 'e', 'instante': 1}])
            reg.backup(pathlib.Path(d) / 'backup.sqlite3')
            with contextlib.closing(sqlite3.connect(pathlib.Path(d) / 'backup.sqlite3')) as con:
                self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(con.execute('SELECT count(*) FROM registros').fetchone()[0], 1)
            restaurada = pathlib.Path(d) / 'restaurada'
            restaurada.mkdir()
            import shutil
            shutil.copy2(pathlib.Path(d) / 'backup.sqlite3', restaurada / 'aprendizado.sqlite3')
            self.assertEqual(Registro(restaurada).ler('s', 'evento'), reg.ler('s', 'evento'))
            reg.db.rename(reg.db.with_suffix('.restaurado'))
