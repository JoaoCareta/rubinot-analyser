const assert=require('node:assert/strict'),fs=require('node:fs');
global.HuntRTC=require('./ui/rtc.js');global.HuntRodaMotor=require('./ui/roda_motor.js');
const T=global.HuntTemporal=require('./ui/temporal.js'),I=require('./ui/integracao.js');
const ataque={id:'atk',cd:2,grupo:2,ajustado:100,tipo:'ofensiva',grupo_id:'ataque'};
const vita={id:'vita',cd:1,grupo:1,cura_hp:100,tipo:'cura',grupo_id:'cura',alvo:'eu',vida_percent:100};
let r=T.simular([ataque,vita],{janelas:[{t:0,fim:6,criaturas:1,alvos:{atk:1},vida:{eu:{atual:0,maxima:1000}}}]},{duracao:6});
assert.equal(r.casts.atk,3);assert.equal(r.casts.vita,6);assert.equal(r.cura,600);assert.equal(r.frequencia.vita,60);
assert.equal(T.simular([ataque],{criaturas:1,alvos:{atk:1}},{duracao:2}).casts.atk,1);
assert.equal(T.simular([{...ataque,cd:30}],{criaturas:1,alvos:{atk:1}},{duracao:30}).casts.atk,1);
// A barra não fornece alvos atingidos.
assert.equal(T.simular([ataque],{criaturas:12},{duracao:30}).score,0);
const gran={...vita,id:'nature_s_embrace',cd:60,alvo:'EK',cura_hp:10000},rp={...gran,alvo:'RP'};
r=T.simular([gran,rp],{vida:{EK:{atual:0,maxima:20000},RP:{atual:0,maxima:20000}}},{duracao:60});
assert.equal(r.casts.nature_s_embrace,1);assert.equal(r.sequencia.length,1);
const mas={...vita,id:'mass_healing',destino:'party_e_propria',cd:2};
r=T.simular([mas],{vida:{eu:{atual:950,maxima:1000},EK:{atual:0,maxima:1000}},cobertos:['EK']},{duracao:2});
assert.equal(r.casts.mass_healing,1);assert.equal(r.cura,150);assert.equal(r.excesso,50);
const sio={...vita,id:'heal_friend',alvo:'EK',link:.25,cura_hp:100};
r=T.simular([sio],{vida:{eu:{atual:0,maxima:1000},EK:{atual:900,maxima:1000}}},{duracao:2});
assert.equal(r.cura,125);assert.equal(r.efeitos.eu,25);assert.equal(r.casts.heal_friend,1);
// Crítico desconhecido não se torna garantido; vida alta não ativa Blessing.
r=T.simular([{...vita,critico_habilitado:true,blessing:.10}],{vida:{eu:{atual:700,maxima:1000}}},{duracao:1});assert.equal(r.cura,100);
r=T.simular([{...vita,blessing:.10}],{vida:{eu:{atual:200,maxima:1000}}},{duracao:1});assert.equal(r.cura,120);
assert.equal(T.limiares([vita],{}).estado,'A calibrar');
const picos={janelas:[{t:0,fim:2,vida:{eu:{atual:500,maxima:1000}}},{t:2,fim:4,valida:false},{t:4,fim:6,vida:{eu:{atual:700,maxima:1000}}}]};
r=T.simular([vita],picos,{duracao:6});assert.equal(r.segundos_validos,4);assert.equal(r.frequencia.vita,60);
// Link+Blessing+Greater: a mesma distribuição abastece o desenho, os efeitos e o RTC.
const cat=HuntRodaMotor.selecionar(JSON.parse(fs.readFileSync('ui/roda_catalogo.json')),'ED');
const candidatas=HuntRodaMotor.candidatas(cat,987,3,'vida_link_critica','cura',{finais:3});
assert(candidatas.distribuicoes.some(p=>HuntRodaMotor.resumo(cat,p).investidos===925));
for(const p of candidatas.distribuicoes){const e=HuntRodaMotor.efeitos(cat,p);assert(e.ranks[28]);assert(e.revelation[11]>0);assert(HuntRTC.validarDistribuicao(cat,p,987).ok);}
const f=cat.fatias.find(f=>f.conviction_id===28);assert(!HuntRodaMotor.efeitos(cat,{[f.id]:199}).ranks[28]);assert(HuntRodaMotor.efeitos(cat,{[f.id]:200}).ranks[28]);
const magias=JSON.parse(fs.readFileSync('ui/magias.json')).magias.filter(m=>m.vocs.includes('ED')).map(m=>({...m,resistencia:100,cobertura:1,ajustado:m.bp}));
const ctx={char:'QA',preset:'ice',total:987,criaturas_histograma:{1:20,4:40,7:40},cura:{},observado:{}};
r=I.calcular(cat,magias,ctx,'dano','vida_link_critica',3,{finais:2,limite_ms:5000});assert.equal(r.estado,'Calculado');assert.equal(r.cura.estado,'Recomendado');assert(!r.personalizada);
assert(r.roda.efeitos.ranks[28]&&r.roda.efeitos.revelation[11]);assert(r.rtc.linhas.filter(m=>m.tipo==='magia').every(m=>m.mana_percent===5));assert(r.roda.gemas.every(g=>g.grau==null||g.grau===1));
assert(r.rtc.linhas.filter(m=>m.tipo==='magia').length<=5);assert(r.rtc.linhas.filter(m=>m.tipo==='runa').length<=2);
assert.equal(I.calcular(cat,magias,{...ctx,total:null},'cura','vida_link',2).estado,'Total não lido');
// O objetivo Cura nunca troca uma medida ausente pelo ranking ofensivo.
r=I.calcular(cat,magias,ctx,'cura','vida_link',0,{finais:1,limite_ms:300});
assert.equal(r.estado,'Calculado');assert.equal(r.valor,r.cura.indice_base);assert(r.valor>0);assert.equal(r.cura.metricas,null);
// Dano contrafactual conserva a cura da candidata, em vez de restaurar o HP gravado.
const sustentado={janelas:Array.from({length:5},(_,i)=>({t:i,fim:i+1,modo_vida:'contrafactual',vida:{eu:{atual:1000,maxima:1000}},dano:{eu:150}}))};
r=T.simular([{...vita,cura_hp:100}],sustentado,{duracao:5});assert.equal(r.cura,500);assert.equal(r.vida_minima,65);
// Mana compartilhada, alcance e prontidão inicial são condições de execução.
r=T.simular([ataque,{...vita,mana:100}],{janelas:[{t:0,fim:6,criaturas:1,alvos:{atk:1},vida:{eu:{atual:100,maxima:1000}},mana:100,mana_maxima:100}]},{duracao:6});assert.equal(r.casts.vita,1);
r=T.simular([{...sio,alcance:7}],{vida:{EK:{atual:500,maxima:1000}},distancias:{EK:8}},{duracao:5});assert(!r.casts.heal_friend);
r=T.simular([ataque],{criaturas:1,alvos:{atk:1},pronta:{atk:2}},{duracao:6});assert.equal(r.casts.atk,2);
// Ampliação de área não inventa cobertura; bônus de BP altera cura medida.
const mh=cat.fatias.filter(f=>f.conviction_id===32),pontosMH=Object.fromEntries(mh.map(f=>[f.id,f.limite]));
const modificada=HuntRodaMotor.modificar(cat,pontosMH,magias.filter(m=>m.id==='mass_healing'),[],{temporal:true})[0];assert.equal(modificada.multiplicador_base,1.04);
const l=T.limiares([{...vita,vida_percent:99,limiar_fixo:true}],sustentado,{duracao:5,rodadas:1});assert.equal(l.linhas[0].vida_percent,99);
const gpath=cat.caminhos_minimos.find(p=>p.tier===3).pontos,dom=Object.entries(HuntRodaMotor.resumo(cat,gpath).vr).find(([,n])=>n===3)[0];
const simples={dominio:dom,tier:3,qualidade:'Greater',basicos:[{mod:38,grau:1},{mod:5,grau:1}]};
let ef=HuntRodaMotor.efeitos(cat,gpath,[simples]);assert(ef.recursos.vida>0);assert(ef.resistencias.ice>0);assert.equal(ef.fixo_hp,HuntRodaMotor.efeitos(cat,gpath).fixo_hp+2);
ef=HuntRodaMotor.efeitos(cat,gpath,[{...simples,mod:72,grau:4,magias:['mass_healing']}]);assert.equal(ef.bp.mass_healing,HuntRodaMotor.efeitos(cat,gpath).bp.mass_healing); // básicos não sustentam grau IV
// Uma gema negativa afeta defesa do jogador e não o elemento dos monstros.
ef=HuntRodaMotor.efeitos(cat,gpath,[{...simples,basicos:[{mod:15,grau:1}]}]);assert(ef.resistencias.earth<0);
// Verificação exaustiva independente: um helper, cem limiares possíveis.
const pequeno={janelas:[{t:0,fim:1,modo_vida:'contrafactual',vida:{eu:{atual:1000,maxima:1000}},dano:{eu:420}}, {t:1,fim:2,modo_vida:'contrafactual',vida:{eu:{atual:1000,maxima:1000}},dano:{eu:350}}]};
const uma={...vita,cura_hp:500,cd:2};let exaustiva=null;
for(let pct=1;pct<=100;pct++){const sim=T.simular([{...uma,vida_percent:pct}],pequeno,{duracao:2,sem_critico:true});if(!exaustiva||T.comparar(sim,exaustiva)>0)exaustiva=sim;}
const calculada=T.limiares([uma],pequeno,{duracao:2,rodadas:1});assert.equal(T.comparar(calculada.seguranca,exaustiva),0);
// Custos e buffs relativos: uma cura medida sob +4% não recebe +4% duas vezes.
const curaCtx={...ctx,cura:{potencia_hp:{mass_healing:1000},base_multiplicadores:{mass_healing:1.04},janelas:[{t:0,fim:2,vida:{eu:{atual:100,maxima:5000}}}],aliados:[]},observado:{cura:{slots:[{tipo:'autocura',id:'mass_healing',vida_percent:90}]}}};
const curaMH=I.curar(cat,pontosMH,[],magias,curaCtx,'mas_res',{fixar_limiares:true});assert.equal(curaMH.linhas.find(m=>m.id==='mass_healing').cura_hp,1000);
const tela=fs.readFileSync('ui/rtc_ui.js','utf8')+fs.readFileSync('ui/rtc_integrado_ui.js','utf8');
// RTC funciona sem pontos e sem escolher uma roda futura.
const semRoda={...ctx,total:null};
const livre=I.calcularRTC(cat,magias,semRoda);
assert(livre.rtc.linhas.some(m=>HuntRTC.categoria(m)==='UE'));
assert(livre.rtc.linhas.some(m=>m.id.startsWith('forked_')));
assert(livre.rtc.linhas.some(m=>m.runa));
assert.equal(livre.cura.linhas.length,7);assert(livre.cura.linhas.every(m=>Number.isInteger(m.vida_percent)));
const rtcAntes=I.calcularRTC(cat,magias,ctx);
const rodas={};
for(const modo of ['vida','utamo'])for(const foco of ['dano','cura'])for(const tier of [0,1,2,3]){
  const r=I.calcularRoda(cat,magias,ctx,foco,tier,{modo_vida:modo,finais:2,limite_ms:400});
  rodas[modo+'_'+foco+'_'+tier]=r;
  assert.equal(r.roda.estado,'Calculado');
  assert(HuntRTC.validarDistribuicao(cat,r.roda.pontos,ctx.total).ok);
  assert.equal(r.roda.livres,3);
  assert.equal(r.roda.investidos,ctx.total-3);
  assert(r.cura.linhas.every(m=>Number.isInteger(m.vida_percent)));
  assert.equal(r.cura.postura,foco==='cura'?modo:null);
  assert(!('rtc' in r));
}
assert.deepEqual(I.calcularRTC(cat,magias,ctx),rtcAntes);
assert(rodas.vida_cura_3.roda.efeitos.ranks[28]);
assert(rodas.utamo_cura_3.roda.efeitos.revelation[11]>0);
assert.notDeepEqual(rodas.vida_cura_3.roda.pontos,rodas.utamo_cura_3.roda.pontos);
assert.throws(()=>I.calcularRoda(cat,magias,ctx,'utamo'));
assert.throws(()=>I.calcularRoda(cat,magias,ctx,'cura',0,{modo_vida:'link'}));
assert(!tela.includes('Modo de cura do RTC'));
assert(tela.includes('Modo de jogo da roda'));
for(const proibido of ['Sequência calculada','Ver turnos e comparações','Premissas deste cenário','Alvos atingidos assumidos','Casa selecionada'])assert(!tela.includes(proibido));
// Regressão da entrega: a sugestão inicial precisa estar utilizável sem calibração.
const fria=I.calcular(cat,magias,{...ctx,criaturas_histograma:{},janelas:[]},'dano','utamo_critica',0,{finais:1,limite_ms:500});
assert.equal(fria.estado,'Calculado');assert(fria.rtc.linhas.some(m=>m.familia==='ue'));assert(fria.rtc.linhas.some(m=>m.id.startsWith('forked_')));assert(fria.rtc.linhas.some(m=>m.runa&&m.alvos!==1));
assert(fria.rtc.linhas.filter(m=>m.tipo==='magia').length<=5);assert(fria.rtc.linhas.filter(m=>m.runa).length<=2);assert(fria.rtc.linhas.filter(m=>HuntRTC.categoria(m)==='Single').length<=1);
assert(fria.cura.linhas.every(m=>Number.isInteger(m.vida_percent)&&m.vida_percent>=1&&m.vida_percent<=100));assert.equal(fria.cura.linhas.filter(m=>!m.vocacao_destino).length,3);assert.equal(fria.cura.linhas.filter(m=>m.vocacao_destino).length,4);assert(!fria.personalizada);
assert(fria.cura.linhas.every(m=>m.origem_percentual==='recomendado'));assert(fria.cura.linhas.every(m=>m.frequencia===null));assert.equal(fria.cura.metricas,null);
const inicial=I.curar(cat,{},[],magias,ctx,'vida_link99');assert.equal(inicial.linhas.find(m=>m.vocacao_destino==='EK'&&m.id==='heal_friend').vida_percent,99);
assert.notEqual(inicial.linhas.find(m=>m.id==='ultimate_healing').vida_percent,fria.cura.linhas.find(m=>m.id==='ultimate_healing').vida_percent);
const parcial=I.calcular(cat,magias.map(m=>({...m,resistencia:null,ajustado:null,cobertura:0})),{...ctx,criaturas_histograma:{}},'dano','vida',0,{finais:1,limite_ms:500});assert(parcial.rtc.linhas.length>=4);assert(parcial.rtc.linhas.some(m=>m.familia==='ue'));assert(parcial.rtc.linhas.some(m=>m.runa));assert(parcial.cura.linhas.every(m=>m.vida_percent!=null));
const neutra=I.ataque(magias.filter(m=>m.tipo==='ofensiva').map(m=>({...m,ajustado:0})),ctx);assert(!neutra.linhas.length); // imunidade não vira candidata positiva.
const integrado=fs.readFileSync('ui/rtc_integrado_ui.js','utf8');assert(!/a calibrar|calibração parcial|Faltam vida|quantidade atingida/i.test(integrado));
// Sem sequência temporal, a mediana de cobertura não inventa espera por uma leva.
const combate=magias.filter(m=>HuntRTC.categoria(m)&&!m.requer_roda);
for(const cobertura of [null,{forked_thorns:1,forked_glacier:1},Object.fromEntries(combate.map(m=>[m.id,1]))]){
  const leve=I.ataque(combate,{...ctx,criaturas_histograma:{1:20,2:30,4:30,11:20},janelas:[],cobertura});
  assert(leve.linhas.filter(m=>!m.runa&&m.alvos!==1&&m.familia!=='ue').every(m=>m.creatures===2));
  assert(leve.linhas.filter(m=>m.runa).every(m=>m.creatures===1&&m.prioridade>=1&&m.prioridade<=2));
  assert(leve.linhas.filter(m=>m.familia==='ue').every(m=>m.creatures===8));
  assert(leve.faixa[0]<leve.faixa[1]); // mapa parcial não se torna cobertura completa
  const duas=T.simular(leve.linhas,{criaturas:2,alvos:Object.fromEntries(leve.linhas.map(m=>[m.id,Math.min(2,m.alvos??2)]))},{duracao:30});
  assert(leve.linhas.filter(m=>m.id.startsWith('forked_')).some(m=>duas.casts[m.id]>0));
  assert(!leve.linhas.filter(m=>m.familia==='ue').some(m=>duas.casts[m.id]>0));
  const apoio=T.simular(leve.linhas,{criaturas:1,disponiveis:{sudden_death_rune:false},alvos:Object.fromEntries(leve.linhas.map(m=>[m.id,1]))},{duracao:6});
  assert(leve.linhas.filter(m=>m.runa&&m.alvos!==1).some(m=>apoio.casts[m.id]>0));
  const isolado=T.simular(leve.linhas,{criaturas:1,alvos:Object.fromEntries(leve.linhas.map(m=>[m.id,1]))},{duracao:6});
  assert(isolado.casts.sudden_death_rune>0);assert(!leve.linhas.filter(m=>!m.runa&&m.alvos!==1).some(m=>isolado.casts[m.id]>0));
}
const cenariosParciais=I.cenarios({...ctx,cobertura:{forked_thorns:1},janelas:[{t:0,fim:6,criaturas:11}]},combate);
assert.equal(cenariosParciais[0].alvos.forked_thorns,Math.min(11,combate.find(m=>m.id==='forked_thorns').alvos??11));
const alvosReais=I.cenarios({...ctx,janelas:[{t:0,fim:6,criaturas:11,origem_alvos:'observado',alvos:{forked_thorns:2}}]},combate);
assert.equal(alvosReais[0].alvos.forked_thorns,2);assert.notEqual(alvosReais[0].origem_alvos,'observado');
const fixa=I.ataque([{...combate.find(m=>m.id==='forked_thorns'),prioridade:2,creatures:3,mana_percent:5}],ctx,{fixar:true});assert.equal(fixa.linhas[0].creatures,3);assert.equal(fixa.linhas[0].prioridade,2);
console.log('Temporal: relógios independentes, limite exclusivo, cura útil, excesso, Link, mas res, gran sio, gaps, mana 5%, grafo, graus e interface aprovados.');

