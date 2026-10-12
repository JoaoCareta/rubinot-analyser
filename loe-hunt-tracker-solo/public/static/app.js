// Telas do tracker. Carrega /api/dados uma vez e desenha a tela pelo endereco.
import { VAZIO, coord, dec, dur, fmtN, hm, kkC, kkh, num, pct, seg } from './fmt.js';

const DIA_S = 86400;

const el = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

let D = null;                              // tudo o que veio do banco
let ordemZona = { k: 'rank', asc: true };  // ordenacao da tabela de zonas

// filtro da visao geral — datas em ISO "AAAA-MM-DD" (comparacao de texto funciona)
let fDe = null, fAte = null, fHunt = '';
let calAberto = false, calMes = null, calPasso = 0, docOuvindo = false;

// imagens prontas da pasta de relatorios, por cave
const MAPAS = {
  ingol: [
    ['mapa_volta_ingol.png', 'O caminho de uma volta'],
    ['caminho_comum_ingol.png', 'Por onde ele mais passou'],
  ],
};

// vocacao do banco -> sigla e nome por extenso, como no site da pt
const VOC = { druid: ['ED', 'Elder Druid'], paladin: ['RP', 'Royal Paladin'] };

// outfits locais em public/assets — nenhuma URL externa
const OUTFITS = {
  'Hetero afeminado': '/assets/hetero_afeminado.png',
  'Traps the cat': '/assets/traps_the_cat.gif',
};

/* ---------- atalhos sobre os dados ---------- */
const sessaoDe = (id) => D.sessoes.find((s) => s.id === id) ?? null;
const voltasDe = (id) => D.voltas.filter((v) => v.sessao_id === id);
const zonasDe = (id) => D.zonas.filter((z) => z.sessao_id === id);
const boxesDe = (id) => D.boxes.filter((b) => b.sessao_id === id);
const abatesDe = (id) => D.abates.filter((a) => a.sessao_id === id);
const dataBR = (iso) => String(iso ?? '').split('-').reverse().join('/');
const especieRotulo = (e) => (e === '?' ? 'não identificada' : e);

/** Nivel de agora: o fim da ultima sessao vale mais que a coluna estatica. */
function nivelAtual(p) {
  const ultima = D.sessoes.find((s) => s.personagem_id === p.id);
  return { n: ultima?.nivel_fim ?? p.nivel, medido: ultima?.nivel_fim != null };
}

/**
 * O filtro da visao geral, puro para o check.js conferir a contagem.
 * Datas em ISO; hunt e o slug ('' = todas).
 */
export function filtra(sessoes, { de = null, ate = null, hunt = '' } = {}) {
  return sessoes.filter((s) => {
    if (hunt && s.hunt_slug !== hunt) return false;
    if (de && s.data < de) return false;
    if (ate && s.data > ate) return false;
    return true;
  });
}

/**
 * Media de varias sessoes da mesma cave. Cada taxa usa so as horas das sessoes
 * que TEM o valor — misturar horas de sessao sem painel diluiria o numero.
 * Onde nenhuma sessao tem o valor, devolve null — e "—" na tela, nao "0/h".
 */
function medidaDaCave(huntId) {
  const ss = D.sessoes.filter((s) => s.hunt_id === huntId);
  if (!ss.length) return null;
  const min = ss.reduce((a, s) => a + (num(s.minutos) ?? 0), 0);
  const porHora = (k) => {
    const uteis = ss.filter((s) => num(s[k]) !== null && num(s.minutos) !== null);
    const horas = uteis.reduce((a, s) => a + num(s.minutos), 0) / 60;
    return horas ? uteis.reduce((a, s) => a + num(s[k]), 0) / horas : null;
  };
  const pesada = (k) => {
    const uteis = ss.filter((s) => num(s[k]) !== null && num(s.minutos) !== null);
    const peso = uteis.reduce((a, s) => a + num(s.minutos), 0);
    return peso ? uteis.reduce((a, s) => a + num(s[k]) * num(s.minutos), 0) / peso : null;
  };
  return {
    sessoes: ss.length,
    minutos: min,
    profit_h: porHora('profit'),
    kills_h: porHora('kills'),
    xp_h: pesada('xp_raw_h_mediana'),
    supplies_h: pesada('supplies_h'),
    dano_por_bicho: pesada('dano_por_bicho'),
    ks_pct: pesada('ks_pct'),
  };
}

/** Buracos entre o fim de uma volta e o inicio da seguinte (refill, pausa). */
function paradas(voltas) {
  const out = [];
  for (let i = 1; i < voltas.length; i++) {
    const a = seg(voltas[i - 1].fim);
    const b = seg(voltas[i].inicio);
    if (a === null || b === null) continue;
    // so temos a hora do relogio: hunt que passa da meia-noite daria diferenca negativa
    const gap = b - a < 0 ? b - a + DIA_S : b - a;
    if (gap >= 60) out.push({ depois: voltas[i - 1].numero, antes: voltas[i].numero, s: gap });
  }
  return out;
}

/* ---------- pedacos de tela ---------- */
function cartao(lab, val, hint, cor) {
  return `<div class="kpi"><div class="lab">${esc(lab)}</div>`
    + `<div class="val${cor ? ' ' + cor : ''}">${esc(val)}</div>`
    + (hint ? `<div class="hint">${esc(hint)}</div>` : '') + '</div>';
}

const st = (lab, val, largo) =>
  `<div class="st${largo ? ' st-wide' : ''}"><span class="lbl">${esc(lab)}</span><span class="v">${esc(val)}</span></div>`;

