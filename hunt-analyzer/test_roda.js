const assert=require('node:assert/strict'),fs=require('node:fs');
global.HuntRTC=require('./ui/rtc.js');global.fflate=require('./ui/fflate.js');
const W=require('./ui/roda_motor.js'),base=JSON.parse(fs.readFileSync('./ui/roda_catalogo.json','utf8'));
const magias=JSON.parse(fs.readFileSync('./ui/magias.json','utf8')).magias;
const resultados=[];
for(const voc of ['ED','MS']){
 const cat=W.selecionar(base,voc);assert.equal(cat.fatias.length,36);
 for(const tier of [1,2,3]){
  const min=W.viabilidade(cat,10000,tier).custo_minimo;
  assert.equal(W.viabilidade(cat,min+2,tier).estado,'Pontos insuficientes');
  assert.equal(W.viabilidade(cat,min+3,tier).estado,'Cabe nos pontos');
  for(const caminho of cat.caminhos_minimos.filter(c=>c.tier===tier)){
   assert(HuntRTC.validarDistribuicao(cat,caminho.pontos,caminho.custo+3).ok);
   assert.equal(Math.max(...Object.values(W.resumo(cat,caminho.pontos).vr)),tier);
   const code=W.exportarCodigo(cat,caminho.pontos),lido=W.importarCodigo(cat,code,caminho.custo+3);
   for(const f of cat.fatias)assert.equal(lido.pontos[f.id],caminho.pontos[f.id]||0);
   assert.throws(()=>W.importarCodigo(W.selecionar(base,voc==='ED'?'MS':'ED'),code,10000));
  }
 }
 const lista=magias.filter(m=>m.vocs.includes(voc)).map(m=>({...m,resistencia:100,cobertura:1,ajustado:m.bp}));
 for(const objetivo of ['dano','cura'])for(const tier of [1,2,3]){
  const r=W.otimizar(cat,987,objetivo,tier,lista,{alvos:8},{slots:7,capacidadeRTC:{magias:5,runas:2},duracao:180});
  if(!(voc==='MS'&&objetivo==='cura'))assert(r.alternativas.length>0);
  for(const a of r.alternativas){assert(HuntRTC.validarDistribuicao(cat,a.pontos,987).ok);assert(987-a.efeitos.investidos>=3);
   assert(Math.max(...Object.values(a.efeitos.vr))>=tier);
   if(a.rotacao){assert.equal(a.metricas.dano,a.rotacao.sequencia.reduce((n,e)=>n+(e.potencia||0),0));assert(a.rotacao.ordem.filter(m=>!m.runa).length<=5);assert(a.rotacao.ordem.filter(m=>m.runa).length<=2);}
  }
  resultados.push({voc,objetivo,tier,estado:r.estado,alternativas:r.alternativas.map(a=>({pontos:a.pontos,metricas:a.metricas,gemas:a.gemas,codigo:W.exportarCodigo(cat,a.pontos)})),comparadas:r.avaliadas});
 }
}
const cat=W.selecionar(base,'ED');
const root=cat.fatias.find(f=>f.raiz),child=cat.fatias.find(f=>!f.raiz&&f.conexoes.includes(root.id));
assert(!HuntRTC.validarDistribuicao(cat,{[root.id]:root.limite-1,[child.id]:1},987).ok);
const trio=[{id:'a',nome:'a',alvos:null,ajustado:10,cd:2,grupo:2,familia:'a',prioridade:2,creatures:1,mana_percent:5},
{id:'b',nome:'b',alvos:null,ajustado:20,cd:2,grupo:2,familia:'b',prioridade:1,creatures:7,mana_percent:5}];
assert.equal(HuntRTC.simular(trio,[],{alvos:7,mana_percent:5},2).sequencia[0].id,'b');
assert.equal(HuntRTC.simular(trio,[],{alvos:6,mana_percent:5},2).sequencia[0].id,'a');
assert.equal(HuntRTC.simular(trio,[],{alvos:7,mana_percent:4},2).score,0);
const sio=cat.fatias.filter(f=>f.conviction_id===33),link=cat.fatias.find(f=>f.conviction_id===28);
const p=Object.fromEntries([...sio,link].map(f=>[f.id,f.limite]));
assert(Math.abs(W.cura(cat,p).sio-110)<1e-9);assert(Math.abs(W.cura(cat,p).autocura_por_sio-27.5)<1e-9);
fs.writeFileSync('../output/planejamento/rtc-roda/qa-final/testes-roda.json',JSON.stringify(resultados,null,2));
console.log('Roda: ED/MS, mínimos exatos, reserva, conectores completos, códigos, 12 cenários, cura separada e prioridades/Mana/Criaturas aprovados.');