const slotsCal=[{tipo:'magia',slot:1,icone_hash:'gelo',mana_percent:5,creatures:2,prioridade:1}];
const escopoCal={char:ctx.char,sessao:ctx.sessao,preset:ctx.preset,rtc_chave:'magia:1:gelo:5:2:1'};
const ctxCal={...ctx,observado:{...ctx.observado,rtc:{slots:slotsCal}},modelo:{rtc_calibracao:{escopo:escopoCal,intervalos_efetivos:{forked_glacier:{segundos:4,validacao:10,suporte_validacao:10}}}}};
const rtcCal=I.calcularRTC(cat,magias,ctxCal).rtc;
assert.equal(rtcCal.linhas.find(m=>m.id==='forked_glacier').cd,4);
assert.equal(I.calcularRTC(cat,magias,{...ctxCal,sessao:'outra'}).rtc.linhas.find(m=>m.id==='forked_glacier').cd,6);
assert.equal(I.calcularRTC(cat,magias,{...ctxCal,preset:'outro'}).rtc.linhas.find(m=>m.id==='forked_glacier').cd,6);
const mudou={...ctxCal,observado:{...ctxCal.observado,rtc:{slots:[{...slotsCal[0],prioridade:2}]}}};
assert.equal(I.calcularRTC(cat,magias,mudou).rtc.linhas.find(m=>m.id==='forked_glacier').cd,6);
console.log('Calibração RTC: intervalo efetivo validado e isolado por sessão/preset/campos.');

