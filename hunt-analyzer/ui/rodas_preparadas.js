// Rodas preparadas em lote: selecionar uma opção somente consulta o resultado.
(function(root){
const versao='rodas-preparadas-7-objetivos';
function opcoes(){return ['dano','cura'].flatMap(objetivo=>(objetivo==='dano'?['utamo']:['vida','utamo']).flatMap(modo=>[0,1,2,3].map(tier=>({objetivo,modo,tier,id:`${objetivo}|${modo}|${tier}`}))));}
function id(objetivo,modo,tier){return `${objetivo}|${objetivo==='dano'?'utamo':modo}|${tier}`;}
let banco;
async function db(){
  if(!root.indexedDB)return null;
  if(!banco)banco=new Promise((resolve,reject)=>{const r=root.indexedDB.open('hunt-rodas-preparadas',1);r.onupgradeneeded=()=>r.result.createObjectStore('rodas');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
  return banco;
}
async function ler(chave){const b=await db();if(!b)return null;return new Promise((resolve,reject)=>{const r=b.transaction('rodas').objectStore('rodas').get(chave);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
async function guardar(chave,resultados){const b=await db();if(!b)return;return new Promise((resolve,reject)=>{const t=b.transaction('rodas','readwrite');t.objectStore('rodas').put(resultados,chave);t.oncomplete=resolve;t.onerror=()=>reject(t.error);});}
class Biblioteca{
  constructor(deps={}){this.criarWorker=deps.criarWorker||(()=>new Worker('/ui/rtc_worker.js?v=rodas-preparadas-7-objetivos'));this.ler=deps.ler||ler;this.guardar=deps.guardar||guardar;this.conjuntos=new Map();this.ativo=null;}
  preparar(chave,pedido){
    this.chaveAtual=chave;
    if(this.ativo&&this.ativo.chave!==chave){this.ativo.worker.terminate();this.ativo.cancelar();this.conjuntos.delete(this.ativo.chave);this.ativo=null;}
    if(this.conjuntos.has(chave))return this.conjuntos.get(chave);
    const ouvintes=new Set(),conjunto={resultados:{},erros:{},observar:f=>{ouvintes.add(f);return()=>ouvintes.delete(f);}};
    const avisar=()=>{for(const f of ouvintes)f(conjunto);};
    this.conjuntos.set(chave,conjunto);
    conjunto.pronto=(async()=>{
      conjunto.resultados=await this.ler(chave).catch(()=>null)||{};avisar();
      if(this.chaveAtual!==chave){this.conjuntos.delete(chave);return conjunto;}
      const pendentes=opcoes().filter(o=>!conjunto.resultados[o.id]);
      if(!pendentes.length)return conjunto;
      await new Promise(resolve=>{
        const worker=this.criarWorker();this.ativo={chave,worker,cancelar:resolve};
        worker.onmessage=e=>{if(this.ativo?.worker!==worker)return;
          if(e.data.id){if(e.data.erro)conjunto.erros[e.data.id]=e.data.erro;else conjunto.resultados[e.data.id]=e.data.resultado;this.guardar(chave,{...conjunto.resultados}).catch(()=>{});avisar();}
          if(e.data.fim){worker.terminate();this.ativo=null;resolve();}
        };
        worker.onerror=()=>{for(const o of pendentes)if(!conjunto.resultados[o.id])conjunto.erros[o.id]='Não foi possível preparar esta roda.';avisar();worker.terminate();this.ativo=null;resolve();};
        worker.postMessage({...pedido,modo:'rodas_preparadas',opcoes_roda:pendentes});
      });return conjunto;
    })();return conjunto;
  }
}
const api={Biblioteca,opcoes,id,versao};root.HuntRodasPreparadas=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
