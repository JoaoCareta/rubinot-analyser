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
for nome, sub in [('HUNT_DATA','hunt_data'),('HUNT_FONTES_RAIZ','fontes'),('HUNT_CONFIGURACOES_RAIZ','configuracoes'),('HUNT_APRENDIZADO_RAIZ','aprendizado'),('HUNT_KS_RAIZ','KS'),('HUNT_CAPTURAS_RAIZ','capture'),('HUNT_AUXILIARES_CONFIG','auxiliares.json')]:
    os.environ[nome] = str(pathlib.Path(isolamento.name) / sub)
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
    aceites_incidentes = []
    (saida / 'e2e-incidentes.json').write_text('[]', encoding='utf8')
    def aceitar_incidente(nome):
        aceites_incidentes.append(nome)
        (saida / 'e2e-incidentes.json').write_text(json.dumps(aceites_incidentes), encoding='utf8')
    with tempfile.TemporaryDirectory(prefix='rubinot-e2e-') as tmp:
        raiz = pathlib.Path(tmp)
        ident = 'qa/' + chave_sessao(completo['pasta'], 'QA')
        pasta = raiz / 'qa' / 'sessoes' / ident.split('/')[1]
        resumo = {**completo, 'fechada': True, 'salvo_em': '2026-01-01T02:00:00',
                  'totais': {'voltas': 8, 'dur_s': 1440, 'xp_raw': 2400000, 'profit': 400000, 'sup_pt': 8000, 'sup_eu': 800, 'bichos': 480}}
        resumo = copy.deepcopy(resumo)
        resumo['voltas'][-1]['especies']['plunder patriarch'] = 7
        import base64
        publicar(pasta, resumo, {'mapa_z13.png': base64.b64decode(completo['andares']['13']['fundo'].split(',')[1])})
        captura = ao_vivo.CAPTURAS / completo['pasta']
        captura.mkdir(parents=True, exist_ok=True)
        for nome in ('q_010000_000.png', 'q_010000_500.png', 'f_010020_000.png'):
            (captura/nome).write_bytes(base64.b64decode(completo['andares']['13']['fundo'].split(',')[1]))
        (captura/'ks.json').write_text(json.dumps({'party':['QA','Tank QA','Archer QA','Mage QA'],'episodios':[]}),encoding='utf8')
        from rubinot.planejamento.registro import Registro
        registro_curas = Registro(os.environ['HUNT_APRENDIZADO_RAIZ'])
        registro_curas.guardar(completo['pasta'],'evento',[
            {'id':'look-ek','t':3600,'kind':'player_info','target':'Tank QA','vocation':'elite knight'},
            {'id':'look-rp','t':3600,'kind':'player_info','target':'Archer QA','vocation':'royal paladin'},
            {'id':'sio-ek','t':3602,'kind':'cast','magia_id':'heal_friend','ator':'QA','alvo':'Tank QA','qualidade':'identificada'},
            {'id':'gran-rp','t':3602,'kind':'cast','magia_id':'nature_s_embrace','ator':'QA','alvo':'Archer QA','qualidade':'identificada'}])
        registro_curas.guardar(completo['pasta'],'recurso',[
            {'id':'vida-1','t':3601,'aliados':{'Tank QA':{'percentual':41.38,'origem':'barra_nameplate_integral'},'Archer QA':{'percentual':58.62,'origem':'barra_nameplate_integral'}}},
            {'id':'vida-2','t':3604,'aliados':{'Tank QA':{'percentual':100,'origem':'barra_nameplate_integral'}}}])
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
                    from e2e_sugestoes import verificar as verificar_sugestoes
                    verificar_sugestoes(browser, url, saida)
                    from e2e_evolucao import verificar as verificar_evolucao
                    verificar_evolucao(browser, url, saida)
                    aceitar_incidente('xp-historico-lacunas')
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    page.on('pageerror', lambda e: erros.append(str(e)))
                    page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url) or route.request.url.startswith('data:') else route.abort())
                    page.goto(url + '/hunt')
                    icone = page.locator('link[rel="icon"]')
                    assert icone.get_attribute('href') == '/ui/hunt_analyzer_icone.png?v=1'
                    resposta_icone = page.request.get(url + icone.get_attribute('href'))
                    prova_aninhada = ao_vivo.ks.RAIZ / 'session_qa/logs/recuperacao/opressor/prova.png'
                    prova_aninhada.parent.mkdir(parents=True,exist_ok=True)
                    prova_aninhada.write_bytes(base64.b64decode(completo['andares']['13']['fundo'].split(',')[1]))
                    resposta_prova = page.request.get(url + '/api/ks/session_qa/logs/recuperacao/opressor/prova.png')
                    assert resposta_prova.status == 200
                    assert resposta_prova.headers['content-type'].startswith('image/png')
                    assert resposta_icone.status == 200
                    assert resposta_icone.body().startswith(b'\x89PNG\r\n\x1a\n')
                    expect(page.locator('#conteudo')).to_have_class(re.compile(r'\bborrado\b'), timeout=10000)
                    dados.update(copy.deepcopy(completo))
                    expect(page.locator('#historico .volta')).to_have_count(8, timeout=15000)
                    # A composição dominante localiza a área; uma aparição rara também deve aparecer.
                    dados['area_atual'] = {'inicio': 0, 'andar': 13, 'especies': ['undertaker']}
                    dados['voltas'][-1]['especies'] = {'undertaker': 3, 'plunder patriarch': 1}
                    page.route('**/api/monstro?nome=plunder*', lambda route: route.fulfill(
                        json={'nome': 'Plunder Patriarch', 'categoria': 'QA', 'hp': None, 'xp': None}))
                    expect(page.locator('#listaMonstros')).to_contain_text('Plunder Patriarch', timeout=15000)
                    page.locator('#listaMonstros').screenshot(path=str(saida/'especie-rara.png'))
                    page.unroute('**/api/monstro?nome=plunder*')
                    dados.pop('area_atual')
                    dados['voltas'] = copy.deepcopy(completo['voltas'])
                    assert '16,00 kk/h' in page.locator('#tiles').inner_text()
                    page.locator('#historico .volta').first.click()
                    assert 'volta' in page.locator('#painel').inner_text().lower()
                    # O estado é consultável por contrato, sem ler globais internas.
                    assert page.evaluate('HuntApp.voltas().length') == 8
                    expect(page.locator('.painel-tabs')).to_be_hidden()
                    expect(page.locator('#abaKS')).to_be_disabled()
                    dados['ks'] = {'episodios': [], 'party': ['QA'], 'estatisticas_party': {
                        'fonte_dano':'Hunt Analyser', 'jogadores':[{'nome':'QA','dano':5823000,
                        'cura':750669,'dano_observado':50000,'golpes':10,'criticos':0,'criticos_pct':0,'fatais':None,'fatais_pct':None}], 'loot':28700000,'supplies':4500000,'profit':24200000}}
                    expect(page.locator('#partyDano')).to_be_visible(timeout=15000)
                    expect(page.locator('#partyDano')).to_contain_text('Dano solo')
                    expect(page.locator('#partyDano th')).to_have_count(6)
                    assert page.locator('#partyDano .party-totais, #partyDano details, #partyDano .party-fonte').count() == 0
                    assert not any(x in page.locator('#partyDano').inner_text() for x in ['Loot','Supplies','Profit','Sobre os números','Party Hunt','Hunt Analyser'])
                    for nome in ['critico','fatal']:
                        from PIL import Image
                        with Image.open('ui/party_'+nome+'.png') as animacao:
                            assert animacao.n_frames > 1
                    assert 'brightness(3)' in page.locator('#partyDano img').nth(1).evaluate('(e)=>getComputedStyle(e).filter')
                    assert page.locator('#partyDano th .party-campo > span:last-child').all_text_contents() == ['Jogador','Dano','Participação','Críticos','Fatais','Maior golpe']
                    expect(page.locator('#partyDano td').nth(3)).to_have_text('00%')
                    expect(page.locator('#partyDano td').nth(4)).to_have_text('——')
                    assert page.locator('#partyDano img').evaluate_all('(xs)=>xs.every(i=>i.complete&&i.naturalWidth>0)')
                    assert page.locator('#partyDano').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
                    page.locator('#partyDano').screenshot(path=str(saida/'party-dano.png'))
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.locator('#partyDano').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
                    page.locator('#partyDano').screenshot(path=str(saida/'party-dano-estreito.png'))
                    page.set_viewport_size({'width':1440,'height':1000})
                    expect(page.locator('#partyDano')).to_contain_text('5,8 kk')
                    dados['ks']['estatisticas_party']['fonte_dano'] = 'Party Hunt'
                    expect(page.locator('#partyDano')).to_contain_text('Dano da party',timeout=15000)
                    dados['ks'] = {'episodios': [{'id': 1, 'inicio': '01:05:00', 'ultimo_t': 3900, 'aberto': True,
                        'dano':{'party':{},'fora':{'Intruso QA':{'dano':10,'golpes':1,'criticos':0}}},
                        'ganhos':{'inicio_t':3900,'fim_t':3900,'xp_raw':40,'loot':70}}]}
                    expect(page.locator('.painel-tabs')).to_be_visible(timeout=15000)
                    expect(page.locator('#ksPainel')).to_be_visible()
                    page.get_by_text('Dados para a guilda · preencher e copiar',exact=True).click()
                    expect(page.get_by_label('Chars da PT que deu KS',exact=True)).to_have_value(completo['sessao']['char'])
                    expect(page.get_by_label('Chars da PT que deu KS',exact=True)).to_have_attribute('readonly','')
                    expect(page.get_by_label('Chars oprimidos (hunted)',exact=True)).to_have_value('Intruso QA')
                    expect(page.get_by_label('Raw XP Gain',exact=True)).to_have_value('40')
                    expect(page.get_by_label('Gold total',exact=True)).to_have_value('70')
                    expect(page.locator('#abaHunt')).to_contain_text('⚔️')
                    expect(page.locator('#abaKS .icone-ks')).to_have_count(1)
                    assert 'data:image/svg+xml' in page.locator('#abaKS .icone-ks').evaluate('(e)=>getComputedStyle(e).maskImage')
                    assert page.locator('#abaHunt').evaluate("e => getComputedStyle(e).borderRadius") == '7px'
                    page.locator('#abaHunt').click()
                    expect(page.locator('#painel')).to_be_visible()
                    page.locator('#abaKS').click()
                    dados['ks'] = {'episodios': []}
                    expect(page.locator('.painel-tabs')).to_be_hidden(timeout=15000)
                    expect(page.locator('#painel')).to_be_visible()
                    page.reload()
                    expect(page.locator('.painel-tabs')).to_be_hidden()
                    expect(page.locator('#painel')).to_be_visible()
                    page.goto(url + '/hunt?h=' + ident)
                    expect(page.locator('#historico .volta')).to_have_count(8, timeout=10000)
                    page.locator('#gravacaoHistorica summary').click()
                    expect(page.locator('#gravacaoHorario')).to_contain_text('01:00:00,000')
                    page.wait_for_function('document.getElementById("gravacaoImagem").naturalWidth > 0')
                    page.locator('#gravacaoProximo').click()
                    expect(page.locator('#gravacaoHorario')).to_contain_text('01:00:00,500')
                    page.locator('#gravacaoProximo').click()
                    expect(page.locator('#gravacaoHorario')).to_contain_text('lacuna de 19,5 s')
                    page.locator('#gravacaoPlay').click()
                    expect(page.locator('#gravacaoHorario')).to_contain_text('3/3', timeout=10000)
                    expect(page.locator('#gravacaoPlay')).to_have_text('Reproduzir')
                    page.locator('#gravacaoHistorica').screenshot(path=str(saida/'gravacao-historica.png'))
                    assert page.request.get(url + f'/api/gravacoes/{completo["pasta"]}/calibracao.json').status == 404
                    aceitar_incidente('replay-com-lacunas')
                    page.locator('#gravacaoHistorica summary').click()
                    assert page.evaluate('HuntApp.dados.estado.historico')
                    curas_hist = page.locator('#historicoCuras')
                    expect(curas_hist.locator('#historicoCurasResumo tbody tr')).to_have_count(2)
                    expect(curas_hist.locator('#historicoCurasResumo')).not_to_contain_text('Mage QA')
                    assert curas_hist.evaluate('(e)=>e.previousElementSibling.id') == 'partyDano'
                    assert curas_hist.locator('#historicoCurasResumo img').evaluate_all('(xs)=>xs.length===2 && xs.every(x=>x.complete && x.naturalWidth>0)')
                    expect(curas_hist.locator('#historicoCurasResumo tbody tr').filter(has_text='Tank QA')).to_contain_text('1')
                    curas_hist.screenshot(path=str(saida/'curas-party.png'))
                    page.locator('#historicoCuras summary').click()
                    expect(curas_hist).to_contain_text('41,38% – 100%')
                    expect(curas_hist.locator('.curas-faixas tbody tr')).to_have_count(6)
                    expect(curas_hist.locator('.curas-faixas tbody tr').nth(1)).to_have_text('30% a < 50%3 s10')
                    expect(curas_hist).to_contain_text('Sem leitura suficiente')
                    expect(curas_hist.get_by_role('button')).to_have_count(0)
                    expect(curas_hist.get_by_role('combobox').locator('option')).to_have_count(2)
                    curas_hist.screenshot(path=str(saida/'sio-ek-historico.png'))
                    curas_hist.get_by_role('combobox').select_option('1')
                    expect(curas_hist).to_contain_text('58,62% – 58,62%')
                    expect(curas_hist.locator('.curas-faixas tbody tr').nth(2)).to_have_text('50% a < 70%—01')
                    page.set_viewport_size({'width':390,'height':844})
                    curas_hist.screenshot(path=str(saida/'sio-rp-estreito.png'))
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.set_viewport_size({'width':1440,'height':1000})
                    expect(page.locator('#btnHunt')).to_be_hidden()
                    page.goto(url + '/hunt?h')
                    expect(page.locator('#lista .cartao')).to_have_count(1, timeout=10000)
                    expect(page.locator('#lista .plunder-indicador')).to_have_text('✦ Plunder avistado')
                    expect(page.locator('#lista .plunder-indicador')).to_have_attribute('aria-label','Plunder Patriarch observado nesta hunt')
                    def lista_motor_anterior(route):
                        resposta = route.fetch()
                        conteudo = resposta.json()
                        for sessao in conteudo['sessoes']:
                            sessao.pop('tem_plunder', None)
                        route.fulfill(response=resposta, json=conteudo)
                    page.route('**/api/historico', lista_motor_anterior)
                    page.reload()
                    expect(page.locator('#lista .plunder-indicador')).to_have_text('✦ Plunder avistado')
                    page.unroute('**/api/historico', lista_motor_anterior)
                    page.evaluate("HuntHistorico.renderizar([{id:'qa/20260101_010001',hunt:'Hunt QA',pt:'pt x4',voltas:1,fechada:true,tem_ks:true,tem_plunder:true},{id:'qa/20260102_010001',hunt:'Hunt QA',pt:'solo',voltas:1,fechada:true,tem_plunder:false}])")
                    expect(page.locator('#lista .plunder-indicador')).to_have_count(1)
                    ks_box = page.locator('#lista .ks-indicador').bounding_box()
                    plunder_box = page.locator('#lista .plunder-indicador').bounding_box()
                    assert plunder_box['y'] >= ks_box['y'] + ks_box['height']
                    page.locator('#lista').screenshot(path=str(saida/'historico-plunder.png'))
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.locator('#lista .plunder-indicador').evaluate('(e)=>e.getBoundingClientRect().right<=e.closest(".quadro").getBoundingClientRect().right')
                    page.locator('#lista').screenshot(path=str(saida/'historico-plunder-estreito.png'))
                    page.set_viewport_size({'width':1440,'height':1000})
                    expect(page.locator('#lista .ks-indicador')).to_have_count(1)
                    expect(page.locator('#lista .ks-indicador')).to_have_attribute('aria-label','Houve KS nesta hunt')
                    expect(page.locator('#lista .cartao').first).to_contain_text('pt x4')
                    page.evaluate("HuntHistorico.renderizar([{id:'qa/20260101_010001',hunt:'Hunt QA',pt:'pt x4',voltas:1,fechada:true,tem_ks:false}])")
                    expect(page.locator('#lista .ks-indicador')).to_have_count(0)
                    expect(page.locator('#lista .plunder-indicador')).to_have_count(0)
                    aceitar_incidente('plunder-historico')
                    page.evaluate("HuntHistorico.renderizar([{id:'qa/20260101_010001',hunt:'Hunt QA',char:'Nome privado',pt:'solo',voltas:1,fechada:true}])")
                    expect(page.locator('#lista .pe')).to_contain_text('solo')
                    expect(page.locator('#lista .pe')).not_to_contain_text('Nome privado')
                    page.goto(url + '/evolucao')
                    expect(page.locator('body')).to_contain_text('Hunt QA', timeout=10000)
                    def com_estudo(route):
                        resposta=route.fetch();conteudo=resposta.json()
                        conteudo['estudo_previsto']=[{'volta':2,'metrica':'raw_h','previsto':11000000,
                            'observado':13000000,'erro':2000000,'modo':'replay_cronologico','contexto':{'hazard':4}}]
                        route.fulfill(response=resposta,json=conteudo)
                    page.route('**/api/configuracoes?*',com_estudo)
                    page.goto(url + '/hunt')
                    expect(page.locator('#historico .volta')).to_have_count(8, timeout=15000)
                    page.wait_for_selector('#elementosHunt .rtc-barra-fill', timeout=15000)
                    classes = page.locator('#recomendacaoMagias > .rtc-classes')
                    expect(classes.locator('img').nth(0)).to_have_attribute('src', '/ui/magia_hell_s_core.png')
                    expect(classes.locator('img').nth(1)).to_have_attribute('src', '/ui/magia_eternal_winter.png')
                    assert classes.evaluate('e => Math.abs(e.getBoundingClientRect().width - e.parentElement.getBoundingClientRect().width) < 2')
                    assert classes.locator('img').evaluate_all('(xs) => xs.every(x => x.complete && x.naturalWidth > 0)')
                    classes.screenshot(path=str(saida / 'ms-ed.png'))
                    fills = page.locator('#elementosHunt .rtc-barra-fill').evaluate_all('(xs)=>xs.map(x=>({h:x.getBoundingClientRect().height,cor:getComputedStyle(x).backgroundColor,w:x.style.width}))')
                    assert fills and all(x['h'] > 0 for x in fills), fills
                    fills_comparacao = page.locator('#recomendacaoMagias .rtc-barra-fill').evaluate_all('(xs)=>xs.map(x=>({h:x.getBoundingClientRect().height,cor:getComputedStyle(x).backgroundColor,w:x.style.width}))')
                    assert fills_comparacao and all(x['h'] > 0 for x in fills_comparacao), fills_comparacao
                    assert [(x['cor'], x['w']) for x in fills] == [(x['cor'], x['w']) for x in fills_comparacao]
                    aceitar_incidente('barras-visiveis')
                    page.screenshot(path=str(saida / 'hunt.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    expect(page.get_by_text('Estudo · previsto e observado',exact=True)).to_have_count(0)
                    expect(page.locator('.estudo-previsto')).to_have_count(0)
                    expect(page.get_by_text('Supplies por item',exact=True)).to_have_count(0)
                    expect(page.get_by_text('Dano recebido · Input Analyser',exact=True)).to_have_count(0)
                    page.wait_for_function('document.documentElement.scrollWidth <= innerWidth + 1',timeout=5000)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(e=>({tag:e.tagName,id:e.id,classe:e.className,largura:e.getBoundingClientRect().width,texto:e.textContent.slice(0,80)}))")
                    page.unroute('**/api/configuracoes?*',com_estudo)
                    page.screenshot(path=str(saida / 'hunt-estreita.png'), full_page=True)
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.locator('#btnHunt').click()
                    expect(page.locator('#btnHunt')).to_have_text('Iniciar hunt', timeout=10000)
                    assert not dados['estado']['ativo']
                    resposta = page.request.post(url + '/api/fonte', data='{', headers={'content-type': 'application/json'})
                    assert resposta.status == 400
                    assert page.request.get(url + '/api/status').status == 200
                    page.route('**/api/status', lambda route: route.fulfill(json={'char': 'Personagem QA', 'jogo': True}))
                    page.route('**/api/configuracoes?*', lambda route: route.fulfill(json={
                        'char': 'Personagem QA', 'calibracoes': {'rtc': {'instante': 1791800000}}}))
                    page.add_init_script("""window.intervalosQA=[];const intervaloOriginal=window.setInterval;
                      window.setInterval=(f,ms,...args)=>{if(ms===5000)window.intervalosQA.push(f);return intervaloOriginal(f,ms,...args)};""")
                    page.goto(url + '/')
                    if page.locator('#guiaSair').is_visible():
                        page.locator('#guiaSair').click()
                    expect(page.locator('#referenciasResumo .referencia-resumo')).to_have_count(3)
                    expect(page.locator('#referenciasResumo')).to_contain_text('Referência guardada:')
                    expect(page.locator('#referenciasResumo')).to_contain_text('Nenhuma leitura coletada.')
                    fonte = page.locator('#fonteCaptura').bounding_box()
                    configuracoes = page.locator('#configuracoesCaptura').bounding_box()
                    assert fonte['x'] < configuracoes['x'] and abs(fonte['y'] - configuracoes['y']) < 2
                    # Resposta lenta não pode esvaziar referências nem deslocar a fonte.
                    page.locator('#fonteTipo').select_option('twitch')
                    page.locator('#fonteCanal').fill('canal-em-edicao')
                    page.locator('#fonteChar').fill('Personagem em edição')
                    page.locator('#fonteCanal').focus()
                    page.evaluate("""()=>{
                      window.refQA=document.querySelector('#referenciasResumo a');
                      window.alturaQA=document.querySelector('#fonteCaptura').getBoundingClientRect().height;
                      window.fetchQA=window.fetch;window.pedidosQA=0;
                      window.fetch=(u,...args)=>String(u).startsWith('/api/configuracoes?')?
                        new Promise((resolve,reject)=>{window.pedidosQA++;window.resolverQA=resolve;window.rejeitarQA=reject}):fetchQA(u,...args);
                      void intervalosQA[0]();
                    }""")
                    page.wait_for_function('window.pedidosQA===1')
                    page.evaluate('void intervalosQA[0]()')
                    assert page.evaluate('window.pedidosQA') == 1
                    expect(page.locator('#referenciasResumo .referencia-resumo')).to_have_count(3)
                    assert page.evaluate("document.querySelector('#referenciasResumo a')===refQA && document.querySelector('#fonteCaptura').getBoundingClientRect().height===alturaQA")
                    expect(page.locator('#fonteCanal')).to_be_focused()
                    page.screenshot(path=str(saida/'calibracao-twitch-consulta.png'),full_page=True)
                    page.evaluate("resolverQA(new Response(JSON.stringify({char:'Personagem QA',rtc:{visto_por_ultimo_em:1791800300}})))")
                    expect(page.locator('#referenciasResumo')).to_contain_text('Última leitura:')
                    assert page.evaluate("document.querySelector('#referenciasResumo a')===refQA")
                    expect(page.locator('#fonteCanal')).to_have_value('canal-em-edicao')
                    expect(page.locator('#fonteChar')).to_have_value('Personagem em edição')
                    page.evaluate('void intervalosQA[0]()')
                    page.wait_for_function('window.pedidosQA===2')
                    page.evaluate("rejeitarQA(Error('falha de rede simulada'))")
                    expect(page.locator('#configuracoesCaptura')).to_contain_text('Não foi possível atualizar')
                    expect(page.locator('#referenciasResumo .referencia-resumo')).to_have_count(3)
                    assert page.evaluate("document.querySelector('#referenciasResumo a')===refQA")
                    page.evaluate('window.fetch=fetchQA; void intervalosQA[0]()')
                    expect(page.locator('#configuracoesCaptura > [role=status]')).to_be_hidden()
                    page.locator('#fonteTipo').select_option('janela')
                    page.screenshot(path=str(saida / 'calibracao.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.get_by_role('link', name='Conferir RTC', exact=True).click()
                    expect(page.locator('#tipo')).to_have_value('rtc')
                    expect(page.locator('#registros')).to_contain_text('Referência guardada em')
                    page.screenshot(path=str(saida / 'configuracoes.png'), full_page=True)
                    page.goto(url + '/configuracoes')
                    expect(page.locator('#tipo')).to_have_value('auto')
                    pedidos_config = []
                    def guardar_config(route):
                        pedidos_config.append(route.request.post_data_json)
                        route.fulfill(json={'ok': True})
                    page.route('**/api/capturar', lambda route: route.fulfill(json={'ok':True,'char':'Personagem QA'}))
                    page.route('**/api/print.png?*', lambda route: route.fulfill(content_type='image/png', body=pathlib.Path('tests/fixtures/leitores/01-rtc-configurado.png').read_bytes()))
                    page.route('**/api/configuracoes/calibrar', guardar_config)
                    page.locator('#capturar').click()
                    expect(page.locator('#salvar')).to_be_enabled()
                    page.locator('#salvar').click()
                    expect(page.locator('#mensagem')).to_contain_text('Janela reconhecida e guardada')
                    assert pedidos_config == [{'tipo':'auto','regiao':None}], pedidos_config
                    import configuracoes as cfg
                    from PIL import Image
                    sessao_qa = dados['estado']['sessao']
                    with Image.open('tests/fixtures/leitores/01-rtc-configurado.png') as im:
                        leitura = cfg.observar('rtc', im.convert('RGB'), 'Personagem QA', sessao_qa,
                                              textos=[{'texto':'Preset: qa','y':2}])['snapshot']
                    page.route('**/api/configuracoes?*', lambda route: route.fulfill(json=cfg.consultar('Personagem QA', sessao_qa)))
                    page.reload()
                    expect(page.get_by_role('button', name='Estou usando o que foi detectado', exact=True)).to_be_visible()
                    expect(page.locator('#declaracaoUso')).to_contain_text('Cura ainda não lida')
                    page.get_by_role('button', name='Estou usando o que foi detectado', exact=True).click()
                    expect(page.locator('#declaracaoUso')).to_contain_text('Uso confirmado do RTC detectado')
                    assert cfg.consultar('Personagem QA', sessao_qa)['elegibilidade_aprendizado']['cadencia_ataque']
                    assert not cfg.consultar('Personagem QA', sessao_qa)['elegibilidade_aprendizado']['cura']
                    page.get_by_role('button', name='Não estou usando: RTC desligado', exact=True).click()
                    expect(page.locator('#declaracaoUso')).to_contain_text('RTC desligado informado')
                    assert not cfg.consultar('Personagem QA', sessao_qa)['elegibilidade_aprendizado']['cadencia_ataque']
                    obsoleta = page.request.post(url + '/api/configuracoes', data={
                        'acao':'declarar_uso','char':'Personagem QA','sessao':sessao_qa,
                        'revisoes':{'rtc':'obsoleta'},'resposta':'uso_confirmado'})
                    assert obsoleta.status == 400
                    assert cfg.consultar('Personagem QA', sessao_qa)['rtc']['id'] == leitura['id']
                    page.screenshot(path=str(saida / 'declaracao-rtc.png'), full_page=True)
                    page.locator('#voltarCalibracao').click()
                    expect(page.locator('#fonteCaptura')).to_be_visible()
                    # Matriz antecipada: selecionar roda não inicia trabalho novo.
                    planejamento = browser.new_page(viewport={'width':1600,'height':1000})
                    planejamento.on('pageerror', lambda erro: erros.append(str(erro)))
                    # Este cenário mede o reuso da mesma hunt. Entregar pontos
                    # antes dos dados da hunt cria outra matriz, de contexto vazio.
                    def configuracao_planejamento(route):
                        planejamento.wait_for_function('HuntApp.dados?.amostras?.length > 0 && HuntApp.voltas().length === 8 && Object.values(HuntApp.catalogo || {}).some(m => m.toma) && Object.values(HuntApp.catalogo || {}).every(m => !m.buscando)')
                        route.fulfill(json={'char':'QA','pontos':{'valor':989},'modelo':{}})
                    planejamento.route('**/api/configuracoes*',configuracao_planejamento)
                    planejamento.add_init_script("""window.preparacoes=0; window.pedidosRoda=[];
                      window.redesenhosRodaQA=0;window.calculosRTCQA=0;
                      window.rodaComparacaoQA=(p,similar=false)=>{
                        const cat=p.catalogo,campo=valor=>({valor,qualidade:'texto_integral'});
                        const ctx={...p.contexto,char:'QA',pt:'pt x4',hunt:'QA',observado:{
                          roda:{campos:{'conviction.Aug. Strong Ice Wave':campo('II'),'conviction.Aug. Heal Friend':campo('II'),
                            'revelation.Twin Bursts':campo('Stage 2'),'revelation.Blessing of the Grove':campo('Stage 1'),
                            'vessels.Strong Ice Wave':campo('+12%'),'vessels.Damage and Healing':campo('+4'),'revelation.Damage and Healing':campo('+13')}},
                          rtc:{slots:[{id:'strong_ice_wave',prioridade:1,creatures:2,mana_percent:5}]}}};
                        const pontos={QTR0:50,QTR3:75,QTR2:100,QTR4:100,QTR7:150,QTR8:11,QBL0:50,QBL1:75,QBL2:100,QBL3:25,QBL4:100,QBL5:150};
                        const roda={estado:'Calculado',pontos,gemas:[],investidos:986,livres:3,efeitos:HuntRodaMotor.efeitos(cat,pontos)};
                        if(similar)ctx.observado.roda.campos={
                          'conviction.Aug. Forked Spells':campo('I'),'conviction.Aug. Strong Ice Wave':campo('I'),
                          'conviction.Aug. Heal Friend':campo('II'),'revelation.Twin Bursts':campo('Stage 2'),
                          'revelation.Blessing of the Grove':campo('Stage 1')};
                        roda.comparacao_atual=HuntIntegracao.compararRoda(cat,p.magias,ctx,roda);
                        return {roda,contexto:ctx};
                      };
                      window.Worker=class{terminate(){}postMessage(p){
                        if(p.modo==='rodas_preparadas'){window.preparacoes++;window.pedidosRoda.push(p);
                          window.chaveRoda=JSON.stringify([HuntRodasPreparadas.versao,p.contexto,p.magias,p.catalogo.versao]);
                          setTimeout(()=>{for(const o of p.opcoes_roda){
                            const anterior=document.querySelector('.rtc-roda-painel svg'),controle=document.querySelector('.rtc-gemas button');
                            this.onmessage?.({data:{id:o.id,resultado:window.rodaComparacaoQA(p,o.tier===3)}});
                            if(anterior&&o.id!=='dano|utamo|0'&&(anterior!==document.querySelector('.rtc-roda-painel svg')||controle!==document.querySelector('.rtc-gemas button')))window.redesenhosRodaQA++;
                          }
                            this.onmessage?.({data:{fim:true}});},10);
                        }else {window.calculosRTCQA++;setTimeout(()=>this.onmessage?.({data:{resultado:{rtc:{linhas:[]},cura:{linhas:[],postura:'vida'}}}}),10);}
                      }};""")
                    planejamento.goto(url+'/hunt?dano')
                    gemas=planejamento.locator('.rtc-gemas button')
                    expect(gemas).to_have_count(4,timeout=15000)
                    expect(gemas.nth(3)).to_be_enabled(timeout=15000)
                    assert gemas.all_text_contents()==['—Sem gemas','Lesser','Regular','Greater']
                    tamanhos=gemas.evaluate_all('(xs)=>xs.map(x=>({w:x.getBoundingClientRect().width,h:x.getBoundingClientRect().height}))')
                    assert max(x['w'] for x in tamanhos)-min(x['w'] for x in tamanhos)<1,tamanhos
                    assert all(x['h']==44 for x in tamanhos),tamanhos
                    assert planejamento.locator('.rtc-gemas img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>0)')
                    # A gravação no IndexedDB é assíncrona. Aguarda o lote completo
                    # antes de selecionar ou recarregar, sem confundir uma nova
                    # configuração carregada com trabalho disparado pela seleção.
                    cache_pronto = """async()=>{const b=await new Promise(r=>{const q=indexedDB.open('hunt-rodas-preparadas',1);q.onsuccess=()=>r(q.result)});
                      const valor=await new Promise(r=>{const q=b.transaction('rodas').objectStore('rodas').get(window.chaveRoda);q.onsuccess=()=>r(q.result)});
                      b.close();return !!valor&&Object.keys(valor).length===12}"""
                    planejamento.wait_for_function(cache_pronto)
                    assert planejamento.evaluate('window.redesenhosRodaQA') == 0
                    # Trocar categoria preserva os painéis independentes.
                    planejamento.evaluate("""()=>{
                      window.rodaQA=document.querySelector('.rtc-roda-painel');
                      window.svgQA=document.querySelector('.rtc-roda-painel svg');
                      window.rtcQA=document.querySelector('.rtc-config-painel');
                      window.calculosAntesQA=window.calculosRTCQA;
                    }""")
                    planejamento.get_by_role('button',name='Single',exact=True).click()
                    assert planejamento.evaluate("document.querySelector('.rtc-roda-painel')===rodaQA && document.querySelector('.rtc-roda-painel svg')===svgQA && document.querySelector('.rtc-config-painel')===rtcQA && window.calculosRTCQA===calculosAntesQA")
                    # Horário novo da mesma leitura não invalida o conteúdo.
                    planejamento.route('**/api/configuracoes*', lambda route: route.fulfill(json={
                        'char':'QA','pontos':{'valor':989},'modelo':{},'roda':{'visto_por_ultimo_em':1791800400}}))
                    planejamento.evaluate("window.magiasQA=document.querySelector('#recomendacaoMagias > .rtc-classes')")
                    planejamento.wait_for_timeout(5500)
                    assert planejamento.evaluate("document.querySelector('.rtc-roda-painel')===rodaQA && document.querySelector('.rtc-roda-painel svg')===svgQA && document.querySelector('#recomendacaoMagias > .rtc-classes')===magiasQA && window.calculosRTCQA===calculosAntesQA")
                    planejamento.unroute('**/api/configuracoes*')
                    planejamento.route('**/api/configuracoes*',configuracao_planejamento)
                    preparacoes_antes=planejamento.evaluate('window.preparacoes')
                    gemas.nth(3).click()
                    planejamento.get_by_role('button',name='Cura',exact=True).click()
                    planejamento.get_by_role('button',name='Vida',exact=True).click()
                    assert planejamento.evaluate('window.preparacoes')==preparacoes_antes, planejamento.evaluate('window.pedidosRoda')
                    botoes=planejamento.locator('header.topo button.botao:visible').evaluate_all('(xs)=>xs.map(x=>({w:x.getBoundingClientRect().width,h:x.getBoundingClientRect().height}))')
                    assert all(x['w']==148 and x['h']==44 for x in botoes),botoes
                    planejamento.screenshot(path=str(saida/'planejamento-paineis.png'),full_page=True)
                    planejamento.locator('.rtc-roda-painel>summary').click()
                    assert planejamento.locator('#painelMagiasElementos').evaluate('(e)=>e.open')
                    assert planejamento.locator('.rtc-config-painel').evaluate('(e)=>e.open')
                    planejamento.wait_for_function(cache_pronto)
                    chave_preparada=planejamento.evaluate("window.chaveRoda")
                    planejamento.reload()
                    expect(planejamento.locator('.rtc-roda-painel>summary')).to_be_visible(timeout=15000)
                    assert not planejamento.locator('.rtc-roda-painel').evaluate('(e)=>e.open')
                    planejamento.locator('.rtc-roda-painel>summary').click()
                    expect(planejamento.locator('.rtc-gemas button').nth(3)).to_be_enabled(timeout=15000)
                    chave_reaberta=planejamento.evaluate('window.chaveRoda')
                    (saida/'cache-comparacao.json').write_text(json.dumps({'antes':chave_preparada,'depois':chave_reaberta},ensure_ascii=False),encoding='utf8')
                    assert planejamento.evaluate('window.preparacoes')==0, {
                        'preparacoes':planejamento.evaluate('window.preparacoes'),
                        'contexto_igual':chave_preparada==chave_reaberta,
                        'antes':chave_preparada,'depois':chave_reaberta}
                    # Comparação real do módulo, com referência parcial sintética:
                    # não apresentar lacuna como zero nem oferecer adoção.
                    cmp = planejamento.get_by_role('region', name='Comparação com sua roda atual')
                    planejamento.locator('.rtc-gemas button').nth(0).click()
                    expect(cmp).to_contain_text('Perde área ampliada')
                    expect(cmp).to_contain_text('18% → 6%')
                    expect(cmp).not_to_contain_text('Ganho real de dano e cura: ainda não comprovado')
                    expect(cmp).not_to_contain_text('Cobertura: perder')
                    expect(cmp).not_to_contain_text('Distribuição atual parcialmente lida')
                    expect(cmp).not_to_contain_text('Gelo mais favorável')
                    expect(cmp).not_to_contain_text('RTC otimizado + roda candidata')
                    expect(cmp).not_to_contain_text('Similar à sugestão')
                    planejamento.locator('.rtc-gemas button').nth(3).click()
                    expect(cmp.locator('.rtc-confere')).to_have_text('✓')
                    expect(cmp.locator('.rtc-confere')).to_have_attribute('aria-label', re.compile('Similar à sugestão:'))
                    planejamento.screenshot(path=str(saida/'roda-comparacao.png'),full_page=True)
                    planejamento.set_viewport_size({'width':390,'height':844})
                    assert planejamento.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    planejamento.screenshot(path=str(saida/'planejamento-estreito.png'),full_page=True)
                    # Mudança real continua recalculando: mantém o desenho
                    # anterior identificado, sem utilizá-lo como resultado novo.
                    planejamento.evaluate("""()=>{
                      window.svgAnteriorQA=document.querySelector('.rtc-roda-painel svg');
                      window.painelAnteriorQA=document.querySelector('.rtc-roda-painel');
                      document.querySelector('.rtc-config-painel').open=false;
                      window.pendentesQA=[];const Original=window.Worker;
                      window.Worker=class extends Original{postMessage(p){window.pendentesQA.push(()=>super.postMessage(p))}};
                    }""")
                    planejamento.route('**/api/configuracoes*',lambda route:route.fulfill(json={
                        'char':'QA','pontos':{'valor':990},'modelo':{}}))
                    planejamento.wait_for_function('window.pendentesQA.length>=2',timeout=15000)
                    assert planejamento.evaluate("document.querySelector('.rtc-roda-painel')===painelAnteriorQA && document.querySelector('.rtc-roda-painel svg')===svgAnteriorQA && !document.querySelector('.rtc-config-painel').open")
                    expect(planejamento.locator('.rtc-roda-painel')).to_contain_text('resultado anterior')
                    assert planejamento.locator('.rtc-roda-painel [aria-busy=true]').evaluate('(e)=>e.inert')
                    planejamento.locator('.rtc-roda-painel').screenshot(path=str(saida/'roda-atualizando.png'))
                    planejamento.evaluate('for(const f of pendentesQA.splice(0))f()')
                    expect(planejamento.locator('.rtc-gemas button').nth(3)).to_be_enabled(timeout=15000)
                    planejamento.wait_for_function("document.querySelector('.rtc-roda-painel svg')!==svgAnteriorQA")
                    assert planejamento.evaluate('window.pedidosRoda.at(-1).contexto.total') == 990
                    assert not planejamento.locator('.rtc-config-painel').evaluate('(e)=>e.open')
                    planejamento.close()
                    # Regressão: histórico sem modelo + feedback guardado só no modelo atual.
                    # Exercita o carregador real da página e o worker, não apenas o motor puro.
                    feedback = {'id':'feedback-cura-qa','origem':'usuario','tipo':'disputa_turno_cura',
                        'vigente':True,'sessao':completo['estado']['sessao'],
                        'contexto':{'char':'QA','hunt':completo['sessao']['hunt'],'pt':'pt x4'},
                        'provas':['prova-inicial-qa','prova-final-qa'],
                        'ajustes':[{'id':'mass_healing','alvo':'eu','anterior':95,'vida_percent':75},
                                   {'id':'ultimate_healing','alvo':'eu','anterior':80,'vida_percent':70}]}
                    from urllib.parse import urlparse, parse_qs
                    feedback_roda = {'id':'rejeicao-roda-qa','origem':'usuario','tipo':'desempenho_insatisfatorio',
                        'vigente':True,'rejeitada':True,'sessao':completo['estado']['sessao'],
                        'contexto':feedback['contexto'],'provas':['roda-reprovada-qa'],
                        'roda_rejeitada':{'preset':'roda-reprovada','beneficios':{'ranks':{'29':2,'31':1,'33':2},'revelation':{'10':1,'11':2}}}}
                    estudo_cura_qa = {}
                    def observacao_feedback(route):
                        hist = parse_qs(urlparse(route.request.url).query).get('historico') == ['true']
                        route.fulfill(json={'char':'QA','pontos':{'valor':998},'hazard_observado':{'nivel':5},'estudo_cura':estudo_cura_qa if hist else None,
                            'roda':{'preset':'minha-roda','campos':{'conviction.Aug. Strong Ice Wave':{'valor':'II','qualidade':'texto_integral'},
                                'conviction.Aug. Heal Friend':{'valor':'II','qualidade':'texto_integral'}}},
                            'modelo':{} if hist else {'feedback_cura':[feedback],'feedback_roda':[feedback_roda]}})
                    retorno = browser.new_page(viewport={'width':1200,'height':1000})
                    retorno.add_init_script("""window.pedidosFeedbackQA=[];const WorkerFeedbackQA=window.Worker;
                        window.Worker=class extends WorkerFeedbackQA{postMessage(p){window.pedidosFeedbackQA.push(p);super.postMessage(p)}};""")
                    retorno.on('pageerror', lambda e: erros.append(str(e)))
                    retorno.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url) or route.request.url.startswith('data:') else route.abort())
                    retorno.route('**/api/configuracoes?*', observacao_feedback)
                    retorno.goto(url+'/hunt?dano=&h='+ident)
                    eu = retorno.locator('.rtc-cura-paineis > section').first
                    try:
                        expect(eu).to_contain_text('Vida 75%', timeout=20000)
                    finally:
                        (saida/'feedback-historico-contexto.json').write_text(json.dumps(retorno.evaluate('window.pedidosFeedbackQA'),ensure_ascii=False),encoding='utf8')
                    expect(eu).to_contain_text('Vida 70%')
                    expect(eu).to_contain_text('Vida 60%')
                    expect(eu).not_to_contain_text('Vida 95%')
                    expect(eu).not_to_contain_text('Vida 80%')
                    eu.screenshot(path=str(saida/'cura-feedback-historico.png'))
                    aceitar_incidente('cura-feedback-historico')
                    roda_mantida = retorno.locator('.rtc-roda-painel')
                    expect(roda_mantida).to_contain_text('Proposta de dano após seu feedback', timeout=30000)
                    expect(roda_mantida).not_to_contain_text('minha-roda')
                    expect(roda_mantida).not_to_contain_text('roda-reprovada')
                    for objetivo in ['Dano','Cura']:
                        roda_mantida.get_by_role('button',name=objetivo,exact=True).click()
                        for tier in ['Sem gemas','Lesser','Regular','Greater']:
                            # O botão sem gemas inclui o símbolo visual “—” no nome acessível.
                            botao=roda_mantida.locator('.rtc-gemas button').filter(has_text=tier)
                            expect(botao).to_be_enabled(timeout=30000)
                            botao.click()
                            expect(botao).to_have_attribute('aria-pressed','true')
                            try:
                                expect(roda_mantida.locator('svg')).to_have_count(1)
                            except AssertionError:
                                (saida/'roda-falha.txt').write_text(objetivo+' / '+tier+'\n'+roda_mantida.inner_text(),encoding='utf8')
                                raise
                            expect(roda_mantida.get_by_role('button',name='Copiar código dos pontos')).to_be_visible()
                            expect(roda_mantida).to_contain_text('3 reservados / 998 totais')
                            if objetivo=='Cura':
                                expect(roda_mantida).not_to_contain_text('Proposta de dano após seu feedback')
                    roda_mantida.screenshot(path=str(saida/'roda-cura-apos-rejeicao-dano.png'))
                    aceitar_incidente('rejeicao-por-objetivo')
                    expect(eu).to_contain_text('Sua correção de emergência')
                    estudo_cura_qa.update(sessao=completo['estado']['sessao'],contexto={'char':'QA'},
                        estado='sugestao_para_testar',referencia=[{'id':'mass_healing','vida_percent':75}],
                        observado={'recursos':120,'episodios':60,'vida_amostras':{'eu':120},'vida_minima':{'eu':71}},
                        avaliacao={'hazard':5,'treino':30,'selecao':15,'teste':15,'antes':{'condicoes_concorrentes':10},'candidata':{'condicoes_concorrentes':3}},
                        sugestoes=[{'id':'mass_healing','anterior':75,'vida_percent':70,'provas':['qa-a','qa-b'],
                            'motivo':'Condições concorrentes diminuíram no teste separado.'}],
                        limite='Candidata observacional para testar; ganho real ainda não medido.',lacunas=[])
                    retorno.reload()
                    avaliacao_cura=retorno.get_by_role('region',name='Avaliação da cura desta hunt')
                    expect(retorno.locator('.rtc-cura-paineis .rtc-slot-mudanca')).to_contain_text('75% → 70%')
                    expect(retorno.locator('.rtc-cura-paineis .rtc-slot-proxima')).to_have_text('Próxima hunt')
                    expect(avaliacao_cura).to_have_count(0)
                    expect(retorno.locator('#otimizacaoRTC')).not_to_contain_text('Condições concorrentes')
                    expect(retorno.locator('#otimizacaoRTC')).not_to_contain_text('Treino:')
                    expect(retorno.locator('#otimizacaoRTC')).not_to_contain_text('quatro cenários')
                    retorno.locator('.rtc-cura-paineis').screenshot(path=str(saida/'cura-sem-estudo.png'))
                    retorno.close()
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