// Runa pronta em prioridade 2 ocupa os turnos de magia 3; ambos usam ataque.
const magiaTurno={id:'wave',tipo:'ofensiva',runa:false,cd:4,grupo:2,grupo_id:'ataque',ajustado:140,creatures:2,prioridade:3};
const runaTurno={id:'rune',tipo:'runa',runa:true,cd:2,grupo:2,grupo_id:'ataque',ajustado:50,creatures:1,prioridade:2};
const estadoTurno={pronta:{wave:0,rune:0},criaturas_histograma:{4:60},janelas:[{t:0,fim:60,criaturas:4,origem_alvos:'observado',alvos:{wave:4,rune:4}}]};
const ocupada=I.ataque([magiaTurno,runaTurno],estadoTurno,{fixar:true});
assert.equal(ocupada.casts.rune,30);assert.equal(ocupada.casts.wave||0,0);
const corrigida=I.ataque([{...magiaTurno,prioridade:1},runaTurno],estadoTurno,{fixar:true});
assert.equal(corrigida.casts.wave,15);assert.equal(corrigida.casts.rune,15);
assert.equal(T.simular([magiaTurno,runaTurno],{criaturas:0,alvos:{wave:0,rune:0}},{duracao:10}).score,0);
console.log('Disputa de turnos: runa pronta ocupa magia inferior; sem monstros não há ataque.');

