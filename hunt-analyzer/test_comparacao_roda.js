const assert=require('node:assert/strict'),fs=require('node:fs');
global.HuntRTC=require('./ui/rtc');global.HuntRodaMotor=require('./ui/roda_motor');global.HuntTemporal=require('./ui/temporal');
const I=require('./ui/integracao'),W=HuntRodaMotor;
const cat=W.selecionar(JSON.parse(fs.readFileSync('ui/roda_catalogo.json')),'ED');
const magias=JSON.parse(fs.readFileSync('ui/magias.json')).magias.filter(m=>m.vocs.includes('ED')).map(m=>({...m,resistencia:m.elemento==='gelo'?120:80,ajustado:m.bp*(m.elemento==='gelo'?1.2:.8)}));
const campo=valor=>({valor,qualidade:'texto_integral'});
const campos={'conviction.Aug. Strong Ice Wave':campo('II'),'conviction.Aug. Forked Spells':campo('I'),
 'conviction.Aug. Heal Friend':campo('II'),'revelation.Twin Bursts':campo('Stage 2'),
 'revelation.Blessing of the Grove':campo('Stage 1'),'vessels.Strong Ice Wave':campo('+12%'),
 'vessels.Damage and Healing':campo('+4'),'revelation.Damage and Healing':campo('+13')};
const ctx={char:'QA',hunt:'QA gelo',pt:'pt x4',hazard:5,total:994,criaturas_histograma:{8:180},
 observado:{roda:{campos,preset:'QA',completo:false},rtc:{completo:true,slots:[{id:'strong_ice_wave',tipo:'magia',slot:1,creatures:2,prioridade:1,mana_percent:5},{id:'forked_glacier',tipo:'magia',slot:2,creatures:2,prioridade:2,mana_percent:5}]},cura:{slots:[],completo:false}},modelo:{}};
const pontos={QTR0:50,QTR3:75,QTR2:100,QTR4:100,QTR7:150,QTR8:16,QBL0:50,QBL1:75,QBL2:100,QBL3:25,QBL4:100,QBL5:150};
const gema={dominio:'TR',tier:3,grau:1,mod:74,basicos:[{mod:38,grau:1},{mod:5,grau:1}]};
const candidata={pontos,gemas:[gema],efeitos:W.efeitos(cat,pontos,[gema])};
const ref=I.referenciaRoda(cat,ctx);
assert.equal(ref.efeitos.fixo_hp,17);assert(Math.abs(ref.efeitos.bp.strong_ice_wave-.18)<1e-9);
assert.equal(ref.completa,false);assert.equal(ref.gemas_completas,false);assert.equal(ref.pontos,null);
const cmp=I.compararRoda(cat,magias,ctx,candidata);
const relato={id:'relato-roda',origem:'usuario',tipo:'desempenho_insatisfatorio',vigente:true,
 sessao:'sessao-qa',contexto:{char:ctx.char,hunt:ctx.hunt,pt:ctx.pt},provas:['roda-pos-troca']};
const ctxRelato={...ctx,sessao:'sessao-qa',modelo:{feedback_roda:[relato]}};
const revista=I.compararRoda(cat,magias,ctxRelato,candidata);
assert.equal(revista.feedback.id,relato.id);assert.equal(revista.recomendar,false);
assert.equal(revista.feedback.beneficio_real_validado,false);
assert.equal(I.compararRoda(cat,magias,{...ctxRelato,pt:'x4'},candidata).feedback.id,relato.id);
assert.equal(revista.ganho_real_dano,null);
const rejeicao={...relato,rejeitada:true,escopo:'mesmo_contexto_proximas_hunts',
 contexto:{...relato.contexto,vocacao:'ED',hazards:[5,6]},
 roda_rejeitada:{preset:'roda-reprovada',beneficios:{ranks:{29:2,31:1,33:2},revelation:{10:1,11:2}}}};
const ctxRejeicao={...ctxRelato,modelo:{feedback_roda:[rejeicao]}};
assert.equal(I.feedbackRoda(cat,{...ctxRejeicao,sessao:'proxima',pt:'x4'}).id,rejeicao.id);
for(const extra of [{char:'outro'},{hunt:'outra'},{pt:'solo'},{pt:'x3'},
 {sessao:'proxima',hazard:4},{sessao:'proxima',hazard:null},
 {modelo:{feedback_roda:[{...rejeicao,vigente:false}]}},
 {modelo:{feedback_roda:[{...rejeicao,qa:true}]}},
 {modelo:{feedback_roda:[{...rejeicao,provas:[]}]}}])assert.equal(I.feedbackRoda(cat,{...ctxRejeicao,...extra}),undefined);
