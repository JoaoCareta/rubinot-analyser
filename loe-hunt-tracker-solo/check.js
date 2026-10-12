// Conferencia do que pode quebrar sem aparecer na tela: formatacao de numeros,
// as regras de soma das sessoes, o filtro da visao geral e a barreira de caminho.
// Rodar: npm run check
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { connect as netConnect } from 'node:net';
import { join, normalize } from 'node:path';
import { getPayload, sessaoExiste } from './db.js';
import { coord, dur, fmtN, hm, kkC, kkh, num, pct, seg } from './public/static/fmt.js';

const RELATORIOS = normalize(process.env.REPORTS_DIR || 'D:/Documentos/rubinot/hunt-analyzer/reports');

/* numeros: kk com virgula, abaixo de 1 kk em k, nunca "M" */
assert.equal(kkC(4130000), '4,13 kk');
assert.equal(kkC(5790000), '5,79 kk');
assert.equal(kkC(741000), '741 k');
assert.equal(kkC(333470), '333 k');
assert.equal(kkC(41500), '41,5 k');
assert.equal(kkC(806), '806');
assert.equal(kkC(0), '0');
assert.equal(kkC(-2500000), '-2,50 kk');
assert.equal(kkC(null), '—');
assert.equal(kkh(4130000), '4,13 kk/h');
// as tres costuras de faixa: nada pode sair com um digito a mais que a faixa de cima
assert.equal(kkC(999500), '1,00 kk');
assert.equal(kkC(999499), '999 k');
assert.equal(kkC(99950), '100 k');
assert.equal(kkC(99949), '99,9 k');
assert.equal(kkC(999.5), '1,0 k');
assert.equal(kkC(999), '999');
for (const n of [1e3, 999.5, 99_950, 999_500, 1e6, 7.87e6, 9.9e8]) {
  assert.ok(!kkC(n).includes('M'), `nao pode ter M: ${kkC(n)}`);
  assert.ok(!/^\d{4}/.test(kkC(n)), `faixa vazou para a de baixo: ${kkC(n)}`);
}
assert.equal(fmtN(1212), '1.212');
assert.equal(dur(246), '4m 06s');
assert.equal(dur(480), '8m 00s');
assert.equal(dur(3720), '1h 02m');
assert.equal(seg('08:15:30'), 29730);
assert.equal(seg('nao e hora'), null);
// coordenada nao e contagem: sem separador de milhar
assert.equal(coord(33681), '33681');
assert.equal(coord(null), '—');
// null nao pode virar zero em NENHUM formatador (regra do README)
assert.equal(num(null), null);
assert.equal(num(''), null);
assert.equal(num('12'), 12);
for (const f of [kkC, kkh, fmtN, coord, dur, hm, pct]) {
  for (const vazio of [null, undefined, '']) {
    assert.equal(f(vazio), '—', `${f.name}(${JSON.stringify(vazio)}) devia ser vazio`);
  }
}
assert.equal(pct(0), '0,0%'); // zero de verdade continua zero
assert.equal(hm(84.17), '1h 24m');

/* banco: as regras de soma, so onde as duas pontas foram medidas de verdade */
const D = getPayload();
assert.equal(D.grupo.nome, 'Johanes Characters');
assert.equal(D.personagens.length, 2);
assert.ok(D.hunts.length >= 4);
assert.ok(D.sessoes.length >= 12);
assert.ok(D.abates.length >= 40, 'abate_especie sumiu do payload');

