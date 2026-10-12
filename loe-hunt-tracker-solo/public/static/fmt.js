// Formatacao de numeros. Regras: kk com virgula ("4,13 kk"), valores abaixo de
// 1 kk em k ("741 k"), nunca "M". Usado pelas telas e pelo check.js.
export const VAZIO = '—'; // travessao

/** Numero de verdade ou null. Sem isto, Number(null) === 0 vira "0,0%" no lugar de "—". */
export function num(n) {
  if (n === null || n === undefined || n === '') return null;
  const v = Number(n);
  return Number.isFinite(v) ? v : null;
}

export function dec(n, casas) {
  return Number(n).toFixed(casas).replace('.', ',');
}

// Os limites sao os do valor JA arredondado, senao a faixa de cima vaza para a
// de baixo: 999.500 sairia "1000 k" e 999,5 sairia "1000".
const LIM_KK = 999_500; // arredonda para 1000 k -> melhor "1,00 kk"
const LIM_K = 99_950;   // arredonda para 100,0 k -> melhor "100 k"
const LIM_UN = 999.5;   // arredonda para 1000 -> melhor "1,0 k"

/** 4130000 -> "4,13 kk" | 741000 -> "741 k" | 41500 -> "41,5 k" | 806 -> "806" */
export function kkC(n) {
  const v = num(n);
  if (v === null) return VAZIO;
  const sinal = v < 0 ? '-' : '';
  const a = Math.abs(v);
  if (a >= LIM_KK) return sinal + dec(a / 1e6, 2) + ' kk';
  if (a >= LIM_K) return sinal + String(Math.round(a / 1e3)) + ' k';
  if (a >= LIM_UN) return sinal + dec(a / 1e3, 1) + ' k';
  return sinal + String(Math.round(a));
}

export function kkh(n) {
  const s = kkC(n);
  return s === VAZIO ? s : s + '/h';
}

export function fmtN(n) {
  const v = num(n);
  return v === null ? VAZIO : v.toLocaleString('pt-BR');
}

/** Coordenada do mapa: contagem nao e, entao nao leva separador de milhar. */
export function coord(n) {
  const v = num(n);
  return v === null ? VAZIO : String(Math.round(v));
}

/** 246 -> "4m 06s" | 3720 -> "1h 02m" | 42 -> "42s" */
export function dur(segundos) {
  const t = num(segundos);
  if (t === null) return VAZIO;
  const s = Math.round(Math.abs(t));
  if (s >= 3600) return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m`;
  if (s >= 60) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
  return `${s}s`;
}

/** 84.17 (minutos) -> "1h 24m" */
export function hm(minutos) {
  const v = num(minutos);
  return v === null ? VAZIO : dur(v * 60);
}

export function pct(n) {
  const v = num(n);
  return v === null ? VAZIO : dec(v, 1) + '%';
}

/** "08:15:30" -> 29730 (segundos do dia). Devolve null se nao der para ler. */
export function seg(hora) {
  const p = String(hora ?? '').split(':').map(Number);
  if (p.length !== 3 || p.some((x) => !Number.isFinite(x))) return null;
  return p[0] * 3600 + p[1] * 60 + p[2];
}