assert.equal(I.feedbackRoda({...cat,vocacao:'MS'},ctxRejeicao),undefined);
assert(I.rodaRejeitada(rejeicao,{...rejeicao.roda_rejeitada.beneficios,fixo_hp:999}),'Renomear ou preencher pontos não elimina rejeição dos benefícios');
assert(!I.rodaRejeitada(rejeicao,ref.efeitos));
assert(I.compararRoda(cat,magias,ctxRejeicao,{...candidata,efeitos:{...candidata.efeitos,...rejeicao.roda_rejeitada.beneficios}}).motivos.some(m=>m.includes('reprovada')));
const mantida=I.calcularRoda(cat,magias,ctxRejeicao,'dano',0,{limite_ms:1500,finais:3});
assert.equal(mantida.roda.estado,'Calculado');
assert.equal(mantida.roda.comparacao_atual.recomendar,false);
assert.equal(mantida.roda.personalizada,false);
assert(Object.keys(mantida.roda.pontos).length>0);
assert(mantida.roda.efeitos.ranks[31]>=2);
assert(mantida.roda.efeitos.revelation[10]>=2);
assert.equal(mantida.roda.rejeicao.melhoria_demonstrada,false);
assert(!I.rodaRejeitada(rejeicao,mantida.roda.efeitos));
assert.equal(I.feedbackRoda(cat,{...ctxRejeicao,objetivo_roda:'cura'}),undefined);
for(const tier of [0,1,2,3])for(const [objetivo,modo] of [['dano','utamo'],['cura','vida'],['cura','utamo']]){
 const r=I.calcularRoda(cat,magias,ctxRejeicao,objetivo,tier,{limite_ms:1000,finais:3,modo_vida:modo});
 assert.equal(r.roda.estado,'Calculado',objetivo+' '+tier);
 assert.equal(r.roda.livres,3);
 assert(HuntRTC.validarDistribuicao(cat,r.roda.pontos,ctxRejeicao.total).ok);
 assert.equal(r.roda.gemas.length>0,tier>0);
 if(tier)assert(r.roda.gemas.some(g=>g.tier===tier));
 for(const g of r.roda.gemas){assert(g.tier<=tier);assert(r.roda.efeitos.vr[g.dominio]>=g.tier);}
 if(objetivo==='cura')assert.equal(r.roda.rejeicao,undefined);
 else {assert(r.roda.efeitos.ranks[31]>=2);assert(r.roda.efeitos.revelation[10]>=2);}
}
// Leitura parcial: a ausência de Blessing no resumo não dispensa o suporte
// exigido para ED em party, inclusive nas sementes de Regular e Greater.
const parcial={...ctxRejeicao,observado:{...ctxRejeicao.observado,roda:{campos:{
 'conviction.Aug. Strong Ice Wave':campo('II'),'conviction.Aug. Heal Friend':campo('II')}}}};
for(const tier of [0,1,2,3]){
 const r=I.calcularRoda(cat,magias,parcial,'dano',tier,{limite_ms:1000,finais:3});
 assert.equal(r.roda.estado,'Calculado','referência parcial '+tier);
 assert(r.roda.efeitos.ranks[31]>=2&&r.roda.efeitos.ranks[33]>=2&&r.roda.efeitos.revelation[11]>=1);
 assert(HuntRTC.validarDistribuicao(cat,r.roda.pontos,parcial.total).ok);
}
const refAntiga={...ctxRejeicao,observado:{...ctxRejeicao.observado,roda:{preset:'roda-reprovada',campos:{...campos,
 'conviction.Aug. Forked Spells':campo('II'),'conviction.Aug. Strong Ice Wave':campo('I'),
 'revelation.Twin Bursts':campo('Stage 1'),'revelation.Blessing of the Grove':campo('Stage 2')}}}};
