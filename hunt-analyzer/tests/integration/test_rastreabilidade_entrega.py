"""Incidentes de entrega: fontes concorrentes, pacote trocado e reversão segura."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

TOOLS = Path(__file__).resolve().parents[3] / 'tools'
sys.path.insert(0, str(TOOLS))
import atualizar_local as atualizar
import rastreabilidade as r
import verificar
from diagnostico_http import DiagnosticoHTTP


def qa(atual, runtime='runtime'):
    return {'schema': 2, 'id': 'qa-sintetico', 'ok': True, 'perfil': 'completo',
            'fontes_sha256': atual['sha256'], 'fontes_finais_sha256': atual['sha256'],
            'runtime_sha256': runtime, 'runtime_final_sha256': runtime,
            'suites': [{'nome': n, 'estado': 'passou'} for n in
                       ['python', 'e2e', 'integridade-fontes', 'incidentes']]}


class RuntimeNativoTest(unittest.TestCase):
    def test_hash_independe_da_inclusao_do_launcher_pelo_compilador(self):
        sys.path.insert(0, str(TOOLS.parent / 'instalador'))
        import montar_pacote as pacote
        normal = verificar.impressao_runtime()
        with patch.object(pacote, 'ENTRADAS', [*pacote.ENTRADAS, 'hunt_launcher']):
            self.assertEqual(verificar.impressao_runtime(), normal)


class RastreabilidadeEntregaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rubinot-teste-entrega-')
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.build = self.raiz / 'build' / 'produto'
        self.build.mkdir(parents=True)
        (self.build / 'HuntAnalyzer.exe').write_bytes(b'binario-sintetico')
        (self.build / 'ui').mkdir()
        (self.build / 'ui/hunt.js').write_bytes(b'asset-validado')
        self.instalacao = self.raiz / 'instalacao'
        self.instalacao.mkdir()
        (self.instalacao / 'HuntAnalyzer.exe').write_bytes(b'binario-anterior')
        (self.instalacao / 'historico.json').write_bytes(b'dados-pessoais-preservados')
        arquivos = {'motor.py': 'abc', 'test_motor.py': 'def'}
        self.atual = {'sha256': r.resumo(arquivos), 'arquivos': arquivos}
        self.prova = self.build.parent / 'proveniencia.json'
        self.evidencia = r.emitir_proveniencia(self.build, self.prova, self.atual, self.atual, 'runtime', 'runtime')
        self.qa = self.raiz / 'qa.json'
        self.qa.write_text(json.dumps(qa(self.atual)), encoding='utf8')
        self.saida = self.raiz / 'evidencias'

    def executar(self, validar=None):
        argumentos = ['atualizar_local.py', '--build', str(self.build), '--instalacao', str(self.instalacao),
                      '--saida', str(self.saida), '--qa', str(self.qa)]
        with patch.object(sys, 'argv', argumentos), patch.object(atualizar, 'fontes', return_value=self.atual), \
                patch.object(verificar, 'impressao_runtime', return_value='runtime'), \
                patch.object(atualizar, 'ativos', return_value=''), \
                patch.object(atualizar, 'validar', side_effect=validar):
            atualizar.main()

    def test_atualizacao_vincula_pacote_qa_e_preserva_dados(self):
        self.executar()
        manifesto = json.loads((self.saida / 'manifesto.json').read_text(encoding='utf8'))
        self.assertEqual(manifesto['estado'], 'atualizado')
        self.assertEqual(manifesto['produto_instalado'], self.evidencia['produto'])
        self.assertEqual(manifesto['proveniencia_id'], self.evidencia['id'])
        self.assertEqual(manifesto['qa_sha256'], r.sha(self.qa))
        self.assertFalse(manifesto['conferido_na_tela'])
        self.assertEqual((self.instalacao / 'historico.json').read_bytes(), b'dados-pessoais-preservados')

    def test_executavel_asset_ou_extra_trocados_bloqueiam_antes_de_copiar(self):
        for nome in ['HuntAnalyzer.exe', 'ui/hunt.js', 'extra.dll']:
            with self.subTest(nome=nome):
                alvo = self.build / nome
                original = alvo.read_bytes() if alvo.exists() else None
                alvo.write_bytes(b'nao-validado')
                with self.assertRaisesRegex(RuntimeError, 'Pacote diverge'):
                    self.executar()
                self.assertEqual((self.instalacao / 'HuntAnalyzer.exe').read_bytes(), b'binario-anterior')
                if original is None:
                    alvo.unlink()
                else:
                    alvo.write_bytes(original)

    def test_falha_pos_copia_reverte_produto_sem_apagar_historico(self):
        def validar(exe, saida):
            if exe.parent == self.instalacao:
                raise RuntimeError('falha simulada no instalado')
        with self.assertRaisesRegex(RuntimeError, 'falha simulada'):
            self.executar(validar)
        self.assertEqual((self.instalacao / 'HuntAnalyzer.exe').read_bytes(), b'binario-anterior')
        self.assertFalse((self.instalacao / 'ui/hunt.js').exists())
        self.assertEqual((self.instalacao / 'historico.json').read_bytes(), b'dados-pessoais-preservados')
        self.assertEqual(json.loads((self.saida / 'manifesto.json').read_text())['estado'], 'revertido_por_falha')

    def test_mutacao_da_instalacao_durante_preparo_nao_e_sobrescrita(self):
        def validar(exe, saida):
            (self.instalacao / 'HuntAnalyzer.exe').write_bytes(b'outro-trabalho')
        with self.assertRaisesRegex(RuntimeError, 'instalação mudou'):
            self.executar(validar)
        self.assertEqual((self.instalacao / 'HuntAnalyzer.exe').read_bytes(), b'outro-trabalho')

    def test_qa_antigo_timeout_skip_ou_fontes_alteradas_nao_autorizam(self):
        for mudanca in [{'schema': 1}, {'ok': False}, {'perfil': 'rapido'},
                        {'fontes_finais_sha256': 'mudou'}, {'fontes_sha256': 'teste-diferente'},
                        {'runtime_final_sha256': 'mudou'}, {'suites': []}]:
            with self.subTest(mudanca=mudanca), self.assertRaises(RuntimeError):
                r.validar_qa({**qa(self.atual), **mudanca}, self.atual, 'runtime')
        for estado in ['falhou', 'inconclusivo_timeout', 'ignorado']:
            dados = qa(self.atual)
            dados['suites'].append({'nome': 'extra', 'estado': estado})
            with self.subTest(estado=estado), self.assertRaises(RuntimeError):
                r.validar_qa(dados, self.atual, 'runtime')

    def test_build_com_fontes_alteradas_nao_recebe_proveniencia(self):
        destino = self.raiz / 'outra.json'
        with self.assertRaisesRegex(RuntimeError, 'mudaram durante'):
            r.emitir_proveniencia(self.build, destino, self.atual,
                                 {'sha256': 'mudou', 'arquivos': {}}, 'runtime', 'runtime')
        self.assertFalse(destino.exists())
        self.assertEqual(json.loads(self.prova.read_text())['id'], self.evidencia['id'])

    def test_duas_atualizacoes_em_processos_distintos_sao_exclusivas(self):
        codigo = ('import sys; sys.path.insert(0,sys.argv[1]); '
                  'from rastreabilidade import trava_instalacao; '
                  '\nwith trava_instalacao(sys.argv[2]): print("adquiriu")')
        with r.trava_instalacao(self.instalacao):
            outro = subprocess.run([sys.executable, '-c', codigo, str(TOOLS), str(self.instalacao)],
                                   cwd=Path.cwd(), capture_output=True, timeout=15)
        self.assertNotEqual(outro.returncode, 0)
        self.assertIn(b'RuntimeError', outro.stderr)
        with r.trava_instalacao(self.instalacao):
            pass

    def test_tentativas_preservam_relatorios_anteriores(self):
        primeira = r.reservar_saida(self.saida)
        (primeira / 'resultado.json').write_text('{"ok":false}')
        segunda = r.reservar_saida(self.saida)
        self.assertNotEqual(primeira, segunda)
        self.assertEqual((primeira / 'resultado.json').read_text(), '{"ok":false}')

    def test_inventario_detecta_inclusao_remocao_e_alteracao_de_testes(self):
        repo = self.raiz / 'repo'; repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        (repo / 'motor.py').write_text('motor')
        (repo / 'test_motor.py').write_text('teste')
        antes = r.fontes(repo)
        (repo / 'motor.py').unlink()
        (repo / 'test_motor.py').write_text('teste alterado')
        (repo / 'novo.py').write_text('novo')
        depois = r.fontes(repo)
        self.assertEqual(r.diferencas(antes['arquivos'], depois['arquivos']),
                         ['motor.py', 'novo.py', 'test_motor.py'])

    def test_incidente_nao_passa_se_teste_sumir_ou_navegador_falhar(self):
        catalogo = [{'id': 'incidente', 'criterio': 'comportamento', 'python': ['teste.exato'], 'suites': ['e2e']}]
        teste = [{'id': 'teste.exato', 'estado': 'passou'}]
        suites = [{'nome': 'e2e', 'estado': 'passou'}]
        self.assertEqual(r.conferir_incidentes(catalogo, suites, [], 'completo')[0]['estado'], 'falhou')
        self.assertEqual(r.conferir_incidentes(catalogo, [], teste, 'completo')[0]['estado'], 'falhou')
        self.assertEqual(r.conferir_incidentes(catalogo, [], teste, 'rapido')[0]['estado'], 'parcial')
        self.assertEqual(r.conferir_incidentes(catalogo, suites, teste, 'completo')[0]['estado'], 'passou')
        catalogo[0]['aceite_e2e'] = 'cenario-real'
        self.assertEqual(r.conferir_incidentes(catalogo, suites, teste, 'completo')[0]['estado'], 'falhou')
        self.assertEqual(r.conferir_incidentes(catalogo, suites, teste, 'completo', ['cenario-real'])[0]['estado'], 'passou')

    def test_timeout_http_preserva_rota_fase_bytes_e_processo(self):
        processo = Mock(pid=123)
        processo.poll.return_value = None
        diagnostico = DiagnosticoHTTP(self.raiz / 'http.json', processo)
        resposta = Mock(status=200, headers={'Content-Length': '20'})
        resposta.read1.side_effect = [b'parcial', TimeoutError('leitura travada')]
        resposta.__enter__ = Mock(return_value=resposta)
        resposta.__exit__ = Mock(return_value=False)
        with patch('urllib.request.urlopen', return_value=resposta):
            with self.assertRaises(TimeoutError):
                with diagnostico.abrir('http://127.0.0.1/ui/app/hunt.js', timeout=10) as corpo:
                    corpo.read1(100)
                    corpo.read1(100)
        registro = json.loads((self.raiz / 'http.json').read_text())['requisicoes'][0]
        self.assertEqual(registro['estado'], 'falhou')
        self.assertEqual(registro['fase'], 'leitura')
        self.assertEqual(registro['bytes'], 7)
        self.assertIn('TimeoutError', registro['erro'])

    def test_runner_reprova_mudanca_durante_testes_e_salva_evidencia(self):
        raiz = self.raiz / 'runner'; (raiz / 'tools').mkdir(parents=True)
        analisador = raiz / 'hunt-analyzer'; analisador.mkdir()
        (raiz / 'tools/incidentes.json').write_text('[]')
        depois = copy.deepcopy(self.atual)
        depois['arquivos']['test_motor.py'] = 'alterado-durante-qa'
        depois['sha256'] = r.resumo(depois['arquivos'])
        def comando(cmd, **kwargs):
            if 'env' in kwargs:
                pasta = Path(kwargs['env']['HUNT_QA_SAIDA'])
                (pasta / 'python-testes.json').write_text('[]')
            return subprocess.CompletedProcess(cmd, 0, stdout='v24' if kwargs.get('text') else b'', stderr=b'')
        saida = raiz / 'saida'
        with patch.object(verificar, 'ROOT', raiz), patch.object(verificar, 'ANALISADOR', analisador), \
                patch.object(verificar, 'fontes', side_effect=[self.atual, depois]), \
                patch.object(verificar, 'impressao_runtime', return_value='runtime'), \
                patch.object(verificar.subprocess, 'run', side_effect=comando), \
                patch.object(sys, 'argv', ['verificar.py', '--saida', str(saida)]):
            self.assertEqual(verificar.main(), 1)
        resultado = json.loads((saida / 'resultado.json').read_text())
        self.assertFalse(resultado['ok'])
        self.assertEqual(resultado['arquivos_alterados_durante_qa'], ['test_motor.py'])


if __name__ == '__main__':
    unittest.main()
