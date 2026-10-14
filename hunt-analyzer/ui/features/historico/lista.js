(function(root){
const {$,el,virg,kk,ouro,dur,durc}=root.HuntUI;
const dataCurta = d => (d || '').split('/').slice(0, 2).join('/');      // "23/09/2026" → "23/09"
let observador, consultas;
const plunders = new Map();
function seloPlunder(eventos) {
  if(eventos.querySelector('.plunder-indicador'))return;
  const plunder=el('span','plunder-indicador','✦ Plunder avistado');
  plunder.title='Plunder Patriarch observado nesta hunt';
  plunder.setAttribute('aria-label',plunder.title);
  eventos.append(plunder);
}
function observarPlunder(pendentes) {
  // Compatibilidade com o motor instalado: consultar só cards visíveis, dois por vez.
  // O resumo novo já fornece tem_plunder e dispensa estas consultas de detalhes.
  const controle=consultas, fila=[];
  let ativos=0;
  const proximo=()=>{
    while(ativos<2&&fila.length&&!controle.signal.aborted){
      const {s,eventos}=fila.shift();ativos++;
      const chave=JSON.stringify([s.id,s.salvo_em]);
      fetch('/api/historico/'+s.id.split('/').map(encodeURIComponent).join('/'),{cache:'no-store',signal:controle.signal})
        .then(r=>r.ok?r.json():null).then(d=>{
          if(!Array.isArray(d?.voltas)||controle.signal.aborted)return;
          const presente=d.voltas.some(v=>Object.entries(v.especies||{}).some(([nome,qtd])=>
            nome.trim().toLowerCase().replace(/\s+/g,' ')==='plunder patriarch'&&typeof qtd==='number'&&qtd>0));
          if(s.fechada&&s.salvo_em)plunders.set(chave,presente);
          if(presente&&eventos.isConnected)seloPlunder(eventos);
        }).catch(()=>{}).finally(()=>{ativos--;proximo();});
    }
  };
  const porElemento=new Map(pendentes.map(p=>[p.eventos,p]));
  const atual=new IntersectionObserver(entradas=>{
    if(controle.signal.aborted)return;
    for(const entrada of entradas)if(entrada.isIntersecting){
      const p=porElemento.get(entrada.target);atual.unobserve(entrada.target);
      if(p){fila.push(p);porElemento.delete(entrada.target);}
    }
    proximo();
  });
  observador=atual;
  for(const p of pendentes)atual.observe(p.eventos);
}
function cartaoSessao(s, capa = {}, pendentes = []) {
  const c = el('div', 'cartao'), q = el('a', 'quadro');
  c.append(el('div', 'data', [dataCurta(s.data), (s.inicio || '').slice(0, 5)].filter(Boolean).join(' · ') || '—'));
  q.href = `/hunt?h=${encodeURIComponent(s.id)}`;
  const eventos = el('div', 'eventos-hunt');
  if(s.tem_ks){
    const ks=el('span','ks-indicador'), icone=el('span','icone-ks');
    icone.setAttribute('aria-hidden','true');ks.append(icone,'KS');
    ks.title='Houve KS nesta hunt';ks.setAttribute('aria-label','Houve KS nesta hunt');
    eventos.append(ks);
  }
  if(s.tem_plunder)seloPlunder(eventos);
  if(typeof s.tem_plunder!=='boolean'){
    const chave=JSON.stringify([s.id,s.salvo_em]);
    if(s.fechada&&s.salvo_em&&plunders.has(chave)){
      if(plunders.get(chave))seloPlunder(eventos);
    }else pendentes.push({s,eventos});
  }
  q.append(eventos);
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
  pe.append(el('b', null, durc(s.dur_s || 0)), ` · ${s.pt || 'modalidade não lida'}`, el('br'),
            'raw ', el('b', null, kk(s.xp_raw)), ' · profit ', el('b', null, ouro(s.profit)));
  if (!s.fechada) pe.append(el('br'), el('span', 'aberta', 'sessão não fechada'));
  c.append(q, pe);
  return c;
}
function renderLista(ss) {
  observador?.disconnect();consultas?.abort();consultas=new AbortController();
  const pendentes=[];
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
    grade.append(...lista.map(s => cartaoSessao(s, capa, pendentes)));
    bloco.append(tit, grade);
    return bloco;
  }));
  if(pendentes.length)observarPlunder(pendentes);
}

root.HuntHistorico={renderizar:renderLista};
})(globalThis);