/** Fundo proporcional na celula, para comparar a olho sem gráfico. */
function barra(v, max) {
  // v null = sem medicao: sem barrinha (Number(null) seria 0 e ganharia os 2% minimos)
  if (!max || v === null || !Number.isFinite(Number(v))) return '';
  const p = Math.max(2, Math.min(100, Math.round((100 * Number(v)) / max)));
  return ` style="background:linear-gradient(90deg, color-mix(in srgb,var(--accent) 20%,transparent) ${p}%, transparent ${p}%)"`;
}

function navegacao(tela, sid) {
  const itens = [['/', 'Visão geral', 'inicio']];
  if (sid) {
    itens.push([`/sessao/${sid}`, 'Sessão', 'sessao']);
    // so aponta para o que a sessao tem — link para tela vazia e convite a beco
    if (zonasDe(sid).length) itens.push([`/sessao/${sid}/zonas`, 'Zonas', 'zonas']);
    if (boxesDe(sid).length) itens.push([`/sessao/${sid}/boxes`, 'Boxes travadas', 'boxes']);
  }
  return `<nav class="nav">${itens
    .map(([href, txt, k]) => `<a href="${href}"${k === tela ? ' class="on" aria-current="page"' : ''}>${esc(txt)}</a>`)
    .join('')}</nav>`;
}

function cabecalho(eyebrow, titulo, sub, tela, sid) {
  el('hd').innerHTML = `<div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(titulo)}</h1>`
    + `<p class="sub">${esc(sub)}</p></div>${navegacao(tela, sid)}`;
}

function galeria(slug) {
  const fotos = MAPAS[slug] || [];
  if (!fotos.length) return '';
  return `<section class="panel"><h2>Mapas da volta</h2>`
    + `<p class="cap">Imagens já geradas pelo analisador. Clique para abrir em tamanho cheio.</p>`
    + `<div class="shots">${fotos.map(([arq, leg]) => `<a class="shot" href="/img/${arq}" target="_blank" rel="noopener">`
      + `<img src="/img/${arq}" alt="${esc(leg)}" loading="lazy">`
      + `<span class="cap2"><span>${esc(leg)}</span><span>${esc(arq)}</span></span></a>`).join('')}</div></section>`;
}

/**
 * Grafico de barras em SVG, desenhado a mao como no site da pt — zero lib.
 * valores pode ter null (vira buraco, nao zero); tooltip nativo via <title>.
 */
