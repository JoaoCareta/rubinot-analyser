/* As contas de um conjunto de voltas, iguais em toda a tela (user, 24/09: "as fórmulas e dados devem
   ser os mesmos tanto no histórico quanto nas análises" · "monstros, loot, supplies etc, tudo deve
   vir da mesma fonte").

   A FONTE DA VERDADE é o Python: `ao_vivo.taxas` e `ao_vivo.especies`. Este arquivo é a cópia que a
   página usa para recalcular ao vivo, na volta escolhida e na prévia — `python ao_vivo.py` roda as
   duas com o node e quebra se elas discordarem em qualquer sessão guardada.

   Regras (CLAUDE.md):
     · arredondamento = Math.round (empates para cima), também no Python
     · volta limpa = fechada, não parcial e com menos de PAUSA_S (a do refill fica de fora, como na
       volta média, na mais rápida e na mais lenta)
     · XP raw/h = MEDIANA das voltas limpas com a raw consolidada (15 min × 4 = o XP Analyser); sem
       nenhuma consolidada, soma da raw lida ÷ o tempo dessas voltas
     · profit, supplies e bichos = só as voltas em que a medida FOI LIDA, por volta (media) e por
       hora (taxa), numerador e denominador das mesmas voltas — volta sem leitura é lacuna, nunca
       zero (foi o que fez o gráfico dizer 12,10 kk/h numa hunt de 13,90) */
const PAUSA_S = 360;

function taxasIntervalos(intervalos) {
  const saida={};
  for(const [metrica,fonte] of [['raw','XP Analyser'],['dano_proprio','Party Hunt'],['dano_pt','Party Hunt']]){
    let total=0,segundos=0,fim=null;const provas=[];
    for(const r of [...intervalos].sort((a,b)=>(a.inicio??0)-(b.inicio??0))){
      const a=r.inicio,b=r.fim,v=r[metrica];
      if(![a,b,v].every(x=>typeof x==='number'&&Number.isFinite(x))||b<=a||v<0||r.fontes?.[metrica]!==fonte||r.reset||r.mista||fim!==null&&a<fim)continue;
      total+=v;segundos+=b-a;fim=b;provas.push(...r.provas||[]);
    }
    saida[metrica]={total:segundos?total:null,tempo_s:segundos,por_h:segundos?total*3600/segundos:null,fonte,provas};
  }
  return saida;
}

function tempoSessao(sessao) {
  const valor = sessao?.tempo_sessao_s;
  return sessao?.tempo_sessao_origem === 'Party Hunt' && Number.isSafeInteger(valor) && valor >= 0 ? valor : null;
}

function taxasDe(voltas) {
  const vs = voltas.filter(v => (v.dur || 0) > 0 && (v.tipo || 'volta') === 'volta');
  const limpas = vs.filter(v => !v.parcial && v.dur < PAUSA_S);
  const est = limpas.filter(v => v.xp_raw_15min).map(v => v.xp_raw_15min * 4).sort((a, b) => a - b);
  const comRaw = limpas.filter(v => v.xp_raw != null);
  const segRaw = comRaw.reduce((a, v) => a + v.dur, 0);
  const lidas = k => limpas.filter(v => v[k] != null);
  const media = k => { const ok = lidas(k); return ok.length ? Math.round(ok.reduce((a, v) => a + v[k], 0) / ok.length) : null; };
  const taxa = k => {
    const ok = lidas(k), seg = ok.reduce((a, v) => a + v.dur, 0);
    return seg ? Math.round(ok.reduce((a, v) => a + v[k], 0) * 3600 / seg) : null;
  };
  const seg = limpas.reduce((a, v) => a + v.dur, 0);
  const parciais = vs.filter(v => v.parcial).length;
  return {
    voltas: limpas.length, total: vs.length, parciais, refil: vs.length - limpas.length - parciais,
    dur_s: seg, dur_media: limpas.length ? Math.round(seg / limpas.length) : null,
    raw_h: est.length ? est[Math.floor(est.length / 2)] : (segRaw ? Math.round(comRaw.reduce((a, v) => a + v.xp_raw, 0) * 3600 / segRaw) : null),
    raw_de: est.length ? '15min' : (segRaw ? 'soma' : null),
    voltas_raw: comRaw.length, voltas_15min: est.length,
    media: {profit: media('profit'), sup_pt: media('sup_pt'), sup_eu: media('sup_eu'), bichos: media('bichos')},
    taxa: {profit_h: taxa('profit'), sup_pt_h: taxa('sup_pt'), sup_eu_h: taxa('sup_eu'), bichos_h: taxa('bichos')},
  };
}

/* Espécies da hunt: {nome: mortes}, a mais morta primeiro — a mesma lista na tela de hunt, no resumo
   guardado e nos bichos da capa do histórico. O motor já tirou de `especies` o que não é bicho e o
   que é de outra hunt; sessão sem espécie em volta nenhuma cai para o `loots` (antes de 21/09 o loot
   ainda vinha pelo Server Log e era ele que dizia o que morreu). Espelha ao_vivo.especies. */
