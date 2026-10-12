// A navegação é a mesma em todas as telas. Os links e seus IDs continuam sendo os da página.
(() => {
  const topo = document.querySelector('header.topo');
  const nav = topo?.querySelector('nav');
  if (!nav) return;
  const parametros = new URLSearchParams(location.search);
  const dano = document.createElement('a');
  const consulta = new URLSearchParams(); consulta.set('dano', '');
  if (parametros.get('h')) consulta.set('h', parametros.get('h'));
  if (parametros.has('previa')) consulta.set('previa', '');
  dano.href = '/hunt?' + consulta.toString(); dano.id = 'navDano';
  nav.insertBefore(dano, nav.lastElementChild);
  if (parametros.has('dano')) {
    nav.querySelectorAll('a').forEach(a => a.classList.remove('ativo'));
    dano.classList.add('ativo');
  }
  const style = document.createElement('style');
  style.textContent = `
    :root { --menu-largura: 224px; }
    body { padding-left: var(--menu-largura); }
    .menu-lateral { position: fixed; inset: 0 auto 0 0; width: var(--menu-largura); z-index: 8;
      display: flex; flex-direction: column; padding: 30px 16px 20px; overflow-y: auto;
      background: radial-gradient(ellipse at 0 0, #d6a84e0b, transparent 55%), #101218;
      border-right: 1px solid var(--borda); }
    .menu-marca { display: flex; align-items: center; gap: 12px; padding: 0 10px 30px; }
    .menu-emblema { width: 38px; height: 44px; color: var(--ouro); flex: none; }
    .menu-marca strong { display: block; font: 600 15px/1.35 var(--serif); color: var(--ouro-claro); letter-spacing: .06em; }
    .menu-marca small { display: block; font: 9px var(--mono); letter-spacing: .24em; color: var(--apagado); margin-top: 6px; }
    .menu-rotulo { margin: 0 14px 12px; font: 10px var(--mono); letter-spacing: .18em; color: var(--apagado); }
    .menu-lateral nav { display: flex; flex-direction: column; gap: 6px; }
    .menu-lateral nav a { display: flex; align-items: center; gap: 12px; padding: 13px 14px;
      border: 1px solid transparent; border-radius: 9px; color: var(--suave); font: 500 13px var(--sans);
      text-decoration: none; transition: color .16s, background .16s, border-color .16s; }
    .menu-lateral nav a svg { width: 19px; height: 19px; flex: none; opacity: .8; }
    .menu-lateral nav a:hover { background: #ffffff05; border-color: var(--borda); color: var(--texto); }
    .menu-lateral nav a.ativo { color: var(--ouro-claro); background: linear-gradient(100deg, #d6a84e1c, #d6a84e06);
      border-color: #d6a84e36; box-shadow: inset 3px 0 var(--ouro); }
    .menu-lateral nav a.ativo::after { content: ''; width: 5px; height: 5px; border-radius: 50%; background: var(--ouro);
      margin-left: auto; box-shadow: 0 0 10px #d6a84e55; }
    .menu-lateral nav a:focus-visible { outline: 2px solid var(--roxo); outline-offset: 2px; }
    .menu-rodape { margin-top: auto; padding: 26px 14px 4px; color: var(--apagado); }
    .menu-rodape::before { content: ''; display: block; height: 1px; margin-bottom: 18px;
      background: linear-gradient(90deg, #d6a84e50, transparent); }
    .menu-rodape span { font: 10px var(--mono); letter-spacing: .2em; }
    .menu-rodape p { font: 12px var(--sans); color: var(--suave); margin: 8px 0 0; }
    header.topo { position: relative; min-height: 96px; padding: 22px 32px; gap: 18px;
      background: radial-gradient(ellipse at 0 0, #d6a84e0c, transparent 60%), var(--barra);
      border-bottom: 1px solid var(--borda); }
    header.topo::after { content: ''; position: absolute; bottom: -1px; left: 32px; width: 112px;
      height: 1px; background: linear-gradient(90deg, var(--ouro), transparent); }
    .topo-contexto { min-width: 0; margin-right: auto; }
    .topo-contexto small { font: 9px var(--mono); letter-spacing: .2em; color: var(--ouro); text-transform: uppercase; }
    .topo-contexto strong { display: block; margin-top: 6px; font: 600 22px/1.2 var(--serif); color: var(--texto); }
    header.topo .jogo { border: 1px solid var(--borda); border-radius: 999px; padding: 9px 13px;
      background: #ffffff02; font-size: 11px; max-width: 40%; overflow-wrap: anywhere; }
    header.topo #btnDesligar { padding: 9px 15px; font-size: 11px; }
    header.topo #btnDesligar:hover { color: var(--vermelho); border-color: #ef6b6b70; }
    body > main { width: 100%; }
    .cabeca { padding: 8px 0 12px; }
    @media (max-width: 1050px) {
      :root { --menu-largura: 188px; }
      .menu-lateral { padding-left: 10px; padding-right: 10px; }
      header.topo { padding: 18px 24px; }
      header.topo .jogo { font-size: 10px; }
    }
    @media (max-width: 700px) {
      :root { --menu-largura: 64px; }
      .menu-lateral { padding: 20px 8px; }
      .menu-marca { padding: 0 5px 24px; }
      .menu-emblema { width: 36px; }
      .menu-marca div, .menu-rotulo, .menu-rodape, .menu-lateral .menu-texto { display: none; }
      .menu-lateral nav a { justify-content: center; padding: 13px 0; }
      .menu-lateral nav a.ativo::after { display: none; }
      header.topo { padding: 18px 14px; min-height: 90px; gap: 10px; flex-wrap: wrap; }
      .topo-contexto { flex: 1 1 100%; }
      .topo-contexto strong { font-size: 20px; }
      header.topo .jogo { margin-left: 0; max-width: none; flex: 1; }
      body > main { padding-left: 16px; padding-right: 16px; }
      .cabeca { flex-wrap: wrap; }
      .salvar { flex-wrap: wrap; gap: 10px; }
      .passo { flex-wrap: wrap; padding: 16px; }
      .botoes { flex-wrap: wrap; }
    }
  `;
  document.head.append(style);
  const svg = paths => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  const icones = [
    '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="var(--barra)"/><circle cx="15" cy="17" r="3" fill="var(--barra)"/>',
    '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>',
    '<path d="M4 5v5h5M4 10a8 8 0 1 1 1 8"/><path d="M12 8v5l3 2"/>',
    '<path d="M4 20h16M6 16v-5m6 5V5m6 11V8"/><path d="m5 7 6-4 7 2"/>',
    '<path d="m14 3-9 11h6l-1 7 9-11h-6z"/>',
    '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  ];
  const nomes = ['Calibração', 'Hunt', 'Histórico', 'Evolução', 'Magias e elementos', 'Auxiliadores'];
  const menu = document.createElement('aside');
  menu.className = 'menu-lateral';
  menu.innerHTML = `<div class="menu-marca"><svg class="menu-emblema" viewBox="0 0 40 48" fill="none" aria-hidden="true">
    <path d="M20 2 37 12v24L20 46 3 36V12Z" stroke="currentColor" opacity=".5"/>
    <path d="m20 9 12 15-12 15L8 24Z" stroke="currentColor"/><path d="M20 16v16M12 24h16" stroke="currentColor"/>
    <circle cx="20" cy="24" r="3" fill="currentColor"/></svg><div><strong>Hunt<br>Analyzer</strong><small>CADA VOLTA CONTA</small></div></div>
    <div class="menu-rotulo">SEU ESPAÇO</div>
    <div class="menu-rodape"><span>RUBINOT</span><p>Da primeira à melhor volta.</p></div>`;
  nav.setAttribute('aria-label', 'Menu principal');
  [...nav.querySelectorAll('a')].forEach((a, i) => {
    a.innerHTML = svg(icones[i]) + `<span class="menu-texto">${nomes[i]}</span>`;
    a.setAttribute('aria-label', nomes[i]);
    a.title = nomes[i];
  });
  menu.insertBefore(nav, menu.querySelector('.menu-rodape'));
  document.body.prepend(menu);
  topo.querySelector('.marca')?.remove();
  const contexto = document.createElement('div');
  contexto.className = 'topo-contexto';
  contexto.innerHTML = '<small>Hunt Analyzer / seu espaço de hunt</small><strong></strong>';
  topo.prepend(contexto);
  const atualiza = () => {
    const ativo = nav.querySelector('a.ativo');
    contexto.querySelector('strong').textContent = ativo?.getAttribute('aria-label') || 'Hunt Analyzer';
    nav.querySelectorAll('a').forEach(a => {
      if (a === ativo) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
  };
  atualiza();
  new MutationObserver(atualiza).observe(nav, {subtree: true, attributes: true, attributeFilter: ['class']});
})();