// A roda parcial já comprova benefícios; não excluir Twin nem exigir fatias ocultas.
const rodaParcial={...ctx,total:null,observado:{roda:{completo:false,campos:{
  'revelation.Twin Bursts':{valor:'Stage 2',qualidade:'texto_integral'},
  'conviction.Aug. Forked Spells':{valor:'I',qualidade:'texto_integral'},
  'conviction.Aug. Strong Ice Wave':{valor:'II',qualidade:'texto_integral'}
}}},criaturas_histograma:{8:180},janelas:[]};
const twinRTC=I.calcularRTC(cat,magias,rodaParcial).rtc;
const twin=twinRTC.linhas.find(m=>m.familia==='bursts');
assert(twin);assert.equal(twin.cd,18);assert.equal(twin.twin_bonus,.4);assert(twinRTC.casts[twin.id]>0);
assert.equal(twinRTC.linhas.find(m=>m.id==='forked_glacier').cd,4);
// Benefício desconhecido não vira desbloqueio, e benefício sem qualidade não entra.
assert(!I.calcularRTC(cat,magias,{...rodaParcial,observado:{roda:{campos:{}}}}).rtc.linhas.some(m=>m.familia==='bursts'));
assert(!I.calcularRTC(cat,magias,{...rodaParcial,observado:{roda:{campos:{'revelation.Twin Bursts':{valor:'Stage 2',qualidade:'parcial'}}}}}).rtc.linhas.some(m=>m.familia==='bursts'));
// Extras que nunca entram não ocupam um slot só para preencher cinco magias.
const somenteGelo=I.ataque(combate.filter(m=>['eternal_winter','strong_ice_wave','forked_glacier','terra_wave','forked_thorns','avalanche_rune','sudden_death_rune'].includes(m.id)).map(m=>m.id==='forked_glacier'?{...m,cd:4}:m),{...ctx,criaturas_histograma:{4:180},janelas:[]});
assert(!somenteGelo.linhas.some(m=>!m.runa&&m.familia!=='ue'&&!somenteGelo.casts[m.id]));
// A roda preserva a composição RTC recomendada e seu desbloqueio Twin.
const alinhada=I.calcularRoda(cat,magias,{...rodaParcial,total:988},'dano',0,{modo_vida:'utamo',finais:8,limite_ms:5000});
assert.equal(alinhada.roda.estado,'Calculado');assert(alinhada.roda.efeitos.revelation[10]>0);
assert.equal(alinhada.roda.investidos,985);
console.log('RTC/roda: Twin observado II executa; extras sem uso não preenchem slots; a roda conserva a composição RTC.');

