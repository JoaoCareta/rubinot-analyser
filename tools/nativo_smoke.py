"""Confere o binário por HTTP sem tocar fontes, captura ou dados pessoais."""
import json
import hashlib
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import sys
import urllib.error
import urllib.request
from diagnostico_http import DiagnosticoHTTP
from rastreabilidade import reservar_saida, sha

sys.path.insert(0, str(pathlib.Path.cwd()))


def main():
    exe = pathlib.Path(os.environ['HUNT_SMOKE_EXE']).resolve()
    saida = pathlib.Path(os.environ['HUNT_QA_SAIDA']).resolve()
    saida = reservar_saida(saida, marcador='smoke')
    print('Evidências do smoke:', saida, flush=True)
    with tempfile.TemporaryDirectory(prefix='rubinot-nativo-') as tmp:
        raiz = pathlib.Path(tmp)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); porta = s.getsockname()[1]
        env = {**os.environ, 'HUNT_PORTA': str(porta)}
        for nome, sub in [('HUNT_DATA','hunt_data'),('HUNT_FONTES_RAIZ','fontes'),
                          ('HUNT_CONFIGURACOES_RAIZ','configuracoes'),('HUNT_APRENDIZADO_RAIZ','aprendizado'),
                          ('HUNT_CAPTURAS_RAIZ','capture'),('HUNT_KS_RAIZ','KS'),('HUNT_AUXILIARES_CONFIG','auxiliares.json')]:
            env[nome] = str(raiz / sub)
        configuracao = raiz / 'configuracoes' / hashlib.sha256(b'qa').hexdigest()[:24]
        configuracao.mkdir(parents=True)
        from PIL import Image
        captura = raiz/'capture/session_20260101_010000'
        captura.mkdir(parents=True)
        Image.new('RGB',(64,48),'#203040').save(captura/'q_010000_000.png')
        resumo = raiz/'hunt_data/qa/sessoes/20260101_010000'
        resumo.mkdir(parents=True)
        (resumo/'resumo.json').write_text(json.dumps({'pasta':captura.name,
            'sessao':{'data':'01/01/2026','inicio':'01:00:00','char':'QA','pt':'solo'}}),encoding='utf8')
        leitura = {'id':'1', 'char':'QA', 'sessao':'smoke', 'tipo':'rtc', 'instante':time.time()-1,
                   'preset':'qa', 'campos':{}, 'slots':[], 'completo':False,
                   'aplicado_confirmado':False, 'estado':'observado_parcial',
                   'pendencias':['fixture sintética parcial'], 'qa':True}
        for nome in ('1_rtc.json','rtc_atual.json'):
            (configuracao / nome).write_text(json.dumps(leitura), encoding='utf8')
        from rubinot.planejamento.registro import Registro
        Registro(raiz/'aprendizado').guardar('smoke','estudo_sio',[{'id':'qa-sio','instante':1,
            'sessao':'smoke','contexto':{'char':'QA','hazard':5},'membros':[{'nome':'EK QA',
                'balanco':{'comparaveis':1,'deficits':1,'janelas':[{'qa':True}]}}],
            'sugestoes':[],'qa':True}])
        url = f'http://127.0.0.1:{porta}'
        with (saida / 'nativo.log').open('wb') as log:
            proc = subprocess.Popen([str(exe), '--processo', 'app', '--sem-gravacao', '--sem-observacao', '--sem-navegador'],
                                    cwd=exe.parent, env=env, stdout=log, stderr=log,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            diagnostico = DiagnosticoHTTP(saida / 'http.json', proc)
            try:
                limite = time.monotonic() + 45
                while True:
                    try:
                        with diagnostico.abrir(url + '/api/status', timeout=2) as r:
                            assert r.status == 200
                            break
                    except OSError:
                        if proc.poll() is not None or time.monotonic() > limite:
                            raise RuntimeError('Binário não abriu HTTP; confira nativo.log.')
                        time.sleep(0.2)
                rotas = {}
                for rota in ['/', '/hunt', '/evolucao', '/auxiliadores', '/configuracoes',
                             '/ui/app/hunt.css', '/ui/app/hunt.js', '/ui/features/planejamento/painel.js',
                             '/api/status', '/api/hunt', '/api/historico',
                             '/ui/features/historico/gravacao.js',
                             '/ui/features/historico/curas.js',
                             '/api/historico/qa/20260101_010000/curas',
                             '/api/historico/qa/20260101_010000/gravacao',
                             '/api/gravacoes/session_20260101_010000/q_010000_000.png']:
                    print('Conferindo', rota, flush=True)
                    # Como o navegador, ler tudo antes de fechar a conexão HTTP/1.1.
                    # urllib força Connection: close; Handler documenta corte no Windows.
                    with diagnostico.abrir(url + rota, timeout=10, persistente=True) as r:
                        partes = []; inicio_leitura = time.monotonic()
                        while bloco := r.read1(16384):
                            partes.append(bloco)
                            assert time.monotonic() - inicio_leitura < 10, (rota, 'leitura excedeu 10 s')
                        corpo = b''.join(partes)
                        assert corpo and r.status == 200
                        assert len(corpo) == int(r.headers['Content-Length']), (rota, len(corpo), r.headers['Content-Length'])
                        if rota.startswith('/ui/'):
                            assert corpo == (exe.parent / rota.lstrip('/')).read_bytes(), rota
                        if rota.endswith('.css'):
                            assert r.headers['Content-Type'].startswith('text/css')
                        if rota.endswith('/gravacao'):
                            indice = json.loads(corpo)
                            assert indice['retencao'] == 'somente_exclusao_solicitada'
                            assert indice['trechos'][0]['quadros'][0]['t'] == 3600
                        if rota.startswith('/api/gravacoes/'):
                            assert corpo.startswith(b'\x89PNG\r\n\x1a\n')
                        elif rota.startswith('/api/'):
                            json.loads(corpo)
                        rotas[rota] = r.status
                try:
                    with diagnostico.abrir(urllib.request.Request(url + '/api/fonte', data=b'{', headers={'Content-Type':'application/json'}), timeout=5):
                        raise AssertionError('JSON inválido aceito.')
                except urllib.error.HTTPError as e:
                    assert e.code == 400; json.loads(e.read())
                with diagnostico.abrir(url + '/api/status', timeout=5) as r:
                    assert r.status == 200
                def uso(revisao, resposta):
                    corpo = json.dumps({'acao':'declarar_uso','char':'QA','sessao':'smoke',
                                        'revisoes':{'rtc':revisao},'resposta':resposta}).encode()
                    return urllib.request.Request(url + '/api/configuracoes', data=corpo,
                                                  headers={'Content-Type':'application/json'})
                with diagnostico.abrir(uso('1','uso_confirmado'), timeout=5) as r:
                    declaracao = json.loads(r.read())['resultado']
                    assert declaracao['resposta'] == 'uso_confirmado'
                with diagnostico.abrir(uso('1','uso_confirmado'), timeout=5) as r:
                    assert json.loads(r.read())['resultado']['id'] == declaracao['id']
                with diagnostico.abrir(url + '/api/configuracoes?char=QA&sessao=smoke', timeout=5) as r:
                    estado = json.loads(r.read())
                    assert estado['elegibilidade_aprendizado']['cadencia_ataque']
                    assert not estado['elegibilidade_aprendizado']['cura']
                    assert not estado['rtc']['aplicado_confirmado']
                    assert estado['estudo_sio']['id']=='qa-sio'
                    assert estado['estudo_sio']['membros'][0]['balanco']['janelas']==[]
                try:
                    with diagnostico.abrir(uso('obsoleta','uso_confirmado'), timeout=5):
                        raise AssertionError('Revisão obsoleta aceita pelo compilado.')
                except urllib.error.HTTPError as e:
                    assert e.code == 400
                with diagnostico.abrir(uso('1','rtc_desligado'), timeout=5) as r:
                    assert json.loads(r.read())['resultado']['resposta'] == 'rtc_desligado'
                if os.environ.get('HUNT_SMOKE_ENCERRAR') == '1':
                    with diagnostico.abrir(urllib.request.Request(url + '/api/desligar', data=b'{}', headers={'Content-Type':'application/json'}), timeout=5) as r:
                        assert json.loads(r.read())['ok']
                    proc.wait(timeout=30)
                resultado = {'ok': True, 'exe': str(exe), 'exe_sha256': sha(exe), 'rotas': rotas, 'json_invalido':400,
                             'uso_detectado':True, 'revisao_obsoleta':400, 'fixture_isolada':True,
                             'encerramento_api': os.environ.get('HUNT_SMOKE_ENCERRAR') == '1'}
                (saida / 'nativo.json').write_text(json.dumps(resultado, indent=2), encoding='utf8')
                print(f'Nativo: {len(rotas)} rotas, gravação preservada e recuperação HTTP aprovados.')
            except Exception as erro:
                (saida / 'nativo.json').write_text(json.dumps({'ok': False, 'exe': str(exe),
                    'exe_sha256': sha(exe), 'erro': type(erro).__name__ + ': ' + str(erro),
                    'codigo_processo': proc.poll(), 'diagnostico': 'http.json'}, indent=2), encoding='utf8')
                raise
            finally:
                if proc.poll() is None:
                    proc.terminate(); proc.wait(timeout=10)
                diagnostico.salvar()


if __name__ == '__main__':
    main()
