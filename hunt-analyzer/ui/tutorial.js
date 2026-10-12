// Tutorial da calibração, apresentado uma vez por versão neste navegador.
(() => {
  const chave = 'hunt-tutorial-stream-v1';
  const passos = [
    ['#fonteCaptura', '1 · Escolha a origem', 'Use a janela do RubinOT ou informe o canal da Twitch e o personagem. Clique em Usar esta fonte. Encerre uma hunt em andamento antes de trocar.'],
    ['#passoCaptura', '2 · Prepare a imagem', 'Na live, preserve a proporção e os pixels do jogo no OBS. Mantenha visíveis: tela do jogo, Server Log (5–6 linhas), Map View, Battle List, Hunt, XP, Supply, Party Hunt e Input Analyser. Spells e Loot são opcionais. Pode calibrar em local seguro, com números zerados.'],
    ['#btnCapturar', '3 · Capture e confira', 'Capturar testa a conexão e traz um quadro da live. Na fonte local, clique na janela do jogo. Confira as regiões encontradas e marque as que faltarem. Faixas pretas fora dos painéis não atrapalham.'],
    ['.area', '4 · Confira cada painel', 'Clique nos cards para entender cada recorte. Não inclua bordas ou barras de rolagem. Um painel vermelho precisa ser corrigido; valores zerados e Battle List vazia são válidos.'],
    ['#btnSalvar', '5 · Salve e acompanhe', 'Salvar calibração inicia a observação da hunt. A fonte Twitch tem o atraso da transmissão. Se a resolução mudar, encerre a hunt e calibre novamente. Este guia fica disponível em Como configurar.']
  ];
  const css = document.createElement('style');
  css.textContent = '.guia-foco{position:relative;z-index:1001!important;box-shadow:0 0 0 4px #d6a84e!important}.guia-sombra{position:fixed;inset:0;background:#000b;z-index:1000}.guia-balao{position:fixed;z-index:1002;bottom:20px;right:24px;max-width:480px;width:calc(100% - 48px);padding:24px;background:#161a23;border:1px solid #d6a84e;border-radius:12px;color:#eee;box-shadow:0 12px 50px #000}.guia-balao h2{color:#f3d98f;margin:0 0 12px}.guia-balao p{line-height:1.6}.guia-balao footer{display:flex;gap:12px;justify-content:flex-end}';
  document.head.append(css);
  let i = 0, foco, sombra, balao, anterior;
  function fechar() { foco?.classList.remove('guia-foco'); sombra?.remove(); balao?.remove(); document.removeEventListener('keydown', teclado); anterior?.focus(); }
  function teclado(e) {
    if (e.key === 'Escape') fechar();
    if (e.key === 'Tab') {
      const bs = [...balao.querySelectorAll('button:not(:disabled)')];
      const n = bs.indexOf(document.activeElement);
      e.preventDefault(); bs[(n + (e.shiftKey ? -1 : 1) + bs.length) % bs.length].focus();
    }
  }
  function mostrar() {
    foco?.classList.remove('guia-foco');
    const [alvo, titulo, texto] = passos[i];
    foco = document.querySelector(alvo); foco?.classList.add('guia-foco'); foco?.scrollIntoView({block:'center'});
    balao.innerHTML = `<h2 id="guiaTitulo">${titulo}</h2><p>${texto}</p><footer><button class="botao" id="guiaSair">Pular</button><button class="botao" id="guiaVoltar" ${i ? '' : 'disabled'}>Voltar</button><button class="botao" id="guiaAvancar">${i === passos.length-1 ? 'Concluir' : 'Avançar'}</button></footer>`;
    balao.querySelector('#guiaSair').onclick = fechar;
    balao.querySelector('#guiaVoltar').onclick = () => { i--; mostrar(); };
    balao.querySelector('#guiaAvancar').onclick = () => { if (++i === passos.length) fechar(); else mostrar(); };
    balao.querySelector('#guiaAvancar').focus();
  }
  function abrir() {
    fechar(); anterior = document.activeElement; i = 0;
    try { localStorage.setItem(chave, '1'); } catch {}
    sombra = document.createElement('div'); sombra.className = 'guia-sombra';
    balao = document.createElement('section'); balao.className = 'guia-balao';
    balao.setAttribute('role','dialog'); balao.setAttribute('aria-modal','true'); balao.setAttribute('aria-labelledby','guiaTitulo');
    document.body.append(sombra,balao); document.addEventListener('keydown',teclado); mostrar();
  }
  document.querySelector('#btnTutorial').onclick = abrir;
  try { if (!localStorage.getItem(chave)) abrir(); } catch {}
})();