// Levas repetidas: cooldown longo pode reunir alvos sem sacrificar as waves.
const levas=[];
for(let t=0;t<180;t+=30)levas.push({t,fim:t+8,criaturas:2},{t:t+8,fim:t+20,criaturas:8},{t:t+20,fim:t+30,criaturas:2});
const balancear=[{id:'burst',familia:'bursts',tipo:'ofensiva',cd:18,grupo:2,ajustado:115},
  {id:'wave',tipo:'ofensiva',cd:4,grupo:2,ajustado:140}];
const eq=I.equalizarCriaturas(balancear,{janelas:levas,criaturas_histograma:{2:108,8:72}});
assert.equal(eq.estado,'replay_validado');assert(eq.linhas[0].creatures>eq.linhas[1].creatures);
assert.equal(eq.linhas[1].creatures,2);assert(eq.potencia_depois>eq.potencia_antes);
assert(eq.equilibrio_depois>eq.equilibrio_antes);
assert(eq.magias[0].ativacoes_depois<eq.magias[0].ativacoes_antes); // aceita menos casts apenas com ganho de potência
assert.equal(eq.origem_alvos,'referencia_parcial');assert.equal(eq.validacao,'trecho_final_separado');
// Se a leva permanece pequena, não há motivo para esperar criaturas inexistentes.
const pequena=I.equalizarCriaturas(balancear,{janelas:[{t:0,fim:180,criaturas:2}],criaturas_histograma:{2:180}});
assert(pequena.linhas.every(m=>m.creatures===2));
// Uma sequência futura desfavorável rejeita o ganho restrito ao começo da hunt.
const instavel=I.equalizarCriaturas(balancear,{janelas:[...levas.filter(j=>j.fim<=120),{t:120,fim:180,criaturas:2}],criaturas_histograma:{2:132,8:48}});
assert.equal(instavel.linhas[0].creatures,2);
const curto=I.equalizarCriaturas(balancear,{janelas:[{t:0,fim:20,criaturas:8}],criaturas_histograma:{8:20}});
assert.equal(curto.estado,'referencia_inicial');
assert.deepEqual(balancear.map(m=>m.creatures),[undefined,undefined]);
console.log('Criaturas: espera com cooldown, ativações versus potência e validação cronológica aprovadas.');