assert.equal(I.calcularRoda(cat,magias,refAntiga,'dano',0,{limite_ms:1000,finais:2}).roda.referencia_reprovada,true,'Referência antiga não pode voltar como manter a atual');
for(const extra of [{sessao:'outra'},{char:'outro'},{pt:'solo'},{pt:'x3'},
 {modelo:{feedback_roda:[{...relato,provas:[]}]}},{modelo:{feedback_roda:[{...relato,qa:true}]}}])
 assert.equal(I.compararRoda(cat,magias,{...ctxRelato,...extra},candidata).feedback,undefined);
assert.equal(cmp.ganhos.fixo_delta,3);assert.equal(cmp.ganhos.sio_base_atual,10);assert.equal(cmp.ganhos.sio_base_candidato,10);
assert.equal(cmp.ganhos.critico_atual,true);assert.equal(cmp.ganhos.blessing_candidato,2);
const frigo=cmp.magias.find(m=>m.id==='strong_ice_wave');
assert(frigo.area_atual&&!frigo.area_candidata);assert(Math.abs(frigo.variacao_base_percent-(1.06/1.18-1)*100)<1e-8);
assert.equal(cmp.recomendar,false);assert.equal(cmp.ganho_real_dano,null);assert.equal(cmp.ganho_real_cura,null);
assert.equal(cmp.cenarios.length,4);assert(cmp.cenarios.every(c=>c.cura_util_hp===null&&c.ganho_real_dano===null));
assert.equal(cmp.cenarios[0].delta_indice_dano,0);assert(cmp.lacunas.some(x=>x.includes('posicionamento')));
const rtcParcial=I.compararRoda(cat,magias,{...ctx,observado:{...ctx.observado,rtc:{...ctx.observado.rtc,completo:false}}},candidata);
assert.equal(rtcParcial.cenarios[0].indice_dano,null);assert.equal(rtcParcial.cenarios[2].indice_dano,null);
const sioFraco={...candidata,pontos:{...pontos,QTR4:0},gemas:[]};sioFraco.efeitos=W.efeitos(cat,sioFraco.pontos);
assert(I.compararRoda(cat,magias,ctx,sioFraco).motivos.some(m=>m.includes('Sio II')));
assert(!I.compararRoda(cat,magias,{...ctx,pt:'solo'},sioFraco).motivos.some(m=>m.includes('Sio II')));
const lacuna=I.referenciaRoda(cat,{...ctx,observado:{...ctx.observado,roda:{campos:{}}}});
assert.equal(lacuna.fixo_conhecido,false);assert.equal(lacuna.bonus_frigo_conhecido,false);
const caminho=cat.caminhos_minimos.find(p=>p.tier===3),dom=Object.entries(W.resumo(cat,caminho.pontos).vr).find(([,n])=>n===3)[0];
const g={dominio:dom,tier:3,mod:69,grau:4,basicos:[{mod:38,grau:4},{mod:5,grau:4}]};
assert.equal(W.efeitos(cat,caminho.pontos,[g]).bp.strong_ice_wave,(W.efeitos(cat,caminho.pontos).bp.strong_ice_wave||0)+.12,'modificador observado resolve a magia sem lista redundante');
const completos=Object.fromEntries(cat.fatias.map(f=>['fatias.'+f.id,campo(caminho.pontos[f.id]||0)]));
completos['gemas.'+dom]=campo({...g,equipada:true,estado:'observado_completo',modificadores:[{mod:69,grau:4}]});
const ctxCompleto={...ctx,total:994,observado:{...ctx.observado,roda:{completo:true,campos:completos}}};
assert.equal(I.referenciaRoda(cat,ctxCompleto).gemas_completas,true);
assert.equal(I.referenciaRoda(cat,{...ctxCompleto,observado:{...ctxCompleto.observado,roda:{completo:true,campos:{...completos,['gemas.'+dom]:campo({estado:'parcial'})}}}}).gemas_completas,false);
const perfil={treino:40,validacao:10,treino_ate:1,teste_desde:2,coeficientes:[Math.log(2),0],escala_comum:1,criaturas_min:1,criaturas_max:8,incerteza_log:.1};
const key='strong_ice_wave|area:1|extra:0|twin:0',ml={char:'QA',regras_versao:cat.versao,contextos:{[JSON.stringify(['solo','QA gelo',5])]:{perfis:{[key]:perfil}}}};
const cML={...ctx,regras_versao:cat.versao,modelo:{combate_ml:ml}},m={id:'strong_ice_wave',area_ampliada:true};
assert.equal(I.perfilCombate(m,cML),null);assert(I.perfilCombate(m,{...cML,pt:'solo'}));
assert.equal(I.perfilCombate(m,{...cML,pt:'solo',hunt:'outra'}),null);assert.equal(I.perfilCombate(m,{...cML,pt:'solo',hazard:4}),null);
const busca=I.calcularRoda(cat,magias,ctx,'dano',0,{limite_ms:1500,finais:3});
assert(busca.roda.efeitos.ranks[33]>=2);assert(busca.roda.efeitos.revelation[11]>0);assert.equal(busca.roda.comparacao_atual.recomendar,false);
// Referência recente sem vocação explícita: os benefícios identificam ED.
const recente={char:'QA',roda:{id:'nova',campos:{...campos,'conviction.Aug. Strong Ice Wave':campo('I'),
 'conviction.Aug. Forked Spells':campo('II'),'revelation.Blessing of the Grove':campo('Stage 2'),
 'vessels.Heal Friend':campo('+7.5%'),'vessels.Damage and Healing':campo('+3')}},rtc:{preset:'ice',slots:ctx.observado.rtc.slots},pontos:{valor:994}};
