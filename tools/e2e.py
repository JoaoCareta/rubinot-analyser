"""Navegador contra HTTP real e fonte controlada, sem captura ou rede externa."""
import re
import copy
import json
import os
import pathlib
import sys
import tempfile
import threading
from unittest.mock import patch

isolamento = tempfile.TemporaryDirectory(prefix='rubinot-e2e-config-')
for nome, sub in [('HUNT_DATA','hunt_data'),('HUNT_FONTES_RAIZ','fontes'),('HUNT_CONFIGURACOES_RAIZ','configuracoes'),('HUNT_APRENDIZADO_RAIZ','aprendizado'),('HUNT_KS_RAIZ','KS'),('HUNT_AUXILIARES_CONFIG','auxiliares.json')]:
    os.environ.setdefault(nome, str(pathlib.Path(isolamento.name) / sub))
sys.path.insert(0, str(pathlib.Path.cwd()))
import app
import ao_vivo
from rubinot.adapters.historico import publicar, chave_sessao
from playwright.sync_api import sync_playwright, expect


def main():
    dados = json.loads(pathlib.Path('tests/fixtures/hunt.json').read_text(encoding='utf8'))
    completo = copy.deepcopy(dados)
    dados['voltas'] = []
    dados['amostras'] = []
    erros = []
    saida = pathlib.Path(os.environ.get('HUNT_QA_SAIDA', '../output/e2e'))
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rubinot-e2e-') as tmp:
        raiz = pathlib.Path(tmp)
        ident = 'qa/' + chave_sessao(completo['pasta'], 'QA')
        pasta = raiz / 'qa' / 'sessoes' / ident.split('/')[1]
        resumo = {**completo, 'fechada': True, 'salvo_em': '2026-01-01T02:00:00',
                  'totais': {'voltas': 8, 'dur_s': 1440, 'xp_raw': 2400000, 'profit': 400000, 'sup_pt': 8000, 'sup_eu': 800, 'bichos': 480}}
        import base64
        publicar(pasta, resumo, {'mapa_z13.png': base64.b64decode(completo['andares']['13']['fundo'].split(',')[1])})
        class Handler(app.Handler):
            def log_message(self, *_):
                pass
        def estado():
            return copy.deepcopy(dados)
        def parar():
            dados['estado']['ativo'] = dados['estado']['gravando'] = False
        with patch.object(ao_vivo, 'HUNT_DATA', raiz), patch.object(ao_vivo, 'json_hunt', side_effect=estado), \
             patch.object(ao_vivo, 'ativo', side_effect=lambda: dados['estado']['ativo']), \
             patch.object(ao_vivo, 'desligar', side_effect=parar), \
             patch.object(app, 'status', return_value={'calibrado': True, 'jogo': True, 'gravando': True}):
            class Servidor(app.Servidor):
                def handle_error(self, request, client_address):
                    if isinstance(sys.exception(), (ConnectionResetError, BrokenPipeError)):
                        return
                    super().handle_error(request, client_address)
            srv = Servidor(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
            host_patch = patch.object(app, 'PORTA', srv.server_port); host_patch.start()
            try:
                url = f'http://127.0.0.1:{srv.server_port}'
                with sync_playwright() as pw:
                    canal = os.environ.get('HUNT_E2E_BROWSER')
                    if not canal and sys.platform == 'win32' and not pathlib.Path(pw.chromium.executable_path).is_file():
                        canal = 'msedge'
                    browser = pw.chromium.launch(headless=True, **({'channel': canal} if canal else {}))
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    page.on('pageerror', lambda e: erros.append(str(e)))
                    page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url) or route.request.url.startswith('data:') else route.abort())
                    page.goto(url + '/hunt')
                    expect(page.locator('#conteudo')).to_have_class(re.compile(r'\bborrado\b'), timeout=10000)
                    dados.update(copy.deepcopy(completo))
                    expect(page.locator('#historico .volta')).to_have_count(8, timeout=15000)
                    assert '16,00 kk/h' in page.locator('#tiles').inner_text()
                    page.locator('#historico .volta').first.click()
                    assert 'volta' in page.locator('#painel').inner_text().lower()
                    # O estado é consultável por contrato, sem ler globais internas.
                    assert page.evaluate('HuntApp.voltas().length') == 8
                    page.goto(url + '/hunt?h=' + ident)
                    expect(page.locator('#historico .volta')).to_have_count(8, timeout=10000)
                    assert page.evaluate('HuntApp.dados.estado.historico')
                    expect(page.locator('#btnHunt')).to_be_hidden()
                    page.goto(url + '/hunt?h')
                    expect(page.locator('#lista .cartao')).to_have_count(1, timeout=10000)
                    page.goto(url + '/evolucao')
                    expect(page.locator('body')).to_contain_text('Hunt QA', timeout=10000)
                    page.goto(url + '/hunt')
                    expect(page.locator('#historico .volta')).to_have_count(8, timeout=15000)
                    page.wait_for_selector('#elementosHunt .rtc-barra-fill', timeout=15000)
                    fills = page.locator('#elementosHunt .rtc-barra-fill').evaluate_all('(xs)=>xs.map(x=>({h:x.getBoundingClientRect().height,cor:getComputedStyle(x).backgroundColor,w:x.style.width}))')
                    assert fills and all(x['h'] > 0 for x in fills), fills
                    page.screenshot(path=str(saida / 'hunt.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'rolagem horizontal'
                    page.screenshot(path=str(saida / 'hunt-estreita.png'), full_page=True)
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.locator('#btnHunt').click()
                    expect(page.locator('#btnHunt')).to_have_text('Iniciar hunt', timeout=10000)
                    assert not dados['estado']['ativo']
                    resposta = page.request.post(url + '/api/fonte', data='{', headers={'content-type': 'application/json'})
                    assert resposta.status == 400
                    assert page.request.get(url + '/api/status').status == 200
                    assert not erros, erros
                    browser.close()
            finally:
                srv.shutdown(); srv.server_close(); thread.join(timeout=5); host_patch.stop()
    print('E2E: espera, volta, mediana, seleção, histórico, evolução, elementos, tela estreita, encerramento e erro HTTP aprovados.')


if __name__ == '__main__':
    try:
        main()
    finally:
        isolamento.cleanup()
