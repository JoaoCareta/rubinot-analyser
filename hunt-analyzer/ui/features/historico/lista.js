(function(root){
const {$,el,virg,kk,ouro,dur,durc}=root.HuntUI;
const dataCurta = d => (d || '').split('/').slice(0, 2).join('/');      // "23/09/2026" → "23/09"
function cartaoSessao(s, capa = {}) {
  const c = el('div', 'cartao'), q = el('a', 'quadro');
  c.append(el('div', 'data', [dataCurta(s.data), (s.inicio || '').slice(0, 5)].filter(Boolean).join(' · ') || '—'));
  q.href = `/hunt?h=${encodeURIComponent(s.id)}`;
  q.title = `${s.hunt} · ${s.data || ''} ${s.inicio || ''} · abrir a análise desta sessão`;
  // capa (user, 24/09): os bichos mais mortos da hunt por cima do mapa da sessão, que fica só como
  // textura no fundo. O desenho do mapa sozinho, em 190 px, não dizia nada.
  const im = (cls, src) => { const i = el('img', cls); i.alt = ''; i.onerror = () => i.remove(); i.src = src; q.append(i); return i; };
  // padronização por hunt (user, 24/09): as sessões da mesma hunt usam o MESMO pôster — o mapa
  // ancorado no mundo mais recente e os bichos da sessão que mais matou. Só os números mudam.
  const fundo = capa.mapa || (s.mapa && s.id);
  if (fundo) im('fundo', `/api/historico/${fundo}/mapa.png`);
  const bichos = (capa.icones || s.icones || []).length ? (capa.icones || s.icones) : (s.icone ? [s.icone] : []);
  bichos.slice(0, 3).forEach((slug, i) => im(`bicho b${i}`, `/monstros/${slug}.gif`));
  if (!fundo && !bichos.length) q.append(el('span', 'vazio', '◆'));
  if (s.pico_xph) {
    const b = el('span', 'pico', `pico ${virg(s.pico_xph / 1e6, 1)} kk/h`);
    b.title = 'melhor volta da sessão';
    q.append(b);
  }
  q.append(el('span', 'n-voltas', `${s.voltas} volta${s.voltas === 1 ? '' : 's'}`));
  const pe = el('div', 'pe');
  pe.append(el('b', null, durc(s.dur_s || 0)), ` · ${s.pt || s.char || ''}`, el('br'),
            'raw ', el('b', null, kk(s.xp_raw)), ' · profit ', el('b', null, ouro(s.profit)));
  if (!s.fechada) pe.append(el('br'), el('span', 'aberta', 'sessão não fechada'));
  c.append(q, pe);
  return c;
}
function renderLista(ss) {
  const L = $('#lista');
  if (!ss.length) return L.replaceChildren(el('p', 'nota', 'Nenhuma hunt guardada ainda. Cada sessão entra aqui sozinha, volta a volta, enquanto você caça.'));
  const grupos = new Map();   // uma seção por hunt, na ordem da mais recente (a lista já vem assim)
  for (const s of ss) grupos.set(s.hunt, [...(grupos.get(s.hunt) || []), s]);
  L.replaceChildren(...[...grupos].map(([hunt, lista]) => {
    const bloco = el('section', 'hunt-bloco'), tit = el('div', 'secao-tit'), tot = el('div', 'totais');
    const soma = k => lista.reduce((a, s) => a + (s[k] || 0), 0);
    tot.append(el('b', null, `${lista.length} ${lista.length > 1 ? 'sessões' : 'sessão'}`),
               ` · ${durc(soma('dur_s'))} · ${soma('voltas')} voltas · raw `, el('b', null, kk(soma('xp_raw'))),
               ' · profit ', el('b', null, ouro(soma('profit'))));
    tit.append(el('h2', null, hunt), tot);
    const grade = el('div', 'sessoes');
    // o pôster da hunt: mapa do mundo mais recente (o local tem outra cara) e os bichos de quem mais matou
    const capa = {mapa: (lista.find(s => s.mapa && s.ancorado) || lista.find(s => s.mapa) || {}).id,
                  icones: [...lista].sort((a, b) => (b.bichos || 0) - (a.bichos || 0))[0]?.icones};
    grade.append(...lista.map(s => cartaoSessao(s, capa)));
    bloco.append(tit, grade);
    return bloco;
  }));
}

root.HuntHistorico={renderizar:renderLista};
})(globalThis);
