"""Regressão visual: lacuna interrompe a curva; zero medido continua visível."""
from playwright.sync_api import expect


def verificar(browser, url, saida):
    page = browser.new_page(viewport={'width': 1500, 'height': 1000})
    erros = []
    page.on('pageerror', lambda e: erros.append(str(e)))
    page.route('**/*', lambda r: r.continue_() if r.request.url.startswith(url) else r.abort())
    sessoes = [{'id': f'qa/202610{dia:02d}_0800', 'hunt': 'QA', 'pt': 'solo',
                'voltas': 1, 'dur_s': 100, 'xp_raw': valor,
                'xp_origens': ['Registro antigo'] if dia == 1 else ['XP Analyser'],
                'taxas': {'raw_h': valor, 'voltas': 1, 'voltas_raw': int(valor is not None),
                          'taxa': {'profit_h': 0, 'sup_pt_h': None, 'sup_eu_h': None, 'bichos_h': 0}}}
               for dia, valor in [(4, 2000000), (3, None), (2, 0), (1, 1000000)]]
    sessoes[-1]['xp_paineis_finais'] = [{'origem': 'XP Analyser', 'horario': '08:30:00',
                                       'raw_xp_gain': 1234567, 'raw_h': 1500000}]
    page.route('**/api/historico', lambda r: r.fulfill(json={'sessoes': sessoes}))
    page.goto(url + '/evolucao')
    expect(page.locator('#g_raw circle.ponto')).to_have_count(3)
    caminho = page.locator('#g_raw path.linha').get_attribute('d')
    assert caminho.count('M') == 2 and caminho.count('L') == 1, caminho
    expect(page.locator('#g_profit circle.ponto')).to_have_count(4)
    expect(page.locator('#g_sup .vazio')).to_contain_text('Sem leitura disponível')
    expect(page.locator('#tiles .tile').nth(3)).to_contain_text('média de 3 sessões')
    expect(page.locator('#tabela tbody tr').nth(2)).to_contain_text('0,00 kk')
    expect(page.locator('#tabela tbody tr').nth(3)).to_contain_text('Registro antigo')
    expect(page.locator('#tabela tbody tr').nth(3)).to_contain_text('1,50 kk/h')
    page.locator('#g_raw .alvo').nth(2).hover()
    expect(page.locator('#g_raw .dica')).to_contain_text('sem leitura')
    page.locator('#g_raw .alvo').nth(0).hover()
    expect(page.locator('#g_raw .dica')).to_contain_text('1,23 kk acumulados')
    page.mouse.move(0, 0)
    page.screenshot(path=str(saida/'evolucao-lacunas.png'), full_page=True)
    assert not erros, erros
    page.close()