delete recente.roda.campos['vessels.Strong Ice Wave'];
const historica={char:'QA',roda:{campos},rtc:{slots:[]},referencia_atual:recente};
const original=JSON.stringify(historica),dados={estado:{historico:true},sessao:{char:'QA'}};
const atualizado=I.contexto(dados,historica,'ED');
assert.equal(atualizado.referencia_roda,'atual_para_proxima_hunt');
assert.equal(atualizado.observado.roda.id,'nova');assert.equal(atualizado.observado.rtc.slots.length,2);
assert.equal(I.contexto(dados,historica,'MS').referencia_roda,'sessao');
assert.equal(I.contexto({...dados,sessao:{char:'OUTRO'}},historica,'ED').referencia_roda,'sessao');
assert.equal(JSON.stringify(historica),original);
const comparada=I.compararRoda(cat,magias,atualizado,candidata);
assert.equal(comparada.ganhos.critico_atual,true);assert.equal(comparada.ganhos.fixo_atual,16);
assert.equal(comparada.ganhos.sio_base_atual,17.5);
assert.equal(comparada.magias.find(m=>m.id==='strong_ice_wave').bonus_roda_atual,6);
assert.equal(comparada.similaridade.similar,true,'Mesmos benefícios; a diferença de estágio das forks permanece registrada');
assert(comparada.similaridade.variacoes.some(v=>v.chave==='ranks.29'));
const candidataSimilar={...candidata,efeitos:{...candidata.efeitos,ranks:{...candidata.efeitos.ranks,29:2}}};
assert.equal(I.similaridadeRoda(cat,I.referenciaRoda(cat,atualizado),candidataSimilar).similar,true);
assert.equal(cmp.similaridade.similar,false,'Perder área não é similar');
const incompleta=I.referenciaRoda(cat,{...ctx,observado:{roda:{campos:{'conviction.Aug. Heal Friend':campo('II')}}}});
assert.equal(I.similaridadeRoda(cat,incompleta,candidata).similar,false);
assert.equal(I.similaridadeRoda(cat,I.referenciaRoda(cat,atualizado),sioFraco).similar,false);
const grade=[...Array.from({length:5},(_,i)=>({tipo:'magia',slot:i+1,estado:'vazio_confirmado',atual:true})),
 {id:'avalanche_rune',tipo:'runa',slot:1,prioridade:2,creatures:1},
 {id:'sudden_death_rune',tipo:'runa',slot:2,prioridade:1,creatures:null}];
assert.equal(I.rtcParaComparacao({slots:grade},magias).completo,true);
assert.equal(I.rtcParaComparacao({slots:grade},magias).slots[1].creatures,1);
assert.equal(I.rtcParaComparacao({slots:grade.slice(1)},magias).completo,false);
assert.equal(I.rtcParaComparacao({slots:grade.map(s=>s.id==='avalanche_rune'?{...s,creatures:null}:s)},magias).completo,false);
assert.equal(I.rtcParaComparacao({slots:grade.map(s=>({...s,atual:false}))},magias).completo,false);
console.log('Comparação atual: gemas/ganhos/perdas, quatro cenários, sio II, área, lacunas e isolamento solo/PT/hunt/Hazard aprovados.');