function especiesDe(voltas) {
  const vs = voltas.filter(v => (v.tipo || 'volta') === 'volta');
  const campo = vs.some(v => Object.keys(v.especies || {}).length) ? 'especies' : 'loots';
  const n = {};
  for (const v of vs) for (const [k, c] of Object.entries(v[campo] || {})) n[k] = (n[k] || 0) + c;
  return Object.fromEntries(Object.entries(n).sort((a, b) => b[1] - a[1]));
}

if (typeof module !== 'undefined') module.exports = {taxasDe, especiesDe, PAUSA_S, pressao, consumoItens, variacoesEstoque, balancoCura, tempoSessao, resumoVida, permanenciaVida, taxasIntervalos};   // o _demo do ao_vivo confere por aqui

function resumoVida(valores){
  const vs=valores.filter(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100);
  return {leituras:vs.length,minima:vs.length?Math.min(...vs):null,maxima:vs.length?Math.max(...vs):null,
    faixas:[[0,30],[30,50],[50,70],[70,90],[90,100]].map(([de,ate])=>({de,ate,leituras:vs.filter(v=>v>=de&&v<ate||v===ate&&ate===100).length}))};
}

function permanenciaVida(leituras,inicio,fim,maxGap=6){
  const numero=v=>typeof v==='number'&&Number.isFinite(v);
  const faixas=resumoVida([]).faixas.map(f=>({...f,tempo_s:0}));
  const porT=new Map(leituras.filter(r=>numero(r.t)&&r.t>=inicio&&r.t<=fim).map(r=>[r.t,r]));
  const rows=[...porT.values()].sort((a,b)=>a.t-b.t);
  const valida=r=>numero(r.percentual)&&r.percentual>=0&&r.percentual<=100;
  const faixa=p=>faixas.find(f=>f.de<=p&&p<f.ate||p===f.ate&&f.ate===100);
  for(const r of rows)if(valida(r))faixa(r.percentual).leituras++;
  for(let i=1;i<rows.length;i++){
    const a=rows[i-1],b=rows[i],dt=b.t-a.t;
    if(valida(a)&&valida(b)&&dt>0&&dt<=maxGap)faixa(a.percentual).tempo_s+=dt;
  }
  const conhecido=faixas.reduce((s,f)=>s+f.tempo_s,0);
  if(!conhecido)for(const f of faixas)f.tempo_s=null;
  return {faixas,tempo_identificado_s:conhecido,tempo_sem_leitura_s:Math.max(0,fim-inicio-conhecido)};
}

if(typeof module==='undefined')globalThis.HuntMetricas={taxasDe,especiesDe,PAUSA_S,pressao,consumoItens,variacoesEstoque};

function variacoesEstoque(leituras,maxGap=6){
 const anteriores=new Map(),saida=[];
 for(const r of leituras.slice().sort((a,b)=>a.t-b.t)){
  const k=JSON.stringify([r.char,r.item,r.serie]),a=anteriores.get(k),v=r.valor;
  if(r.origem!=='estoque_hotkey'||!r.char||!r.item||!r.serie||r.unidade!=='unidades'||!Number.isInteger(v)||v<0){anteriores.delete(k);continue;}anteriores.set(k,r);
  if(!a)continue;
  const dt=r.t-a.t,delta=a.valor-v;
  let estado=delta<0?'reposicao_ou_movimentacao':delta?'queda_de_estoque':'estoque_estavel';
  if(!(dt>0&&dt<=maxGap)||JSON.stringify(a.local??null)!==JSON.stringify(r.local??null))estado='lacuna_ou_layout_alterado';
  const estimativa=estado==='queda_de_estoque'?delta:estado==='estoque_estavel'?0:null,preco=r.preco_observado||{},unitario=preco.gold;
  const mesmo=Object.keys(preco).length===Object.keys(a.preco_observado||{}).length&&Object.keys(preco).every(k=>preco[k]===a.preco_observado[k]);
  const custo=estimativa!=null&&typeof unitario==='number'&&unitario>=0&&mesmo?estimativa*unitario:null;
  saida.push({item:r.item,char:r.char,inicio:a.t,fim:r.t,estado,estoque_antes:a.valor,estoque_depois:v,quantidade_estimada:estimativa,consumo_confirmado:null,
   custo_estimado_gold:custo,preco_origem:preco.origem??null,por_minuto_estimado:estimativa!=null?60*estimativa/dt:null,duracao_s:dt,provas:[a.prova??null,r.prova??null],
   limite:'Queda de estoque pode ser movimentação; não somar ao contador de uso nem ao Supplies.'});
 }return saida;
}

