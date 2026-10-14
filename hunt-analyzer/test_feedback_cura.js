const assert=require('node:assert/strict'),fs=require('node:fs');
global.HuntRTC=require('./ui/rtc.js');global.HuntRodaMotor=require('./ui/roda_motor.js');
const T=global.HuntTemporal=require('./ui/temporal.js'),I=require('./ui/integracao.js');
const cat=HuntRodaMotor.selecionar(JSON.parse(fs.readFileSync('ui/roda_catalogo.json')),'ED');
const magias=JSON.parse(fs.readFileSync('ui/magias.json')).magias.filter(m=>m.vocs.includes('ED'));
const feedback={id:'relato-qa',origem:'usuario',tipo:'disputa_turno_cura',vigente:true,sessao:'s1',registrado_em:100,
 contexto:{char:'QA',hunt:'Hunt QA',pt:'pt x4',hazard:null,postura:null},provas:['inicial','final'],
 ajustes:[{id:'mass_healing',alvo:'eu',anterior:95,vida_percent:75},{id:'ultimate_healing',alvo:'eu',anterior:80,vida_percent:70}]};
const ctx={char:'QA',hunt:'Hunt QA',pt:'pt x4',sessao:'s1',hazard:6,modelo:{feedback_cura:[feedback]},
 elegibilidade_aprendizado:{cura:false},cura:{aliados:[{nome:'EK QA',vocacao:'EK'}]},observado:{}};