for (const s of D.sessoes) {
  const todas = D.voltas.filter((v) => v.sessao_id === s.id);
  const boas = todas.filter((v) => !v.descartada);
  // regra 1: a volta descartada nao entra na conta (sessao sem voltas fica de fora)
  if (s.voltas !== null) assert.equal(boas.length, s.voltas, `sessao ${s.id}: voltas boas`);
  if (s.kills !== null && todas.length) {
    assert.equal(boas.reduce((a, v) => a + (v.kills || 0), 0), s.kills, `sessao ${s.id}: abates`);
  }
  // lucro por volta so fecha com o total quando as voltas vieram do painel (tem xp_raw);
  // volta de chat estima o loot e nao tem obrigacao de bater com o painel
  if (s.profit !== null && boas.some((v) => v.xp_raw !== null)) {
    const lucro = boas.reduce((a, v) => a + (v.profit || 0), 0);
    // sem dividir: profit 0 daria NaN e profit negativo inverteria a comparacao
    assert.ok(Math.abs(lucro - s.profit) <= Math.abs(s.profit) * 0.01, `sessao ${s.id}: lucro fora de 1%`);
  }
  // ks_pct 0 so vale como medicao de verdade: se a obs lista KS, zero e mentira.
  // Onde ninguem chegou a medir (sessao 1, fonte so em texto), o campo e NULL.
  if (s.ks_pct === 0) {
    assert.ok(!String(s.obs ?? '').includes('KS:'), `sessao ${s.id}: ks_pct 0 mas a obs lista KS`);
  }

  const zs = D.zonas.filter((z) => z.sessao_id === s.id);
  zs.forEach((z, i) => assert.equal(z.rank, i + 1, `sessao ${s.id}: posicao das zonas com buraco`));

  // as colunas estimadas tem que ser UMA taxa por bicho aplicada a todas as zonas
  // (era uma constante colada no build_db, que envelhecia sozinha)
  if (zs.length) {
    const comXp = boas.filter((v) => v.xp_raw !== null);
    const taxaXp = comXp.reduce((a, v) => a + v.xp_raw, 0) / comXp.reduce((a, v) => a + (v.kills || 0), 0);
    const taxaLucro = s.profit / s.kills;
    for (const z of zs) {
      assert.ok(Math.abs(z.xp / z.kills - taxaXp) < 1, `zona ${z.rank}: xp fora da taxa medida`);
      assert.ok(Math.abs(z.profit / z.kills - taxaLucro) < 1, `zona ${z.rank}: lucro fora da taxa medida`);
    }
  }

  for (const b of D.boxes.filter((x) => x.sessao_id === s.id)) {
    assert.ok(b.imagem, `box ${b.n} sem imagem`);
    assert.ok(existsSync(join(RELATORIOS, 'boxes_travadas', b.imagem)), `imagem faltando: ${b.imagem}`);
  }

  // bichos por especie: fonte conhecida, contagem positiva, percentuais fechando ~100
  const as = D.abates.filter((a) => a.sessao_id === s.id);
  for (const a of as) {
    assert.ok(['loot_corpo', 'xp_chat'].includes(a.fonte), `sessao ${s.id}: fonte de abate "${a.fonte}"`);
    assert.ok(a.abates > 0, `sessao ${s.id}: especie ${a.especie} com abates ${a.abates}`);
  }
  if (as.length) {
    const somaPct = as.reduce((a, x) => a + x.pct, 0);
    assert.ok(Math.abs(somaPct - 100) < 1, `sessao ${s.id}: percentuais das especies somam ${somaPct}`);
  }
}
// regra 2: sem nenhuma volta descartada no banco, a regra 1 acima nao testa nada
assert.ok(D.voltas.some((v) => v.descartada), 'nenhuma volta descartada: a regra 1 fica sem cobertura');
assert.equal(sessaoExiste(D.sessoes[0].id), true);
assert.equal(sessaoExiste(9999), false);
assert.equal(sessaoExiste('abc'), false);

/* servidor: barreira de caminho e rotas */
process.env.PORT = process.env.CHECK_PORT || '3399';
const { dentro, raizDe } = await import('./server.js');
const base = `http://127.0.0.1:${process.env.PORT}`;
const pega = async (p, init) => (await fetch(base + p, { redirect: 'manual', ...init })).status;

// a barreira tem que valer com e sem barra no fim da raiz (REPORTS_DIR ajustavel)
for (const raiz of ['D:/tmp/reports', 'D:/tmp/reports/', 'D:\\tmp\\reports\\', 'D:/tmp/reports//']) {
  const r = raizDe(raiz);
  assert.ok(dentro(r, 'mapa.png'), `raiz "${raiz}": arquivo legitimo devia passar`);
  assert.equal(dentro(r, '../../segredo'), null, `raiz "${raiz}": fuga devia bater na barreira`);
}