// Cura pertence ao RTC, independente da roda que está sendo planejada.
assert.equal(livre.cura.postura,'vida');
assert.deepEqual(I.calcularRTC(cat,magias,semRoda,{modo_vida:'utamo'}).cura,livre.cura);
assert.equal(livre.cura.aprendizado.estado,'coletando');
const linkLido={...semRoda,observado:{roda:{campos:{'conviction.Healing Link':{valor:'I',qualidade:'texto_integral'}}}}};
const curaLink=I.calcularRTC(cat,magias,linkLido).cura;
assert.equal(curaLink.linhas.find(m=>m.id==='heal_friend'&&m.vocacao_destino==='EK').vida_percent,90);
assert.equal(curaLink.linhas.find(m=>m.id==='heal_friend'&&m.vocacao_destino==='RP').vida_percent,85);
assert.equal(curaLink.linhas.find(m=>m.id==='heal_friend').link,.25);
const magiasMS=JSON.parse(fs.readFileSync('ui/magias.json')).magias.filter(m=>m.vocs.includes('MS')).map(m=>({...m,ajustado:m.bp,resistencia:100}));
const catMS=HuntRodaMotor.selecionar(JSON.parse(fs.readFileSync('ui/roda_catalogo.json')),'MS');
assert(!I.calcularRTC(catMS,magiasMS,semRoda).cura.linhas.some(m=>m.vocacao_destino));

