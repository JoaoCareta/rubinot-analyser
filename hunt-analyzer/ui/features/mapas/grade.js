(function(root){
function agrega(amostras, A, z, cel=4) {
  const mapa = new Map();
  let antes = null;
  for (let i = 0; i < amostras.length; i++) {
    const [t, az, x, y, b] = amostras[i];
    const dt = i + 1 < amostras.length ? Math.min(amostras[i + 1][0] - t, 3) : 1;
    if (az !== z || x < A.x0 || y < A.y0 || x >= A.x0 + A.w || y >= A.y0 + A.h) { antes = null; continue; }
    const cx = Math.floor((x - A.x0) / cel), cy = Math.floor((y - A.y0) / cel), k = cx + ',' + cy;
    const c = mapa.get(k) || {cx, cy, seg: 0, bsoma: 0, visitas: 0};
    c.seg += dt; c.bsoma += (b || 0) * dt;   // battle sem leitura no frame não vira NaN na escala
    if (antes !== k) c.visitas++;
    antes = k;
    mapa.set(k, c);
  }
  return [...mapa.values()].map(c => ({...c, bichos: c.bsoma / c.seg}));
}
function faixas(valores) {   // 5 faixas por quantil, como a legenda do vídeo
  const v = [...valores].sort((a, b) => a - b);
  if (!v.length) return null;
  const q = p => v[Math.min(v.length - 1, Math.floor(p * v.length))];
  return [v[0], q(.2), q(.4), q(.6), q(.8), v[v.length - 1]];
}
const faixa = (lim, x) => lim ? Math.max(0, Math.min(4, [1, 2, 3, 4].filter(i => x >= lim[i]).length)) : 0;


const api={agrega,faixas,faixa};if(typeof module!=="undefined")module.exports=api;else root.HuntMapas=api;
})(globalThis);