assert.equal(await pega('/api/dados'), 200);
assert.equal(await pega('/static/app.css'), 200);
assert.equal(await pega('/static/app.js'), 200);
// os outfits dos integrantes sao arquivos locais, nunca URL externa
assert.equal(await pega('/assets/hetero_afeminado.png'), 200);
assert.equal(await pega('/assets/traps_the_cat.gif'), 200);
assert.equal(await pega('/'), 200);
assert.equal(await pega('/sessao/1'), 200);
assert.equal(await pega('/sessao/1/zonas'), 200);
assert.equal(await pega('/sessao/1/boxes'), 200);
assert.equal(await pega('/img/mapa_volta_ingol.png'), 200);
assert.equal(await pega('/img/boxes_travadas/boxgrid_01.png'), 200);
// ".." escapado tem que bater na barreira, nao no disco
assert.equal(await pega('/img/%2e%2e%2f%2e%2e%2fdb.js'), 403);
assert.equal(await pega('/static/%2e%2e%2f%2e%2e%2fdb.js'), 403);
assert.equal(await pega('/assets/%2e%2e%2f%2e%2e%2fdb.js'), 403);
// um nivel de ".." dentro de /static continua dentro de public/ — nao e fuga, e arquivo que nao existe
assert.equal(await pega('/static/%2e%2e%2fdb.js'), 404);
assert.equal(await pega('/nao/existe'), 404);
assert.equal(await pega('/img/nao_existe.png'), 404);
assert.equal(await pega('/api/dados', { method: 'POST' }), 405);
// numero de sessao que nao existe e 404, nao 200
assert.equal(await pega('/sessao/99'), 404);
// request-target malformado ("//[" vira URL invalida) tem que dar 400, nunca derrubar o processo
await new Promise((fim, erro) => {
  const s = netConnect(Number(process.env.PORT), '127.0.0.1', () => {
    s.write('GET //[ HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n');
  });
  let resposta = '';
  s.on('data', (d) => { resposta += d; });
  s.on('close', () => (resposta.startsWith('HTTP/1.1 400')
    ? fim() : erro(new Error(`request malformado devia dar 400, veio: ${resposta.slice(0, 40)}`))));
  s.on('error', erro);
});
assert.equal(await pega('/api/dados'), 200, 'servidor caiu depois do request malformado');
// barra no fim e o mesmo endereco
assert.equal(await pega('/sessao/1/'), 301);

/* as telas desenham de verdade? (DOM de mentira, dados de verdade) */
let alvos = {};
globalThis.document = {
  getElementById: (id) => (alvos[id] ??= {
    innerHTML: '', addEventListener() {}, dataset: {}, querySelector: () => null,
  }),
  addEventListener() {},
};
globalThis.location = { pathname: '/' };
const fetchReal = globalThis.fetch;
globalThis.fetch = (u, init) => fetchReal(u.startsWith('http') ? u : base + u, init);

/* o filtro da visao geral conta certo? (funcao pura exportada pelo app.js) */
const { filtra } = await import('./public/static/app.js?v=0');
assert.equal(filtra(D.sessoes, {}).length, D.sessoes.length, 'sem filtro tem que devolver tudo');
assert.equal(filtra(D.sessoes, { hunt: 'ingol' }).length, 3, 'Ingol tem as sessoes 1, 5 e 6');
assert.equal(filtra(D.sessoes, { de: '2026-07-25', ate: '2026-07-25' }).length, 7, 'dia 25 tem 7 sessoes');
assert.equal(filtra(D.sessoes, { de: '2026-07-27', ate: '2026-07-27' }).length, 2, 'dia 27 tem 2 sessoes');
assert.equal(filtra(D.sessoes, { de: '2026-07-26', ate: '2026-07-27', hunt: 'falcon_bastion' }).length, 3,
  'Falcon nos dias 26-27 tem 3 sessoes');
assert.equal(filtra(D.sessoes, { de: '2026-08-01' }).length, 0, 'periodo sem hunt tem que vir vazio');

async function desenha(pathname, versao) {
  alvos = {};
  globalThis.location = { pathname };
  await import(`./public/static/app.js?v=${versao}`);
  for (let i = 0; i < 200 && !alvos.app?.innerHTML; i++) await new Promise((r) => setTimeout(r, 10));
  const html = (alvos.hd?.innerHTML || '') + (alvos.app?.innerHTML || '');
  assert.ok(html.length > 500, `${pathname}: tela veio vazia`);
  for (const lixo of ['undefined', 'NaN', '>null<', 'null,', '—%']) {
    assert.ok(!html.includes(lixo), `${pathname}: sobrou "${lixo}" na tela`);
  }
  return html;
}

// visao geral: rotulo novo, integrantes com outfit local e a barra de filtros da pt
const inicio = await desenha('/', 1);
for (const t of ['Solo Hunt Tracker', 'Johanes Characters', 'Integrantes',
  'assets/hetero_afeminado.png', 'assets/traps_the_cat.gif',
  'ED · Lvl 787', 'RP · Lvl 941', 'informado à mão',
  'Tudo', 'De', 'até', `/ ${D.sessoes.length} sessões`, 'Todas',
  'Ingol', 'Falcon Bastion', 'Infernatil Hell', 'Dragolisk',
  'Hetero afeminado', 'Traps the cat', '4,13 kk/h']) {
  assert.ok(inicio.includes(t), `visao geral sem "${t}"`);
}
// sem filtro, o contador mostra o total dos dois lados
assert.ok(inicio.includes(`<b>${D.sessoes.length}</b>`), 'contador nao bate com o total de sessoes');
// o botao de adicionar sessao do site da pt NAO existe aqui: insercao e automatica
assert.ok(!inicio.includes('Adicionar sessão'), 'botao de adicionar sessao nao devia existir');

