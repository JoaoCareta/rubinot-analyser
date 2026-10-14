const assert=require('node:assert/strict'),fs=require('node:fs');
global.HuntRTC=require('./ui/rtc');
const W=require('./ui/roda_motor'),T=require('./ui/temporal');
const cat=W.selecionar(JSON.parse(fs.readFileSync('./ui/roda_catalogo.json','utf8')),'ED');
const print={QTR0:50,QTR3:75,QTR2:100,QTR4:100,QTR7:150,QTR8:200,QTR5:64,QBL0:50,QBL1:75,QBL2:100,QBL5:25};
const alternativasSio=W.alternativasSio(cat,print,992),original=W.efeitos(cat,print);
assert(alternativasSio.length,'ressonância de 75 deve financiar sio II sem perder ofensiva');
for(const p of alternativasSio){const e=W.efeitos(cat,p);
 assert(HuntRTC.validarDistribuicao(cat,p,992).ok);assert.equal(e.investidos,989);assert.equal(e.ranks[33],2);
 assert.deepEqual(e.revelation,original.revelation);assert.deepEqual(e.vr,original.vr);assert.deepEqual(e.cd,original.cd);assert.deepEqual(e.alvos,original.alvos);
 assert.equal(e.bp.strong_ice_wave,original.bp.strong_ice_wave);assert.equal(e.fixo_hp,original.fixo_hp);assert(e.recursos.mana>=original.recursos.mana);
}
assert.equal(W.alternativasSio(W.selecionar(JSON.parse(fs.readFileSync('./ui/roda_catalogo.json','utf8')),'MS'),print,992).length,0);
global.HuntRodaMotor=W;global.HuntTemporal=T;global.HuntPersonalizacao=require('./ui/personalizacao');
const I=require('./ui/integracao');
const comparacao=(score,rank)=>({rtc:{robusto:score,score},roda:{efeitos:{ranks:{33:rank}}}});
assert(I.compararDano(comparacao(100,2),comparacao(100,1),true)>0);
assert(I.compararDano(comparacao(99,2),comparacao(100,1),true)<0,'não ocultar custo ofensivo');
assert.equal(I.compararDano(comparacao(100,2),comparacao(100,1),false),0);
const contextoSio={char:'ED QA',sessao:'qa-sio',hazard:5,total:992,pt:'pt x4',criaturas_histograma:{8:180},modelo:{},
 cura:{aliados:[{nome:'EK QA',vocacao:'EK'}]},observado:{rtc:{slots:[],campos:{}},cura:{slots:[],campos:{}},roda:{campos:{}}},
 estudo_sio:{sessao:'qa-sio',contexto:{char:'ED QA',hazard:5},membros:[],sugestoes:[{origem:'aprendizado_sio_parcial',sessao:'qa-sio',hazard:5,id:'heal_friend',vocacao_destino:'EK',anterior:80,vida_percent:90,provas:['qa-prova']}]},
 configuracoes_informadas:[{origem:'usuario',componente:'cura',id:'nature_s_embrace',vocacao_destino:'EK',vida_percent:50}]};
const poolSio=JSON.parse(fs.readFileSync('./ui/magias.json','utf8')).magias.filter(m=>m.vocs.includes('ED'));
const contextoXP={...contextoSio,vocacao:'ED',observado:{...contextoSio.observado,roda:{campos:{'revelation.Twin Bursts':{valor:'Stage 2',qualidade:'texto_integral'}}}}};
const refXP=I.calcularRTC(cat,poolSio,{...contextoXP,twin:{referencia:5}});
assert.equal(refXP.rtc.linhas.find(m=>['ice_burst','terra_burst'].includes(m.id)).creatures,5,'referência de XP precede simulação de dano');
const testeXP=I.calcularRTC(cat,poolSio,{...contextoXP,twin:{referencia:5,proposta:{candidato:4}},
 observado:{...contextoXP.observado,rtc:{completo:true,slots:refXP.rtc.linhas.map(m=>({...m,creatures:m.id==='ice_burst'?5:m.creatures}))},cura:{slots:refXP.cura.linhas}}});
