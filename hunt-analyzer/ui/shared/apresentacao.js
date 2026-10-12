(function(root){
const $ = s => document.querySelector(s);
const el =(tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const virg = (v, c = 2) => v.toFixed(c).replace('.', ',');
const kk = v => v == null ? '–' : `${virg(v / 1e6)} kk`;
const ouro = v => v == null ? '–' : (Math.abs(v) >= 1e6 ? `${virg(v / 1e6)} kk` : `${Math.round(v / 1000)}k`);
const dur = s => `${Math.floor(s / 60)}m${String(Math.round(s % 60)).padStart(2, '0')}`;
const hms = t => [t / 3600, (t % 3600) / 60, t % 60].map(v => String(Math.floor(v)).padStart(2, '0')).join(':');
const durc = s => s >= 3600 ? `${Math.floor(s / 3600)}h${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}` : dur(s);

root.HuntUI={$ ,el,virg,kk,ouro,dur,hms,durc};
})(globalThis);