// Ajuste aprendido em perigo recorrente; a validação é cronologicamente posterior.
const politica=[{...vita,cd:2,cura_hp:500,vida_percent:30,origem_percentual:'recomendado'}];
const vidaTreino=Array.from({length:90},(_,i)=>({t:i*2,fim:i*2+2,modo_vida:'contrafactual',vida:{eu:{atual:1000,maxima:1000}},dano:{eu:180}}));
const aprendizadoCtx={janelas:vidaTreino,qualidade:{vita:{validacao:4}}};
const aprendeu=T.aprenderCura(politica,aprendizadoCtx);
assert.equal(aprendeu.aprendizado.estado,'aprendizado_validado');
assert(aprendeu.linhas[0].vida_percent>politica[0].vida_percent);
assert(aprendeu.aprendizado.depois.vida_minima>aprendeu.aprendizado.antes.vida_minima);
assert(aprendeu.aprendizado.treino_ate<=aprendeu.aprendizado.teste_desde);
assert(aprendeu.aprendizado.ajustes.length<=2);
assert.equal(politica[0].vida_percent,30);assert.equal(vidaTreino[0].vida.eu.atual,1000);
const naoGeneraliza=T.aprenderCura(politica,{...aprendizadoCtx,janelas:vidaTreino.map((j,i)=>i<60?j:{...j,modo_vida:'observado',dano:{eu:900}})});
assert.equal(naoGeneraliza.aprendizado.estado,'validado_sem_melhoria');
assert.equal(naoGeneraliza.linhas[0].vida_percent,30);
assert.equal(naoGeneraliza.aprendizado.ajustes.length,0);
for(const semEvidencia of [{...aprendizadoCtx,qualidade:{}},{...aprendizadoCtx,janelas:vidaTreino.slice(0,10)},
 {...aprendizadoCtx,janelas:vidaTreino.map((j,i)=>i===30?{...j,vida:{eu:{atual:90}}}:j)},
 {...aprendizadoCtx,janelas:vidaTreino.filter((j,i)=>i!==40)}]){
 const q=T.aprenderCura(politica,semEvidencia);assert.equal(q.aprendizado.estado,'coletando');assert.equal(q.linhas[0].vida_percent,30);assert.equal(q.linhas[0].frequencia,null);
}
const aliados=[{...politica[0],id:'heal_friend',alvo:'Knight',vocacao_destino:'EK'}, {...politica[0],id:'heal_friend',alvo:'Paladin',vocacao_destino:'RP',vida_percent:45}];
const partyAprendida=T.aprenderCura(aliados,{qualidade:{heal_friend:{validacao:4}},janelas:vidaTreino.map(j=>({...j,vida:{Knight:{atual:1000,maxima:1000},Paladin:{atual:1000,maxima:1000}},dano:{Knight:180,Paladin:60}}))});
assert.deepEqual(partyAprendida.linhas.map(m=>m.vocacao_destino),['EK','RP']);
assert.deepEqual(partyAprendida.linhas.map(m=>m.alvo),['Knight','Paladin']);
assert(partyAprendida.aprendizado.ajustes.length<=2);
console.log('Cura RTC: política aprendida, validação futura, lacunas, EK/RP e independência da roda aprovados.');

