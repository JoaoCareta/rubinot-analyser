(function(root){
let rodaModoVida='utamo',rtcRodaObjetivo='dano',rtcTier=0;
const rtcCacheIntegrado=new Map(),rtcWorkers=new Map();
function rtcCancelaCalculos(){for(const w of rtcWorkers.values())w.terminate();rtcWorkers.clear();}
async function rtcOperacao(dados){
  const r=await fetch('/api/configuracoes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)}),d=await r.json();
  if(!r.ok||!d.ok)throw Error(d.erro||'Não foi possível guardar.');return d.resultado;
}
function rtcLinhasConfiguradas(linhas,bloco,cura=false){
  const lista=HuntUI.el('div','rtc-slots');
  for(const m of linhas){const c=HuntUI.el('article','rtc-slot');if(m.imagem)c.append(rtcImagem(m));
    c.append(HuntUI.el('strong',null,`${cura?(m.vocacao_destino?m.vocacao_destino+' · ':''):m.tipo==='runa'?'Runa '+m.slot+' · ':'Magia '+m.slot+' · '}${rtcNome(m)}`));
    c.append(HuntUI.el('p','nota',cura?`Vida ${m.vida_percent}%${m.origem_percentual==='observado'?' · lido no jogo':''}`:`${m.tipo==='runa'?'':`Mana ${m.mana_percent}% · `}${m.runa&&m.alvos===1?'':`Criaturas ${m.creatures}+ · `}Prioridade ${m.prioridade}º`));
    if(m.frequencia!=null)c.append(HuntUI.el('p','nota',`Frequência de ativação: ${rtcFmt(m.frequencia)} /min · previsão`));
    if(!cura){const conf=HuntRTC.conferirRTC(m,m,rtcObservado.rtc);c.append(HuntUI.el('span',conf.estado==='Ajustar'?'rtc-ajustar':'nota',conf.estado));}
    lista.append(c);
  }
  if(!linhas.length)lista.append(HuntUI.el('p','nota','Aguardando leitura e contexto da hunt.'));bloco.append(lista);
}
function rtcMostrarRoda(r,roda,cat){
  roda.replaceChildren();
  rtcMostrarAprendizado(r.roda.aprendizado,roda);
  if(r.roda.estado==='Calculado'){
    roda.append(HuntUI.el('p','nota',`${r.roda.investidos} investidos · ${r.roda.livres} ${r.roda.livres===3?"reservados":"livres"} / ${r.contexto.total} totais`));
    const atual=Object.fromEntries(Object.entries(rtcObservado.roda?.campos||{}).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
    const visual=HuntRodaVisual.montar(cat,r.roda.pontos,r.contexto.total,atual);if(visual.elemento)roda.append(visual.elemento);
    const e=r.roda.efeitos,beneficios=HuntUI.el('div','rtc-beneficios');
    if(e.ranks[28])beneficios.append(HuntUI.el('p','nota','Healing Link completo · autocura de 25% da cura aplicada por sio/gran sio'));
    if(e.revelation[10])beneficios.append(HuntUI.el('p','nota',`Twin Bursts · estágio ${e.revelation[10]} · cooldown ${[0,22,18,14][e.revelation[10]]} s · dano adicional condicionado à vida do alvo`));
    if(e.revelation[11])beneficios.append(HuntUI.el('p','nota',`Blessing of the Grove · estágio ${e.revelation[11]} · bônus condicionado à vida e ao crítico`));
    for(const [id,n] of Object.entries(e.ranks)){
      const perk=cat.conviction[id];if(!perk||id==='28')continue;
      beneficios.append(HuntUI.el('p','nota',`${perk.Name.split('|')[0]} · ${n}`));
    }
    roda.append(beneficios,HuntUI.el('p','nota',r.roda.gemas.length?'Gemas sugeridas · equipamento não conferido':'Sem gemas'));
    for(const g of r.roda.gemas)roda.append(HuntUI.el('p','nota',`${g.dominio} · ${g.qualidade} · ${g.nome||'Gema observada'}${g.grau?' · grau '+g.grau:''}`));
    for(const g of r.roda.gemas)for(const b of g.basicos||[])roda.append(HuntUI.el('p','nota',`${g.dominio} · ${cat.basicos_normalizados?.[b.mod]?.nome||'Modificador básico'} · grau ${b.grau}`));
    if(e.magic_level)roda.append(HuntUI.el('p','nota',`Magic level da roda: +${e.magic_level}`));
    const codigo=HuntRodaMotor.exportarCodigo(cat,r.roda.pontos);
    roda.append(rtcBotao('Copiar código dos pontos',async()=>{try{await navigator.clipboard.writeText(codigo);}catch{const campo=HuntUI.el('input');campo.readOnly=true;campo.value=codigo;campo.setAttribute('aria-label','Código dos pontos');roda.append(campo);campo.select();}}));
  }else roda.append(HuntUI.el('p','nota',r.roda.estado));
}
function rtcMostrarConfiguracao(r,bloco){
  bloco.replaceChildren();
  rtcMostrarAprendizado(r.rtc.aprendizado,bloco);
  rtcMostrarCura(r,bloco);
  bloco.append(HuntUI.el('h3',null,'Magias e runas'),HuntUI.el('p','nota','Sugestão para a próxima hunt'));
  if(r.rtc.equalizacao?.estado==='replay_validado')bloco.append(HuntUI.el('p','nota','Criaturas ajustadas pelo cooldown e pelo equilíbrio entre ativações e dano previsto.'));
  rtcLinhasConfiguradas(r.rtc.linhas||[],bloco);
}
function rtcMostrarAprendizado(a,bloco){
  if(!a)return;
  bloco.append(HuntUI.el('p','nota',a.estado==='aprendizado_validado_parcial'?`Aprendizado ativo · ${a.amostras} exemplos · validado em dados posteriores. Cobertura de dano parcial.`:`Aprendizado em coleta · ${a.amostras} exemplos · sua roda atual é a referência.`));
}
function rtcMostrarCura(r,bloco){
  const cura=HuntUI.el('div','rtc-cura-paineis'),eu=HuntUI.el('section'),pt=HuntUI.el('section');
  eu.append(HuntUI.el('h3',null,'Autocura · '+(r.cura.postura==='utamo'?'Utamo':'Vida')));
  rtcLinhasConfiguradas((r.cura.linhas||[]).filter(m=>!m.vocacao_destino),eu,true);
  pt.append(HuntUI.el('h3',null,'Cura da party · sio e gran sio'));
  rtcLinhasConfiguradas((r.cura.linhas||[]).filter(m=>m.vocacao_destino),pt,true);
  cura.append(eu);if((r.cura.linhas||[]).some(m=>m.vocacao_destino))cura.append(pt);bloco.append(cura);
}
function rtcEscolhas(opcoes,valor,acao,nome){
  const grupo=HuntUI.el('div','rtc-classes');grupo.setAttribute('aria-label',nome);
  for(const [id,label] of opcoes){const b=rtcBotao(label,()=>acao(id));b.setAttribute('aria-pressed',String(id===valor));grupo.append(b);}
  return grupo;
}
function renderIntegradoRTC(bloco){
  const cat=RTC_RODA?.vocacoes?HuntRodaMotor.selecionar(RTC_RODA,rtcVoc):RTC_RODA;
  if(!cat?.fatias?.length)return;
  rtcCancelaCalculos();bloco.replaceChildren();
  const ctx=HuntIntegracao.contexto({...HuntApp.dados,voltas:rtcVoltas()},rtcObservado,rtcVoc),geracao=rtcGeracao;
  const paineis=HuntUI.el('div','rtc-independentes'),rtc=HuntUI.el('section','rtc-config-painel'),roda=HuntUI.el('section','rtc-roda-painel');
  rtc.setAttribute('aria-label','Configuração do RTC');roda.setAttribute('aria-label','Roda de habilidade');
  rtc.append(HuntUI.el('div','rotulo','RTC'),HuntUI.el('h2',null,'Otimizar curas e magias'),HuntUI.el('p','nota','Autocura, cura da party, magias e runas para a próxima hunt.'));
  if(HuntApp.historico)rtc.append(HuntUI.el('p','nota',ctx.referencia_roda==='atual_para_proxima_hunt'?'Sugestão recalculada para esta hunt com sua roda atual. Os registros da sessão permanecem como foram observados.':'Sugestão recalculada com os dados disponíveis desta sessão.'));
  roda.append(HuntUI.el('div','rotulo','RODA DE HABILIDADE'),HuntUI.el('h2',null,'Distribuir os pontos'),HuntUI.el('p','nota','Escolha o foco da roda.'));
  const rtcControles=HuntUI.el('div'),rodaControles=HuntUI.el('div'),rtcResultado=HuntUI.el('div'),rodaResultado=HuntUI.el('div'),conf=HuntUI.el('div','rtc-confirmacao');
  rtcResultado.setAttribute('aria-live','polite');rodaResultado.setAttribute('aria-live','polite');
  rtc.append(rtcControles,rtcResultado);roda.append(rodaControles,rodaResultado);paineis.append(rtc,roda);bloco.append(paineis,conf);
  const especies=especiesDe(rtcVoltas()),magias=[...HuntRTC.comparar(RTC_CATALOGO.magias,especies,HuntApp.catalogo,rtcVoc),...RTC_CATALOGO.magias.filter(m=>m.tipo==='cura'&&m.vocs.includes(rtcVoc))];
  const baseChave=JSON.stringify([ctx,especies,Object.entries(HuntApp.catalogo).map(([n,m])=>[n,m.toma]),RTC_CATALOGO.versao,cat.versao]);
  const resultados={};
  function confirmar(){
    conf.replaceChildren();
    if(!resultados.rtc||!resultados.roda)return;
    const a=resultados.rtc,b=resultados.roda;
    if(HuntApp.historico||HuntApp.previa||!ctx.char||!a.rtc.linhas?.length||b.roda.estado!=='Calculado')return;
    const payload={versao:2,regras_versao:b.regras_versao,modelo_versao:b.modelo_versao,contexto:b.contexto,
      objetivo:rtcRodaObjetivo,estrategia:b.estrategia,modo_vida:rodaModoVida,tier:rtcTier,independentes:true,revisao_interface:'roda_rtc_uso_v3',
      rtc:a.rtc,cura:a.cura,roda:b.roda,revisao_rtc:'rtc_cura_ml_v1'};
    const escolha=JSON.stringify([rodaModoVida,rtcRodaObjetivo,rtcTier]),mensagem=HuntUI.el('p','nota');mensagem.setAttribute('role','status');
    let id=null;
    const botao=rtcBotao('Estou usando esta configuração',async()=>{
      if(!id)return;botao.disabled=true;
      try{const c=await rtcOperacao({acao:'confirmar',char:ctx.char,id});rtcObservado.confirmacao={...c,valida:true};mensagem.textContent='Confirmado por você. A leitura do jogo continua conferindo cada componente.';}
      catch(e){mensagem.textContent=e.message;}finally{botao.disabled=false;}
    });botao.disabled=true;conf.append(botao,mensagem);
    const salvo=rtcObservado.sugestao;
    const igual=salvo?.revisao_rtc===payload.revisao_rtc&&salvo?.revisao_interface===payload.revisao_interface&&salvo.modo_vida===rodaModoVida&&salvo.objetivo===rtcRodaObjetivo&&salvo.tier===rtcTier&&salvo.contexto?.vocacao===rtcVoc&&JSON.stringify(salvo.rtc)===JSON.stringify(a.rtc)&&JSON.stringify(salvo.cura)===JSON.stringify(a.cura)&&JSON.stringify(salvo.roda)===JSON.stringify(b.roda);
    const pronta=igual?Promise.resolve(salvo):rtcOperacao({acao:'sugestao',char:ctx.char,sugestao:payload});
    pronta.then(s=>{if(geracao!==rtcGeracao||escolha!==JSON.stringify([rodaModoVida,rtcRodaObjetivo,rtcTier]))return;
      id=s.id;rtcObservado.sugestao=s;botao.disabled=false;
      if(rtcObservado.confirmacao?.valida&&rtcObservado.confirmacao.sugestao_id===id)mensagem.textContent='Confirmado por você.';
    }).catch(e=>{if(geracao===rtcGeracao)mensagem.textContent=e.message;});
  }
  function calcular(tipo){
    const alvo=tipo==='rtc'?rtcResultado:rodaResultado;
    const escolha=tipo==='rtc'?null:[rtcRodaObjetivo,rtcTier,rodaModoVida],chave=JSON.stringify([tipo,baseChave,escolha]);
    rtcWorkers.get(tipo)?.terminate();rtcWorkers.delete(tipo);delete resultados[tipo];conf.replaceChildren();
    const mostrar=r=>{resultados[tipo]=r;if(tipo==='rtc')rtcMostrarConfiguracao(r,alvo);else rtcMostrarRoda(r,alvo,cat);confirmar();};
    const salva=rtcObservado.sugestao,c=rtcObservado.confirmacao;
    
    if(rtcCacheIntegrado.has(chave)){mostrar(rtcCacheIntegrado.get(chave));return;}
    alvo.replaceChildren(HuntUI.el('p','nota',tipo==='rtc'?'Calculando magias e cura…':'Calculando a roda…'));
    const w=new Worker('/ui/rtc_worker.js?v=20261012_rtc_roda_ml_v1');rtcWorkers.set(tipo,w);
    w.onmessage=e=>{if(geracao!==rtcGeracao||rtcWorkers.get(tipo)!==w)return;w.terminate();rtcWorkers.delete(tipo);
      if(e.data.erro){alvo.textContent=e.data.erro;return;}
      rtcCacheIntegrado.set(chave,e.data.resultado);if(rtcCacheIntegrado.size>48)rtcCacheIntegrado.delete(rtcCacheIntegrado.keys().next().value);mostrar(e.data.resultado);
    };
    w.onerror=()=>{if(geracao===rtcGeracao){alvo.textContent='Não foi possível calcular. Tente outra opção.';w.terminate();rtcWorkers.delete(tipo);}};
    w.postMessage({chave:geracao,modo:tipo==='rtc'?'rtc_independente':'roda_independente',catalogo:cat,magias,contexto:ctx,objetivo:rtcRodaObjetivo,tier:rtcTier,opcoes:{limite_ms:12000,finais:8,modo_vida:rodaModoVida}});
  }
  function controlesRoda(){
    rodaControles.replaceChildren(rtcEscolhas([['dano','Dano'],['cura','Cura']],rtcRodaObjetivo,id=>{rtcRodaObjetivo=id;controlesRoda();calcular('roda');},'Foco da roda'));
    if(rtcRodaObjetivo==='cura')rodaControles.append(HuntUI.el('p','nota','Como você vai jogar?'),rtcEscolhas([['vida','Vida'],['utamo','Utamo']],rodaModoVida,id=>{rodaModoVida=id;controlesRoda();calcular('roda');},'Modo de jogo da roda'));
    rodaControles.append(HuntUI.el('p','nota','Qualidade das gemas'));
    const gemas=HuntUI.el('div','rtc-gemas');
    for(const [tier,nome] of [[0,'Sem gemas'],[1,'T1 · Lesser'],[2,'T2 · Regular'],[3,'T3 · Greater']]){
      const b=rtcBotao(nome,()=>{rtcTier=tier;controlesRoda();calcular('roda');});b.setAttribute('aria-pressed',String(tier===rtcTier));gemas.append(b);
    }rodaControles.append(gemas);
    if(ctx.total==null){
      const l=HuntUI.el('label','rtc-escolha','Qual é o total de pontos mostrado na roda?'),n=HuntUI.el('input');n.type='number';n.min='0';n.max='10000';n.step='1';l.append(n);const msg=HuntUI.el('p','nota');
      rodaControles.append(l,rtcBotao('Guardar total',async()=>{try{const v=Number(n.value);if(n.value===''||!Number.isInteger(v))throw Error('Informe o total de pontos.');const r=await rtcOperacao({acao:'pontos',char:ctx.char,valor:v});rtcObservado.pontos=r;rtcAssinatura='';renderMagiasRTC();}catch(e){msg.textContent=e.message;}}),msg);
    }
  }
  controlesRoda();calcular('rtc');calcular('roda');
}

let RTC_CATALOGO=null, RTC_RODA=null, rtcVoc='ED', rtcAlvo='', rtcCategoria='Área', rtcDuracao=30;
let rtcAssinatura='', rtcWorker=null, rtcGeracao=0, rtcObservado={}, rtcObsChave='', rtcObsSolicitada='';

const rtcRodasImportadas=new Map();
const RTC_CAPACIDADE={magias:5,runas:2};
const RTC_DANO=new URLSearchParams(location.search).has('dano');
const rtcFmt=n=>n==null?'—':n.toLocaleString('pt-BR',{maximumFractionDigits:2});
const rtcApelidos={'Sudden Death Rune':'SD','Eternal Winter':'mas frigo','Wrath of Nature':'mas tera',
  'Ice Burst':'ulus frigo','Terra Burst':'ulus tera','Strong Ice Wave':'Frigo Hur','Terra Wave':'Tera Hur',
  'Forked Glacier':'fork de gelo','Forked Thorns':'fork de terra','Ultimate Healing':'exura vita','Restoration':'exura max vita','Mass Healing':'mas res','Heal Friend':'sio',"Nature's Embrace":'gran sio','Intense Healing':'exura gran'};
const rtcNome=m=>rtcApelidos[m.nome]||m.nome;
function rtcImagem(m,classe='dano-icone') {const img=HuntUI.el('img',classe);img.src=m.imagem;img.alt=m.nome;img.width=38;img.height=38;return img;}
function rtcBotao(texto,acao) {const b=HuntUI.el('button','rtc-acao',texto);b.type='button';b.onclick=acao;return b;}


function rtcVoltas() {return HuntApp.recorte==='volta' && HuntApp.voltaEscolhida()?[HuntApp.voltaEscolhida()]:HuntApp.voltas();}
function rtcIdentidade() {return {char:HuntApp.dados?.sessao?.char||HuntApp.dados?.estado?.char||rtcObservado.char||'',sessao:HuntApp.dados?.estado?.sessao||HuntApp.dados?.sessao?.origem||'',historico:!!HuntApp.historico};}
async function rtcCarregarObservacao(identidade){
  const ler=async parametros=>{const r=await fetch('/api/configuracoes?'+new URLSearchParams(parametros),{cache:'no-store'});if(!r.ok)throw Error('Configuração indisponível.');return r.json();};
  const [historica,atual]=await Promise.all([
    ler({char:identidade.char,sessao:identidade.sessao,historico:String(identidade.historico)}),
    identidade.historico?ler({char:identidade.char}).catch(()=>null):null
  ]);
  // Preserva os snapshots usados pelos selos de leitura da sessão.
  return identidade.historico?{...historica,referencia_atual:atual?{
    char:atual.char,rtc:{vocacao:atual.rtc?.vocacao},roda:atual.roda,pontos:atual.pontos,
    modelo:{combate_ml:atual.modelo?.combate_ml}
  }:null}:historica;
}
function iniciaPainelDano() {
  if(!RTC_DANO)return;
  document.body.classList.add('modo-dano');document.title='Magias e elementos · Hunt Analyzer';
  const pagina=HuntUI.el('section','dano-pagina');pagina.append(HuntUI.el('div','rotulo','— potência, RTC e roda'),HuntUI.el('h1',null,'Magias e elementos'));
  const campos=HuntUI.el('div','dano-sessao'),label=HuntUI.el('label',null,'Sessão da hunt'),select=HuntUI.el('select');
  const vivo=HuntUI.el('option',null,'Hunt atual');vivo.value='';select.append(vivo);label.append(select);campos.append(label);pagina.append(campos);
  const contexto=HuntUI.el('p','sub');contexto.id='danoContexto';pagina.append(contexto);
  pagina.append(document.querySelector('section.filtros'),HuntUI.$('#recomendacaoMagias'),HuntUI.$('#otimizacaoRTC'));document.querySelector('main').prepend(pagina);
  select.onchange=()=>{const q=new URLSearchParams();q.set('dano','');if(select.value)q.set('h',select.value);location.href='/hunt?'+q;};
  fetch('/api/historico',{cache:'no-store'}).then(r=>r.json()).then(r=>{
    for(const s of r.sessoes||[]) {const o=HuntUI.el('option',null,`${s.hunt} · ${s.data||s.id} · ${s.char||''}`);o.value=s.id;select.append(o);}
    const h=new URLSearchParams(location.search).get('h');if(h && ![...select.options].some(o=>o.value===h)){const o=HuntUI.el('option',null,h);o.value=h;select.append(o);}select.value=h||'';
  }).catch(()=>{contexto.textContent='Não foi possível carregar as sessões.';});
}
function rtcClasses() {
  const grupo=HuntUI.el('div','rtc-classes');grupo.setAttribute('aria-label','Vocação consultada');
  for(const [voc,nome] of [['MS','Master Sorcerer'],['ED','Elder Druid']]) {
    const b=rtcBotao('',()=>{rtcVoc=voc;if(!HuntRTC.categoriasDe(voc).includes(rtcCategoria))rtcCategoria=voc==='MS'?'Beam':'Twin';rtcAssinatura='';renderMagiasRTC();});
    b.setAttribute('aria-pressed',String(voc===rtcVoc));
    const img=HuntUI.el('img','rtc-classe-icone');img.src=`/ui/voc_${voc.toLowerCase()}.png`;img.alt='';img.width=44;img.height=44;
    const texto=HuntUI.el('span');texto.append(HuntUI.el('strong',null,voc),HuntUI.el('small',null,nome));b.append(img,texto);grupo.append(b);
  }return grupo;
}
function rtcBarras(p) {
  const {linhas,max}=p,bloco=HuntUI.el('div','rtc-barras');
  bloco.append(HuntUI.el('h3','rotulo','Elementos que a hunt recebe'));
  if(!p.total){bloco.append(HuntUI.el('p','nota','Aguardando criaturas nas voltas fechadas.'));return bloco;}
  for(const r of linhas) {
    const barra=HuntUI.el('div','rtc-barra'),fill=HuntUI.el('div','rtc-barra-fill'),texto=HuntUI.el('div','rtc-barra-texto');
    const valor=r.valor,distancia=valor==null?0:Math.min(1,Math.abs(valor-100)/100);
    fill.style.width=(valor==null?0:valor/max*100)+'%';
    fill.style.background=valor==null||valor===100?'#454752':valor>100?`hsl(143 35% ${30-12*distancia}%)`:`hsl(0 40% ${32-13*distancia}%)`;
    const referencia=HuntUI.el('i','rtc-barra-ref');referencia.style.left=(100/max*100)+'%';
    const nome=HuntUI.el('span','rtc-elemento-nome');
    const icones={'físico':'fisico.png','fogo':'fogo.png','terra':'terra.png','energia':'energia.png','gelo':'gelo.png','sagrado':'sagrado.png','morte':'morte.png'};
    if(icones[r.e]){const icone=HuntUI.el('img','rtc-elemento-icone');icone.src='/ui/elemento_'+icones[r.e];icone.alt='';icone.width=18;icone.height=18;nome.append(icone);}
    nome.append(HuntUI.el('span',null,r.e));
    texto.append(nome,HuntUI.el('strong',null,valor==null?'Não lido':rtcFmt(valor)+'%'));
    barra.append(fill,referencia,texto);bloco.append(barra);
  }
  if(p.peso<p.total)bloco.append(HuntUI.el('p','nota',`População comum: ${rtcFmt(p.total?p.peso/p.total*100:0)}% das criaturas. Elementos incompletos permanecem pendentes.`));
  return bloco;
}

function renderMagiasRTC() {
  if(!HuntApp.dados)return;
  const bloco=HuntUI.$('#recomendacaoMagias'),opt=HuntUI.$('#otimizacaoRTC'),especies=especiesDe(rtcVoltas());
  const identidade=rtcIdentidade(),obsChave=JSON.stringify(identidade);
  if(obsChave!==rtcObsChave && obsChave!==rtcObsSolicitada){
    rtcObsSolicitada=obsChave;rtcObservado={};
    rtcCarregarObservacao(identidade)
      .then(d=>{if(rtcObsSolicitada!==obsChave)return;rtcObservado=d;rtcObsChave=obsChave;rtcAssinatura='';renderMagiasRTC();}).catch(()=>{rtcObsSolicitada='';});
  }
  const assinatura=JSON.stringify([especies,rtcVoc,rtcAlvo,rtcCategoria,rtcDuracao,HuntApp.recorte,HuntApp.selecao,identidade,[rtcObservado.rtc,rtcObservado.cura,rtcObservado.roda,rtcObservado.pontos,rtcObservado.contexto,rtcObservado.modelo,rtcObservado.referencia_atual],Object.entries(HuntApp.catalogo).map(([n,m])=>[n,m.toma])]);
  if(assinatura===rtcAssinatura)return;
  const abertos=new Set([bloco,opt].flatMap(p=>[...p.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent)));
  const restaura=()=>{for(const p of [bloco,opt])for(const d of p.querySelectorAll('details'))if(abertos.has(d.querySelector('summary')?.textContent))d.open=true;};
  rtcAssinatura=assinatura;rtcGeracao++;rtcWorker?.terminate();rtcWorker=null;rtcCancelaCalculos();bloco.replaceChildren();opt.replaceChildren();
  // Um cálculo, duas instâncias do mesmo componente, com o mesmo HuntApp.recorte.
  const elementos=HuntRTC.elementos(especies,HuntApp.catalogo);
  HuntUI.$('#elementosHunt')?.replaceChildren(rtcBarras(elementos));
  if(RTC_DANO)HuntUI.$('#danoContexto').textContent=[HuntApp.dados.sessao?.hunt,identidade.char,HuntApp.dados.sessao?.data,HuntApp.recorte==='volta'?`Volta ${HuntApp.voltaEscolhida()?.n||'—'}`:`${rtcVoltas().length} voltas`].filter(Boolean).join(' · ');
  bloco.append(rtcClasses(),HuntUI.el('p','nota',`Vocação consultada: ${rtcVoc} · personagem observado: ${identidade.char||'não lido'}. A consulta não altera o perfil real.`));
  if(!RTC_CATALOGO){bloco.append(HuntUI.el('p','nota','Carregando o catálogo de magias…'));return;}
  if(!Object.keys(especies).length){bloco.append(HuntUI.el('p','nota','Aguardando criaturas nas voltas fechadas. Você também pode escolher uma sessão no histórico.'));renderIntegradoRTC(opt);restaura();return;}
  const amostra=especies;bloco.append(rtcBarras(elementos));
  const resultados=Object.fromEntries(HuntRTC.categoriasDe(rtcVoc).map(c=>[c,HuntRTC.compararCategoria(RTC_CATALOGO.magias,amostra,HuntApp.catalogo,rtcVoc,c,rtcDuracao)]));
  const tabs=HuntUI.el('div','rtc-tabs');tabs.setAttribute('aria-label','Categorias');
  for(const [c,r] of Object.entries(resultados)){
    const b=rtcBotao('',()=>{rtcCategoria=c;renderMagiasRTC();[...HuntUI.$('#recomendacaoMagias').querySelectorAll('.rtc-tabs button')].find(x=>x.getAttribute('aria-label')===c)?.focus();});
    b.setAttribute('aria-label',c);b.title=c;b.setAttribute('aria-pressed',String(c===rtcCategoria));
    const m=r.linhas.find(m=>r.vencedoras.includes(HuntRTC.id(m)));
    if(m?.imagem)b.append(rtcImagem(m,'rtc-tab-icone'));else b.append(HuntUI.el('span','rtc-tab-icone','—'));
    const nome=HuntUI.el('span','rtc-tab-nome',c);b.append(nome);tabs.append(b);
  }
  const r=resultados[rtcCategoria],res=HuntUI.el('div','rtc-comparativo');res.setAttribute('aria-live','polite');
  res.append(tabs,HuntUI.el('div','rotulo',`${RTC_DANO?'Tabela limpa':'Categoria em foco'} · ${rtcCategoria}`),HuntUI.el('p','nota',`Potência comparativa em ${rtcDuracao} s · um alvo comum`));
  if(!r.linhas.length)res.append(HuntUI.el('p','nota','Categoria indisponível no catálogo desta vocação.'));
  const opcoes=HuntUI.el('div','rtc-opcoes');
  for(const m of r.linhas.slice(0,2)){const card=HuntUI.el('article','rtc-opcao'),venceu=r.vencedoras.includes(HuntRTC.id(m));
    card.append(HuntUI.el('div','rtc-recomendado',venceu?(r.empate?'Empate no cenário':'Recomendado no cenário'):''));
    if(m.imagem)card.append(rtcImagem(m));card.append(HuntUI.el('strong',null,rtcNome(m)),HuntUI.el('small',null,m.elemento));
    card.append(HuntUI.el('div',venceu?'rtc-total rtc-vencedor':'rtc-total',rtcFmt(m.total)),HuntUI.el('small',null,'potência na janela'),
      HuntUI.el('p','nota',`${rtcFmt(m.ajustado)} por uso`));
    const observado=rtcObservado.rtc?.vocacao===rtcVoc?rtcObservado.rtc:null;
    const selo=HuntRTC.conferirRTC(m,null,observado);card.append(HuntUI.el('span',selo.estado==='No RTC'?'rtc-selo':'nota',selo.estado));opcoes.append(card);
  }res.append(opcoes);
  if(r.peso<r.total)res.append(HuntUI.el('p','nota',`Cobertura comum: ${rtcFmt(r.total?r.peso/r.total*100:0)}%. Sem vencedora definitiva. Faltam: ${r.faltam.join(', ')}.`));
  if(r.linhas.length&&r.linhas.every(m=>m.total===0))res.append(HuntUI.el('p','nota','Todos os elementos desta categoria são imunes na população lida. Sem recomendação.'));
  bloco.append(res);
  if(r.linhas.length>2)res.append(HuntUI.el('p','nota rtc-comparativo-nota',`${r.linhas.length} opções comparadas. As duas melhores estão acima.`));
  renderIntegradoRTC(opt);restaura();
}
Promise.all([fetch('/ui/magias.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}),fetch('/ui/roda_catalogo.json',{cache:'no-store'}).then(r=>r.ok?r.json():{})])
  .then(([magias,roda])=>{RTC_CATALOGO=magias;RTC_RODA=roda;rtcAssinatura='';renderMagiasRTC();})
  .catch(()=>{document.querySelector('#recomendacaoMagias').textContent='Catálogo indisponível. Reabra a tela para tentar novamente.';});
setInterval(async()=>{
  if(!HuntApp.dados)return;const identidade=rtcIdentidade(),chave=JSON.stringify(identidade);
  try{const d=await rtcCarregarObservacao(identidade);if(chave!==JSON.stringify(rtcIdentidade()))return;
    const relevantes=x=>JSON.stringify([x.char,x.rtc,x.cura,x.roda,x.pontos,x.contexto,x.modelo,x.referencia_atual]);const mudou=relevantes(d)!==relevantes(rtcObservado);rtcObservado=d;rtcObsChave=chave;if(mudou){rtcAssinatura='';renderMagiasRTC();}
  }catch{}
},5000);

root.HuntPlanejamento={renderizar:renderMagiasRTC,iniciar:iniciaPainelDano, get modoDano(){return RTC_DANO;}};
})(globalThis);