// sessao 1 (27/07, Ingol): volta a volta completa, bichos por especie e graficos
const sessao = await desenha('/sessao/1', 2);
for (const t of ['5,79 kk', '7,02 kk', '6,55 kk', '1h 24m', 'descartada',
  'mapa_volta_ingol.png', 'caminho_comum_ingol.png',
  'Como os números foram medidos', 'Bicho roubado (KS)', '5m 06s depois da volta #10',
  'não foi contado nesta sessão',
  'Bichos abatidos', 'rhindeer', 'crape man', 'corpos saqueados',
  '<svg class="chart"', 'Gráficos por volta', 'Lucro por volta']) {
  assert.ok(sessao.includes(t), `sessao sem "${t}"`);
}
assert.ok(!sessao.includes('frames apagados'), 'sessao 1 TEM volta a volta');
// a linha descartada nao ganha barrinha, e a escala da barra e ancorada numa volta boa
const linhaFora = /<tr class="fora">[\s\S]*?<\/tr>/.exec(sessao)?.[0] ?? '';
assert.ok(linhaFora.includes('descartada'), 'linha descartada sem marca na tela');
assert.ok(!linhaFora.includes('linear-gradient'), 'volta descartada entrou na escala da barra');
// quem ancora a escala (barra em 100%) tem que ser a MELHOR VOLTA BOA, nao qualquer linha
const boasS1 = D.voltas.filter((v) => v.sessao_id === 1 && !v.descartada && v.dur_s);
const topo = boasS1.reduce((a, v) => ((v.profit || 0) / v.dur_s > (a.profit || 0) / a.dur_s ? v : a));
const linhaTopo = sessao.split('<tr').find((r) => r.includes(`<td class="txt">#${topo.numero}<`)) ?? '';
assert.ok(linhaTopo.includes(' 100%, transparent 100%'),
  `a barra de 100% devia estar na volta #${topo.numero}, a melhor das voltas boas`);

// sessao 2: painel medido mas sem voltas — agregados + aviso, sem grafico por volta
const s2 = await desenha('/sessao/2', 3);
for (const t of ['sem volta a volta (frames apagados)', 'Falcon Bastion', '3,67 kk',
  'Bichos abatidos', 'falcon knight']) {
  assert.ok(s2.includes(t), `sessao 2 sem "${t}"`);
}
assert.ok(!s2.includes('Gráficos por volta'), 'sessao 2 nao tem volta a volta para desenhar');

// sessao 8: voltas vindas do chat — XP rotulada como boostada, painel sem medicao
const s8 = await desenha('/sessao/8', 4);
for (const t of ['Experiência (chat, com bônus)', 'Gráficos por volta', 'wardragon',
  'não identificada', 'sem medição no painel']) {
  assert.ok(s8.includes(t), `sessao 8 sem "${t}"`);
}
// volta de chat nao tem lucro medido: a coluna "Lucro por hora" mostra "—", nunca "0/h"
assert.ok(D.voltas.some((v) => v.sessao_id === 8 && !v.descartada && v.profit === null && v.dur_s),
  'sessao 8 devia ter volta sem lucro medido (senao esta checagem nao testa nada)');
assert.ok(!s8.includes('>0/h<'), 'volta sem lucro medido virou "0/h" na tela');

const zonas = await desenha('/sessao/1/zonas', 5);
for (const t of ['reta oeste', 'quina sudoeste', 'Vida por bicho', 'estimada', 'aria-sort',
  '<button type="button" data-k="kills"', '33681']) {
  assert.ok(zonas.includes(t), `zonas sem "${t}"`);
}
assert.ok(!zonas.includes('role="button"'), 'th com role=button descarta o aria-sort');
assert.ok(!zonas.includes('33.681'), 'coordenada com separador de milhar');
const boxes = await desenha('/sessao/1/boxes', 6);
for (const t of ['boxgrid_01.png', 'boxgrid_08.png', 'passagem estreita', 'volta não identificada',
  'Chão livre em volta', '33723, 32564']) {
  assert.ok(boxes.includes(t), `boxes sem "${t}"`);
}
assert.ok(!boxes.includes('Saídas livres'), 'abertura nao e saida livre');

console.log('tudo certo');
process.exit(0);
