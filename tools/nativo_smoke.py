"""Confere o binário por HTTP sem tocar fontes, captura ou dados pessoais."""
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def main():
    exe = pathlib.Path(os.environ['HUNT_SMOKE_EXE']).resolve()
    saida = pathlib.Path(os.environ['HUNT_QA_SAIDA']).resolve()
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rubinot-nativo-') as tmp:
        raiz = pathlib.Path(tmp)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); porta = s.getsockname()[1]
        env = {**os.environ, 'HUNT_PORTA': str(porta)}
        for nome, sub in [('HUNT_DATA','hunt_data'),('HUNT_FONTES_RAIZ','fontes'),
                          ('HUNT_CONFIGURACOES_RAIZ','configuracoes'),('HUNT_APRENDIZADO_RAIZ','aprendizado'),
                          ('HUNT_CAPTURAS_RAIZ','capture'),('HUNT_KS_RAIZ','KS'),('HUNT_AUXILIARES_CONFIG','auxiliares.json')]:
            env[nome] = str(raiz / sub)
        url = f'http://127.0.0.1:{porta}'
        with (saida / 'nativo.log').open('wb') as log:
            proc = subprocess.Popen([str(exe), '--processo', 'app', '--sem-gravacao', '--sem-observacao', '--sem-navegador'],
                                    cwd=exe.parent, env=env, stdout=log, stderr=log,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                limite = time.monotonic() + 45
                while True:
                    try:
                        with urllib.request.urlopen(url + '/api/status', timeout=2) as r:
                            assert r.status == 200
                            break
                    except OSError:
                        if proc.poll() is not None or time.monotonic() > limite:
                            raise RuntimeError('Binário não abriu HTTP; confira nativo.log.')
                        time.sleep(0.2)
                rotas = {}
                for rota in ['/', '/hunt', '/evolucao', '/auxiliadores', '/configuracoes',
                             '/ui/app/hunt.css', '/ui/app/hunt.js', '/ui/features/planejamento/painel.js',
                             '/api/status', '/api/hunt', '/api/historico']:
                    with urllib.request.urlopen(url + rota, timeout=10) as r:
                        corpo = r.read(); assert corpo and r.status == 200
                        if rota.endswith('.css'):
                            assert r.headers['Content-Type'].startswith('text/css')
                        if rota.startswith('/api/'):
                            json.loads(corpo)
                        rotas[rota] = r.status
                try:
                    urllib.request.urlopen(urllib.request.Request(url + '/api/fonte', data=b'{', headers={'Content-Type':'application/json'}), timeout=5)
                    raise AssertionError('JSON inválido aceito.')
                except urllib.error.HTTPError as e:
                    assert e.code == 400; json.loads(e.read())
                with urllib.request.urlopen(url + '/api/status', timeout=5) as r:
                    assert r.status == 200
                if os.environ.get('HUNT_SMOKE_ENCERRAR') == '1':
                    with urllib.request.urlopen(urllib.request.Request(url + '/api/desligar', data=b'{}', headers={'Content-Type':'application/json'}), timeout=5) as r:
                        assert json.loads(r.read())['ok']
                    proc.wait(timeout=30)
                resultado = {'ok': True, 'exe': str(exe), 'rotas': rotas, 'json_invalido':400,
                             'encerramento_api': os.environ.get('HUNT_SMOKE_ENCERRAR') == '1'}
                (saida / 'nativo.json').write_text(json.dumps(resultado, indent=2), encoding='utf8')
                print('Nativo: 11 rotas, assets novos e recuperação HTTP aprovados.')
            finally:
                if proc.poll() is None:
                    proc.terminate(); proc.wait(timeout=10)


if __name__ == '__main__':
    main()