const calcular=c=>I.calcularRTC(cat,magias,c).cura;
const pct=(r,id)=>r.linhas.find(m=>m.id===id).vida_percent;
const resultado=calcular(ctx);
assert.equal(pct(resultado,'mass_healing'),75);assert.equal(pct(resultado,'ultimate_healing'),70);
assert.equal(pct(resultado,'restoration'),60);assert.equal(pct(resultado,'heal_friend'),80);
assert.equal(resultado.feedback.beneficio_real_validado,false);
assert.equal(resultado.linhas.filter(m=>m.origem_percentual==='feedback_usuario').length,2);
// Histórico sem modelo congelado recebe o feedback posterior do mesmo personagem,
// mesmo se a roda atual estiver ausente. Nenhuma leitura antiga é reescrita.
const historica={char:'QA',referencia_atual:{char:'QA',modelo:{feedback_cura:[feedback]}}};
const dados={estado:{historico:true,sessao:'s1'},sessao:{char:'QA',hunt:'Hunt QA',pt:'pt x4'}};
assert.equal(pct(calcular(I.contexto(dados,historica,'ED')),'mass_healing'),75);
assert.equal(pct(calcular(I.contexto(dados,{...historica,referencia_atual:{char:'Outro',modelo:{feedback_cura:[feedback]}}},'ED')),'mass_healing'),95);
assert.equal(historica.modelo,undefined);
const slotsReferencia=[{id:'heal_friend',tipo:'party',destino_indice:1,vocacao_destino:'EK',vida_percent:90,ativo:true}];
const desabilitada=I.contexto(dados,{char:'QA',cura:{id:'historica',slots:slotsReferencia},referencia_atual:{char:'QA',cura:{id:'atual',slots:slotsReferencia.map(s=>({...s,vida_percent:null,ativo:false}))}}},'ED');
assert.equal(desabilitada.observado.cura.slots[0].vida_percent,90);
assert.equal(desabilitada.observado.cura.slots[0].ativo,false);
assert.equal(desabilitada.observado.cura.slots[0].percentual_referencia_id,'historica');
assert.equal(pct(calcular({...ctx,elegibilidade_aprendizado:{cura:true}}),'mass_healing'),75);
assert.equal(pct(calcular({...ctx,cura:{postura:'utamo'}}),'mass_healing'),59);
for(const pt of ['x4','pt x4','4','PT X4'])assert.equal(pct(calcular({...ctx,pt}),'mass_healing'),75);
for(const extra of [{char:'outro'},{hunt:'outra'},{pt:'solo'},{pt:'x3'},{pt:''},{sessao:'s2'},
 {modelo:{feedback_cura:[{...feedback,provas:[]}]}},{modelo:{feedback_cura:[{...feedback,vigente:false}]}},
 {modelo:{feedback_cura:[{...feedback,qa:true}]}},{modelo:{feedback_cura:[{...feedback,origem:'inferido'}]}},
 {modelo:{feedback_cura:[{...feedback,ajustes:[{...feedback.ajustes[0],vida_percent:0}]}]}},
 {modelo:{feedback_cura:[{...feedback,ajustes:[feedback.ajustes[0],feedback.ajustes[0]]}]}}]){
 assert.equal(calcular({...ctx,...extra}).feedback,undefined);
}
const contextual={...feedback,contexto:{...feedback.contexto,hazard:6,postura:'vida'}};
assert.equal(pct(calcular({...ctx,sessao:'s2',postura:'vida',modelo:{feedback_cura:[contextual]}}),'mass_healing'),75);
assert.equal(calcular({...ctx,sessao:'s2',hazard:5,postura:'vida',modelo:{feedback_cura:[contextual]}}).feedback,undefined);
// Mesmo cooldown de cura: mas res cedo toma a oportunidade de sio, mas sua
// cobertura real pode ajudar o EK. Não tratar mas res como sempre prejudicial.
const mas={id:'mass_healing',tipo:'cura',destino:'party_e_propria',alvo:'eu',cd:2,grupo:1,cura_hp:100,vida_percent:95};
const sio={id:'heal_friend',tipo:'cura',alvo:'EK',cd:1,grupo:1,cura_hp:350,vida_percent:90};
const janela={t:0,fim:1,vida:{eu:{atual:900,maxima:1000},EK:{atual:500,maxima:1000}},cobertos:[]};
const antes=T.simular([mas,sio],{janelas:[janela]},{duracao:1});
const depois=T.simular([{...mas,vida_percent:75},sio],{janelas:[janela]},{duracao:1});
assert.equal(antes.casts.heal_friend,undefined);assert.equal(depois.casts.heal_friend,1);
assert.equal(antes.efeitos.EK,undefined);assert.equal(depois.efeitos.EK,350);
const coberto=T.simular([mas,sio],{janelas:[{...janela,cobertos:['EK']}]},{duracao:1});assert.equal(coberto.efeitos.EK,100);
const emergencia=T.simular([{...mas,vida_percent:75},sio],{janelas:[{...janela,vida:{...janela.vida,eu:{atual:300,maxima:1000}}}]},{duracao:1});
assert.equal(emergencia.casts.mass_healing,1);
// Um limiar emergencial não vira ótimo aprendido nem é elevado por busca.
const janelas=Array.from({length:40},(_,i)=>({t:i*4,fim:(i+1)*4,vida:{eu:{atual:900,maxima:1000},EK:{atual:800,maxima:1000}},dano:{eu:20,EK:70},cobertos:['EK']}));
const aprendida=T.aprenderCura([{...mas,vida_percent:75,limiar_maximo_feedback:75},sio],{janelas,qualidade:{mass_healing:{validacao:4},heal_friend:{validacao:4}}});
assert(aprendida.linhas.find(m=>m.id==='mass_healing').vida_percent<=75);
assert.equal(feedback.ajustes[0].vida_percent,75);assert.equal(ctx.observado.cura,undefined);
// A referência lida não é substituída pelo default nem ganha selo de otimização.
const propria=calcular({...ctx,modelo:{},observado:{cura:{slots:[{id:'mass_healing',tipo:'autocura',vida_percent:65}]}}});
assert.equal(pct(propria,'mass_healing'),65);
assert.equal(propria.linhas[0].origem_percentual,'observado');
const estudo={sessao:'s1',contexto:{char:'QA'},estado:'sugestao_para_testar',
 avaliacao:{hazard:6},
 referencia:[{id:'mass_healing',vida_percent:75}],
 sugestoes:[{id:'mass_healing',anterior:75,vida_percent:70,provas:['a','b'],motivo:'Condições concorrentes menores no teste separado.'}]};
const sugerida=calcular({...ctx,estudo_cura:estudo});
assert.equal(pct(sugerida,'mass_healing'),70);
assert.equal(sugerida.linhas[0].origem_percentual,'estudo_cura_observacional');
assert.equal(pct(calcular({...ctx,estudo_cura:{...estudo,sessao:'outra'}}),'mass_healing'),75);
assert.equal(pct(calcular({...ctx,estudo_cura:{...estudo,avaliacao:{hazard:5}}}),'mass_healing'),75);
assert.equal(pct(calcular({...ctx,estudo_cura:{...estudo,referencia:[{id:'mass_healing',vida_percent:95}]}}),'mass_healing'),75);
console.log('Feedback de cura: escopo, lacunas, emergência, cobertura e disputa de turno aprovados.');
