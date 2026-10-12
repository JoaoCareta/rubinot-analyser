const fs=require('node:fs'),assert=require('node:assert/strict');
global.HuntRTC=require('./ui/rtc');global.HuntTemporal=require('./ui/temporal');global.HuntRodaMotor=require('./ui/roda_motor');
const I=require('./ui/integracao'),cat=HuntRodaMotor.selecionar(JSON.parse(fs.readFileSync('ui/roda_catalogo.json')),'ED');
const magias=JSON.parse(fs.readFileSync('ui/magias.json')).magias.filter(m=>m.vocs.includes('ED')).map(m=>({...m,ajustado:m.bp}));
const observado={rtc:{slots:[['eternal_winter',8],['ice_burst',5],['strong_ice_wave',2],['forked_glacier',2],['avalanche_rune',1],['sudden_death_rune',1]].map(([id,creatures],i)=>({id,creatures,prioridade:i===4?2:1,mana_percent:5}))},roda:{campos:{
 'conviction.Aug. Strong Ice Wave':{valor:'II',qualidade:'texto_integral'},
 'conviction.Aug. Forked Spells':{valor:'I',qualidade:'texto_integral'},
 'revelation.Twin Bursts':{valor:'Stage 2',qualidade:'texto_integral'}}}};
const ctx={char:'QA',total:989,observado,criaturas_histograma:{8:180},janelas:[]};
const r=I.calcularRoda(cat,magias,ctx,'dano',0,{finais:8,limite_ms:6000});
assert.equal(r.estrategia,'dano');assert.equal(r.modo,null);assert.equal(r.roda.efeitos.ranks[31],2);assert.equal(r.roda.efeitos.revelation[10],2);assert(!r.roda.efeitos.ranks[28]);assert(!r.roda.efeitos.ranks[30]);
const p={treino:40,validacao:10,treino_ate:1,teste_desde:2,coeficientes:[Math.log(2),0],escala_comum:1,criaturas_min:1,criaturas_max:8,incerteza_log:.1};
const c={char:'QA',regras_versao:cat.versao,modelo:{combate_ml:{char:'QA',regras_versao:cat.versao,perfis:{'strong_ice_wave|area:1|extra:0|twin:0':p}}}};
const m={id:'strong_ice_wave',area_ampliada:true};
assert(I.perfilCombate(m,c));assert.equal(I.perfilCombate({...m,area_ampliada:false},c),null);
assert.equal(I.perfilCombate(m,{...c,char:'outro'}),null);assert.equal(I.perfilCombate(m,{...c,regras_versao:'outra'}),null);
assert.equal(I.rendimentoAprendido(m,8,c).central,2);
const ms=[{id:'wave',familia:'waves',tipo:'ofensiva',ajustado:100,cd:2,grupo:2,alvos:8}];
const modelo={combate_ml:{char:'QA',regras_versao:cat.versao,perfis:{'wave|area:0|extra:0|twin:0':p}}};
const base={char:'QA',regras_versao:cat.versao,criaturas_histograma:{8:180},janelas:[{t:0,fim:180,criaturas:8}],modelo:{}};
assert.notEqual(I.ataque(ms,{...base,modelo},{fixar:true}).score,I.ataque(ms,base,{fixar:true}).score);
const completa={...base,janelas:[{t:0,fim:180,criaturas:8,origem_alvos:'observado',alvos:{wave:4}}]};
assert.equal(I.ataque(ms,{...completa,modelo},{fixar:true}).score,I.ataque(ms,completa,{fixar:true}).score);
const rtc={preset:'ice',slots:observado.rtc.slots.map((s,i)=>({...s,tipo:i<4?'magia':'runa',slot:i<4?i+1:i-3}))};
const chave=rtc.slots.slice().sort((a,b)=>a.tipo.localeCompare(b.tipo)||a.slot-b.slot).map(s=>['tipo','slot','icone_hash','mana_percent','creatures','prioridade'].map(k=>s[k]==null?'None':String(s[k])).join(':')).join('|');
const fase={...ctx,sessao:'s1',preset:'ice',observado:{...observado,rtc},modelo:{rtc_calibracao:{escopo:{char:'QA',sessao:'s1',preset:'ice',rtc_chave:chave,roda_efeitos:{ranks:{29:1,31:1},revelation:{10:2}}},intervalos_efetivos:{strong_ice_wave:{segundos:2,validacao:20,suporte_validacao:20}}}}};
assert.equal(I.calcularRTC(cat,magias.filter(m=>m.id==='strong_ice_wave'),fase,{fixar:true}).rtc.linhas.find(m=>m.id==='strong_ice_wave').cd,4); // roda anterior I não calibra a atual II
console.log('ML compartilhado: muda o replay, preserva medição completa e isola personagem, regras, área e estágios. Dano mantém Frigo II/Twin II sem Link/Terra.');
