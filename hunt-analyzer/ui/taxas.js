/* As contas de um conjunto de voltas, iguais em toda a tela (user, 24/09: "as fórmulas e dados devem
   ser os mesmos tanto no histórico quanto nas análises" · "monstros, loot, supplies etc, tudo deve
   vir da mesma fonte").

   A FONTE DA VERDADE é o Python: `ao_vivo.taxas` e `ao_vivo.especies`. Este arquivo é a cópia que a
   página usa para recalcular ao vivo, na volta escolhida e na prévia — `python ao_vivo.py` roda as
   duas com o node e quebra se elas discordarem em qualquer sessão guardada.

   Regras (CLAUDE.md):
     · arredondamento = Math.round (empates para cima), também no Python
     · volta limpa = fechada, não parcial e com menos de PAUSA_S (a do refill fica de fora, como na
       volta média, na mais rápida e na mais lenta)
     · XP raw/h = MEDIANA das voltas limpas com a raw consolidada (15 min × 4 = o XP Analyser); sem
       nenhuma consolidada, soma da raw lida ÷ o tempo dessas voltas
     · profit, supplies e bichos = só as voltas em que a medida FOI LIDA, por volta (media) e por
       hora (taxa), numerador e denominador das mesmas voltas — volta sem leitura é lacuna, nunca
       zero (foi o que fez o gráfico dizer 12,10 kk/h numa hunt de 13,90) */
const PAUSA_S = 360;

function taxasDe(voltas) {
  const vs = voltas.filter(v => (v.dur || 0) > 0 && (v.tipo || 'volta') === 'volta');
  const limpas = vs.filter(v => !v.parcial && v.dur < PAUSA_S);
  const est = limpas.filter(v => v.xp_raw_15min).map(v => v.xp_raw_15min * 4).sort((a, b) => a - b);
  const comRaw = limpas.filter(v => v.xp_raw != null);
  const segRaw = comRaw.reduce((a, v) => a + v.dur, 0);
  const lidas = k => limpas.filter(v => v[k] != null);
  const media = k => { const ok = lidas(k); return ok.length ? Math.round(ok.reduce((a, v) => a + v[k], 0) / ok.length) : null; };
  const taxa = k => {
    const ok = lidas(k), seg = ok.reduce((a, v) => a + v.dur, 0);
    return seg ? Math.round(ok.reduce((a, v) => a + v[k], 0) * 3600 / seg) : null;
  };
  const seg = limpas.reduce((a, v) => a + v.dur, 0);
  const parciais = vs.filter(v => v.parcial).length;
  return {
    voltas: limpas.length, total: vs.length, parciais, refil: vs.length - limpas.length - parciais,
    dur_s: seg, dur_media: limpas.length ? Math.round(seg / limpas.length) : null,
    raw_h: est.length ? est[Math.floor(est.length / 2)] : (segRaw ? Math.round(comRaw.reduce((a, v) => a + v.xp_raw, 0) * 3600 / segRaw) : null),
    raw_de: est.length ? '15min' : (segRaw ? 'soma' : null),
    voltas_raw: comRaw.length, voltas_15min: est.length,
    media: {profit: media('profit'), sup_pt: media('sup_pt'), sup_eu: media('sup_eu'), bichos: media('bichos')},
    taxa: {profit_h: taxa('profit'), sup_pt_h: taxa('sup_pt'), sup_eu_h: taxa('sup_eu'), bichos_h: taxa('bichos')},
  };
}

/* Espécies da hunt: {nome: mortes}, a mais morta primeiro — a mesma lista na tela de hunt, no resumo
   guardado e nos bichos da capa do histórico. O motor já tirou de `especies` o que não é bicho e o
   que é de outra hunt; sessão sem espécie em volta nenhuma cai para o `loots` (antes de 21/09 o loot
   ainda vinha pelo Server Log e era ele que dizia o que morreu). Espelha ao_vivo.especies. */
function especiesDe(voltas) {
  const vs = voltas.filter(v => (v.tipo || 'volta') === 'volta');
  const campo = vs.some(v => Object.keys(v.especies || {}).length) ? 'especies' : 'loots';
  const n = {};
  for (const v of vs) for (const [k, c] of Object.entries(v[campo] || {})) n[k] = (n[k] || 0) + c;
  return Object.fromEntries(Object.entries(n).sort((a, b) => b[1] - a[1]));
}

if (typeof module !== 'undefined') module.exports = {taxasDe, especiesDe, PAUSA_S};   // o _demo do ao_vivo confere por aqui
