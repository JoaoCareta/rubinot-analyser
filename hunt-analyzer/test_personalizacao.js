const assert=require('node:assert/strict');
const P=require('./ui/personalizacao.js');
const atual=[{id:'a',tipo:'magia',slot:1,prioridade:1,creatures:2,mana_percent:5,cd:4,grupo:2},
{id:'b',tipo:'magia',slot:2,prioridade:2,creatures:2,mana_percent:5,cd:6,grupo:2}];
const pool=[...atual,{...atual[1],id:'c'}];
for(const c of P.candidatas(atual,pool))assert.ok(P.alteracoes(atual,c).length<=2);
const janelas=Array.from({length:12},(_,n)=>({t:n*10,fim:n*10+10,origem_alvos:'observado',vida:{eu:{atual:100,maxima:100}},mana_maxima:100,criaturas:4}));
const partes=P.dividir(janelas);assert.equal(partes.treino.length,6);assert.equal(partes.selecao.length,3);assert.equal(partes.teste.length,3);
const ctx={char:'QA',sessao:'s',pt:'solo',pronta:{a:0,b:0,c:0},janelas,elegibilidade_aprendizado:{selecao_ataque:true},validacao_execucao:{promover:true,escopo:{char:'QA',sessao:'s'}}};
let testes=0;
const sim=(lista,c)=>{if(c.janelas.length===3&&c.janelas[0].t===0)testes++;
return {score:lista.some(m=>m.id==='c')?120:100,mortes:0,tempo_critico:0,manaGasta:5,
saude:{eu:{vida_minima:100,cobertura_s:30}},casts:Object.fromEntries(lista.map(m=>[m.id,5]))};};
assert.equal(P.buscar(atual,pool,{...ctx,validacao_execucao:{}},sim).personalizada,false);
assert.equal(P.buscar(atual,pool,{...ctx,hazard:4},sim).personalizada,false);
const r=P.buscar(atual,pool,ctx,sim);assert.equal(r.personalizada,true);assert.ok(r.alteracoes.length<=2);assert.equal(r.validacao.testes_abertos,1);
const pior=(lista,c)=>({...sim(lista,c),saude:{eu:{vida_minima:lista.some(m=>m.id==='c')?20:100,cobertura_s:30}}});
assert.equal(P.buscar(atual,pool,ctx,pior).personalizada,false);
assert.equal(P.buscar(atual,pool,{...ctx,janelas:janelas.map(j=>({...j,origem_alvos:'referencia'}))},sim).personalizada,false);
assert.equal(P.buscar(atual,pool,{...ctx,pronta:{}},sim).personalizada,false);
assert.equal(P.buscar(atual,pool,{...ctx,pt:'x2'},sim).personalizada,false);
assert.equal(P.buscar(atual,pool,{...ctx,declaracao_uso_id:'nova',validacao_execucao:{...ctx.validacao_execucao,escopo:{...ctx.validacao_execucao.escopo,declaracao_uso_id:'antiga'}}},sim).personalizada,false);
const base={rtc:atual,cura:[{id:'sio',alvo:'EK',vida_percent:70}],pontos:{a:100,b:100}};
assert.equal(P.alteracoesPacote(base,{...base,pontos:{a:95,b:105}}).length,2);
assert.equal(P.alteracoesPacote(base,{...base,cura:[{id:'sio',alvo:'EK',vida_percent:80}],pontos:{a:95,b:105}}).length,3);
console.log('Personalização: limites de ajustes, cobertura, partição e rejeição de risco aprovados.');