// Sugestões no histórico usam a roda atual sem inventar uma leitura no passado.
const huntAntiga={estado:{historico:true,sessao:'antiga'},sessao:{char:'ED teste',hunt:'Cripta'},
  voltas:[{ini:0,fim:180}],amostras:Array.from({length:91},(_,i)=>[i*2,13,100,100,6])};
const referencia={char:'ED teste',rtc:{vocacao:'ED'},pontos:{valor:989},
  roda:{campos:{'revelation.Twin Bursts':{valor:'Stage 2',qualidade:'texto_integral'}}},
  contexto:{cura:{janelas:[{t:999}]},nivel:999},modelo:{rtc_calibracao:{sessao:'nova'},combate_ml:{char:'ED teste',estado:'coletando'}}};
const obsAntiga={char:'ED teste',referencia_atual:referencia};
const antesObs=JSON.stringify(obsAntiga),ctxAntigo=I.contexto(huntAntiga,obsAntiga,'ED');
assert.equal(ctxAntigo.referencia_roda,'atual_para_proxima_hunt');
assert.equal(ctxAntigo.total,989);assert.equal(ctxAntigo.janelas.length,90);
assert.deepEqual(ctxAntigo.cura,{});assert.equal(ctxAntigo.nivel,null);
assert.equal(ctxAntigo.modelo.rtc_calibracao,undefined);
assert.deepEqual(ctxAntigo.observado.rtc.slots,[]);
assert(I.calcularRTC(cat,magias,ctxAntigo).rtc.linhas.some(m=>m.familia==='bursts'));
assert.equal(JSON.stringify(obsAntiga),antesObs);assert.equal(obsAntiga.roda,undefined);
for(const [dados,obs,voc] of [[huntAntiga,{...obsAntiga,referencia_atual:{...referencia,char:'Outro'}},'ED'],
  [huntAntiga,obsAntiga,'MS'],[{...huntAntiga,estado:{historico:false}},obsAntiga,'ED'],[huntAntiga,{char:'ED teste'},'ED']]){
  const c=I.contexto(dados,obs,voc);assert.equal(c.referencia_roda,'sessao');assert.deepEqual(c.observado.roda.campos,{});
}
console.log('Histórico: roda atual por personagem/vocação, Twin e isolamento das leituras aprovados.');
