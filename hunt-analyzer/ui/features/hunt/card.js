(function(root){
const {taxasDe,PAUSA_S}=root.HuntMetricas || require('../../taxas.js');
const xph = v => v.xp_raw_15min ? v.xp_raw_15min * 4 : (v.xp_raw ? v.xp_raw * 3600 / v.dur : null);
function pct(a, b) { return (a == null || b == null || b === 0) ? null : Math.round(100 * (a - b) / Math.abs(b)); }
// volta parcial (a gravação parou no meio, user 21/09): fora das comparações, nas duas pontas
const anterior = (vs, i) => { for (let j = i - 1; j >= 0; j--) if (!vs[j].parcial) return vs[j]; return null; };
function comparacoes(v, ant) {
  if (v.parcial) ant = null;
  const mesmaRaw = ant && !v.estabilizando && !!v.xp_raw_15min === !!ant.xp_raw_15min;
  const mesmaBase = ant && (v.base || null) === (ant.base || null);   // solo não tem Party Hunt: base null nas duas compara
  // 22/09: Party Hunt zerado numa das duas = profit e supplies da pt só de um pedaço da volta
  const zerou = !!(v.reset || ant?.reset);
  return {
    xp: mesmaRaw ? pct(xph(v), xph(ant)) : null,
    profit: mesmaBase && !zerou ? pct(v.profit, ant.profit) : null,
    sup_pt: ant && !zerou ? pct(v.sup_pt, ant.sup_pt) : null,
    sup_eu: ant ? pct(v.sup_eu, ant.sup_eu) : null,
    bichos: ant ? pct(v.bichos, ant.bichos) : null,
  };
}
function humor(v, c) {
  if (v.parcial) return 'parcial';
  if (v.estabilizando) return '⏳';
  const ds = [c.xp, c.profit, c.bichos].filter(x => x != null);
  if (!ds.length) return '📖';
  const m = ds.reduce((a, b) => a + b, 0) / ds.length;
  return m >= 8 ? '🔥' : m > 0 ? '👍' : m <= -8 ? '🐌' : '😐';
}
// 24/09 (user): o card é a última volta enquanto a raw ainda não consolidou (a janela do XP
// Analyser é de 15 min); passados os 15 min de hunt ele vira a MÉDIA da hunt, porque volta a volta
// já fica no histórico logo abaixo. Volta parcial fica fora da média (CLAUDE.md).
const RAW_MIN_S = 900;
function mediaDa(vs) {
  // os números vêm todos do taxasDe (ui/taxas.js = a cópia de ao_vivo.taxas): a tela, o histórico e
  // os gráficos leem a MESMA conta. Aqui só entra o que é do card: solo e o recorte de horário.
  const t = taxasDe(vs);
  if (!t.voltas) return null;
  const limpas = vs.filter(v => !v.parcial && v.dur < PAUSA_S), ult = limpas[limpas.length - 1];
  return {n: t.voltas, total: t.total, parciais: t.parciais, refil: t.refil, dur: t.dur_media,
          xph: t.raw_h, profit: t.media.profit, sup_pt: t.media.sup_pt, sup_eu: t.media.sup_eu,
          bichos: t.media.bichos, solo: ult.solo ?? (ult.sup_pt == null), ini: limpas[0].ini, fim: ult.fim};
}
const api={xph,pct,anterior,comparacoes,humor,mediaDa,RAW_MIN_S};
if(typeof module!=='undefined')module.exports=api;else root.HuntCard=api;
})(globalThis);