assert.equal(testeXP.rtc.linhas.find(m=>['ice_burst','terra_burst'].includes(m.id)).creatures,4);
assert.deepEqual(testeXP.rtc.linhas.filter(m=>!['ice_burst','terra_burst'].includes(m.id)).map(m=>[m.id,m.creatures,m.prioridade,m.mana_percent]),refXP.rtc.linhas.filter(m=>!['ice_burst','terra_burst'].includes(m.id)).map(m=>[m.id,m.creatures,m.prioridade,m.mana_percent]));
const curaSio=I.calcularRTC(cat,poolSio,contextoSio).cura;
assert.equal(curaSio.linhas.find(m=>m.id==='heal_friend'&&m.vocacao_destino==='EK').vida_percent,90);
assert.equal(curaSio.linhas.find(m=>m.id==='nature_s_embrace'&&m.vocacao_destino==='EK').vida_percent,50);
assert.equal(I.calcularRTC(cat,poolSio,{...contextoSio,hazard:4}).cura.estudo_sio,null,'não transferir estudo entre Hazard');
const r=W.candidatas(cat,989,3,'vida','dano',{preencher:true,convictions_uteis:[29,31],revelations_uteis:[10],
  pesos_magias:{strong_ice_wave:1,ice_burst:1,terra_burst:1,forked_glacier:1},larguraRoda:24});
assert(r.distribuicoes.length);
for(const p of r.distribuicoes){assert(HuntRTC.validarDistribuicao(cat,p,989).ok);assert.equal(W.resumo(cat,p).investidos,986);assert(W.resumo(cat,p).revelation[10]<3);}
assert(r.distribuicoes.some(p=>{const s=W.resumo(cat,p);return s.revelation[10]===2&&s.ranks[31]&&s.ranks[33]}));
const dupla=r.distribuicoes.find(p=>{const s=W.resumo(cat,p);return s.revelation[10]===2&&Object.values(s.revelation).filter(x=>x>0).length>=2;});
assert(dupla,'busca precisa preservar Twin II combinado com outro benefício');
const duplaE=W.efeitos(cat,dupla);
assert(duplaE.fixo_hp>=13,'II + I soma 9 + 4 HP fixos por aplicação');
assert(duplaE.beneficios.length>=2);
const ataque={id:'ice_burst',tipo:'ataque',familia:'bursts',bp:100,cd:22,grupo:2};
const mod=W.modificar(cat,dupla,[ataque],[],{temporal:true})[0];
assert.equal(mod.dano_fixo_hp,duplaE.fixo_hp);
assert.equal(mod.bp,ataque.bp*(1+(duplaE.bp.ice_burst||0)),'HP fixo não pode ser somado a Base Power');
const comTera=cat.fatias.find(f=>f.conviction_id===30),p=W.caminho(cat,comTera.id);
const magias=JSON.parse(fs.readFileSync('./ui/magias.json','utf8')).magias.filter(m=>['strong_ice_wave','forked_glacier'].includes(m.id));
assert(!W.modificar(cat,p,magias,[],{temporal:true}).some(m=>m.id==='terra_wave'));
const m={mortes:0,tempo_critico:0,vida_minima:70,cobertura_s:100};
const antes={saude:{EK:m,RP:m}};
assert.equal(T.naoPiora({saude:{EK:{...m,vida_minima:90},RP:{...m,vida_minima:40}}},antes),false);
assert.equal(T.naoPiora({saude:{EK:{...m,vida_minima:90}}},antes),false);
assert.equal(T.naoPiora({saude:{EK:{...m,vida_minima:90},RP:m}},antes),true);
console.log(JSON.stringify({ok:true,distribuicoes:r.distribuicoes.length,orcamento:986,hibridas:r.distribuicoes.filter(p=>W.resumo(cat,p).ranks[33]).length}));
