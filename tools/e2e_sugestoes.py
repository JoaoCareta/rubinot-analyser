"""Contrato visual dos cards reais, com leituras sintéticas e rede local."""
import pathlib

from playwright.sync_api import expect


def verificar(browser, url, saida, fonte_painel=None):
    page = browser.new_page(viewport={'width': 1140, 'height': 1100})
    page.route('**/*', lambda r: r.continue_() if r.request.url.startswith(url) else r.abort())
    page.set_content(f'<base href="{url}/"><link rel="stylesheet" href="/ui/app/hunt.css">'
                     '<main class="rtc-independentes" style="margin:20px"><div id="cards"></div></main>')
    page.add_script_tag(url=url+'/ui/shared/apresentacao.js')
    fonte = pathlib.Path(fonte_painel or 'ui/features/planejamento/painel.js').read_text(encoding='utf8')
    # Usa as funções de produção sem ligar consultas/worker do restante da página.
    funcoes = fonte[fonte.index('function rtcIconeConfere'):fonte.index('function rtcMostrarRoda')]
    nomes = fonte[fonte.index('const rtcFmt='):fonte.index('function rtcBotao')]
    page.add_script_tag(content=nomes+'\n'+funcoes)
    magias = page.request.get(url+'/ui/magias.json').json()['magias']
    page.evaluate('''magias=>{
      window.catalogoQA=Object.fromEntries(magias.map(m=>[m.id,m]));
      window.curasQA=[['mass_healing',75],['ultimate_healing',70],['restoration',60],
        ['heal_friend',90,'EK'],['nature_s_embrace',50,'EK'],['heal_friend',85,'RP'],['nature_s_embrace',45,'RP']]
        .map(([id,vida_percent,vocacao_destino])=>({...catalogoQA[id],vida_percent,vocacao_destino,origem_percentual:'observado'}));
      window.ataquesQA=['eternal_winter','ice_burst','strong_ice_wave','forked_glacier','avalanche_rune','sudden_death_rune']
        .map((id,i)=>({...catalogoQA[id],id,slot:i<4?i+1:i-3,tipo:i<4?'magia':'runa',runa:i>=4,
          mana_percent:5,creatures:[8,2,2,2,1,null][i],prioridade:i===4?2:1,alvos:i===5?1:8}));
      window.leituraQA={cura:{slots:curasQA.map(m=>({...m,tipo:m.vocacao_destino?'party':'autocura'}))},
        rtc:{slots:ataquesQA.map(m=>({...m,creatures:m.id==='ice_burst'?9:m.creatures}))}};
      window.renderQA=()=>{const b=document.getElementById('cards');b.replaceChildren();
        const cura=HuntUI.el('div','rtc-cura-paineis');
        for(const [nome,linhas] of [['Autocura · Vida',curasQA.filter(m=>!m.vocacao_destino)],['Cura da party · sio e gran sio',curasQA.filter(m=>m.vocacao_destino)]]){
          const s=HuntUI.el('section');s.append(HuntUI.el('h3',null,nome));rtcLinhasConfiguradas(linhas,s,true,leituraQA);cura.append(s);}
        b.append(cura,HuntUI.el('h3',null,'Magias e runas'),HuntUI.el('p','nota','Sugestão para a próxima hunt'));
        rtcLinhasConfiguradas(ataquesQA,b,false,leituraQA);};renderQA();
    }''', magias)
    cards = page.locator('#cards')
    expect(cards.locator('.rtc-slot')).to_have_count(13)
    expect(cards.locator('.rtc-slot-sugerido')).to_have_count(1)
    twin = cards.locator('[data-magia="ice_burst"]')
    expect(twin.locator('.rtc-slot-mudanca')).to_have_text('Criaturas 9+ → 2+')
    expect(twin.locator('.rtc-confere')).to_have_count(3)  # posição, mana, prioridade
    expect(cards.locator('.rtc-cura-paineis .rtc-confere')).to_have_count(7)
    expect(cards).not_to_contain_text('lido no jogo')
    expect(cards).not_to_contain_text('sugestão para testar')
    expect(cards.locator('.rtc-confere').first).to_have_attribute('aria-label', 'Similar à sugestão: Vida')
    page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
    for largura in [1140, 760, 390]:
        page.set_viewport_size({'width': largura, 'height': 1100})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert cards.locator('.rtc-slot').evaluate_all('(xs)=>xs.every(e=>e.scrollWidth<=e.clientWidth)')
        cards.screenshot(path=str(saida/f'sugestoes-{largura}.png'))
    # Uma leitura parcial confirma somente o campo conhecido, sem preencher lacunas.
    page.evaluate('leituraQA.rtc.slots=[{id:"ice_burst",tipo:"magia",mana_percent:5}];renderQA()')
    expect(twin.locator('.rtc-confere')).to_have_count(1)
    expect(twin.locator('.rtc-slot-mudanca')).to_have_count(0)
    # Referência antiga, inativa, duplicada ou ausente nunca ganha selo.
    for alteracao in ['leituraQA.rtc.slots[0].atual=false',
                      'leituraQA.rtc.slots[0].atual=true;leituraQA.rtc.slots[0].ativo=false',
                      'leituraQA.rtc.slots[0].ativo=true;leituraQA.rtc.slots.push({...leituraQA.rtc.slots[0]})',
                      'leituraQA.rtc.slots=[]']:
        page.evaluate(alteracao+';renderQA()')
        expect(twin.locator('.rtc-confere')).to_have_count(0)
    # EK e RP não são intercambiáveis, mesmo com o mesmo nome de magia.
    page.evaluate('leituraQA.cura.slots=leituraQA.cura.slots.filter(s=>s.vocacao_destino!=="RP");renderQA()')
    expect(cards.locator('[data-destino="RP"] .rtc-confere')).to_have_count(0)
    expect(cards.locator('[data-destino="EK"] .rtc-confere')).to_have_count(2)
    page.evaluate('leituraQA.cura.atual=false;renderQA()')
    expect(cards.locator('.rtc-cura-paineis .rtc-confere')).to_have_count(0)
    # O histórico da proposta não deve sobrepor uma nova leitura que já confere.
    page.evaluate('leituraQA.cura.atual=true;curasQA[0].origem_percentual="estudo_cura_observacional";curasQA[0].vida_percent_anterior=95;renderQA()')
    expect(cards.locator('[data-magia="mass_healing"] .rtc-confere')).to_have_count(1)
    expect(cards.locator('[data-magia="mass_healing"] .rtc-slot-mudanca')).to_have_count(0)
    # Última leitura atualiza fora do cálculo da roda e sem confirmar aplicação.
    atualizacao=fonte[fonte.index('function rtcAtualizarTwin'):fonte.index('function renderIntegradoRTC')]
    page.add_script_tag(content='let rtcIntegradoUI={twin:document.getElementById("cards")};'
        'let rtcObservado={};const HuntApp={previa:false};\n'+atualizacao)
    page.evaluate('rtcObservado={rtc:{slots:[{id:"ice_burst",creatures:5}],visto_por_ultimo_em:10},twin:{referencia:5}};rtcAtualizarTwin()')
    expect(cards).to_contain_text('Próxima hunt: 5+')
    expect(cards.locator('.rtc-confere')).to_have_count(1)
    expect(cards).to_contain_text('ativação automática ainda não comprovada')
    page.evaluate('rtcObservado.uso_componentes={rtc:{estado:"rtc_desligado"}};rtcAtualizarTwin()')
    expect(cards.locator('.rtc-confere')).to_have_count(0)
    expect(cards).to_contain_text('RTC desligado')
    page.evaluate('rtcObservado.uso_componentes={};rtcAtualizarTwin()')
    page.evaluate('rtcObservado.rtc.slots[0].creatures=2;rtcAtualizarTwin()')
    expect(cards).to_contain_text('Última leitura: 2+')
    expect(cards.locator('.rtc-confere')).to_have_count(0)
    page.evaluate('rtcObservado.rtc.slots[0].creatures=null;rtcObservado.leitor={fila:{pendentes:3}};rtcAtualizarTwin()')
    expect(cards).to_contain_text('não legível')
    expect(cards).to_contain_text('Leitura do RTC em atraso')
    expect(cards.locator('.rtc-confere')).to_have_count(0)
    page.close()
