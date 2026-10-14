const assert=require('node:assert/strict');
const {Biblioteca,opcoes,id}=require('./ui/rodas_preparadas.js');
(async()=>{
  const arquivos=new Map();let calculos=0;
  const deps={ler:async k=>arquivos.get(k),guardar:async(k,r)=>arquivos.set(k,r),criarWorker:()=>({
    terminate(){},postMessage(p){calculos++;queueMicrotask(()=>{for(const o of p.opcoes_roda)this.onmessage({data:{id:o.id,resultado:{pontos:p.contexto.total,tier:o.tier}}});this.onmessage({data:{fim:true}});});}
  })};
  assert.equal(opcoes().length,12);assert.equal(new Set(opcoes().map(o=>o.id)).size,12);
  assert.equal(id('dano','vida',3),id('dano','utamo',3));
  const primeira=new Biblioteca(deps),a=primeira.preparar('versao1|ED|989|hunt1',{contexto:{total:989}});
  await a.pronto;assert.equal(calculos,1);assert.equal(Object.keys(a.resultados).length,12);
  for(const o of opcoes())assert.equal(a.resultados[o.id].tier,o.tier);
  assert.equal(primeira.preparar('versao1|ED|989|hunt1',{}),a);assert.equal(calculos,1);
  const reaberta=new Biblioteca(deps);await reaberta.preparar('versao1|ED|989|hunt1',{}).pronto;assert.equal(calculos,1);
  const nova=reaberta.preparar('versao1|ED|990|hunt1',{contexto:{total:990}});await nova.pronto;
  assert.equal(calculos,2);assert.equal(nova.resultados[id('cura','vida',0)].pontos,990);
  const semBanco=new Biblioteca({...deps,ler:async()=>{throw Error('banco indisponível');},guardar:async()=>{throw Error('quota');}});
  await semBanco.preparar('outro',{contexto:{total:700}}).pronto;assert.equal(calculos,3);
  assert.equal(a.resultados[id('dano','utamo',0)].pontos,989);
  console.log('Rodas: matriz antecipada, consulta sem cálculo, reabertura persistida, mudança de pontos e falha de armazenamento aprovadas.');
})().catch(e=>{console.error(e);process.exitCode=1;});
