(() => {
  const id = new URLSearchParams(location.search).get('h');
  if (!id) return;
  const $ = nome => document.getElementById('gravacao' + nome);
  const painel = $('Historica'); painel.hidden = false;
  let trechos = [], quadros = [], pos = 0, timer = null, tocando = false, carregado = false;
  const hora = t => `${String(Math.floor(t / 3600)).padStart(2,'0')}:${String(Math.floor(t / 60) % 60).padStart(2,'0')}:${(t % 60).toFixed(3).padStart(6,'0').replace('.',',')}`;
  function parar() { tocando = false; clearTimeout(timer); $('Play').textContent = 'Reproduzir'; }
  function mostrar() {
    if (!quadros.length) return;
    const q = quadros[pos], anterior = quadros[pos - 1];
    const intervalo = anterior ? q.t - anterior.t : 0;
    const url = `/api/gravacoes/${encodeURIComponent($('Trecho').value)}/${encodeURIComponent(q.nome)}`;
    $('Posicao').value = pos;
    $('Horario').textContent = `${hora(q.t)} · ${pos + 1}/${quadros.length}` + (intervalo > 1.5 ? ` · lacuna de ${intervalo.toFixed(1).replace('.',',')} s antes deste quadro` : '');
    $('Imagem').src = url; $('Original').href = url;
    $('Anterior').disabled = pos === 0; $('Proximo').disabled = pos === quadros.length - 1;
  }
  // Avança somente após a imagem carregar. Nunca preenche uma lacuna com imagem repetida.
  $('Imagem').onload = () => {
    if (!tocando) return;
    if (pos >= quadros.length - 1) return parar();
    timer = setTimeout(() => { pos++; mostrar(); }, 500);
  };
  $('Imagem').onerror = () => { parar(); $('Aviso').textContent = 'Não foi possível abrir este quadro. Selecione outro ou reabra a gravação.'; };
  $('Play').onclick = () => {
    if (tocando) return parar();
    if (pos >= quadros.length - 1) pos = 0;
    tocando = true; $('Play').textContent = 'Pausar'; mostrar();
  };
  $('Posicao').oninput = () => { parar(); pos = Number($('Posicao').value); mostrar(); };
  $('Anterior').onclick = () => { parar(); pos = Math.max(0, pos - 1); mostrar(); };
  $('Proximo').onclick = () => { parar(); pos = Math.min(quadros.length - 1, pos + 1); mostrar(); };
  $('Trecho').onchange = () => {
    parar(); pos = 0; quadros = trechos.find(t => t.sessao === $('Trecho').value)?.quadros || [];
    $('Posicao').max = Math.max(0, quadros.length - 1); mostrar();
  };
  painel.ontoggle = async () => {
    if (!painel.open) return parar();
    if (carregado) return;
    $('Aviso').textContent = 'Carregando gravação…';
    try {
      const r = await fetch(`/api/historico/${id.split('/').map(encodeURIComponent).join('/')}/gravacao`);
      if (!r.ok) throw Error('consulta');
      const dados = await r.json();
      const vazios = dados.trechos.filter(t => !t.quadros.length).length;
      trechos = dados.trechos.filter(t => t.quadros.length);
      $('Aviso').textContent = dados.limite + ' Retenção: até você solicitar exclusão. Reprodução quadro a quadro; lacunas são sinalizadas.' + (vazios ? ` ${vazios} trecho(s) sem imagens preservadas.` : '');
      if (!trechos.length) { $('Aviso').textContent += ' Nenhum quadro disponível para esta hunt.'; return; }
      $('Trecho').replaceChildren(...trechos.map(t => { const o = document.createElement('option'); o.value = t.sessao; o.textContent = t.sessao; return o; }));
      $('Controles').hidden = false; carregado = true; $('Trecho').onchange();
    } catch { $('Aviso').textContent = 'Não foi possível carregar. Feche e abra este painel para tentar novamente.'; }
  };
})();
