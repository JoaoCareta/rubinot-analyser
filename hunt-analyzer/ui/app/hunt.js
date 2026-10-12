(function(){
// ------------------------------------------------------------ escalas (validadas: ordinais, fundo escuro #11141b)
const RAMPA_PERM = ['#6b4f1a', '#94702a', '#bb923a', '#dcb455', '#f3d98f'];
const RAMPA_DENS = ['#225585', '#2b71a8', '#3a91c8', '#5db3e1', '#a6dcf4'];
// PAUSA_S (volta de 6 min ou mais = refill/pausa, fora da média) vem do ui/taxas.js, que é a cópia
// de ao_vivo.taxas: a regra de quais voltas contam mora num lugar só

let PREVIA = new URLSearchParams(location.search).has('previa');   // ?previa = mockup com os dados de 21/09 e a barra que simula as voltas
// histórico (user, 23/09): ?h = lista das hunts guardadas · ?h=<hunt>/<AAAAMMDD_HHMM> = uma sessão
// no MESMO painel da hunt ao vivo, em modo leitura. A troca é pela URL: o voltar do navegador serve.
const HIST = new URLSearchParams(location.search).get('h');
const {$,el,virg,kk,ouro,dur,hms,durc}=HuntUI;
// mapa montado dos próprios quadros (23/09): sem as coordenadas do mundo, o "andar" é só o número
// da área que o programa separou — então a tela chama de área, para ninguém ler "andar 0" numa cripta
const mapaLocal = () => { const m = D?.estado?.mapa; return !!m && m.fonte === 'local' && !m.ancorado; };
const rotZ = () => mapaLocal() ? 'área' : 'andar';

let D = null;            // dados da hunt
let mostradas = 0;       // voltas fechadas visíveis (0 = aguardando a primeira)
let selN = null;         // volta escolhida no histórico (null = a mais recente)
let andar = 12, recorte = 'sessao';
// Contrato público da aplicação: consumidores não acessam variáveis de outro script.
globalThis.HuntApp={
 get dados(){return D;}, get recorte(){return recorte;}, get selecao(){return selN;},
 get catalogo(){return CATALOGO;}, get historico(){return HIST;}, get previa(){return PREVIA;},
 voltas:()=>voltasVisiveis(), voltaEscolhida:()=>voltaEscolhida()
};

const cel = 4;           // sem seletor de andar nem de célula (user, 21/09): não ajudavam na análise

// ------------------------------------------------------------ regras do card (as mesmas do party_card)
const {xph,pct,anterior,comparacoes,humor,mediaDa,RAW_MIN_S}=HuntCard;
function chip(p, inverso = false) {
  const c = el('span', 'chip');
  if (p == null) { c.textContent = '–'; return c; }
  const sobe = p >= 5, desce = p <= -5;
  if (sobe || desce) c.classList.add((sobe !== inverso) ? 'bom' : 'ruim');
  c.textContent = `${sobe ? '▲' : desce ? '▼' : '●'} ${p > 0 ? '+' : ''}${p}%`;
  return c;
}

// ------------------------------------------------------------ agregação por célula
function amostrasDe(ini, fim) {
  return D.amostras.filter(a => a[0] >= ini && a[0] <= fim);
}
const {faixas,faixa}=HuntMapas;
const agrega=(amostras,z)=>HuntMapas.agrega(amostras,D.andares[z],z,cel);

// ------------------------------------------------------------ desenho dos mapas
const MAPAS = {
  perm: {canvas: '#cPerm', leg: '#lPerm', rampa: RAMPA_PERM, valor: c => c.seg, fmt: s => s >= 60 ? dur(s) : `${Math.round(s)}s`, min: 3},  // < 3 s = só passagem: o caminho mostra
  dens: {canvas: '#cDens', leg: '#lDens', rampa: RAMPA_DENS, valor: c => c.bichos, fmt: b => virg(b, 1), min: 3},
};
const vista = {};
function desenhaMapa(qual, paineis) {
  const M = MAPAS[qual], cv = $(M.canvas);
  const lista = paineis.flatMap(p => p.celulas.filter(c => c.seg >= M.min)), lim = faixas(lista.map(M.valor));
  const larg = Math.max(1, cv.parentElement.clientWidth - 28), dpr = window.devicePixelRatio || 1;
  let altura = 0;
  const planos = paineis.map(p => {
    const A = D.andares[p.z], esc = Math.min(larg / A.w, Math.max(larg * 1.25, 560) / A.h);
    const desenho = {...p, A, esc, lado:cel * esc, topo:altura, y:altura + 26, w:A.w * esc, h:A.h * esc};
    altura += desenho.h + 46; return desenho;
  });
  const W = larg, H = Math.max(1, altura - 20);
  cv.style.width = W + 'px'; cv.style.height = H + 'px'; cv.width = Math.round(W*dpr); cv.height = Math.round(H*dpr);
  const g = cv.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);g.imageSmoothingEnabled = false;
  for(const p of planos){
    g.fillStyle = '#e9bd64';g.font = '12px monospace';g.fillText(`${rotZ()} ${p.z}`,0,p.topo+15);
    g.save();g.translate(0,p.y);g.filter='grayscale(.85) brightness(.5)';
    if(fundos[p.z])g.drawImage(fundos[p.z],0,0,p.w,p.h);g.filter='none';
    const lado=p.lado,vao=Math.min(2,lado*.15);
    for(const c of p.celulas.filter(c=>c.seg>=M.min)){
      g.globalAlpha=.9;g.fillStyle=M.rampa[faixa(lim,M.valor(c))];
      g.fillRect(c.cx*lado+vao/2,c.cy*lado+vao/2,lado-vao,lado-vao);
    }
    const trilha=p.caminho,n=trilha.length,CLARO='#f4f1ea',ESCURO='#0b0c10';
    const quadrado=(c,f)=>{const tamanho=Math.max(4,lado*f);return [c.cx*lado+(lado-tamanho)/2,c.cy*lado+(lado-tamanho)/2,tamanho,tamanho];};
    trilha.forEach((c,i)=>{
      g.globalAlpha=.35+.65*(n>1?i/(n-1):1);g.fillStyle=CLARO;g.fillRect(...quadrado(c,.42));
      g.strokeStyle=ESCURO;g.lineWidth=1;g.strokeRect(...quadrado(c,.42));
    });
    g.globalAlpha=1;
    if(n){g.strokeStyle=CLARO;g.lineWidth=2;g.strokeRect(trilha[0].cx*lado+2,trilha[0].cy*lado+2,lado-4,lado-4);
      g.fillStyle=CLARO;g.fillRect(...quadrado(trilha[n-1],.62));g.strokeStyle=ESCURO;g.lineWidth=1.5;g.strokeRect(...quadrado(trilha[n-1],.62));}
    const hover=vista[qual]?.hover;
    if(hover?.z===p.z){g.strokeStyle='#ece6d8';g.lineWidth=2;g.strokeRect(hover.cx*lado+1,hover.cy*lado+1,lado-2,lado-2);}
    g.restore();
  }
  vista[qual]={...(vista[qual]||{}),lista,paineis:planos,lim};
  $(M.leg).replaceChildren(...M.rampa.map((cor,i)=>{const d=el('div'),sw=el('i');sw.style.background=cor;d.append(sw,lim?`${M.fmt(lim[i])}–${M.fmt(lim[i+1])}`:'–');return d;}));
}

// ------------------------------------------------------------ dica ao passar o mouse
function ligaDica(qual) {
  const cv = $(MAPAS[qual].canvas), dica = $('#dica');
  cv.addEventListener('mousemove', e => {
    const V = vista[qual]; if (!V) return;
    const r = cv.getBoundingClientRect();
    const P=V.paineis.find(p=>e.clientY-r.top>=p.y&&e.clientY-r.top<p.y+p.h);
    if(!P){dica.style.display='none';return;}
    const cx = Math.floor((e.clientX - r.left) / P.lado), cy = Math.floor((e.clientY - r.top-P.y) / P.lado);
    const passo = P.caminho.find(k => k.cx === cx && k.cy === cy) || null;
    const c = V.lista.find(k => k.z === P.z && k.cx === cx && k.cy === cy) || passo;
    // compara pela célula: cada renderMapas cria objetos novos, e por identidade todo movimento redesenhava
    if (c?.z !== V.hover?.z || c?.cx !== V.hover?.cx || c?.cy !== V.hover?.cy) { V.hover = c; renderMapas(); }
    if (!c) { dica.style.display = 'none'; return; }
    const A = P.A, x = A.x0 + cx * cel, y = A.y0 + cy * cel;
    dica.replaceChildren();
    if (c === passo && !V.lista.includes(c)) {  // só passagem: sem cor de calor, só o quadrado do caminho
      dica.append(el('b', null, 'caminho da volta ' + voltaCaminho), passo.seg >= 1 ? `passou por aqui em ${MAPAS.perm.fmt(passo.seg)}` : 'só de passagem');
    } else {
      const forte = el('b', null, qual === 'perm' ? `${MAPAS.perm.fmt(c.seg)} parado` : `${virg(c.bichos, 1)} bichos em média`);
      dica.append(forte, qual === 'perm'
        ? `${c.visitas} visita${c.visitas > 1 ? 's' : ''} · ${virg(c.bichos, 1)} bichos em média`
        : `${MAPAS.perm.fmt(c.seg)} de amostra · ${c.visitas} visita${c.visitas > 1 ? 's' : ''}`);
      if (passo) dica.append(el('br'), `no caminho da volta ${voltaCaminho}`);
    }
    dica.append(el('br'), `${rotZ()} ${P.z} · célula de ${cel} sqm em (${x}, ${y})`);
    dica.style.display = 'block';
    dica.style.left = Math.min(e.clientX + 14, innerWidth - 270) + 'px';
    dica.style.top = (e.clientY + 14) + 'px';
  });
  cv.addEventListener('mouseleave', () => { $('#dica').style.display = 'none'; if (vista[qual]) { vista[qual].hover = null; renderMapas(); } });
}

// ------------------------------------------------------------ montagem da tela
const voltasVisiveis = () => D.voltas.slice(0, mostradas);
function voltaEscolhida() {
  const vs = voltasVisiveis();
  return vs.find(v => v.n === selN) || vs[vs.length - 1] || null;
}
function recorteAtual() {
  const vs = voltasVisiveis(), v = voltaEscolhida();
  if (!v) return {amostras: [], caminhoDe: null};
  const lista = recorte === 'sessao' ? amostrasDe(vs[0].ini, vs[vs.length - 1].fim) : amostrasDe(v.ini, v.fim);
  return {amostras: lista, caminhoDe: v};
}
let voltaCaminho = null;
function caminho(v, zAlvo = andar) {             // células por onde a volta passou neste andar, na ordem da 1ª passagem
  if (!v) return [];
  const A = D.andares[zAlvo], celulas = new Map(), am = amostrasDe(v.ini, v.fim);
  const marca = (x, y, dt) => {
    if (x < A.x0 || y < A.y0 || x >= A.x0 + A.w || y >= A.y0 + A.h) return;
    const cx = Math.floor((x - A.x0) / cel), cy = Math.floor((y - A.y0) / cel), k = cx + ',' + cy;
    const c = celulas.get(k) || {cx, cy, seg: 0};
    c.seg += dt;
    celulas.set(k, c);
  };
  am.forEach(([t, z, x, y], i) => {
    if (z !== zAlvo) return;
    const prox = am[i + 1], dt = prox ? prox[0] - t : 1;
    marca(x, y, Math.min(dt, 3));
    // 1 ponto a cada ~2 s e com haste o char anda até ~18 sqm nisso: liga ao próximo ponto para o
    // caminho não ficar pontilhado. Troca de andar, captura parada ou salto acima de 10 sqm/s não liga.
    const d = prox && prox[1] === z && dt <= 3 ? Math.hypot(prox[2] - x, prox[3] - y) : Infinity;
    for (let s = .5; d <= 10 * dt && s < d; s += .5) marca(x + (prox[2] - x) * s / d, y + (prox[3] - y) * s / d, 0);
  });
  return [...celulas.values()].map(c=>({...c,z:zAlvo}));   // o Map guarda a ordem de inserção = ordem da 1ª passagem
}
function andarComMaisTempo(amostras) {   // o mapa mostra o andar onde a pt passou mais tempo no recorte
  const n = {};
  for (const a of amostras) if (D.andares[a[1]]) n[a[1]] = (n[a[1]] || 0) + 1;
  const z = Object.keys(n).sort((a, b) => n[b] - n[a])[0] || (D.andares[andar] ? andar : Object.keys(D.andares)[0]);
  return z != null ? Number(z) : null;   // null = cave sem mapa preparado
}
function renderMapas() {
  const {amostras, caminhoDe} = recorteAtual();
  andar = andarComMaisTempo(amostras);
  voltaCaminho = caminhoDe ? caminhoDe.n : null;
  $('#conteudo').classList.toggle('sem-mapas', andar == null);
  // 23/09 (user): quando o cliente não gravou o minimapa da região, o mapa vem dos próprios quadros
  $('#fonteMapa').hidden = !mapaLocal() || andar == null;
  $('#fonteMapa').textContent = 'mapa montado pelo minimapa da sessão (o jogo ainda não gravou esta região)';
  $('#thAndar').textContent = rotZ();
  if (andar == null) {
    vista.perm = vista.dens = null;
    $('#tPerm').textContent = 'permanência'; $('#tDens').textContent = 'densidade de bichos';
    $('#nPerm').textContent = $('#nDens').textContent = '';
    return [];
  }
  const paineis=Object.keys(D.andares).map(Number).sort((a,b)=>a-b).map(z=>({z,celulas:agrega(amostras,z).map(c=>({...c,z})),caminho:caminho(caminhoDe,z)})).filter(p=>p.celulas.length);
  const cels=paineis.flatMap(p=>p.celulas),trilha=paineis.flatMap(p=>p.caminho);
  const legCaminho = trilha.length ? `caminho da volta ${voltaCaminho}: mais forte perto do fim · □ início · ■ fim` : 'a volta escolhida não passou por este andar';
  document.querySelectorAll('.legenda-caminho span').forEach(s => s.textContent = legCaminho);
  desenhaMapa('perm', paineis);
  desenhaMapa('dens', paineis);
  const alvo = recorte === 'sessao' ? `sessão até a volta ${mostradas || '—'}` : `volta ${caminhoDe ? caminhoDe.n : '—'}`;
  const rotulo=paineis.length>1?`${mapaLocal()?'áreas':'andares'} ${paineis.map(p=>p.z).join(' e ')}`:`${rotZ()} ${andar}`;
  $('#tPerm').textContent = `${rotulo} — permanência`;
  $('#tDens').textContent = `${rotulo} — densidade de bichos`;
  $('#nPerm').textContent = alvo; $('#nDens').textContent = alvo;
  return cels;
}
function renderTiles() {
  const vs = voltasVisiveis(), limpas = vs.filter(v => v.dur < PAUSA_S && !v.parcial);
  const T = taxasDe(vs);   // o mesmo taxasDe do card e dos gráficos: um número só por medida
  const zs = Object.keys(D.andares).map(Number);   // chaves vêm como texto; as amostras guardam o andar em número
  const celsSessao = vs.length && zs.length ? zs.reduce((n, z) => n + agrega(amostrasDe(vs[0].ini, vs[vs.length - 1].fim), z).length, 0) : null;
  const media = limpas.length ? limpas.reduce((a, v) => a + v.dur, 0) / limpas.length : null;
  const rapida = limpas.length ? limpas.reduce((a, v) => v.dur < a.dur ? v : a) : null;
  const lenta = limpas.length ? limpas.reduce((a, v) => v.dur > a.dur ? v : a) : null;
  const tempo = vs.length ? vs[vs.length - 1].fim - vs[0].ini : null;
  const parciais = vs.filter(v => v.parcial).length;
  // refil (user, 22/09): quem mede é o motor — a ida ao depot nem chega a virar volta, então não
  // dá mais para contar "volta com refill" pelo tamanho dela
  const fechado = D.estado?.historico || D.estado?.gravando === false;
  const refis = (D.refis || []).filter(r => !fechado || (vs.length && !r.aberto && r.inicio >= vs[0].ini && r.fim < vs[vs.length-1].fim));
  const totalRefil = refis.reduce((s,r) => s + r.dur_s,0);
  const R = fechado ? {n:refis.length,total_s:totalRefil,media_s:refis.length ? totalRefil/refis.length : 0,fracao:tempo ? totalRefil/tempo : 0} : D.refil || {};
  const aberto = !fechado && refis.some(r => r.aberto);
  const dados = [
    ['tempo de hunt', tempo != null ? `${Math.floor(Math.round(tempo / 60) / 60)}h${String(Math.round(tempo / 60) % 60).padStart(2, '0')}` : '—', vs.length ? `desde ${hms(vs[0].ini).slice(0, 5)}` : ''],
    ['voltas', vs.length || '—', parciais ? `${parciais} parcia${parciais > 1 ? 'is' : 'l'}` : 'fechadas'],
    ['volta média', media ? dur(media) : '—', 'sem refill'],
    ['mais rápida', rapida ? dur(rapida.dur) : '—', rapida ? `volta ${rapida.n}` : ''],
    ['mais lenta', lenta ? dur(lenta.dur) : '—', lenta ? `volta ${lenta.n}` : ''],
    ['refil e pausas', R.n ? dur(R.total_s) : '—',
     R.n ? `${R.n} parada${R.n > 1 ? `s · média ${dur(R.media_s)}` : ''} · ${Math.round((R.fracao || 0) * 100)}% da hunt${aberto ? ' · uma em curso' : ''}`
         : 'nenhuma até agora', 'largo'],   // com 1 parada a média é o próprio total, que já está no número
    ['células', celsSessao ?? '—', zs.length ? `de ${cel} sqm, ${zs.length} ${rotZ()}${zs.length > 1 ? (mapaLocal() ? 's' : 'es') : ''}` : 'mapa ainda não encontrado'],
    ['raw estabilizada', T.raw_h ? `${virg(T.raw_h / 1e6)} kk/h` : '—',
     T.raw_de === '15min' ? `mediana de ${T.voltas_15min} voltas, 15 min` : T.raw_de ? 'raw ÷ tempo, sem os 15 min' : 'aos 15 min'],
  ];
  $('#tiles').replaceChildren(...dados.map(([r, n, o, cls]) => {
    const t = el('div', 'tile' + (cls ? ' ' + cls : ''));
    t.append(el('div', 'rotulo', r), el('div', 'num', String(n)), el('div', 'obs', o));
    return t;
  }));
}
// trechos e entradas (user, 22/09): o caminho pela cidade e o refil ficam fora das voltas, mas o
// tempo deles é da sessão. Uma barra e duas linhas de texto bastam — o mapa continua sendo o da hunt.
const TRECHO = {cidade: ['#4b5563', 'cidade e caminho'], espera: ['#374151', 'esperando na hunt'],
                hunt: ['#d6a84e', 'caçando'], refil: ['#b06cf5', 'refil ou pausa'],
                inicio_hunt: ['#60758a', 'início da hunt'], fim_hunt: ['#60758a', 'fim da hunt'],
                ks: ['#d96d78', 'KS'], house: ['#6b8e82', 'house do player'],
                inicio_house: ['#6b8e82', 'início da hunt · house do player'],
                fim_house: ['#6b8e82', 'fim da hunt · house do player']};
const MARCO = {inicio_hunt: 'hunt começou', entrada_hunt: 'entrou na área da hunt', entrada_cave: 'entrou na cave'};
function renderTempo() {
  const original = D.trechos || [], ms = [...(D.entradas || [])].sort((a, b) => a.t - b.t);
  const hunts = original.filter(t => t.tipo === 'hunt');
  const fechado = D.estado?.historico || D.estado?.gravando === false;
  const vs = D.voltas || [];
  const primeiro = vs.length ? Math.min(...vs.map(v => v.ini)) : hunts.length ? Math.min(...hunts.map(t => t.inicio)) : null;
  const ultimo = vs.length ? Math.max(...vs.map(v => v.fim)) : hunts.length ? Math.max(...hunts.map(t => t.fim)) : null;
  const segundos = h => (h || '00:00:00').split(':').reduce((s,n) => s*60+Number(n),0);
  const intervalosKS = (D.ks?.episodios || []).map(e => [segundos(e.inicio), e.ultimo_t ?? segundos(e.fim || e.ultimo_evento?.ts || e.inicio)]);
  const ts = original.flatMap(t => {
    const limites = [...intervalosKS.flat(), primeiro, ...(fechado ? [ultimo] : [])].filter(v => v != null && v > t.inicio && v < t.fim);
    const cortes = [...new Set([t.inicio, t.fim, ...limites])].sort((a,b) => a-b);
    return cortes.slice(0,-1).map((ini,i) => ({...t, inicio:ini, fim:cortes[i+1], dur_s:cortes[i+1]-ini,
      tipo:intervalosKS.some(([a,b]) => ini < b && cortes[i+1] > a) ? 'ks'
        : primeiro != null && cortes[i+1] <= primeiro ? (t.tipo === 'house' ? 'inicio_house' : 'inicio_hunt')
        : fechado && ultimo != null && ini >= ultimo ? (t.tipo === 'house' ? 'fim_house' : 'fim_hunt') : t.tipo,
      house:t.tipo === 'house'}));
  });
  $('#tempo').hidden = !ts.length;
  if (!ts.length) return;
  const soma = {};
  for (const t of ts) soma[t.tipo] = (soma[t.tipo] || 0) + t.dur_s;
  $('#tempoBarra').replaceChildren(...ts.map(t => {
    const [cor, rot] = TRECHO[t.tipo] || ['#4b5563', t.tipo], d = el('div');
    d.style.flex = `${Math.max(t.dur_s, 1)} 0 0`; d.style.background = cor;
    const areas = [...new Set(t.areas || [])];   // o cliente repete a subárea ao atravessar de novo
    d.title = `${rot} · ${hms(t.inicio).slice(0, 5)} → ${hms(t.fim).slice(0, 5)} · ${dur(t.dur_s)}`
            + (t.andares?.length ? ` · ${rotZ()} ${t.andares.join(', ')}` : '') + (areas.length ? `\n${areas.join(' · ')}` : '');
    return d;
  }));
  $('#tempoLista').replaceChildren(...Object.entries(soma).sort((a, b) => b[1] - a[1]).map(([tipo, s]) => {
    const [cor, rot] = TRECHO[tipo] || ['#4b5563', tipo], sp = el('span'), i = el('i');
    i.style.background = cor;
    sp.append(i, rot + ' ', el('b', null, dur(s)));
    return sp;
  }));
  $('#tempoMarcos').replaceChildren(...ms.filter(m => MARCO[m.tipo]).map(m => {
    const sp = el('span');
    sp.append(MARCO[m.tipo] + ' ', el('b', null, hms(m.t).slice(0, 5) + (m.z != null ? ` · ${rotZ()} ${m.z}` : '')));
    return sp;
  }));
}
function renderPainel() {
  const p = $('#painel'), vs = voltasVisiveis(), v = voltaEscolhida();
  p.replaceChildren();
  if (!v) { p.append(el('div', 'rotulo', 'última volta'), el('h2', null, '—'), el('p', 'nota', 'O card aparece quando a primeira volta fechar.')); return; }
  const i = vs.indexOf(v), ant = anterior(vs, i), c = comparacoes(v, ant);
  // média da hunt: só sem volta escolhida no histórico e passados os 15 min que consolidam a raw
  const M = selN == null && vs[vs.length - 1].fim - vs[0].ini >= RAW_MIN_S ? mediaDa(vs) : null;
  const topo = el('div', 'topo-card');
  topo.append(el('div', 'rotulo', M ? 'média da hunt' : v === vs[vs.length - 1] ? 'última volta fechada' : 'volta escolhida'));
  if (v !== vs[vs.length - 1]) { const b = el('button', 'voltar', 'ver a hunt'); b.onclick = () => { selN = null; recorte = 'sessao'; tudo(); }; topo.append(b); }
  // "26 de 29" no título (user, 24/09): o tile diz 29 voltas fechadas e a média usa 26 — sem o
  // "de 29" os dois números batiam de frente na mesma tela
  const cab = M ? [`Média · ${M.n}${M.n < M.total ? ` de ${M.total}` : ''} voltas · ${dur(M.dur)}`, hms(M.ini), hms(M.fim)]
                : [`Volta ${v.n} · ${dur(v.dur)} ${humor(v, c)}`, hms(v.ini), hms(v.fim)];
  p.append(topo, el('h2', null, cab[0]), el('p', 'sub', `${D.sessao.hunt} · ${cab[1].slice(0, 5)} → ${cab[2].slice(0, 5)}`));
  const tab = el('table', 'metricas');
  // no modo média o ▲▼ é a última volta contra a média (a comparação com a volta anterior já está
  // em cada card do histórico); no modo volta continua sendo contra a volta anterior
  const cm = M && {xp: pct(xph(v), M.xph), profit: pct(v.profit, M.profit), sup_pt: pct(v.sup_pt, M.sup_pt),
                   sup_eu: pct(v.sup_eu, M.sup_eu), bichos: pct(v.bichos, M.bichos)};
  const linhas = M ? [
    ['📈 XP raw/h', M.xph ? `${kk(M.xph)}/h` : '–', chip(cm.xp)],
    ['💰 Profit', ouro(M.profit), chip(cm.profit)],
    ['🧪 Supplies da pt', ouro(M.sup_pt), chip(cm.sup_pt, true)],
    ['🧪 Seus supplies', ouro(M.sup_eu), chip(cm.sup_eu, true)],
    ['💀 Bichos mortos', M.bichos == null ? '–' : virg(M.bichos, 1), chip(cm.bichos)],
  ] : [
    ['📈 XP raw/h', xph(v) ? `${kk(xph(v))}/h` : '–', chip(c.xp)],
    ['💰 Profit', ouro(v.profit), chip(c.profit)],
    ['🧪 Supplies da pt', ouro(v.sup_pt), chip(c.sup_pt, true)],
    ['🧪 Seus supplies', ouro(v.sup_eu), chip(c.sup_eu, true)],
    ['💀 Bichos mortos', v.bichos ?? '–', chip(c.bichos)],
  ];
  // solo (CLAUDE.md): só a linha do jogador. 22/09: pelo "solo" do pt_card; sup_pt nulo também vem
  // de base do loot trocada no meio da volta (pt). Sem o campo (card antigo): sup_pt nulo = solo
  const solo = M ? M.solo : (v.solo ?? (v.sup_pt == null));
  if (solo) linhas.splice(2, 1);
  for (const [rot, val, ch] of linhas) {
    const tr = el('tr'), td = el('td', 'var');
    td.append(ch);
    tr.append(el('td', null, rot), el('td', 'valor', String(val)), td);
    tab.append(tr);
  }
  p.append(tab);
  const notas = [];
  const forasco = [M && M.parciais && `${M.parciais} parcia${M.parciais > 1 ? 'is' : 'l'}`,
                   M && M.refil && `${M.refil} de 6 min ou mais (refill ou pausa)`].filter(Boolean).join(' e ');
  if (M) notas.push(`Das ${M.total} voltas fechadas, ${M.n} entram na média${forasco ? ` — ${forasco} ficam de fora, as mesmas dos tiles lá em cima` : ''}. ` +
                    `XP raw/h é a mediana das voltas com a raw consolidada; o ▲▼ é a volta ${v.n} contra esta média.`);
  else if (v.parcial) notas.push('Volta parcial: a gravação parou no meio dela. Fica fora da média, da mais rápida e das comparações.');
  else if (v.estabilizando) notas.push('⏳ Raw estabilizando: a janela de 15 min ainda pega o início da hunt ou um refill, então a XP é da própria volta e não compara.');
  else if (v.xp_raw_15min) notas.push('XP raw/h = raw dos últimos 15 min, o mesmo número do XP Analyser.');
  const baseMudou = ant && v.base && ant.base && v.base !== ant.base;
  if (baseMudou) notas.push(`Base do loot mudou (${ant.base} → ${v.base}): o profit não compara com a volta anterior.`);
  if (v.reset) notas.push('O Party Hunt foi zerado no meio desta volta: profit e supplies da pt contam só depois do zeramento e não comparam.');
  else if (v.profit == null && !baseMudou) notas.push(`Profit sem leitura nesta volta: o ${solo ? 'Hunt Analyser' : 'Party Hunt'} não foi lido.`);
  if (notas.length) p.append(el('p', 'nota', notas.join(' ')));
  const tot = vs.slice(0, i + 1);
  const sessao = el('div', 'sessao');
  sessao.append(el('div', 'rotulo tit', M ? 'na sessão inteira' : `na sessão, até a volta ${v.n}`));
  for (const [r, n] of [['raw', kk(tot.reduce((a, x) => a + (x.xp_raw || 0), 0))],
                        ['profit', ouro(tot.reduce((a, x) => a + (x.profit || 0), 0))],
                        ['bichos', tot.some(x => x.bichos != null) ? tot.reduce((a, x) => a + (x.bichos || 0), 0).toLocaleString('pt-BR') : '–']]) {   // sem fator da cave = sem contagem
    const d = el('div'); d.append(el('div', 'rotulo', r), el('div', 'num', n)); sessao.append(d);
  }
  p.append(sessao);
}
function renderHistorico(novaN) {
  const vs = voltasVisiveis(), atual = voltaEscolhida();
  $('#histInfo').textContent = vs.length ? `${vs.length} volta${vs.length > 1 ? 's' : ''} · a mais nova primeiro · clique para ver a volta nos mapas` : '';
  $('#historico').replaceChildren(...[...vs].reverse().map((v) => {
    const c = comparacoes(v, anterior(vs, vs.indexOf(v)));
    const b = el('button', 'volta' + (v === atual ? ' sel' : '') + (v.n === novaN ? ' nova' : ''));
    const l = el('div', 'linha');
    l.append(el('span', 'n', `Volta ${v.n}`), el('span', 'd', `${dur(v.dur)} ${humor(v, c)}`));
    const vals = el('div', 'vals');
    vals.append('XP raw/h', el('b', null, xph(v) ? virg(xph(v) / 1e6) : '–'), 'profit', el('b', null, ouro(v.profit)), 'bichos', el('b', null, String(v.bichos ?? '–')));
    b.append(l, vals);
    b.onclick = () => { selN = v.n; recorte = 'volta'; tudo(); };
    return b;
  }));
}
function renderTabela(cels) {
  const top = [...cels].sort((a, b) => b.seg - a.seg).slice(0, 10);
  const limP = vista.perm?.lim;
  $('#tabela').replaceChildren(...top.map(c => {
    const tr = el('tr'), t1 = el('td'), A = D.andares[c.z];
    const sw = el('i'); sw.style.background = RAMPA_PERM[faixa(limP, c.seg)];
    t1.append(sw, MAPAS.perm.fmt(c.seg));
    tr.append(el('td', null, String(c.z)), el('td', null, `(${A.x0 + c.cx * cel}, ${A.y0 + c.cy * cel})`), t1,
              el('td', null, String(c.visitas)), el('td', null, virg(c.bichos, 1)));
    return tr;
  }));
}
function renderFiltros() {
  const grupo = (id, opcoes, atual, muda) => $(id).replaceChildren(...opcoes.map(([valor, rotulo]) => {
    const b = el('button', 'pilula' + (valor === atual ? ' ativa' : ''), rotulo);
    b.onclick = () => { muda(valor); tudo(); };
    return b;
  }));
  grupo('#fRecorte', [['sessao', 'sessão inteira'], ['volta', 'volta escolhida']], recorte, v => recorte = v);
}
function renderCabeca() {
  renderAbaPainel();
  renderKS();
  renderPartyDano();
  const vs = voltasVisiveis(), S = D.sessao || {}, E = D.estado || {};
  const roster = new Set([...(D.ks?.party || []), ...(D.ks?.sessoes || []).flatMap(s => s.party || [])].map(n => n.replace(/\s+/g, '').toLocaleLowerCase()));
  const pt = roster.size >= 2 ? `pt x${roster.size}` : S.pt;
  const nome = S.hunt || E.local || 'Hunt';   // o backend manda o nome; local = lugar pelo catálogo
  $('#huntNome').textContent = nome;
  $('#huntSub').textContent = [E.local !== nome && E.local, S.data, S.char, pt,
    D.sessoes_origem?.length > 1 && `${D.sessoes_origem.length} gravações reunidas`,
    E.historico ? 'hunt guardada, em modo leitura' : S.inicio && `gravação desde ${S.inicio}`].filter(Boolean).join(' · ') || '—';  // pt "" em solo
  const espera = !vs.length && !E.historico;   // hunt guardada sem volta fechada: a tela mostra o que tem
  $('#conteudo').classList.toggle('borrado', espera);
  $('#conteudo').inert = espera;   // borrado não recebe foco nem clique de teclado
  if (espera) $('#dica').style.display = 'none';   // inert não dispara mouseleave: a dica do mapa ficaria presa
  $('#espera').classList.toggle('on', espera);
  // hunt guardada (user, 23/09): modo leitura, sem estado ao vivo nenhum
  if (E.historico) {
    $('#dotVivo').className = 'dot';
    $('#aoVivo').replaceChildren('hunt guardada · ', el('b', null, [S.inicio, S.fim].filter(Boolean).join(' → ') || '—'));
    return;
  }
  if (!PREVIA) return renderEstado(vs, E);
  $('#dotVivo').className = 'dot gravando';
  $('#aoVivo').replaceChildren('gravando · ', el('b', null, `volta ${vs.length + 1} em andamento`));
  $('#previaInfo').textContent = `${vs.length} de ${D.voltas.length} voltas`;
  $('#esperaTxt').textContent = `A hunt começou às ${S.inicio}. O mapa, o card e o histórico aparecem quando a primeira volta fechar.`;
}

function ksNumero(v) {
  const magnitude = Math.abs(v);
  const divisor = magnitude >= 1e6 ? 1e6 : magnitude >= 1e3 ? 1e3 : 1;
  return (v / divisor).toLocaleString('pt-BR', {maximumFractionDigits: divisor === 1 ? 0 : 1}) + (divisor === 1e6 ? ' kk' : divisor === 1e3 ? 'k' : '');
}
function ksDiferenca(atual, outro, rival = false) {
  if (!Number.isFinite(atual) || !Number.isFinite(outro) || outro <= 0)
    return {texto:'—', classe:'', dica:'Sem comparação: falta leitura ou a base é zero.'};
  const pct = (atual - outro) / outro * 100;
  const favoravel = pct > 0;
  return {texto:(pct > 0 ? '▲ +' : pct < 0 ? '▼ −' : '= ') + Math.abs(pct).toLocaleString('pt-BR', {maximumFractionDigits:1}) + '%',
    classe:pct === 0 ? '' : favoravel ? 'favoravel' : 'desfavoravel',
    dica:(rival ? 'Time de fora comparado à sua party' : 'Sua party comparada ao time de fora') + ': (dano deste time ÷ dano do outro − 1) × 100. Apenas dano observado.'};
}
const ksExpansao = new Map();
let abaPainel = 'hunt', sessaoPainel = null, assinaturaKS = null;
const ksVistos = new Set(), rascunhosKS = new Map();
const chaveKS = ep => JSON.stringify([sessaoPainel,ep.id,ep.inicio]);
function lePreferencia(chave) { try { return JSON.parse(localStorage.getItem(chave)); } catch { return null; } }
function guardaPreferencia(chave, valor) { try { localStorage.setItem(chave,JSON.stringify(valor)); return true; } catch { return false; } }
function renderAbaPainel() {
  const id = D.estado?.id || D.estado?.sessao || [D.sessao?.data,D.sessao?.inicio,D.sessao?.char].join('|');
  const eps = D.ks?.episodios || [];
  if (id !== sessaoPainel) {
    sessaoPainel = id; ksVistos.clear(); assinaturaKS = null;
    for (const chave of lePreferencia('hunt:ks-vistos:'+id) || []) ksVistos.add(chave);
    const salva = lePreferencia('hunt:aba:'+id);
    abaPainel = salva === 'ks' ? 'ks' : 'hunt';
    // Histórico já conhecido respeita a escolha salva; uma detecção nova ao vivo abre KS.
    if (D.estado?.historico && salva) for (const ep of eps) ksVistos.add(chaveKS(ep));
  }
  for (const ep of eps) if (!ksVistos.has(chaveKS(ep))) {
    ksVistos.add(chaveKS(ep)); abaPainel = 'ks';
    guardaPreferencia('hunt:ks-vistos:'+id,[...ksVistos]);
  }
  $('#painel').hidden = abaPainel !== 'hunt'; $('#ksPainel').hidden = abaPainel !== 'ks';
  for (const [id,aba] of [['abaHunt','hunt'],['abaKS','ks']]) {
    const b = $('#'+id), selecionada = abaPainel === aba;
    b.setAttribute('aria-selected',String(selecionada)); b.tabIndex = selecionada ? 0 : -1;
    b.onclick = () => { abaPainel = aba; guardaPreferencia('hunt:aba:'+sessaoPainel,aba); renderAbaPainel(); renderKS(); };
    b.onkeydown = e => { if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {
      e.preventDefault(); const alvo = $('#'+(e.key === 'Home' ? 'abaHunt' : e.key === 'End' ? 'abaKS' : aba === 'hunt' ? 'abaKS' : 'abaHunt')); alvo.click(); alvo.focus();
    } };
  }
  $('#abaKS').textContent = 'KS';
  $('.painel-alternavel').classList.toggle('aba-ks',abaPainel === 'ks');
  $('#abaKS').classList.toggle('ks-alerta',eps.some(e => e.aberto));
}

function registroGuilda(ep) {
  const chave = 'hunt:ks-guilda:'+chaveKS(ep);
  let edicoes = rascunhosKS.get(chave);
  if (!edicoes) { edicoes = lePreferencia(chave) || {}; rascunhosKS.set(chave,edicoes); }
  const segundo = h => (h || '00:00:00').split(':').reduce((s,n)=>s*60+Number(n),0);
  const g = ep.ganhos, ganhos = g && Math.abs(g.inicio_t-segundo(ep.inicio)) <= 5 && Math.abs(g.fim_t-ep.ultimo_t) <= 5 ? g : null;
  const base = {chars:Object.keys(ep.dano?.fora || {}).join(', '), hunted:'', respawn:D.sessao?.hunt || '',
    raw:ganhos?.xp_raw ?? '', gold:ganhos?.loot ?? '', inicio:(ep.inicio || '').slice(0,5),
    fim:(ep.fim || ep.ultimo_evento?.ts || '').slice(0,5), descricao:'', tankando:false};
  const valores = {...base,...edicoes}, form = el('div','ks-guilda');
  form.append(el('div','rotulo','Dados para a guilda'));
  const status = el('p','ks-note'); status.setAttribute('role','status');
  const altera = (key,value) => { edicoes[key] = value; valores[key] = value;
    status.textContent = guardaPreferencia(chave,edicoes) ? 'Rascunho salvo neste navegador.' : 'Rascunho mantido nesta tela; o navegador não permitiu salvar.'; };
  function campo(key,label,tipo='text',nota='') {
    const wrap = el('label','ks-campo'), input = el(tipo === 'textarea' ? 'textarea' : 'input');
    input.setAttribute('aria-label',label);
    wrap.append(el('span',null,label));
    if (tipo !== 'textarea') input.type = tipo;
    input.value = valores[key];
    if (tipo === 'number') { input.min = '0'; input.step = '1'; input.placeholder = 'Sem leitura · preencher'; }
    if (tipo === 'textarea') input.maxLength = 500;
    input.addEventListener('input',() => { altera(key,input.value); if (key === 'descricao') ajuda.textContent = `${input.value.length}/500 caracteres`;
      else if (tipo === 'number') ajuda.textContent = 'Informado por você.'; });
    const ajuda = el('small',null,key === 'descricao' ? `${String(valores[key]).length}/500 caracteres`
      : tipo === 'number' ? key in edicoes ? 'Informado por você.' : valores[key] === '' ? 'Sem leitura desse período.' : 'Leitura dos painéis.' : nota);
    wrap.append(input,ajuda); return wrap;
  }
  form.append(campo('chars','Chars da PT que deu KS','text','Nomes detectados no dano de fora da party. Separe os nomes por vírgula.'),
    campo('hunted','Chars oprimidos (hunted)','text','Preencha se houver. Pode informar mais de um.'),campo('respawn','Respawn'));
  const camposGanhos = el('div','ks-dupla'); camposGanhos.append(campo('raw','Raw XP Gain','number'),campo('gold','Gold total','number')); form.append(camposGanhos,
    el('p','ks-note','XP raw do seu personagem e gold (loot) da sua party/solo durante o KS. Leituras automáticas usam quadros próximos dos horários, com até 5 s de diferença em cada ponta. Sem leitura, preencha pelos painéis do jogo.'));
  const horas = el('div','ks-dupla'); horas.append(campo('inicio','Início do KS','time'),campo('fim','Término do KS','time',ep.aberto ? 'Horário do último dano registrado; acompanha novos golpes.' : 'Horário do último dano registrado na prova.')); form.append(horas,campo('descricao','Descrição','textarea'));
  if (ganhos?.limite) form.append(el('p','ks-note',ganhos.limite));
  const tank = el('label','ks-tank'), check = el('input'); check.type='checkbox'; check.checked=Boolean(valores.tankando);
  check.addEventListener('change',() => altera('tankando',check.checked)); tank.append(check,'Estava tankando o KS'); form.append(tank);
  const copiar = el('button','ks-proof ks-copy','Copiar dados para a guilda'); copiar.type='button';
  copiar.onclick = async () => {
    for (const input of form.querySelectorAll('input')) if (!input.reportValidity()) return;
    const campos = [['Chars da PT que deu KS',valores.chars],['Chars oprimidos (hunted)',valores.hunted],['Respawn',valores.respawn],
      ['Raw XP Gain',valores.raw],['Gold total',valores.gold],['Início do KS',valores.inicio],['Término do KS',valores.fim || 'Sem leitura'],['Descrição',valores.descricao],['Tankando KS',valores.tankando ? 'Sim' : 'Não marcado']];
    const texto = [`Data: ${D.sessao?.data || '—'}`,...campos.map(([k,v]) => `${k}: ${v === '' ? 'Não informado' : v}`),
      ...['party','fora'].map(g => `Dano observado — ${g === 'party' ? 'sua party' : 'fora da party'}: ${Object.values(ep.dano?.[g] || {}).reduce((s,p)=>s+p.dano,0).toLocaleString('pt-BR')}`),
      'Dano parcial: golpes legíveis do Server Log.',ganhos?.limite || 'XP/gold: confira os painéis do período.',
      ...['prova_inicio',ep.prova_fim ? 'prova_fim' : 'prova_ultimo'].filter(k=>ep[k]?.print).map(k=>`${k === 'prova_inicio' ? 'Print do início' : ep.prova_fim ? 'Print do fim' : 'Print do último golpe'}: anexar ${ep[k].print.split('/').pop()}`)].join('\n');
    try { await navigator.clipboard.writeText(texto); status.textContent='Dados copiados. Os prints podem ser baixados abaixo.'; }
    catch { const area=el('textarea');area.value=texto;area.setAttribute('aria-label','Dados para copiar');form.append(area);area.focus();area.select();status.textContent='Selecione e copie os dados abaixo.'; }
  };
  form.append(copiar,status); return form;
}
function renderPartyDano() {
  const kk = ksNumero;
  const painel = $('#partyDano'), k = D.ks || {};
  const stats = k.estatisticas_party || {}, pessoas = [...(stats.jogadores || [])];
  const roster = [...(k.party || []), ...(k.sessoes || []).flatMap(s => s.party || [])];
  const chaveNome = n => n.replace(/\s+/g, '').toLocaleLowerCase();
  for (const nome of roster) if (!pessoas.some(p => chaveNome(p.nome) === chaveNome(nome))) pessoas.push({nome});
  painel.hidden = !pessoas.some(p => p.dano != null || p.dano_observado != null);
  if (painel.hidden) { painel.replaceChildren(); return; }
  const titulo = el('div', 'secao-tit');
  titulo.append(el('h2', null, 'Dano individual da party'), el('span', 'sub', 'acumulado do Party Hunt · extras do Server Log'));
  const filhos = [titulo];
  const numero = v => v == null ? '—' : v.toLocaleString('pt-BR');
  const porcento = v => v == null ? '—' : v.toLocaleString('pt-BR', {maximumFractionDigits:1}) + '%';
  if (pessoas.length) {
    const wrap = el('div', 'rolagem'), tabela = el('table'), head = el('thead'), linha = el('tr');
    for (const nome of ['Jogador','Dano · painel','Participação','Profit · painel','Cura · painel','Golpes lidos','Críticos','Críticos %','Fatais','Fatais %','Maior golpe lido']) linha.append(el('th',null,nome));
    head.append(linha); tabela.append(head);
    const corpo = el('tbody');
    for (const p of pessoas) {
      const tr = el('tr');
      for (const v of [p.nome, p.dano == null ? '—' : kk(p.dano), porcento(p.participacao), p.profit == null ? '—' : kk(p.profit), p.cura == null ? '—' : kk(p.cura), numero(p.golpes), numero(p.criticos), porcento(p.criticos_pct), numero(p.fatais), porcento(p.fatais_pct), p.maior_golpe == null ? '—' : kk(p.maior_golpe)]) tr.append(el('td',null,v));
      tr.title = `Dano dos golpes críticos: ${p.dano_critico == null ? 'sem leitura' : kk(p.dano_critico)} · Dano dos golpes fatais: ${p.dano_fatal == null ? 'sem leitura' : kk(p.dano_fatal)}`;
      corpo.append(tr);
    }
    tabela.append(corpo); wrap.append(tabela); filhos.push(wrap);
  } else filhos.push(el('p','sub','Aguardando a identificação da party e golpes legíveis no Server Log.'));
  const totais = ['loot','supplies','profit'].filter(c => stats[c] != null).map(c => `${{loot:'Loot da pt',supplies:'Supplies da pt',profit:'Profit da pt'}[c]}: ${kk(stats[c])}`);
  if (totais.length) filhos.push(el('p','sub',totais.join(' · ') + (stats.tipo ? ` · ${stats.tipo}` : '')));
  filhos.push(el('p','sub','Dano, participação, profit e cura vêm do Party Hunt visível, incluindo o acumulado anterior à abertura do analisador. Críticos, fatais (Onslaught), golpes e maior golpe vêm apenas das linhas lidas no Server Log; são parciais e contam por alvo. Crítico e fatal podem ocorrer juntos. — indica informação não medida.'));
  painel.replaceChildren(...filhos);
}
function renderKS() {
  const painel = $('#ksPainel'), k = D?.ks || {}, eps = k.episodios || [];
  const assinatura = JSON.stringify([sessaoPainel,eps,D.sessao?.hunt,D.sessao?.data,D.estado?.gravando,D.estado?.historico]);
  if (assinatura === assinaturaKS || document.activeElement?.closest('.ks-guilda')) return;
  assinaturaKS = assinatura;
  const filhos = [];
  const kk = ksNumero;
  if (!eps.length) filhos.push(el('div','painel', 'Nenhum KS identificado nesta hunt. A aba abre automaticamente quando um novo KS é detectado; você pode voltar para Hunt quando quiser.'));
  for (const ep of [...eps].reverse()) {
    const chaveExpansao = chaveKS(ep);
    const card = el('details', 'ks-card'), head = el('summary', 'ks-head'), intro = el('div');
    card.open = ksExpansao.get(chaveExpansao) ?? ep === eps[eps.length-1];
    card.addEventListener('toggle', () => { if (card.isConnected) ksExpansao.set(chaveExpansao, card.open); });
    intro.append(el('div', 'rotulo', '— INTERFERÊNCIA NA HUNT · KS'), el('h2', null, 'Sua party × fora da party'), el('div', 'sub', `${ep.inicio} → ${ep.fim || 'último golpe: ' + (ep.ultimo_evento?.ts || '—')}`));
    const totais = ['party','fora'].map(g => Object.values(ep.dano?.[g] || {}).reduce((s,p) => s + p.dano, 0));
    const encerrada = D.estado?.historico || D.estado?.gravando === false;
    const comparavel = ['party','fora'].every(g => Object.keys(ep.dano?.[g] || {}).length);
    const vencedor = !comparavel ? 'Sem leitura' : totais[0] === totais[1] ? 'Empate' : totais[0] > totais[1] ? 'Sua PT' : 'PT inimiga';
    const destaque = el('div','ks-maior-dano');
    destaque.append(el('span',null,encerrada ? 'Maior dano: ' : 'Maior dano atual: '),
      el('strong',comparavel && totais[0] !== totais[1] ? totais[0] > totais[1] ? 'aliada' : 'inimiga' : null,vencedor));
    destaque.title = 'Comparação do dano observado no Server Log durante este KS.';
    intro.append(destaque);
    const acoes = el('div', 'ks-actions'), alternar = el('span', 'ks-toggle');
    alternar.append(el('span', 'ks-expandir', '▸ Expandir'), el('span', 'ks-recolher', '▾ Recolher'));
    acoes.append(el('span', 'ks-badge', ep.aberto ? 'KS em acompanhamento' : 'KS encerrado'), alternar);
    head.append(intro, acoes);
    card.append(head);
    const soma = totais[0] + totais[1], grid = el('div', 'ks-grid');
    for (const [i, grupo, label] of [[0,'party','Sua party'],[1,'fora','Fora da party']]) {
      const team = el('section', 'ks-team' + (i ? ' rival' : ''));
      team.append(el('h3', null, label));
      const pessoas = Object.entries(ep.dano?.[grupo] || {}).sort((a,b) => b[1].dano - a[1].dano);
      for (const [label, value, atual, outro] of [
        ['Dano observado',pessoas.length ? kk(totais[i]) : 'Sem leitura',pessoas.length ? totais[i] : null,Object.keys(ep.dano?.[i ? 'party' : 'fora'] || {}).length ? totais[1-i] : null]]) {
        const row=el('div','ks-metric'), valores=el('div','ks-value'), delta=ksDiferenca(atual,outro,Boolean(i));
        const badge=el('span','ks-delta '+delta.classe,delta.texto);badge.title=delta.dica;
        badge.setAttribute('aria-label',delta.dica+' '+delta.texto);
        valores.append(el(value==='Sem leitura'?'small':'strong',null,value),badge);
        row.append(el('span',null,label),valores);team.append(row);
      }
      const pct=soma ? totais[i]/soma*100 : null;
      const share=el('div','ks-share');share.append(el('span',null,'Parcela do dano registrado'),el('b',null,pct===null?'—':pct.toLocaleString('pt-BR',{maximumFractionDigits:1})+'%'));
      const bar=el('div','ks-bar'),fill=el('span');fill.style.width=(pct || 0)+'%';bar.append(fill);team.append(share,bar);
      for(const [nome,p] of pessoas){
        const row=el('div','ks-player');row.append(el('b',null,nome),el('strong',null,kk(p.dano)),el('small',null,`${p.golpes.toLocaleString('pt-BR')} golpes · ${p.criticos.toLocaleString('pt-BR')} críticos`));team.append(row);
      }
      if(!pessoas.length)team.append(el('p','ks-note','Nenhum golpe classificado para este time.'));
      grid.append(team);
    }
    card.append(grid);
    const guilda=el('details','ks-guilda-bloco');
    guilda.open=ksExpansao.get(chaveExpansao+':guilda') ?? false;
    guilda.addEventListener('toggle',()=>{if(guilda.isConnected)ksExpansao.set(chaveExpansao+':guilda',guilda.open)});
    guilda.append(el('summary',null,'Dados para a guilda · preencher e copiar'),registroGuilda(ep));
    card.append(guilda);
    const foot=el('div','ks-prints');
    for(const [key,label] of [['prova_inicio','Ver print do início'],[ep.prova_fim?'prova_fim':'prova_ultimo',ep.prova_fim?'Ver print do fim':'Ver último golpe']]){
      const p=ep[key]?.print;if(p){const wrap=el('div'),a=el('a','ks-print'),img=el('img');
        a.href='/api/ks/'+p;a.target='_blank';a.rel='noopener';img.src=a.href;img.alt=label;img.loading='lazy';a.append(img,label);
        const baixar=el('a','ks-print-download','Baixar print');baixar.href=a.href;baixar.download=p.split('/').pop();wrap.append(a,baixar);foot.append(wrap);}
    }
    card.append(foot,el('p','ks-note','Dano parcial do Server Log. ▲▼ compara os times; a participação no dano não representa divisão de XP ou gold.'));
    const repetidos=Object.keys(ep.dano?.party || {}).filter(n=>n in (ep.dano?.fora || {}));
    if(repetidos.length)card.append(el('p','ks-note',repetidos.join(', ')+' aparece nos dois lados porque a identificação da party mudou durante a captura.'));
    filhos.push(card);
  }
  painel.replaceChildren(...filhos);
}

// ------------------------------------------------------------ ao vivo (user, 21/09): o estado vem do /api/hunt
const pausada = E => E.gravando && E.ultimo_quadro_s > 30;   // a captura só grava com o jogo na frente
// refil em curso (user, 22/09): o motor marca a pausa quando você para de matar, e a tela diz há quanto
const refilAberto = () => (D?.refis || []).find(r => r.aberto);
const haQuanto = () => { const r = refilAberto(); return r ? ` há ${dur(r.dur_s)}` : ''; };
// mensagem do programa sem nome de exceção nem caminho de arquivo (user, 21/09): corta a parte técnica
const semJargao = m => { const t = (m || '').replace(/[:\s]*[^:.]*\b\w*(Error|Exception|Traceback|File ")[\s\S]*$/, '').replace(/[\s.:,;]*$/, ''); return t && t + '.'; };
function renderEstado(vs, E) {
  $('#jogo').replaceChildren(el('span', 'dot' + (E.jogo ? ' on' : '')), E.fonte?.tipo === 'twitch'
    ? `Twitch · ${E.fonte.canal} · ${E.jogo ? 'recebendo' : 'sem sinal'} · com atraso`
    : E.jogo ? `RubinOT aberto${E.char ? ' · ' + E.char : ''}` : 'RubinOT fechado');
  // 24/09 (user): iniciar/encerrar a hunt aqui mesmo. Reiniciar só faz sentido com a gravação ligada.
  $('#btnHunt').textContent = E.ativo ? 'Encerrar hunt' : 'Iniciar hunt';
  $('#btnHunt').title = E.ativo ? 'Para de gravar e guarda esta hunt no histórico; o programa continua aberto'
                                : 'Começa uma sessão nova e volta a gravar';
  $('#btnReiniciar').hidden = !E.ativo;
  const [dot, ...vivo] = semResposta ? ['erro', 'sem resposta do programa']
    : !E.gravando ? ['', 'gravação parada']
    : pausada(E) ? ['pausa', E.fonte?.tipo === 'twitch' ? 'live sem quadros recentes' : 'jogo fora da frente, gravação pausada']
    : E.pausa && E.hunt_comecou ? ['pausa', `pausa ou refill${haQuanto()} · `, el('b', null, `a volta ${E.volta_atual || vs.length + 1} recomeça quando a hunt voltar`)]
    : ['gravando', 'gravando · ', el('b', null, E.hunt_comecou ? `volta ${E.volta_atual || vs.length + 1} em andamento` : 'aguardando a hunt começar')];
  const chave = dot + vivo.map(x => x.textContent ?? x).join('');
  if ($('#aoVivo').dataset.chave !== chave) {   // role=status lê em voz alta cada troca: só troca quando muda
    $('#aoVivo').dataset.chave = chave;
    $('#dotVivo').className = 'dot ' + dot;
    $('#aoVivo').replaceChildren(...vivo);
  }

  // caixa da espera: os passos mostram onde o programa está de verdade
  const hora = (E.hunt_comecou || '').slice(0, 5);
  let rot = '— gravando', tit, txt;
  if (semResposta) [rot, tit, txt] = ['— hunt analyzer', 'Sem resposta do programa', ['Confira no painel de controle se o analisador está ligado.']];
  else if (!E.calibrado) {
    const a = el('a', null, 'tela de calibração'); a.href = '/';
    [rot, tit, txt] = ['— calibração', 'Calibre primeiro', ['Marque onde fica cada painel na ', a, ' e salve. Depois disso o programa grava e acompanha a hunt sozinho.']];
  } else if (!E.gravando) [rot, tit, txt] = ['— gravação parada', 'Gravação parada', [semJargao(E.mensagem) || 'A gravação começa quando o RubinOT estiver aberto.']];
  else if (pausada(E)) [rot, tit, txt] = ['— gravação pausada', E.fonte?.tipo === 'twitch' ? 'Aguardando a transmissão' : 'Traga o jogo para a frente', [semJargao(E.mensagem) || 'O Windows só deixa gravar a janela do RubinOT quando ela está na frente.']];
  else if (E.pausa && E.hunt_comecou) [rot, tit, txt] = ['— pausa', 'Pausa ou refill', [`Parado${haQuanto()}. A volta recomeça sozinha quando a hunt voltar, e este tempo entra nas estatísticas de refil.`]];
  else if (E.hunt_comecou) [tit, txt] = ['Aguardando a primeira volta', [`A hunt começou às ${hora}. O mapa, o card e o histórico aparecem quando a primeira volta fechar.`]];
  else [tit, txt] = ['Aguardando a hunt começar', ['Pode ir caçar: o programa percebe sozinho quando a hunt começa.']];
  $('#esperaRot').textContent = rot; $('#esperaTit').textContent = tit; $('#esperaTxt').replaceChildren(...txt);
  const passos = [[E.calibrado, 'calibração salva'], [E.gravando, 'gravando'],
                  [!!E.hunt_comecou, E.hunt_comecou ? `hunt detectada às ${hora}` : 'aguardando a hunt começar'], [false, 'primeira volta']];
  const agora = passos.findIndex(p => !p[0]);
  $('#passos').style.display = semResposta ? 'none' : '';
  $('#passos').replaceChildren(...passos.map(([feito, t], i) => {
    const s = el('span', feito ? 'feito' : i === agora ? 'agora' : null);
    if (feito) s.append('✓ ', t);
    else if (i === agora && E.gravando && !pausada(E)) s.append(el('span', 'dot gravando'), t);   // acontecendo agora
    else s.append('○ ', t);
    return s;
  }));
  relogio();
}
function relogio() {              // tempo desde o início da hunt (ou da gravação), pelo relógio do PC
  const E = D?.estado || {}, ref = E.hunt_comecou || E.desde, mostra = !semResposta && E.gravando && !!ref;
  $('#relogio').style.display = mostra ? '' : 'none';
  if (!mostra) return;
  const [h, m, s] = ref.split(':').map(Number), d = new Date();
  const seg = ((d.getHours() - h) * 3600 + (d.getMinutes() - m) * 60 + d.getSeconds() - s + 86400) % 86400;   // passa da meia-noite
  $('#relogio').textContent = seg >= 3600 ? hms(seg) : hms(seg).slice(3);
}
// ------------------------------------------------------------ monstros (user, 21/09): o programa cataloga sozinho pelo
// TibiaWiki e separa pelas classes do Bestiary; cada monstro é uma linha que abre com o que ele toma, bate e dropa
const CATALOGO = {}, abertos = new Set();
const milhar = v => v == null ? '?' : v.toLocaleString('pt-BR');
const classeToma = p => p == null || p === 100 ? '' : p === 0 ? 'imune' : p > 100 ? 'fraco' : 'resiste';
// a MESMA lista do resumo guardado e dos bichos da capa do histórico (ui/taxas.js = ao_vivo.especies)
const monstrosDaHunt = () => D.area_atual?.especies || Object.keys(especiesDe(voltasVisiveis()));
function pedeMonstro(nome) {      // o servidor devolve do catálogo ou busca no TibiaWiki e guarda
  if (CATALOGO[nome]) return;
  CATALOGO[nome] = {buscando: true};
  fetch('/api/monstro?nome=' + encodeURIComponent(nome)).then(r => r.json())
    .catch(() => ({erro: 'sem resposta do programa'}))
    .then(e => { CATALOGO[nome] = e; renderMonstros(); });
}
const linhaDet = (rot, txt) => { const p = el('p', 'det'); p.append(el('b', null, rot), txt); return p; };
function detalhe(e) {
  const d = el('div', 'detalhe'), grade = el('div', 'toma');
  for (const [elem, p] of Object.entries(e.toma)) {
    const c = el('div', 'elem ' + classeToma(p));
    c.append(elem, el('b', null, p == null ? '?' : p === 0 ? 'imune' : p + '%'));
    grade.append(c);
  }
  d.append(el('div', 'rotulo', 'toma de cada elemento'), grade,
           el('p', 'nota', 'verde = toma mais · âmbar = resiste'));
  const bate = Object.entries(e.bate), loot = Object.entries(e.loot);
  d.append(el('div', 'rotulo', 'bate com'), ...(bate.length ? bate.map(([k, a]) => linhaDet(k, a.join(' · '))) : [el('p', 'nota', 'o wiki não lista ataques')]));
  d.append(el('div', 'rotulo', 'loot'), ...(loot.length ? loot.map(([k, i]) => linhaDet(k, i.join(', '))) : [el('p', 'nota', 'não dropa loot')]));
  const fonte = el('p', 'nota'), a = el('a', null, 'TibiaWiki');
  a.href = e.fonte; a.target = '_blank'; a.rel = 'noopener';
  fonte.append('fonte: ', a, ` · catalogado em ${e.catalogado.split('-').reverse().join('/')}`);
  d.append(fonte);
  return d;
}
function linhaMonstro(nome) {
  const e = CATALOGO[nome], aberto = abertos.has(nome), item = el('div', 'monstro' + (aberto ? ' aberto' : ''));
  const b = el('button', 'linha-monstro'), foto = el('span', 'foto'), txt = el('span', 'txt');
  if (e.gif) { const img = el('img'); img.src = '/monstros/' + e.gif; img.alt = ''; foto.append(img); }
  txt.append(el('span', 'nome', e.nome || nome),
             el('span', 'obs', e.buscando ? 'buscando no TibiaWiki…' : e.erro ? `${e.erro} · clique para tentar de novo` : `${milhar(e.hp)} HP · ${milhar(e.xp)} XP`));
  b.append(foto, txt, el('span', 'seta', e.erro || e.buscando ? '' : aberto ? '▾' : '▸'));
  b.setAttribute('aria-expanded', String(aberto));
  b.onclick = () => {
    if (e.buscando) return;
    if (e.erro) { delete CATALOGO[nome]; pedeMonstro(nome); }
    else if (aberto) abertos.delete(nome); else abertos.add(nome);
    renderMonstros();
  };
  item.append(b);
  if (aberto && e.toma) item.append(detalhe(e));
  return item;
}
function renderMonstros() {
  const nomes = monstrosDaHunt();
  nomes.forEach(pedeMonstro);
  HuntPlanejamento.renderizar();
  $('#monstrosInfo').textContent = nomes.length ? `${nomes.length} espécie${nomes.length > 1 ? 's' : ''} · ${D.area_atual ? 'presença na área atual' : 'clique para abrir'}` : '';
  if (!nomes.length) $('#listaMonstros').replaceChildren(el('p', 'nota', voltasVisiveis().length ? 'Nenhum monstro lido nas voltas fechadas até agora.' : 'Os monstros aparecem quando a primeira volta fechar.'));
  else {
    const grupos = new Map();       // classe do Bestiary → espécies
    for (const n of nomes) {
      const c = CATALOGO[n].categoria || (CATALOGO[n].buscando ? 'buscando' : 'sem classe');
      grupos.set(c, [...(grupos.get(c) || []), n]);
    }
    $('#listaMonstros').replaceChildren(...[...grupos].flatMap(([c, ns]) => [el('div', 'classe', `${c} · ${ns.length}`), ...ns.map(linhaMonstro)]));
  }
  // bicho de outra hunt (user, 22/09): o programa tirou da conta, mas diz quais eram e de onde são
  const fora = Object.entries(D.especies_fora || {});
  if (fora.length) $('#listaMonstros').append(el('p', 'nota', 'Fora da conta, vistos só no caminho ou em poucas voltas: '
    + fora.map(([n, f]) => `${n} (${f.local?.[0] || 'sem local no wiki'})`).join(' · ') + '.'));
}

// ------------------------------------------------------------ histórico das hunts guardadas (user, 23/09)
// "depois da hunt quis fazer a análise dela e não consegui": a sessão já ficava guardada em
// hunt_data/<hunt>/sessoes/, faltava abrir. Uma seção por hunt, um quadrado por sessão com a data
// em cima, e o clique abre o MESMO painel da hunt ao vivo com os dados do disco.
function erroHist(txt) {
  if (HuntPlanejamento.modoDano) $('#recomendacaoMagias').replaceChildren(el('p', 'nota', txt));
  $('.ao-vivo').hidden = true;   // sem painel não há sessão para datar
  $('#huntNome').textContent = 'Histórico';
  $('#huntSub').textContent = txt;
  $('#lista').hidden = false; $('#conteudo').hidden = true;
  $('#lista').replaceChildren(el('p', 'nota', txt));
}
async function abreLista() {
  $('#conteudo').hidden = true; $('#lista').hidden = false;
  let r = null;
  try { r = await (await fetch('/api/historico', {cache: 'no-store'})).json(); } catch { }
  if (!r) return erroHist('Sem resposta do programa: confira no painel de controle se o analisador está ligado.');
  const ss = r.sessoes || [];
  $('#huntNome').textContent = 'Histórico';
  $('#huntSub').textContent = ss.length
    ? `${ss.length} ${ss.length > 1 ? 'sessões guardadas' : 'sessão guardada'} · clique num quadrado para abrir a análise dela`
    : 'nenhuma hunt guardada ainda';
  HuntHistorico.renderizar(ss);
}
async function abreSessao(id) {
  let d = null;
  try { d = await (await fetch('/api/historico/' + id, {cache: 'no-store'})).json(); } catch { }
  if (!d?.estado) return erroHist(d?.erro ? `Esta hunt não está mais guardada (${d.erro}).` : 'Sem resposta do programa ao abrir a hunt guardada.');
  D = Object.fromEntries(Object.entries(VAZIO).map(([k, v]) => [k, d[k] ?? v]));
  D.voltas = D.voltas.filter(v => (v.tipo || 'volta') === 'volta');
  await aplicaAjustesMapa(D);
      await carregaFundos();
  mostradas = D.voltas.length;
  tudo();
}
async function modoHistorico() {   // a tela inteira em leitura: nada aqui grava nem consulta o jogo
  $('#navHunt').classList.remove('ativo'); if (!HuntPlanejamento.modoDano) $('#navHist').classList.add('ativo');
  $('.cabeca .rotulo').textContent = '— histórico';
  $('#jogo').hidden = true; $('#btnReiniciar').hidden = true; $('#btnHunt').hidden = true;
  $('#btnVoltarHist').hidden = !HIST;
  $('.ao-vivo').hidden = !HIST;
  return HIST ? abreSessao(HIST) : abreLista();
}

function tudo(novaN) {
  renderCabeca(); renderFiltros(); renderTiles(); renderTempo();
  const cels = renderMapas();
  renderPainel(); renderMonstros(); renderHistorico(novaN); renderTabela(cels);
}

// ------------------------------------------------------------ prévia: simula as voltas fechando
document.querySelectorAll('[data-previa]').forEach(b => b.onclick = () => {
  const alvo = b.dataset.previa, antes = mostradas;
  mostradas = alvo === 'todas' ? D.voltas.length : alvo === '+1' ? Math.min(D.voltas.length, mostradas + 1) : Number(alvo);
  selN = null; if (!mostradas) recorte = 'sessao';
  tudo(mostradas > antes ? D.voltas[mostradas - 1].n : null);
});
let inicioRelogio = Date.now();
setInterval(() => {
  if (!PREVIA) return relogio();
  const s = Math.floor((Date.now() - inicioRelogio) / 1000) + 47; $('#relogio').textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}, 1000);

const fundos = {}, fundoSrc = {};
function carregaFundos() {        // só baixa o fundo do andar que chegou novo ou mudou
  return Promise.all(Object.entries(D.andares).filter(([z, A]) => A.fundo && fundoSrc[z] !== A.fundo).map(([z, A]) => new Promise(ok => {
    const i = new Image();
    i.onload = () => { fundos[z] = i; fundoSrc[z] = A.fundo; ok(); };
    i.onerror = ok;
    i.src = A.fundo;
  })));
}
window.addEventListener('resize', () => D && renderMapas());
ligaDica('perm'); ligaDica('dens');

// ------------------------------------------------------------ ao vivo: pergunta ao programa a cada 5 s
const VAZIO = {estado: null, sessao: {}, andares: {}, voltas: [], amostras: [],
               refis: [], refil: {}, trechos: [], entradas: [], especies_fora: {}, ks: {}, sessoes_origem: [], intervalos_gravacao: [], area_atual: null, areas_hunt: []};
const ajustesMapa=fetch('/ui/mapa_ajustes.json',{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({}));
async function aplicaAjustesMapa(dados){
  const ajuste=(await ajustesMapa).sessoes?.[dados.estado?.sessao];
  if(!ajuste||ajuste.char!==dados.sessao?.char)return dados;
  const porTempo=new Map(ajuste.correcoes.map(c=>[c.t,c]));
  dados.amostras=dados.amostras.map(a=>{const c=porTempo.get(a[0]);return c&&c.antes.every((n,i)=>n===a[i+1])?[a[0],...c.depois,...a.slice(4)]:a;});
  for(const [z,A] of Object.entries(ajuste.andares||{}))if(dados.andares[z])dados.andares[z]=A;
  return dados;
}
let semResposta = false, assinatura = null, desligou = false;
async function busca() {
  if (desligou) return;
  try {
    let novo = null;
    try { novo = await (await fetch('/api/hunt', {cache: 'no-store'})).json(); } catch { }
    semResposta = !novo?.estado;
    if (novo?.estado) {             // campo null vira vazio; sem resposta: fica com o que tem
      D = Object.fromEntries(Object.entries(VAZIO).map(([k, v]) => [k, novo[k] ?? v]));
      // deslocamento e refil não são volta (user, 22/09): o motor já separa, isto é a garantia da tela
      D.voltas = D.voltas.filter(v => (v.tipo || 'volta') === 'volta');
      await aplicaAjustesMapa(D);
      await carregaFundos();
    }
    else D = D || VAZIO;
    const antes = mostradas, v = D.voltas, fim = v.length ? v[v.length - 1].fim : -1;
    // só o que aparece na tela: amostra depois da última volta fechada não entra nos mapas, então não redesenha
    const sig = JSON.stringify([v.length, v[v.length - 1], D.amostras.filter(a => a[0] <= fim).length, Object.keys(D.andares), D.sessao]);
    mostradas = v.length;
    if (sig !== assinatura) {
      // volta nova não tira a volta escolhida (user, 21/09): sem escolha (selN null), o card já segue a mais nova
      const nova = assinatura != null && mostradas > antes;   // na 1ª leitura nada entra animado
      tudo(nova ? v[mostradas - 1].n : null);
      assinatura = sig;                                       // só depois do desenho: se falhar, tenta de novo
    } else renderCabeca();                                    // só o estado mudou (jogo, frames, relógio)
  } catch (e) {
    console.error(e);                                         // um desenho que falha não pode parar a consulta
  } finally {
    setTimeout(busca, 5000);
  }
}

let tToast = null;
function aviso(txt) {     // resposta do programa a um botão, sem travar a tela com um alert
  const t = $('#toast');
  t.textContent = txt; t.hidden = false;
  clearTimeout(tToast); tToast = setTimeout(() => t.hidden = true, 9000);
}
// reiniciar a análise (user, 22/09): fecha a sessão, guarda o histórico e volta a esperar a hunt —
// antes disso só dava para fechar e abrir o programa, e aí ele retomava a mesma sessão errada
$('#btnReiniciar').onclick = async () => {
  if (PREVIA) return aviso('Esta é a prévia do design: aqui o botão não reinicia nada.');
  if (!confirm('Reiniciar a análise?\n\nA sessão de agora é fechada e guardada no histórico, e o programa começa outra do zero, esperando a hunt começar de novo. A gravação continua ligada.')) return;
  let r = null;
  try { r = await (await fetch('/api/reiniciar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})).json(); } catch { }
  if (!r) return aviso('Sem resposta do programa: a análise não reiniciou.');
  if (!r.ok) return aviso(`Não deu para reiniciar: ${r.erro || 'o programa não disse o motivo'}.`);
  D = null; mostradas = 0; selN = null; recorte = 'sessao'; assinatura = null; abertos.clear();
  aviso(`Análise reiniciada na sessão ${r.sessao}. A tela volta a esperar a hunt começar; a sessão anterior ficou guardada no histórico.`);
};

// iniciar/encerrar a hunt (user, 24/09): "hoje eu tive que desligar, o programa fechou, para depois
// abrir novamente". Encerrar para a gravação e guarda a sessão; Iniciar abre uma sessão NOVA (a de
// menos de 1 h só é retomada quando o programa sobe sozinho, não quando alguém pediu hunt nova).
$('#btnHunt').onclick = async () => {
  if (PREVIA) return aviso('Esta é a prévia do design: aqui o botão não grava nada.');
  const ligar = !D?.estado?.ativo;
  if (!ligar && !confirm('Encerrar a hunt?\n\nA gravação para e a sessão é guardada no histórico. O programa continua aberto: é só clicar em Iniciar hunt quando quiser gravar de novo.')) return;
  const b = $('#btnHunt');
  b.disabled = true;
  let r = null;
  try { r = await (await fetch('/api/gravacao', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ligar})})).json(); } catch { }
  b.disabled = false;
  if (!r) return aviso('Sem resposta do programa.');
  if (!r.ok) return aviso(`Não deu para ${ligar ? 'iniciar' : 'encerrar'}: ${r.erro || 'o programa não disse o motivo'}.`);
  D = null; mostradas = 0; selN = null; recorte = 'sessao'; assinatura = null; abertos.clear();
  aviso(ligar ? `Gravando de novo na sessão ${r.sessao}. A tela espera a hunt começar.`
              : 'Hunt encerrada e guardada no histórico. Clique em Iniciar hunt para gravar a próxima.');
};

$('#btnDesligar').onclick = async () => {    // igual ao da calibração
  if (PREVIA) return;
  if (!confirm('Desligar o analisador? Todos os processos dele serão encerrados.')) return;
  desligou = true;
  await fetch('/api/desligar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}).catch(() => null);
  $('#desligado').classList.add('on');
};

HuntPlanejamento.iniciar();
(async () => {
  if (HIST !== null) return modoHistorico();   // ?h = histórico guardado, sem consultar a hunt ao vivo
  const mock = PREVIA && await fetch('/ui/mock_hunt.json').catch(() => null);
  if (!mock?.ok) { PREVIA = false; return busca(); }   // sem o mock (instalação dos amigos): a tela de verdade
  $('.previa').hidden = false;
  $('#btnDesligar').title = 'Na prévia este botão não desliga nada';
  $('#jogo').replaceChildren(el('span', 'dot on'), 'RubinOT aberto · prévia');
  D = await mock.json();
  await aplicaAjustesMapa(D);
      await carregaFundos();
  mostradas = 0;
  tudo();
})();

})();