function pressao(recursos,maxGap=6,recuperacao=2){
 const rows=recursos.slice().sort((a,b)=>(a.t||0)-(b.t||0)),faixas={'70':0,'50':0,'30':0},episodios=[];
 let cobertura=0,combate=0,protegido=0,exposto=0,episodio=null,recuperando=null,queda=null,minimo=null;
 const cortar=()=>{if(episodio){episodio.incompleto=true;episodios.push(episodio);episodio=null;}recuperando=null;};
 for(let i=1;i<rows.length;i++){
  const a=rows[i-1],b=rows[i],dt=b.t-a.t;
  if(!(dt>0&&dt<=maxGap&&a.combate===true&&b.combate===true)){cortar();continue;}
  combate+=dt;if(a.escudo===true)protegido+=dt;else if(a.escudo===false)exposto+=dt;
  const pa=a.vida?.percentual,pb=b.vida?.percentual;
  if(pa==null||pb==null||!(pa>=0&&pa<=100&&pb>=0&&pb<=100)){cortar();continue;}
  cobertura+=dt;minimo=Math.min(pa,pb,minimo??100);queda=Math.max(0,(pa-pb)/dt,queda||0);
  for(const n of Object.keys(faixas))if(pa<Number(n))faixas[n]+=dt;
  if(pa<70||pb<70){
   episodio??={inicio:a.t,fim:b.t,minimo:Math.min(pa,pb),incompleto:pa<70};episodio.fim=b.t;episodio.minimo=Math.min(episodio.minimo,pa,pb);recuperando=null;
  }else if(episodio){recuperando??=a.t;episodio.fim=b.t;if(b.t-recuperando>=recuperacao){episodios.push(episodio);episodio=null;recuperando=null;}}
 }
 cortar();
 return {versao:'pressao-descritiva-1',combate_observavel_s:combate,vida_cobertura_s:cobertura,vida_minima_observada:minimo,abaixo_faixa_s:faixas,queda_max_pct_s:queda,episodios,
 escudo_com_s:protegido,escudo_sem_s:exposto,escudo_desconhecido_s:combate-protegido-exposto,
 escudo_cobertura_pct:combate?(protegido+exposto)/combate*100:null,escudo_protegido_pct:protegido+exposto?protegido/(protegido+exposto)*100:null};
}
function consumoItens(leituras){
 const anteriores=new Map(),saida=[];
 for(const r of leituras.slice().sort((a,b)=>a.t-b.t)){
  const chave=JSON.stringify([r.char??null,r.item??null,r.serie??null,r.unidade??null]),anterior=anteriores.get(chave),valor=r.valor;
  if(r.origem!=='contador_uso'||!r.char||!r.item||!Number.isInteger(valor)||valor<0){anteriores.delete(chave);continue;}anteriores.set(chave,r);
  if(!anterior||!r.continuidade||!r.serie||r.unidade!=='unidades')continue;
  const dt=r.t-anterior.t,delta=valor-anterior.valor;if(dt<=0||delta<0)continue;
  saida.push({char:r.char??null,item:r.item??null,serie:r.serie,inicio:anterior.t,fim:r.t,quantidade:delta,duracao_s:dt,por_minuto:60*delta/dt,unidade:'unidades',denominador:'intervalo_entre_contadores',provas:[anterior.prova??null,r.prova??null]});
 }return saida;
}
function balancoCura(janelas){
 const comparaveis=[],numero=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0;
 for(const j of janelas){const dur=(j.fim??0)-(j.inicio??0),dano=j.dano_hp,sio=j.sio_hp;
  if(!(dur>0)||!numero(dano)||!numero(sio))continue;
  const total=numero(j.outras_hp)?sio+j.outras_hp:null;
  comparaveis.push({...j,duracao_s:dur,dano_hp_s:dano/dur,sio_hp_s:sio/dur,saldo_sio_hp:sio-dano,
   razao_sio_dano:dano?sio/dano:null,recuperacao_total_hp:total,saldo_total_hp:total===null?null:total-dano});
 }
 const dano=comparaveis.reduce((n,j)=>n+j.dano_hp,0),sio=comparaveis.reduce((n,j)=>n+j.sio_hp,0);
 return {versao:'balanco-cura-1',unidade:'HP',janelas:comparaveis,comparaveis:comparaveis.length,lacunas:janelas.length-comparaveis.length,
  duracao_comparavel_s:comparaveis.reduce((n,j)=>n+j.duracao_s,0),dano_hp:comparaveis.length?dano:null,sio_hp:comparaveis.length?sio:null,
  razao_sio_dano:dano?sio/dano:null,deficits:comparaveis.filter(j=>j.saldo_sio_hp<0).length,
  cobertura_completa:!!comparaveis.length&&comparaveis.length===janelas.length&&comparaveis.every(j=>j.cobertura_completa===true),
  limite:'Déficit no recorte observado; outras recuperações e lacunas impedem concluir insuficiência da hunt inteira.'};
}
