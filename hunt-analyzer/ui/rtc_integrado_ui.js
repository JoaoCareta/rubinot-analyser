let rodaModoVida='utamo',rtcRodaObjetivo='dano',rtcTier=0;
const rtcCacheIntegrado=new Map(),rtcWorkers=new Map();
function rtcCancelaCalculos(){for(const w of rtcWorkers.values())w.terminate();rtcWorkers.clear();}
async function rtcOperacao(dados){
  const r=await fetch('/api/configuracoes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)}),d=await r.json();
  if(!r.ok||!d.ok)throw Error(d.erro||'Não foi possível guardar.');return d.resultado;
}
function rtcLinhasConfiguradas(linhas,bloco,cura=false){
  const lista=el('div','rtc-slots');
  for(const m of linhas){const c=el('article','rtc-slot');if(m.imagem)c.append(rtcImagem(m));
    c.append(el('strong',null,`${cura?(m.vocacao_destino?m.vocacao_destino+' · ':''):m.tipo==='runa'?'Runa '+m.slot+' · ':'Magia '+m.slot+' · '}${rtcNome(m)}`));
    c.append(el('p','nota',cura?`Vida ${m.vida_percent}%${m.origem_percentual==='observado'?' · lido no jogo':''}`:`${m.tipo==='runa'?'':`Mana ${m.mana_percent}% · `}${m.runa&&m.alvos===1?'':`Criaturas ${m.creatures}+ · `}Prioridade ${m.prioridade}º`));
    if(m.frequencia!=null)c.append(el('p','nota',`Frequência de ativação: ${rtcFmt(m.frequencia)} /min · previsão`));
    if(!cura){const conf=HuntRTC.conferirRTC(m,m,rtcObservado.rtc);c.append(el('span',conf.estado==='Ajustar'?'rtc-ajustar':'nota',conf.estado));}
    lista.append(c);
  }
  if(!linhas.length)lista.append(el('p','nota','Aguardando leitura e contexto da hunt.'));bloco.append(lista);
}
function rtcMostrarRoda(r,roda,cat){
  roda.replaceChildren();
  rtcMostrarAprendizado(r.roda.aprendizado,roda);
  if(r.roda.estado==='Calculado'){
    roda.append(el('p','nota',`${r.roda.investidos} investidos · ${r.roda.livres} ${r.roda.livres===3?"reservados":"livres"} / ${r.contexto.total} totais`));
    const atual=Object.fromEntries(Object.entries(rtcObservado.roda?.campos||{}).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
    const visual=HuntRodaVisual.montar(cat,r.roda.pontos,r.contexto.total,atual);if(visual.elemento)roda.append(visual.elemento);
    const e=r.roda.efeitos,beneficios=el('div','rtc-beneficios');
    if(e.ranks[28])beneficios.append(el('p','nota','Healing Link completo · autocura de 25% da cura aplicada por sio/gran sio'));
    if(e.revelation[10])beneficios.append(el('p','nota',`Twin Bursts · estágio ${e.revelation[10]} · cooldown ${[0,22,18,14][e.revelation[10]]} s · dano adicional condicionado à vida do alvo`));
    if(e.revelation[11])beneficios.append(el('p','nota',`Blessing of the Grove · estágio ${e.revelation[11]} · bônus condicionado à vida e ao crítico`));
    for(const [id,n] of Object.entries(e.ranks)){
      const perk=cat.conviction[id];if(!perk||id==='28')continue;
      beneficios.append(el('p','nota',`${perk.Name.split('|')[0]} · ${n}`));
    }
    roda.append(beneficios,el('p','nota',r.roda.gemas.length?'Gemas sugeridas · equipamento não conferido':'Sem gemas'));
    for(const g of r.roda.gemas)roda.append(el('p','nota',`${g.dominio} · ${g.qualidade} · ${g.nome||'Gema observada'}${g.grau?' · grau '+g.grau:''}`));
    for(const g of r.roda.gemas)for(const b of g.basicos||[])roda.append(el('p','nota',`${g.dominio} · ${cat.basicos_normalizados?.[b.mod]?.nome||'Modificador básico'} · grau ${b.grau}`));
    if(e.magic_level)roda.append(el('p','nota',`Magic level da roda: +${e.magic_level}`));
    const codigo=HuntRodaMotor.exportarCodigo(cat,r.roda.pontos);
    roda.append(rtcBotao('Copiar código dos pontos',async()=>{try{await navigator.clipboard.writeText(codigo);}catch{const campo=el('input');campo.readOnly=true;campo.value=codigo;campo.setAttribute('aria-label','Código dos pontos');roda.append(campo);campo.select();}}));
  }else roda.append(el('p','nota',r.roda.estado));
}
function rtcMostrarConfiguracao(r,bloco){
  bloco.replaceChildren();
  rtcMostrarAprendizado(r.rtc.aprendizado,bloco);
  rtcMostrarCura(r,bloco);
  bloco.append(el('h3',null,'Magias e runas'),el('p','nota','Sugestão para a próxima hunt'));
  if(r.rtc.equalizacao?.estado==='replay_validado')bloco.append(el('p','nota','Criaturas ajustadas pelo cooldown e pelo equilíbrio entre ativações e dano previsto.'));
  rtcLinhasConfiguradas(r.rtc.linhas||[],bloco);
}
function rtcMostrarAprendizado(a,bloco){
  if(!a)return;
  bloco.append(el('p','nota',a.estado==='aprendizado_validado_parcial'?`Aprendizado ativo · ${a.amostras} exemplos · validado em dados posteriores. Cobertura de dano parcial.`:`Aprendizado em coleta · ${a.amostras} exemplos · sua roda atual é a referência.`));
}
function rtcMostrarCura(r,bloco){
  const cura=el('div','rtc-cura-paineis'),eu=el('section'),pt=el('section');
  eu.append(el('h3',null,'Autocura · '+(r.cura.postura==='utamo'?'Utamo':'Vida')));
  rtcLinhasConfiguradas((r.cura.linhas||[]).filter(m=>!m.vocacao_destino),eu,true);
  pt.append(el('h3',null,'Cura da party · sio e gran sio'));
  rtcLinhasConfiguradas((r.cura.linhas||[]).filter(m=>m.vocacao_destino),pt,true);
  cura.append(eu);if((r.cura.linhas||[]).some(m=>m.vocacao_destino))cura.append(pt);bloco.append(cura);
}
function rtcEscolhas(opcoes,valor,acao,nome){
  const grupo=el('div','rtc-classes');grupo.setAttribute('aria-label',nome);
  for(const [id,label] of opcoes){const b=rtcBotao(label,()=>acao(id));b.setAttribute('aria-pressed',String(id===valor));grupo.append(b);}
  return grupo;
}
function renderIntegradoRTC(bloco){
  const cat=RTC_RODA?.vocacoes?HuntRodaMotor.selecionar(RTC_RODA,rtcVoc):RTC_RODA;
  if(!cat?.fatias?.length)return;
  rtcCancelaCalculos();bloco.replaceChildren();
  const ctx=HuntIntegracao.contexto({...D,voltas:rtcVoltas()},rtcObservado,rtcVoc),geracao=rtcGeracao;
  const paineis=el('div','rtc-independentes'),rtc=el('section','rtc-config-painel'),roda=el('section','rtc-roda-painel');
  rtc.setAttribute('aria-label','Configuração do RTC');roda.setAttribute('aria-label','Roda de habilidade');
  rtc.append(el('div','rotulo','RTC'),el('h2',null,'Otimizar curas e magias'),el('p','nota','Autocura, cura da party, magias e runas para a próxima hunt.'));
  if(HIST)rtc.append(el('p','nota',ctx.referencia_roda==='atual_para_proxima_hunt'?'Sugestão recalculada para esta hunt com sua roda atual. Os registros da sessão permanecem como foram observados.':'Sugestão recalculada com os dados disponíveis desta sessão.'));
  roda.append(el('div','rotulo','RODA DE HABILIDADE'),el('h2',null,'Distribuir os pontos'),el('p','nota','Escolha o foco da roda.'));
  const rtcControles=el('div'),rodaControles=el('div'),rtcResultado=el('div'),rodaResultado=el('div'),conf=el('div','rtc-confirmacao');
  rtcResultado.setAttribute('aria-live','polite');rodaResultado.setAttribute('aria-live','polite');
  rtc.append(rtcControles,rtcResultado);roda.append(rodaControles,rodaResultado);paineis.append(rtc,roda);bloco.append(paineis,conf);
  const especies=especiesDe(rtcVoltas()),magias=[...HuntRTC.comparar(RTC_CATALOGO.magias,especies,CATALOGO,rtcVoc),...RTC_CATALOGO.magias.filter(m=>m.tipo==='cura'&&m.vocs.includes(rtcVoc))];
  const baseChave=JSON.stringify([ctx,especies,Object.entries(CATALOGO).map(([n,m])=>[n,m.toma]),RTC_CATALOGO.versao,cat.versao]);
  const resultados={};
  function confirmar(){
    conf.replaceChildren();
    if(!resultados.rtc||!resultados.roda)return;
    const a=resultados.rtc,b=resultados.roda;
    if(HIST||PREVIA||!ctx.char||!a.rtc.linhas?.length||b.roda.estado!=='Calculado')return;
    const payload={versao:2,regras_versao:b.regras_versao,modelo_versao:b.modelo_versao,contexto:b.contexto,
      objetivo:rtcRodaObjetivo,estrategia:b.estrategia,modo_vida:rodaModoVida,tier:rtcTier,independentes:true,revisao_interface:'roda_rtc_uso_v3',
      rtc:a.rtc,cura:a.cura,roda:b.roda,revisao_rtc:'rtc_cura_ml_v1'};
    const escolha=JSON.stringify([rodaModoVida,rtcRodaObjetivo,rtcTier]),mensagem=el('p','nota');mensagem.setAttribute('role','status');
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
    alvo.replaceChildren(el('p','nota',tipo==='rtc'?'Calculando magias e cura…':'Calculando a roda…'));
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
    if(rtcRodaObjetivo==='cura')rodaControles.append(el('p','nota','Como você vai jogar?'),rtcEscolhas([['vida','Vida'],['utamo','Utamo']],rodaModoVida,id=>{rodaModoVida=id;controlesRoda();calcular('roda');},'Modo de jogo da roda'));
    rodaControles.append(el('p','nota','Qualidade das gemas'));
    const gemas=el('div','rtc-gemas');
    for(const [tier,nome] of [[0,'Sem gemas'],[1,'T1 · Lesser'],[2,'T2 · Regular'],[3,'T3 · Greater']]){
      const b=rtcBotao(nome,()=>{rtcTier=tier;controlesRoda();calcular('roda');});b.setAttribute('aria-pressed',String(tier===rtcTier));gemas.append(b);
    }rodaControles.append(gemas);
    if(ctx.total==null){
      const l=el('label','rtc-escolha','Qual é o total de pontos mostrado na roda?'),n=el('input');n.type='number';n.min='0';n.max='10000';n.step='1';l.append(n);const msg=el('p','nota');
      rodaControles.append(l,rtcBotao('Guardar total',async()=>{try{const v=Number(n.value);if(n.value===''||!Number.isInteger(v))throw Error('Informe o total de pontos.');const r=await rtcOperacao({acao:'pontos',char:ctx.char,valor:v});rtcObservado.pontos=r;rtcAssinatura='';renderMagiasRTC();}catch(e){msg.textContent=e.message;}}),msg);
    }
  }
  controlesRoda();calcular('rtc');calcular('roda');
}
