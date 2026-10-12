const assert=require('node:assert/strict'),fs=require('node:fs');
global.HuntRTC=require('./ui/rtc');
const W=require('./ui/roda_motor'),T=require('./ui/temporal');
const cat=W.selecionar(JSON.parse(fs.readFileSync('./ui/roda_catalogo.json','utf8')),'ED');
const r=W.candidatas(cat,989,3,'vida','dano',{preencher:true,convictions_uteis:[29,31],revelations_uteis:[10],
  pesos_magias:{strong_ice_wave:1,ice_burst:1,terra_burst:1,forked_glacier:1},larguraRoda:24});
assert(r.distribuicoes.length);
for(const p of r.distribuicoes){assert(HuntRTC.validarDistribuicao(cat,p,989).ok);assert.equal(W.resumo(cat,p).investidos,986);assert(W.resumo(cat,p).revelation[10]<3);}
assert(r.distribuicoes.some(p=>{const s=W.resumo(cat,p);return s.revelation[10]===2&&s.ranks[31]&&s.ranks[33]}));
const comTera=cat.fatias.find(f=>f.conviction_id===30),p=W.caminho(cat,comTera.id);
const magias=JSON.parse(fs.readFileSync('./ui/magias.json','utf8')).magias.filter(m=>['strong_ice_wave','forked_glacier'].includes(m.id));
assert(!W.modificar(cat,p,magias,[],{temporal:true}).some(m=>m.id==='terra_wave'));
const m={mortes:0,tempo_critico:0,vida_minima:70,cobertura_s:100};
const antes={saude:{EK:m,RP:m}};
assert.equal(T.naoPiora({saude:{EK:{...m,vida_minima:90},RP:{...m,vida_minima:40}}},antes),false);
assert.equal(T.naoPiora({saude:{EK:{...m,vida_minima:90}}},antes),false);
assert.equal(T.naoPiora({saude:{EK:{...m,vida_minima:90},RP:m}},antes),true);
console.log(JSON.stringify({ok:true,distribuicoes:r.distribuicoes.length,orcamento:986,hibridas:r.distribuicoes.filter(p=>W.resumo(cat,p).ranks[33]).length}));