function grafBarras(rotulos, valores, fmt, cor) {
  const W = 560, H = 230, P = { t: 18, r: 20, b: 34, l: 64 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const n = rotulos.length;
  const uteis = valores.filter((v) => v !== null);
  if (!uteis.length) return '';
  let mx = Math.max(...uteis, 0), mn = Math.min(...uteis, 0);
  if (mx === mn) mx = mn + Math.max(1, Math.abs(mn));
  const folga = (mx - mn) * 0.18;
  mx += folga;
  if (mn < 0) mn -= folga;
  const X = (i) => P.l + (n <= 1 ? iw / 2 : (iw * i) / (n - 1));
  const Y = (v) => P.t + ih * (1 - (v - mn) / (mx - mn));
  let g = '';
  for (let t = 0; t <= 4; t++) {
    const val = mn + ((mx - mn) * t) / 4, y = Y(val);
    g += `<line x1="${P.l}" y1="${y.toFixed(1)}" x2="${W - P.r}" y2="${y.toFixed(1)}" stroke="var(--grid)"/>`;
    g += `<text x="${P.l - 8}" y="${(y + 3.5).toFixed(1)}" text-anchor="end" font-size="10.5">${esc(fmt(val))}</text>`;
  }
  if (mn < 0) {
    const y0 = Y(0);
    g += `<line x1="${P.l}" y1="${y0.toFixed(1)}" x2="${W - P.r}" y2="${y0.toFixed(1)}" stroke="var(--axis)" stroke-width="1.4"/>`;
  }
  const passo = n > 8 ? Math.ceil(n / 6) : 1;
  for (let i = 0; i < n; i++) {
    if (i % passo !== 0 && i !== n - 1) continue;
    g += `<text x="${X(i).toFixed(1)}" y="${H - 12}" text-anchor="middle" font-size="10">${esc(rotulos[i])}</text>`;
  }
  const base = Y(mn < 0 ? 0 : mn);
  const bw = Math.min(n <= 1 ? iw * 0.5 : (iw / n) * 0.62, 46);
  valores.forEach((v, i) => {
    if (v === null) return;
    const yv = Y(v), topo = Math.min(yv, base), h = Math.max(Math.abs(yv - base), 1);
    const cx = X(i), r = Math.min(4, h / 2, bw / 2);
    g += `<rect x="${(cx - bw / 2).toFixed(1)}" y="${topo.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}"`
      + ` rx="${r.toFixed(1)}" fill="${cor}"><title>${esc(rotulos[i])}: ${esc(fmt(v))}</title></rect>`;
  });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img">${g}</svg>`;
}

/* ---------- filtro: calendario e rotulos ---------- */
function isoHoje() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
const ddmm = (iso) => iso.slice(8, 10) + '/' + iso.slice(5, 7);

function periodoRotulo() {
  if (!fDe && !fAte) return 'todo o histórico';
  const f = fDe ? ddmm(fDe) : '…', t = fAte ? ddmm(fAte) : '…';
  return f === t ? f : `${f} – ${t}`;
}

function mesDaUltima() {
  const iso = D.sessoes[0]?.data ?? isoHoje();
  return new Date(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, 1);
}

function calPick(iso) {
  if (calPasso === 0) {           // 1o clique: ancora um dia e deixa aberto
    fDe = iso; fAte = iso; calPasso = 1;
  } else {                        // 2o clique: fecha o intervalo (mesmo dia = um dia so)
    if (iso < fDe) { fAte = fDe; fDe = iso; } else { fAte = iso; }
    calPasso = 0; calAberto = false;
  }
  telaInicio();
}

function calendario() {
  const dias = new Set(D.sessoes.map((s) => s.data));
  const y = calMes.getFullYear(), m = calMes.getMonth();
  const titulo = calMes.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  const dow0 = new Date(y, m, 1).getDay();
  const nDias = new Date(y, m + 1, 0).getDate();
  const hoje = isoHoje();
  let cels = '';
  for (let i = 0; i < dow0; i++) cels += '<div class="cal-cell"></div>';
  for (let d = 1; d <= nDias; d++) {
    const iso = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const cls = ['cal-cell', 'cal-day'];
    if (dias.has(iso)) cls.push('cal-hunt');
    if (fDe && fAte && iso >= fDe && iso <= fAte) cls.push('cal-sel');
    if (iso === fDe || iso === fAte) cls.push('cal-end');
    if (iso === hoje) cls.push('cal-today');
    cels += `<button type="button" class="${cls.join(' ')}" data-iso="${iso}">${d}</button>`;
  }
  return `<div class="cal-head"><button type="button" class="cal-nav" data-nav="-1" aria-label="Mês anterior">‹</button>`
    + `<span class="cal-title">${esc(titulo)}</span>`
    + `<button type="button" class="cal-nav" data-nav="1" aria-label="Próximo mês">›</button></div>`
    + `<div class="cal-dow"><span>D</span><span>S</span><span>T</span><span>Q</span><span>Q</span><span>S</span><span>S</span></div>`
    + `<div class="cal-grid">${cels}</div>`
    + `<div class="cal-foot"><span class="cal-legend"><span class="cal-dot"></span>dia com hunt</span>`
    + `<button type="button" class="cal-clear" id="calClear">Limpar</button></div>`;
}

/* ---------- tela: visao geral ---------- */
function telaInicio() {
  const lista = filtra(D.sessoes, { de: fDe, ate: fAte, hunt: fHunt });
  const nSess = D.sessoes.length;
  cabecalho(
    'Solo Hunt Tracker',
    D.grupo?.nome ?? 'Johanes Characters',
    `${D.personagens.length} personagens, ${D.hunts.length} caves e `
    + `${nSess} ${nSess === 1 ? 'sessão gravada' : 'sessões gravadas'}.`,
    'inicio', null,
  );

  const integrantes = `<section class="panel">`
    + `<div class="panel-head"><div><h2>Integrantes</h2></div></div>`
    + `<div class="members-row">${D.personagens.map((p) => {
      const [sigla, cheio] = VOC[p.vocacao] ?? [p.vocacao, p.vocacao];
      const nv = nivelAtual(p);
      const origem = nv.medido ? 'nível medido no fim da última sessão' : 'nível informado à mão';
      return `<div class="member-card" title="${esc(`${cheio} · ${origem}`)}">`
        + `<div class="member-sprite"><img src="${esc(OUTFITS[p.nome] ?? '')}" alt=""></div>`
        + `<div class="member-info"><div class="member-name">${esc(p.nome)}</div>`
        + `<div class="member-voc">${esc(sigla)} · Lvl ${esc(String(nv.n))}</div></div></div>`;
    }).join('')}</div></section>`;

  const opcoes = D.hunts.map((h) =>
    `<option value="${esc(h.slug)}"${h.slug === fHunt ? ' selected' : ''}>${esc(h.nome)}</option>`).join('');
  const filtroBarra = `<section class="filterbar">`
    + `<div class="fb-row1">`
    + `<div class="fseg"><button type="button" id="fTudo"${!fDe && !fAte ? ' class="on"' : ''}>Tudo</button></div>`
    + `<div class="fdate">`
    + `<button type="button" class="cal-btn" id="calBtn" aria-label="Abrir calendário" aria-expanded="${calAberto}">📅</button>`
    + `<span class="fdate-lbl">De</span><span class="fdate-val">${fDe ? ddmm(fDe) : VAZIO}</span>`
    + `<span class="fdate-lbl">até</span><span class="fdate-val">${fAte ? ddmm(fAte) : VAZIO}</span>`
    + `<div class="cal-pop" id="calPop"${calAberto ? '' : ' hidden'}>${calAberto ? calendario() : ''}</div>`
    + `</div>`
    + `<label class="loc-filter">Hunt <select id="locFilter"><option value="">Todas</option>${opcoes}</select></label>`
    + `</div>`
    + `<div class="fsess-btn"><b>${lista.length}</b> / ${nSess} sessões</div>`
    + `</section>`;

  const somaSe = (k) => {
    const vs = lista.map((s) => num(s[k])).filter((v) => v !== null);
    return vs.length ? vs.reduce((a, v) => a + v, 0) : null;
  };
  const minTot = lista.reduce((a, s) => a + (num(s.minutos) ?? 0), 0);
  const melhor = lista.reduce((a, s) =>
    (a === null || (num(s.profit_h) ?? -Infinity) > (num(a.profit_h) ?? -Infinity) ? s : a), null);
  const temMelhor = melhor !== null && num(melhor.profit_h) !== null;
  const lucro = somaSe('profit');
  const huntSel = fHunt ? D.hunts.find((h) => h.slug === fHunt)?.nome : '';
  const kpis = `<section class="kpis">`
    + cartao('Sessões no período', String(lista.length), periodoRotulo() + (huntSel ? ` · ${huntSel}` : ''))
    + cartao('Tempo de hunt', lista.length ? hm(minTot) : VAZIO, 'somando as sessões filtradas')
    + cartao('Lucro somado', kkC(lucro),
      lucro === null ? 'nenhuma sessão com painel medido no filtro' : 'só as sessões com painel medido', 'pos')
    + cartao('Melhor lucro por hora', temMelhor ? kkh(melhor.profit_h) : VAZIO,
      temMelhor ? `${melhor.hunt}, ${dataBR(melhor.data)}` : 'sem sessão com painel no filtro', 'pos')
    + `</section>`;

  // a classe de cor entra so quando ha numero: "—" pintado de verde confunde
  const cel = (txt, cls) => `<td class="${txt === VAZIO ? '' : cls || ''}">${esc(txt)}</td>`;
  const linhasSess = lista.map((s) => `<tr class="sess-row" data-sid="${s.id}">`
    + `<td class="txt"><a href="/sessao/${s.id}">${esc(dataBR(s.data))}</a></td>`
    + `<td class="txt">${esc(s.personagem)}</td>`
    + `<td class="txt">${esc(s.hunt)}</td>`
    + `<td>${esc(hm(s.minutos))}</td>`
    + cel(kkC(s.loot))
    + cel(kkC(s.supplies), 'neg')
    + cel(kkC(s.profit), (num(s.profit) ?? 0) < 0 ? 'neg' : 'pos')
    + cel(kkh(s.profit_h), (num(s.profit_h) ?? 0) < 0 ? 'neg' : 'pos')
    + cel(kkh(s.xp_raw_h_mediana))
    + `</tr>`).join('');

  const sessoes = `<section class="panel">`
    + `<div class="panel-head"><div><h2>Sessões</h2>`
    + `<p class="cap">Clique na linha para abrir a sessão. Loot, gastos e lucro vêm do painel do jogo; `
    + `onde está "—" o painel daquela sessão não foi capturado.</p></div></div>`
    + (lista.length
      ? `<div class="scroll"><table id="sessTbl"><thead><tr><th>Data</th><th>Personagem</th><th>Hunt</th>`
        + `<th>Tempo</th><th>Loot</th><th>Gastos</th><th>Lucro</th><th>Lucro por hora</th>`
        + `<th>Experiência por hora</th></tr></thead><tbody>${linhasSess}</tbody></table></div>`
      : `<div class="empty">nenhuma sessão no período escolhido</div>`)
    + `<p class="foot-star">* valores referentes a ${esc(periodoRotulo())}${huntSel ? `, só ${esc(huntSel)}` : ''}.</p>`
    + `</section>`;

  const arred = (v) => (num(v) === null ? null : Math.round(num(v)));
  const linhasCave = D.hunts.map((h) => {
    const m = medidaDaCave(h.id);
    const nome = `${esc(h.nome)}${m ? '' : ' <span class="tag">sem medição</span>'}`;
    return `<tr${m ? '' : ' class="fora"'}>`
      + `<td class="txt">${nome}</td>`
      + `<td>${esc(h.andar ?? VAZIO)}</td>`
      + `<td>${esc(h.dur_tipica_s ? dur(h.dur_tipica_s) : VAZIO)}</td>`
      + cel(kkh(m?.profit_h), 'pos')
      + cel(kkh(m?.xp_h))
      + cel(fmtN(arred(m?.kills_h)))
      + cel(kkh(m?.supplies_h), 'neg')
      + cel(fmtN(arred(m?.dano_por_bicho)))
      + cel(pct(m?.ks_pct))
      + `</tr>`;
  }).join('');

  const historico = D.hunts.filter((h) => h.ks_historico)
    .map((h) => `<p class="nota"><b>${esc(h.nome)}:</b> ${esc(h.ks_historico)}</p>`).join('');

  const caves = `<section class="panel"><h2>Comparativo das caves</h2>`
    + `<p class="cap">Cada taxa usa só as sessões que mediram aquele valor — sessão sem painel não `
    + `dilui a conta. Onde está "—" ninguém mediu.</p>`
    + `<div class="scroll"><table><thead><tr><th>Cave</th><th>Andar</th><th>Volta típica</th>`
    + `<th>Lucro por hora</th><th>Experiência por hora</th><th>Abates por hora</th>`
    + `<th>Gastos por hora</th><th>Dano por bicho</th><th>Bicho roubado</th>`
    + `</tr></thead><tbody>${linhasCave}</tbody></table></div>`
    + (historico ? `<div style="margin-top:14px">${historico}</div>` : '')
    + `<p class="foot-star">* "bicho roubado" é a parte dos abates que outro jogador levou (KS). `
    + `Onde está "—" é porque ninguém contou: a fonte só anotou por escrito o que viu, `
    + `sem chegar a um número.</p>`
    + `</section>`;

  el('app').innerHTML = integrantes + filtroBarra + kpis + sessoes + caves;

  /* ---- fios da barra de filtros (a tela e redesenhada a cada mudanca) ---- */
  el('fTudo')?.addEventListener('click', () => { fDe = null; fAte = null; calPasso = 0; telaInicio(); });
  el('calBtn')?.addEventListener('click', () => {
    calAberto = !calAberto;
    if (calAberto) {
      const ref = fAte || fDe;
      calMes = ref ? new Date(Number(ref.slice(0, 4)), Number(ref.slice(5, 7)) - 1, 1) : mesDaUltima();
      calPasso = 0;
    }
    telaInicio();
  });
  el('calPop')?.addEventListener('click', (e) => {
    const nav = e.target.closest?.('[data-nav]');
    if (nav) {
      calMes = new Date(calMes.getFullYear(), calMes.getMonth() + Number(nav.dataset.nav), 1);
      return telaInicio();
    }
    if (e.target.closest?.('#calClear')) { fDe = null; fAte = null; calPasso = 0; return telaInicio(); }
    const dia = e.target.closest?.('[data-iso]');
    if (dia) calPick(dia.dataset.iso);
  });
  el('locFilter')?.addEventListener('change', (e) => { fHunt = e.target.value; telaInicio(); });
  el('sessTbl')?.addEventListener('click', (e) => {
    if (e.target.closest?.('a')) return; // o link da data ja navega sozinho
    const tr = e.target.closest?.('tr[data-sid]');
    if (tr) location.href = `/sessao/${tr.dataset.sid}`;
  });
  if (!docOuvindo && typeof document.addEventListener === 'function') {
    docOuvindo = true;
    // clique fora fecha o calendario, como no site da pt
    document.addEventListener('click', (e) => {
      if (calAberto && !e.target.closest?.('.fdate')) { calAberto = false; calPasso = 0; telaInicio(); }
    });
  }
}

/* ---------- tela: sessao ---------- */
function telaSessao(sid) {
  const s = sessaoDe(sid);
  if (!s) return semSessao(sid);

  const [de, ate] = String(s.janela || '').split(' - ');
  const [sigla] = VOC[s.vocacao] ?? [s.vocacao];
  cabecalho(
    `sessão · ${dataBR(s.data)}`, s.hunt,
    `${s.personagem} (${sigla})`
    + (s.nivel_ini !== null ? `, nível ${s.nivel_ini} no começo` : '')
    + (de && ate ? ` · das ${de} às ${ate}` : ''),
    'sessao', sid,
  );

  const kpis = [
    cartao('Loot', kkC(s.loot), s.loot === null ? 'painel não capturado' : 'painel do jogo', 'pos'),
    cartao('Gastos', kkC(s.supplies), s.supplies === null ? 'painel não capturado' : 'poção e munição', 'neg'),
    cartao('Balanço', kkC(s.balance), s.balance === null ? 'sem medição no painel' : 'loot menos gastos',
      (num(s.balance) ?? 0) < 0 ? 'neg' : 'pos'),
    cartao('Lucro por hora', kkh(s.profit_h),
      s.profit_h === null ? 'sem medição' : `lucro de ${kkC(s.profit)} em ${hm(s.minutos)}`,
      (num(s.profit_h) ?? 0) < 0 ? 'neg' : 'pos'),
    cartao('Abates', fmtN(s.kills),
      s.kills === null ? 'sem contagem confiável no chat' : `${fmtN(s.kills_h)} por hora, contagem do chat`),
    cartao('Experiência por hora', kkh(s.xp_raw_h_mediana),
      s.xp_raw_h_mediana === null ? 'sem medição' : 'painel do jogo'),
  ];
  if (s.nivel_ini !== null && s.nivel_fim !== null) {
    const subiu = s.nivel_fim - s.nivel_ini;
    kpis.push(cartao('Nível', `${s.nivel_ini} → ${s.nivel_fim}`, subiu > 0 ? `subiu ${subiu}` : 'sem mudança'));
  }
  if (s.dano_por_bicho !== null) {
    kpis.push(cartao('Dano por bicho', fmtN(s.dano_por_bicho), 'quanto ele levou por bicho morto'));
  }
  kpis.push(cartao('Bicho roubado', pct(s.ks_pct),
    num(s.ks_pct) === null ? 'não foi contado nesta sessão' : 'quanto outro jogador levou (KS)'));
  const topo = `<section class="kpis">${kpis.join('')}</section>`;

  el('app').innerHTML = topo + secaoBichos(sid, s) + secaoVoltas(sid, s) + galeria(s.hunt_slug);
}

/** Bichos abatidos por especie, com grafico de barras como no site da pt. */
function secaoBichos(sid, s) {
  const as = abatesDe(sid);
  if (!as.length) return '';
  const FONTES = {
    loot_corpo: 'contagem pelos corpos saqueados, volta a volta',
    xp_chat: 'contagem pelo chat de experiência, que fica abaixo do real',
  };
  const svg = grafBarras(as.map((a) => especieRotulo(a.especie)), as.map((a) => a.abates),
    (v) => fmtN(Math.round(v)), 'var(--accent)');
  const linhas = as.map((a) => `<tr><td class="txt">${esc(especieRotulo(a.especie))}</td>`
    + `<td>${esc(fmtN(a.abates))}</td><td>${esc(pct(a.pct))}</td></tr>`).join('');
  const somaEsp = as.reduce((a, x) => a + x.abates, 0);
  const difere = s.kills !== null && somaEsp !== s.kills;
  return `<section class="panel"><h2>Bichos abatidos</h2>`
    + `<p class="cap">Por espécie — ${esc(FONTES[as[0].fonte] ?? as[0].fonte)}.</p>`
    + svg
    + `<div class="scroll"><table><thead><tr><th>Espécie</th><th>Abates</th><th>%</th></tr></thead>`
    + `<tbody>${linhas}<tr style="font-weight:700"><td class="txt">Total</td>`
    + `<td>${esc(fmtN(somaEsp))}</td><td>100,0%</td></tr></tbody></table></div>`
    + (difere
      ? `<p class="foot-star">* as espécies somam ${esc(fmtN(somaEsp))} e o total da sessão é `
        + `${esc(fmtN(s.kills))}: as duas contagens vêm de leituras diferentes.</p>`
      : '')
    + `</section>`;
}

/** Graficos por volta + tabela volta a volta; ou o aviso de que nao ha volta a volta. */
function secaoVoltas(sid, s) {
  const vs = voltasDe(sid);
  if (!vs.length) {
    return `<section class="panel"><h2>Volta a volta</h2>`
      + `<div class="empty">sem volta a volta (frames apagados) — só os totais do painel desta sessão</div>`
      + `</section>`;
  }

  const temRaw = vs.some((v) => v.xp_raw !== null);
  const temChat = !temRaw && vs.some((v) => v.xp_chat !== null);
  const xpDe = (v) => (temRaw ? v.xp_raw : v.xp_chat);
  const rotuloXp = temRaw ? 'Experiência' : 'Experiência (chat, com bônus)';
  const temDano = vs.some((v) => v.dano_tomado !== null);
  const temBattle = vs.some((v) => v.battle_medio !== null);
  const temRot = vs.some((v) => v.rotacao !== null);

  // graficos: a volta descartada vira buraco, nao barra
  const rotulos = vs.map((v) => (v.inicio ? v.inicio.slice(0, 5) : '#' + v.numero));
  const gLucro = grafBarras(rotulos, vs.map((v) => (v.descartada ? null : num(v.profit))), kkC, 'var(--accent)');
  const gXp = (temRaw || temChat)
    ? grafBarras(rotulos, vs.map((v) => (v.descartada ? null : num(xpDe(v)))), kkC, 'var(--accent-2)')
    : '';
  const graficos = (gLucro || gXp)
    ? `<section class="panel"><h2>Gráficos por volta</h2>`
      + `<p class="cap">A volta descartada fica de fora.`
      + `${temChat ? ' A experiência aqui vem do chat e já inclui o bônus de rate.' : ''}</p>`
      + (gLucro ? `<div class="chart-hd"><span class="k-title">Lucro por volta</span></div>${gLucro}` : '')
      + (gXp ? `<div class="chart-hd"><span class="k-title">${esc(rotuloXp)} por volta</span></div>${gXp}` : '')
      + `</section>`
    : '';

  // lucro nao medido fica null (a tela mostra "—"): virar 0/h seria dado inventado
  const lucroPorHora = (v) => (num(v.dur_s) && num(v.profit) !== null ? num(v.profit) * 3600 / num(v.dur_s) : null);
  // a escala da barrinha sai das mesmas voltas que entram nos totais
  const maxLucroH = Math.max(...vs.filter((v) => !v.descartada).map((v) => lucroPorHora(v) ?? 0), 0);
  const linhas = vs.map((v) => {
    const lucroH = lucroPorHora(v);
    let tds = `<td class="txt">#${v.numero}${v.descartada ? ' <span class="tag warn">descartada</span>' : ''}</td>`
      + `<td>${esc(v.inicio ?? VAZIO)}</td>`
      + `<td>${esc(v.fim ?? VAZIO)}</td>`
      + `<td>${esc(dur(v.dur_s))}</td>`
      + `<td>${esc(fmtN(v.kills))}</td>`
      + `<td class="pos">${esc(kkC(v.profit))}</td>`
      + `<td class="pos"${v.descartada ? '' : barra(lucroH, maxLucroH)}>${esc(lucroH === null ? VAZIO : kkh(lucroH))}</td>`
      + `<td>${esc(kkC(xpDe(v)))}</td>`;
    if (temDano) tds += `<td class="neg">${esc(kkC(v.dano_tomado))}</td>`;
    if (temBattle) tds += `<td>${esc(v.battle_medio === null ? VAZIO : dec(v.battle_medio, 1))}</td>`;
    if (temRot) tds += `<td class="txt">${esc(v.rotacao ?? VAZIO)}</td>`;
    return `<tr${v.descartada ? ' class="fora"' : ''}>${tds}</tr>`;
  }).join('');

  let cabs = `<th>Volta</th><th>Começo</th><th>Fim</th><th>Duração</th><th>Abates</th>`
    + `<th>Lucro</th><th>Lucro por hora</th><th>${esc(rotuloXp)}</th>`;
  if (temDano) cabs += `<th>Dano recebido</th>`;
  if (temBattle) cabs += `<th>Bichos por perto</th>`;
  if (temRot) cabs += `<th>Rotação</th>`;

  const semXp = temRaw ? vs.filter((v) => v.xp_raw === null).map((v) => '#' + v.numero) : [];
  const pausas = paradas(vs);
  const notas = [
    s.nota ? `<p class="nota"><b>Como os números foram medidos:</b> ${esc(s.nota)}</p>` : '',
    s.obs ? `<p class="nota"><b>Bicho roubado (KS):</b> ${esc(s.obs)}</p>` : '',
    pausas.length
      ? `<p class="nota"><b>Pausa entre voltas:</b> ${pausas
        .map((p) => `${dur(p.s)} depois da volta #${p.depois}`).join('; ')}. `
        + `Foi aí que ele parou para repor.</p>`
      : '',
    semXp.length
      ? `<p class="nota"><b>Sem leitura de experiência:</b> ${semXp.join(', ')}. `
        + `A célula fica vazia em vez de contar zero.</p>`
      : '',
  ].join('');

  const rodape = temRaw
    ? `* abates e dano são lidos do chat e ficam abaixo do real, de forma parecida em todas as `
      + `voltas — servem para comparar uma volta com a outra, não como número absoluto. Lucro e `
      + `experiência vêm do painel do jogo. Os totais do topo não incluem a volta descartada. `
      + `"bichos por perto" é a média de bichos em volta dele durante a volta.`
    : `* abates, lucro e experiência destas voltas vêm do chat: ficam abaixo do real e a `
      + `experiência já inclui o bônus de rate — servem para comparar uma volta com a outra, `
      + `não como número absoluto.`;

  const tabela = `<section class="panel">`
    + `<div class="panel-head"><div><h2>Volta a volta</h2>`
    + `<p class="cap">${vs.length} voltas gravadas, ${s.voltas} entram na conta.</p></div>`
    + `<span class="tag">${esc(dataBR(s.data))}</span></div>`
    + (notas ? `<div style="margin-bottom:14px">${notas}</div>` : '')
    + `<div class="scroll"><table><thead><tr>${cabs}</tr></thead><tbody>${linhas}</tbody></table></div>`
    + `<p class="foot-star">${rodape}</p>`
    + `</section>`;

  return graficos + tabela;
}

/* ---------- tela: zonas ---------- */
const COLS_ZONA = [
  { k: 'rank', t: 'Posição', txt: true, v: (z) => '#' + z.rank },
  { k: 'trecho', t: 'Trecho', txt: true, v: (z) => esc(z.trecho ?? VAZIO) },
  { k: 'kills', t: 'Abates', v: (z) => fmtN(z.kills), bar: true },
  { k: 'bichos_volta', t: 'Bichos por volta', v: (z) => (z.bichos_volta === null ? VAZIO : dec(z.bichos_volta, 2)) },
  { k: 'hp_por_bicho', t: 'Vida por bicho', v: (z) => fmtN(z.hp_por_bicho) },
  { k: 'dwell_s', t: 'Tempo na zona', v: (z) => dur(z.dwell_s) },
  { k: 'xp', t: 'Experiência estimada', v: (z) => kkC(z.xp) },
  { k: 'profit', t: 'Lucro estimado', v: (z) => kkC(z.profit) },
  { k: 'x', t: 'X', v: (z) => coord(z.x) },
  { k: 'y', t: 'Y', v: (z) => coord(z.y) },
];

const SEM_TRECHO = 'trecho não identificado';

function telaZonas(sid) {
  const s = sessaoDe(sid);
  if (!s) return semSessao(sid);
  cabecalho('zonas', 'Onde os abates aconteceram',
    `${s.hunt}, ${dataBR(s.data)}. Clique no título da coluna para reordenar.`, 'zonas', sid);

  const zs = zonasDe(sid);
  const maxKills = Math.max(...zs.map((z) => z.kills || 0), 0);
  const somaKills = zs.reduce((a, z) => a + (num(z.kills) ?? 0), 0);
  const ordenadas = [...zs].sort((a, b) => {
    const x = a[ordemZona.k], y = b[ordemZona.k];
    const cmp = typeof x === 'string' || typeof y === 'string'
      ? String(x ?? '').localeCompare(String(y ?? ''), 'pt-BR')
      : (Number(x ?? 0) - Number(y ?? 0));
    return ordemZona.asc ? cmp : -cmp;
  });

  // o botao vai DENTRO do th: trocar o papel do th por "button" faria o leitor de
  // tela descartar o aria-sort, que so vale em cabecalho de coluna
  const cabs = COLS_ZONA.map((c) => {
    const atual = c.k === ordemZona.k;
    const on = atual ? ` on${ordemZona.asc ? '' : ' desc'}` : '';
    return `<th class="ord${on}" aria-sort="${atual ? (ordemZona.asc ? 'ascending' : 'descending') : 'none'}">`
      + `<button type="button" data-k="${c.k}">${esc(c.t)}</button></th>`;
  }).join('');

  const linhas = ordenadas.map((z) => '<tr>' + COLS_ZONA
    .map((c) => `<td${c.txt ? ' class="txt"' : ''}${c.bar ? barra(z.kills, maxKills) : ''}>${c.v(z)}</td>`)
    .join('') + '</tr>').join('');

  const porTrecho = {};
  for (const z of zs) {
    const t = porTrecho[z.trecho || SEM_TRECHO] ??= { zonas: 0, kills: 0, hp: 0 };
    t.zonas++; t.kills += z.kills || 0; t.hp += (z.hp_por_bicho || 0) * (z.kills || 0);
  }
  const resumo = Object.entries(porTrecho)
    .sort((a, b) => b[1].kills - a[1].kills)
    .map(([nome, t]) => st(nome, `${fmtN(t.kills)} abates · ${fmtN(Math.round(t.hp / (t.kills || 1)))} de vida`))
    .join('');

  el('app').innerHTML = `<section class="panel">`
    + `<div class="panel-head"><div><h2>Trechos do percurso</h2>`
    + `<p class="cap">Somando as zonas de cada trecho, com a vida média por bicho.</p></div></div>`
    + `<div class="stats">${resumo}</div></section>`
    + `<section class="panel"><h2>Zonas, uma por linha</h2>`
    + `<p class="cap">${zs.length} zonas, da que mais matou para a que menos matou.</p>`
    + (zs.length
      ? `<div class="scroll"><table id="tzonas"><thead><tr>${cabs}</tr></thead><tbody>${linhas}</tbody></table></div>`
      : `<div class="empty">sem zonas nesta sessão</div>`)
    + `<p class="foot-star">* experiência e lucro por zona são estimativa: o valor medido por `
    + `bicho na sessão, multiplicado pelos abates da zona. Não foram medidos zona por zona. `
    + `Somando as zonas dá ${fmtN(somaKills)} abates contra ${fmtN(s.kills)} da sessão, `
    + `porque as duas contagens vêm de leituras diferentes — por isso as colunas estimadas `
    + `não fecham com o total do topo. Vida por bicho e tempo na zona são medidos.</p>`
    + `</section>`;

  const t = el('tzonas');
  if (!t) return;
  const trocar = (b) => {
    const k = b?.dataset.k;
    if (!k) return;
    ordemZona = k === ordemZona.k ? { k, asc: !ordemZona.asc } : { k, asc: k !== 'rank' };
    telaZonas(sid);
    // a tabela e redesenhada: sem isto o foco cai no body e quem usa teclado se perde
    el('tzonas')?.querySelector(`th.ord button[data-k="${k}"]`)?.focus();
  };
  t.addEventListener('click', (e) => trocar(e.target.closest('th.ord button')));
}

/* ---------- tela: boxes travadas ---------- */
function telaBoxes(sid) {
  const s = sessaoDe(sid);
  if (!s) return semSessao(sid);
  const bs = boxesDe(sid);
  cabecalho('boxes travadas', `${bs.length} travadas na sessão`,
    `${s.hunt}, ${dataBR(s.data)}. Cada cartão traz o motivo, os três passos do que aconteceu e a imagem.`,
    'boxes', sid);

  const cartoes = bs.map((b) => {
    const passos = [b.historia_1, b.historia_2, b.historia_3]
      .filter(Boolean).map((h) => `<li>${esc(h)}</li>`).join('');
    return `<article class="boxcard">`
      + `<div><div class="bh"><span class="bn">Travada ${b.n}</span>`
      + `<span class="tag">${b.volta === null ? 'volta não identificada' : 'volta #' + b.volta}</span>`
      + `<span class="tag warn">${esc(dur(b.dur_s))} parado</span></div>`
      + `<p class="causa">${esc(b.causa ?? 'sem motivo apontado')}</p>`
      + (passos ? `<ol class="passos">${passos}</ol>` : `<div class="empty">sem narrativa gravada</div>`)
      + `<div class="stats" style="margin-top:14px">`
      + st('Dano levado', fmtN(b.dano))
      + st('Bichos em volta', fmtN(b.pilha))
      // "abertura" na fonte e chao andavel na janela de 5x5 — nao saida livre
      + st('Chão livre em volta', `${fmtN(b.abertura)} de 25`)
      + st('Posição', `${coord(b.x)}, ${coord(b.y)}`)
      + `</div></div>`
      // ponytail: cada grid tem ~2,8 MB, e os 8 dao 21 MB se o usuario rolar a tela toda.
      // Fica assim porque e leitura de disco local e o loading="lazy" adia o que nao esta
      // na tela. Se um dia incomodar, gerar um thumbnail no build_db e linkar o grande.
      + (b.imagem
        ? `<a class="shot" href="/img/boxes_travadas/${encodeURIComponent(b.imagem)}" target="_blank" rel="noopener">`
          + `<img src="/img/boxes_travadas/${encodeURIComponent(b.imagem)}" alt="Sequência da travada ${b.n}" loading="lazy">`
          + `<span class="cap2"><span>quadro a quadro</span><span>${esc(b.imagem)}</span></span></a>`
        : `<div class="empty">sem imagem</div>`)
      + `</article>`;
  }).join('');

  el('app').innerHTML = `<section class="panel"><h2>Uma por uma</h2>`
    + `<p class="cap">"Chão livre em volta" é quanto do piso ao redor dele dava para pisar, de 25 `
    + `quadrados. Número alto e ele travado do mesmo jeito quer dizer que quem fechou a passagem `
    + `foram os bichos parados em cima do chão livre, não a parede. O motivo logo abaixo do título `
    + `pode citar um número menor: é o do lugar por onde ele entrou, alguns segundos antes.</p>`
    + (bs.length ? `<div class="boxlist">${cartoes}</div>` : `<div class="empty">nenhuma travada nesta sessão</div>`)
    + `</section>`;
}

function semSessao(sid) {
  // sem sid no menu: apontar "Sessão" para outra sessao sem avisar seria pior que nao ter menu
  cabecalho('sessão', 'Sessão não encontrada', `Não existe sessão com o número ${sid}.`, '', null);
  el('app').innerHTML = `<section class="panel"><div class="empty">`
    + `nada gravado com esse número — <a href="/">voltar para a visão geral</a></div></section>`;
}

/* ---------- entrada ---------- */
function pintar() {
  const m = location.pathname.match(/^\/sessao\/(\d+)(?:\/(zonas|boxes))?$/);
  if (!m) return telaInicio();
  const sid = Number(m[1]);
  if (m[2] === 'zonas') return telaZonas(sid);
  if (m[2] === 'boxes') return telaBoxes(sid);
  return telaSessao(sid);
}

(async function boot() {
  const aviso = (txt) => {
    el('app').innerHTML = `<section class="panel"><div class="empty">${esc(txt)}</div></section>`;
  };
  try {
    D = await (await fetch('/api/dados')).json();
  } catch {
    return aviso('não consegui falar com o servidor — ele está rodando?');
  }
  if (D?.erro) return aviso(D.erro); // o servidor manda o motivo em texto
  pintar();
})();
