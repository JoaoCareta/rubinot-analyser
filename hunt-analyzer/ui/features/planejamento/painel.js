(function(root){
let rodaModoVida='utamo',rtcRodaObjetivo='dano',rtcTier=0;
const rtcCacheIntegrado=new Map(),rtcWorkers=new Map();
const rtcBibliotecaRodas=new HuntRodasPreparadas.Biblioteca(),rtcContextosRoda=new Map();
let rtcRodaDesobservar=null;
let rtcIntegradoAssinatura='',rtcIntegradoUI=null;
// Provas e horários de uma releitura não mudam o conteúdo calculável.
// Não aplicar este filtro ao modelo/estudos: neles o tempo é significativo.
function rtcConteudoLeitura(leitura){
  if(Array.isArray(leitura))return leitura.map(rtcConteudoLeitura);
  if(!leitura||typeof leitura!=='object')return leitura;
  return Object.fromEntries(Object.entries(leitura).filter(([k])=>!['instante','prova','capturado_em','processado_em','visto_por_ultimo_em'].includes(k)).map(([k,v])=>[k,rtcConteudoLeitura(v)]));
}
function rtcChaveContexto(ctx){return {...ctx,observado:rtcConteudoLeitura(ctx.observado),helper:rtcConteudoLeitura(ctx.helper)};}
function rtcPrepararPainel(painel,id){
  painel.classList.add('planejamento-painel');painel.dataset.painel=id;
  try{painel.open=localStorage.getItem('hunt:painel:'+id)!=='fechado';}catch{painel.open=true;}
  painel.addEventListener('toggle',()=>{try{localStorage.setItem('hunt:painel:'+id,painel.open?'aberto':'fechado');}catch{}});
}
function rtcPainel(id,titulo,classe){
  const painel=HuntUI.el('details',classe),conteudo=HuntUI.el('div','planejamento-conteudo');
  painel.append(HuntUI.el('summary',null,titulo),conteudo);rtcPrepararPainel(painel,id);return {painel,conteudo};
}
function rtcCancelaCalculos(){for(const w of rtcWorkers.values())w.terminate();rtcWorkers.clear();}
async function rtcOperacao(dados){
  const r=await fetch('/api/configuracoes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)}),d=await r.json();
  if(!r.ok||!d.ok)throw Error(d.erro||'Não foi possível guardar.');return d.resultado;
}
function rtcIconeConfere(escopo){
  const selo=HuntUI.el('span','rtc-confere','✓');
  selo.setAttribute('role','img');selo.setAttribute('aria-label','Similar à sugestão: '+escopo);
  selo.title='Similar à sugestão: '+escopo;return selo;
}
function rtcLeituraConfigurada(m,cura,observado){
  const leitura=cura?observado?.cura:observado?.rtc;
  if(leitura?.atual===false)return null;
  const candidatas=(leitura?.slots||[]).filter(s=>s.id===m.id&&(cura?
    (m.vocacao_destino?s.vocacao_destino===m.vocacao_destino:s.tipo==='autocura'):
    (!s.tipo||s.tipo===(m.runa||m.tipo==='runa'?'runa':'magia'))));
  // Uma leitura ambígua, antiga ou desativada não confirma a sugestão.
  const s=candidatas.length===1?candidatas[0]:null;
  return s&&s.atual!==false&&s.ativo!==false?s:null;
}
function rtcLinhasConfiguradas(linhas,bloco,cura=false,observado=rtcObservado){
  const lista=HuntUI.el('div','rtc-slots');
  for(const m of linhas){const c=HuntUI.el('article','rtc-slot'),cab=HuntUI.el('div','rtc-slot-cabecalho'),titulo=HuntUI.el('div','rtc-slot-titulo');
    c.dataset.magia=m.id;if(m.vocacao_destino)c.dataset.destino=m.vocacao_destino;
    const lida=rtcLeituraConfigurada(m,cura,observado),runa=m.runa||m.tipo==='runa';
    if(m.imagem)cab.append(rtcImagem(m));
    if(!cura){const pos=HuntUI.el('span','rtc-slot-posicao',`${runa?'Runa':'Magia'} ${m.slot??'—'}`);
      if(lida&&Number.isFinite(m.slot)&&lida.slot===m.slot)pos.append(rtcIconeConfere('posição'));
      titulo.append(pos);}
    titulo.append(HuntUI.el('strong',null,`${cura&&m.vocacao_destino?m.vocacao_destino+' · ':''}${rtcNome(m)}`));cab.append(titulo);c.append(cab);
    const campos=HuntUI.el('div','rtc-slot-campos');let ajustes=0;
    const campo=(chave,nome,sufixo='',anterior=null)=>{
      const valor=m[chave],atual=lida?.[chave],confere=Number.isFinite(valor)&&Number.isFinite(atual)&&valor===atual;
      const antes=Number.isFinite(atual)?atual:anterior,mudou=Number.isFinite(valor)&&Number.isFinite(antes)&&valor!==antes;
      const linha=HuntUI.el('div','rtc-slot-campo'+(mudou?' rtc-slot-mudanca':'')),valores=HuntUI.el('span','rtc-slot-valores');
      linha.dataset.campo=chave;linha.append(HuntUI.el('span','rtc-slot-rotulo',nome+' '));
      if(mudou){ajustes++;const de=HuntUI.el('span','rtc-slot-anterior',`${antes}${sufixo}`);de.title='Atual';
        valores.append(de,HuntUI.el('span','rtc-slot-seta',' → '));}
      const para=HuntUI.el('strong',null,Number.isFinite(valor)?`${valor}${sufixo}`:'—');if(mudou)para.title='Sugerido para a próxima hunt';valores.append(para);
      if(confere)valores.append(rtcIconeConfere(nome));linha.append(valores);campos.append(linha);
    };
    if(cura){
      const proposta=['feedback_analisado','aprendizado_sio_parcial','estudo_cura_observacional','aprendizado_validado'].includes(m.origem_percentual);
      campo('vida_percent','Vida','%',proposta?m.vida_percent_anterior:null);
    }else{
      if(!runa)campo('mana_percent','Mana','%');
      if(!(runa&&m.alvos===1))campo('creatures','Criaturas','+');
      campo('prioridade','Prioridade','º');
      if(lida&&Number.isFinite(lida.slot)&&Number.isFinite(m.slot)&&lida.slot!==m.slot)campo('slot','Posição');
    }
    c.append(campos);
    if(ajustes){c.classList.add('rtc-slot-sugerido');c.append(HuntUI.el('span','rtc-slot-proxima','Próxima hunt'));}
    if(cura&&!lida){const notas={informado_usuario:'Configuração atual informada por você.',feedback_usuario:'Sua correção de emergência · referência, ainda não otimizada.',recomendado:'Referência inicial · sem avaliação individual.'};
      if(notas[m.origem_percentual])c.append(HuntUI.el('p','nota',notas[m.origem_percentual]));}
    if(m.frequencia!=null)c.append(HuntUI.el('p','nota',`Frequência de ativação: ${rtcFmt(m.frequencia)} /min · previsão`));
    lista.append(c);
  }
  if(!linhas.length)lista.append(HuntUI.el('p','nota','Aguardando leitura e contexto da hunt.'));bloco.append(lista);
}
function rtcMostrarRoda(r,roda,cat){
  roda.replaceChildren();
  const cmp=r.roda.comparacao_atual;
  if(cmp){
    const box=HuntUI.el('section','rtc-comparacao-atual');box.setAttribute('aria-label','Comparação com sua roda atual');
    box.append(HuntUI.el('h3',null,cmp.estado),HuntUI.el('p','nota','Sua roda e suas gemas são a referência. A distribuição abaixo é uma candidata para comparação.'));
    if(cmp.feedback)box.append(HuntUI.el('p','nota','Revisão do foco Dano após seu relato. A distribuição preserva os benefícios lidos após a troca; os pontos não lidos foram calculados. Proposta sem ganho real confirmado.'));
    if(cmp.similaridade?.similar)box.querySelector('h3').append(rtcIconeConfere(cmp.similaridade.escopo||'benefícios da roda'));
    const tabela=(cabecalhos,linhas)=>{const t=HuntUI.el('table'),head=HuntUI.el('thead'),tr=HuntUI.el('tr'),body=HuntUI.el('tbody');
      for(const nome of cabecalhos)tr.append(HuntUI.el('th',null,nome));head.append(tr);
      for(const valores of linhas){const row=HuntUI.el('tr');for(const valor of valores)row.append(HuntUI.el('td',null,String(valor)));body.append(row);}t.append(head,body);return t;};
    const pct=n=>n==null?'Não lido':rtcFmt(n)+'%',sinal=n=>n==null?'Não medido':(n>0?'+':'')+rtcFmt(n);
    const g=cmp.ganhos;
    if(g)box.append(tabela(['Benefício','Atual','Candidata'],[
      ['Sio · bônus de cura base',pct(g.sio_base_atual),pct(g.sio_base_candidato)],
      ['Cura crítica',g.critico_atual==null?'Não lida':g.critico_atual?'Ativa':'Inativa',g.critico_candidato?'Ativa':'Inativa'],
      ['Dano/cura fixos por aplicação',g.fixo_atual==null?'Não lido':'+'+rtcFmt(g.fixo_atual),'+'+rtcFmt(g.fixo_candidato)+' · diferença '+sinal(g.fixo_delta)]
    ]));
    const relevantes=(cmp.magias||[]).filter(m=>['strong_ice_wave','terra_wave','forked_glacier','forked_thorns','ice_burst'].includes(m.id));
    if(relevantes.length)box.append(tabela(['Magia','Bônus base atual → candidata','Área / alvos'],relevantes.map(m=>[
      rtcNome(m),`${m.bonus_base_atual==null&&m.bonus_roda_atual!=null?pct(m.bonus_roda_atual)+' da roda · gemas pendentes':pct(m.bonus_base_atual)} → ${pct(m.bonus_base_candidato)}`,
      m.area_atual==null?'Área atual não lida':m.area_atual&&!m.area_candidata?'Perde área ampliada':!m.area_atual&&m.area_candidata?'Ganha área ampliada':m.alvos_atual!==m.alvos_candidato?`${m.alvos_atual??'Não lido'} → ${m.alvos_candidato??'Área'} alvos`:'Mantidos'
    ])));
    roda.append(box);
  }
  if(r.roda.estado==='Calculado'){
    roda.append(HuntUI.el('p','nota',`${r.roda.investidos} investidos · ${r.roda.livres} ${r.roda.livres===3?"reservados":"livres"} / ${r.contexto.total} totais`));
    const atual=Object.fromEntries(Object.entries(rtcObservado.roda?.campos||{}).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
    const visual=HuntRodaVisual.montar(cat,r.roda.pontos,r.contexto.total,atual);if(visual.elemento)roda.append(visual.elemento);
    const e=r.roda.efeitos,beneficios=HuntUI.el('div','rtc-beneficios');
    if(Number.isFinite(e.fixo_hp))beneficios.append(HuntUI.el('p','nota',`Bônus fixo de dano e cura: +${e.fixo_hp} HP por aplicação · soma dos estágios e ressonâncias. Não é percentual nem vida máxima.`));
    for(const b of e.beneficios||[])beneficios.append(HuntUI.el('p','nota',`${b.nome} ${['','I','II','III'][b.estagio]} · +${b.bonus_fixo_hp} dano/cura${b.uso==='ativacao_ou_contingencia'?' · efeito especial depende de ativação; sem uso presumido':''}`));
    if(r.roda.comparacao_bonus)beneficios.append(HuntUI.el('p','nota',r.roda.comparacao_bonus.criterio));
    if(r.roda.prioridade_sio?.ativa)beneficios.append(HuntUI.el('p','nota',`Prioridade ao sio: estágio ${['—','I','II'][r.roda.prioridade_sio.estagio]} · ${r.roda.prioridade_sio.criterio}`));
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
function rtcMostrarConfiguracao(r,bloco,observado=rtcObservado){
  bloco.replaceChildren();
  rtcMostrarCura(r,bloco,observado);
  bloco.append(HuntUI.el('h3',null,'Magias e runas'),HuntUI.el('p','nota','Sugestão para a próxima hunt'));
  const pessoal=r.rtc.personalizacao;
  if(pessoal?.personalizada)for(const ajuste of pessoal.alteracoes.slice(0,2))bloco.append(HuntUI.el('p','nota',`${ajuste.campo}: ${ajuste.antes??'vazio'} → ${ajuste.depois??'vazio'} · sugestão para a próxima hunt.`));
  if(r.rtc.equalizacao?.estado==='replay_validado')bloco.append(HuntUI.el('p','nota','Criaturas ajustadas pelo cooldown e pelo equilíbrio entre ativações e dano previsto.'));
  rtcLinhasConfiguradas(r.rtc.linhas||[],bloco,false,observado);
}
function rtcMostrarCura(r,bloco,observado=rtcObservado){
  const cura=HuntUI.el('div','rtc-cura-paineis'),eu=HuntUI.el('section'),pt=HuntUI.el('section');
  eu.append(HuntUI.el('h3',null,'Autocura · '+(r.cura.postura==='utamo'?'Utamo':'Vida')));
  rtcLinhasConfiguradas((r.cura.linhas||[]).filter(m=>!m.vocacao_destino),eu,true,observado);
  pt.append(HuntUI.el('h3',null,'Cura da party · sio e gran sio'));
  rtcLinhasConfiguradas((r.cura.linhas||[]).filter(m=>m.vocacao_destino),pt,true,observado);
  cura.append(eu);if((r.cura.linhas||[]).some(m=>m.vocacao_destino))cura.append(pt);bloco.append(cura);
}
function rtcEscolhas(opcoes,valor,acao,nome,habilitada=()=>true){
  const grupo=HuntUI.el('div','rtc-classes');grupo.setAttribute('aria-label',nome);
  for(const [id,label] of opcoes){const b=rtcBotao(label,()=>acao(id));b.setAttribute('aria-pressed',String(id===valor));b.disabled=!habilitada(id);grupo.append(b);}
  return grupo;
}
function rtcAtualizarTwin(){
  const alvo=rtcIntegradoUI?.twin;
  if(!alvo)return;
  const obs=rtcObservado.rtc||{},t=rtcObservado.twin||{};
  const slots=(obs.slots||[]).filter(s=>['ice_burst','terra_burst'].includes(s.id)&&s.atual!==false&&obs.atual!==false);
  const slot=slots.length===1?slots[0]:null;
  const rtcDesligado=obs.ativo===false||rtcObservado.uso_componentes?.rtc?.estado==='rtc_desligado';
  const desligado=slot?.ativo===false||rtcDesligado;
  const sugerido=t.proposta?.candidato??t.referencia??rtcIntegradoUI.twinSugerida;
  const fila=rtcObservado.leitor?.fila;
  const chave=JSON.stringify([slot,sugerido,obs.visto_por_ultimo_em,t.estado,t.proposta,t.resultado,fila,desligado,rtcObservado.uso_componentes?.rtc?.uso_confirmado]);
  if(alvo.dataset.chave===chave)return;alvo.dataset.chave=chave;alvo.replaceChildren();
  if(!slot&&!sugerido)return;
  if(t.pode_propor&&!t.proposta&&!HuntApp.previa){
    for(const candidato of t.candidatos||[4,6])alvo.append(rtcBotao(`Preparar teste em ${candidato}+ para a próxima hunt`,async()=>{
      try{await rtcOperacao({acao:'experimento_twin',char:rtcIdentidade().char,sessao:rtcIdentidade().sessao,candidato});rtcObservado=await rtcCarregarObservacao(rtcIdentidade());rtcAtualizarTwin();renderMagiasRTC();}
      catch(e){alvo.append(HuntUI.el('p','nota',e.message));}
    }));
  }
  const linha=HuntUI.el('p','nota');
  linha.append(HuntUI.el('strong',null,'Twin · '),document.createTextNode(`Última leitura: ${slot?.creatures==null?'não legível':slot.creatures+'+'}${sugerido==null?'':` · Próxima hunt: ${sugerido}+`}`));
  if(!desligado&&slot?.creatures!=null&&slot.creatures===sugerido){const selo=HuntUI.el('span','rtc-confere',' ✓');selo.title='Limiar da Twin confere com a sugestão';selo.setAttribute('aria-label',selo.title);linha.append(selo);}
  const instante=obs.visto_por_ultimo_em??slot?.instante;
  if(instante)linha.append(document.createTextNode(' · '+new Date(instante*1000).toLocaleTimeString('pt-BR')));
  alvo.append(linha);
  if(slot)alvo.append(HuntUI.el('p','nota',desligado?(rtcDesligado?'RTC desligado.':'Twin desativada.'):rtcObservado.uso_componentes?.rtc?.uso_confirmado?'Uso informado por você.':'Configuração visível; ativação automática ainda não comprovada.'));
  if(t.proposta){alvo.append(HuntUI.el('p','nota',`Próximo teste: Twin ${t.proposta.candidato}+ · ${t.proposta.motivo}`));}
  if(t.resultado){alvo.append(HuntUI.el('p','nota',`Resultado do teste: ${t.resultado.estado.replaceAll('_',' ')} · manter ${t.resultado.manter}+.${t.resultado.ganho_raw_h==null?'':` Diferença observada: ${rtcFmt(t.resultado.ganho_raw_h/1e6)} kk raw XP/h.`}`));}
  if(fila?.erro)alvo.append(HuntUI.el('p','nota','Não foi possível concluir a leitura do RTC.'));
  else if(fila?.pendentes)alvo.append(HuntUI.el('p','nota','Leitura do RTC em atraso.'));
  // Cobertura e amostragem do estudo permanecem internas (AGENTS.md).
}
function renderIntegradoRTC(bloco){
  rtcAtualizarTwin();
  const cat=RTC_RODA?.vocacoes?HuntRodaMotor.selecionar(RTC_RODA,rtcVoc):RTC_RODA;
  if(!cat?.fatias?.length||!RTC_CATALOGO||rtcObsChave!==JSON.stringify(rtcIdentidade()))return;
  const ctx=HuntIntegracao.contexto({...HuntApp.dados,voltas:rtcVoltas()},rtcObservado,rtcVoc);
  const especies=especiesDe(rtcVoltas()),catalogo=Object.entries(HuntApp.catalogo).map(([n,m])=>[n,m.toma]);
  const assinatura=JSON.stringify([rtcChaveContexto(ctx),especies,catalogo,RTC_CATALOGO.versao,cat.versao,HuntApp.recorte,
    rtcVoltas().map(v=>[v.n,v.ini,v.fim]),rtcObservado.uso_componentes,rtcObservado.confirmacao]);
  if(assinatura===rtcIntegradoAssinatura)return;
  rtcIntegradoAssinatura=assinatura;
  const geracao=++rtcGeracao;
  rtcCancelaCalculos();
  rtcRodaDesobservar?.();rtcRodaDesobservar=null;
  const identidade=JSON.stringify([rtcIdentidade(),rtcVoc]);
  if(rtcIntegradoUI?.identidade!==identidade){
  bloco.replaceChildren();
  const paineis=HuntUI.el('div','rtc-independentes'),pRTC=rtcPainel('rtc','RTC','rtc-config-painel'),pRoda=rtcPainel('roda','Roda de habilidades','rtc-roda-painel'),rtc=pRTC.conteudo,roda=pRoda.conteudo;
  pRTC.painel.setAttribute('aria-label','Configuração do RTC');pRoda.painel.setAttribute('aria-label','Roda de habilidades');
  rtc.append(HuntUI.el('div','rotulo','RTC'),HuntUI.el('h2',null,'Otimizar curas e magias'),HuntUI.el('p','nota','Autocura, cura da party, magias e runas para a próxima hunt.'));
  roda.append(HuntUI.el('div','rotulo','RODA DE HABILIDADE'),HuntUI.el('h2',null,'Distribuir os pontos'),HuntUI.el('p','nota','Escolha o foco da roda.'));
  const rtcControles=HuntUI.el('div'),rodaControles=HuntUI.el('div'),rtcResultado=HuntUI.el('div'),rodaResultado=HuntUI.el('div'),conf=HuntUI.el('div','rtc-confirmacao');
  const rtcAviso=HuntUI.el('p','nota'),rodaAviso=HuntUI.el('p','nota'),twin=HuntUI.el('div','rtc-twin-resultado');
  twin.setAttribute('aria-live','polite');
  rtcAviso.hidden=rodaAviso.hidden=true;
  rtcResultado.setAttribute('aria-live','polite');rodaResultado.setAttribute('aria-live','polite');
  rtc.append(rtcControles,twin,rtcAviso,rtcResultado);roda.append(rodaControles,rodaAviso,rodaResultado);paineis.append(pRTC.painel,pRoda.painel);bloco.append(paineis,conf);
  rtcIntegradoUI={identidade,rodaControles,rtcResultado,rodaResultado,rtcAviso,rodaAviso,conf,twin};
  }
  const {rodaControles,rtcResultado,rodaResultado,conf}=rtcIntegradoUI;
  const magias=[...HuntRTC.comparar(RTC_CATALOGO.magias,especies,HuntApp.catalogo,rtcVoc),...RTC_CATALOGO.magias.filter(m=>m.tipo==='cura'&&m.vocs.includes(rtcVoc))];
  const baseChave=JSON.stringify([rtcChaveContexto(ctx),especies,catalogo,RTC_CATALOGO.versao,cat.versao]);
  // Preparar a matriz uma vez por conjunto de voltas/configuração. Leituras
  // posteriores alimentam o próximo conjunto, sem reiniciar por troca de aba.
  const perfilContextual=ctx.modelo?.combate_ml?.contextos?.[JSON.stringify([HuntIntegracao.modalidade(ctx.pt),ctx.hunt||'',ctx.hazard??null])]?.perfis;
  const chaveContexto=JSON.stringify([ctx.char,ctx.sessao,ctx.hunt,ctx.pt,ctx.hazard,perfilContextual,rtcVoc,ctx.total,HuntApp.recorte,
    rtcVoltas().map(v=>[v.n,v.ini,v.fim]),especies,rtcConteudoLeitura(ctx.observado),ctx.modelo?.versao,ctx.modelo?.feedback_cura,ctx.modelo?.feedback_roda,cat.versao,HuntIntegracao.versao]);
  if(!rtcContextosRoda.has(chaveContexto))rtcContextosRoda.set(chaveContexto,ctx);
  const contextoRoda=rtcContextosRoda.get(chaveContexto);
  const rodas=ctx.total==null?null:rtcBibliotecaRodas.preparar(JSON.stringify([HuntRodasPreparadas.versao,contextoRoda,magias,cat.versao]),
    {catalogo:cat,magias,contexto:contextoRoda,opcoes:{limite_ms:12000,finais:8}});
  const resultados={};
  function confirmar(){
    if(resultados.rtc){rtcIntegradoUI.twinSugerida=resultados.rtc.rtc.linhas?.find(s=>['ice_burst','terra_burst'].includes(s.id))?.creatures;rtcAtualizarTwin();}
    conf.replaceChildren();
    const link=HuntUI.el('a',null,'Conferir configuração detectada');link.href='/configuracoes?'+new URLSearchParams({char:ctx.char||'',sessao:ctx.sessao||''});conf.append(HuntUI.el('p','nota',rtcObservado.uso_componentes?.rtc?.uso_confirmado?'Uso do RTC detectado confirmado na calibração.':'Uso do RTC detectado ainda não confirmado.'),link);
    if(!resultados.rtc||!resultados.roda)return;
    const a=resultados.rtc,b=resultados.roda;
    if(b.roda.referencia_reprovada){conf.append(HuntUI.el('p','nota','Roda reprovada retirada das sugestões. Conferir a referência após a troca.'));return;}
    if(b.roda.comparacao_atual&&!b.roda.comparacao_atual.recomendar){conf.append(HuntUI.el('p','nota',b.roda.manter_atual?'Roda reprovada retirada das sugestões. Manter sua referência atual; melhoria ainda não demonstrada.':'A roda permanece como cenário de comparação. Manter sua roda atual: vantagem e segurança ainda não comprovadas.'));return;}
    if(HuntApp.historico||HuntApp.previa||!ctx.char||!a.rtc.linhas?.length||b.roda.estado!=='Calculado')return;
    const payload={versao:2,regras_versao:b.regras_versao,modelo_versao:b.modelo_versao,contexto:b.contexto,
      objetivo:rtcRodaObjetivo,estrategia:b.estrategia,modo_vida:rodaModoVida,tier:rtcTier,independentes:true,revisao_interface:'roda_rtc_uso_v3',
      rtc:a.rtc,cura:a.cura,roda:b.roda,revisao_rtc:'rtc_cura_ml_v1'};
    payload.personalizada=!!a.rtc.personalizada||!!b.roda.personalizada;
    payload.alteracoes=HuntPersonalizacao.alteracoesPacote({rtc:ctx.observado.rtc.slots,
      cura:ctx.observado.cura.slots,pontos:Object.fromEntries(Object.entries(ctx.observado.roda.campos).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]))},
      {rtc:a.rtc.linhas,cura:a.cura.linhas||[],pontos:b.roda.pontos});
    payload.expectativa=a.rtc.expectativa||b.roda.expectativa||null;
    payload.objetivo_declarado=rtcRodaObjetivo;
    const escolha=JSON.stringify([rodaModoVida,rtcRodaObjetivo,rtcTier]),mensagem=HuntUI.el('p','nota');mensagem.setAttribute('role','status');
    if(payload.personalizada&&payload.alteracoes.length>2){conf.append(HuntUI.el('p','nota','Este conjunto de RTC e roda excede dois ajustes. As propostas permanecem separadas; confirme na calibração somente o que aplicar.'));return;}
    let id=null;
    const botao=rtcBotao('Pretendo adotar esta sugestão na próxima hunt',async()=>{
      if(!id)return;botao.disabled=true;
      try{const c=await rtcOperacao({acao:'confirmar',char:ctx.char,id});rtcObservado.confirmacao={...c,valida:true};mensagem.textContent='Intenção registrada. Confirme o uso da leitura na calibração depois de aplicar.';}
      catch(e){mensagem.textContent=e.message;}finally{botao.disabled=false;}
    });botao.disabled=true;conf.append(botao,mensagem);
    const salvo=rtcObservado.sugestao;
    const igual=salvo?.revisao_rtc===payload.revisao_rtc&&salvo?.revisao_interface===payload.revisao_interface&&salvo.modo_vida===rodaModoVida&&salvo.objetivo===rtcRodaObjetivo&&salvo.tier===rtcTier&&salvo.contexto?.vocacao===rtcVoc&&JSON.stringify(salvo.rtc)===JSON.stringify(a.rtc)&&JSON.stringify(salvo.cura)===JSON.stringify(a.cura)&&JSON.stringify(salvo.roda)===JSON.stringify(b.roda);
    const pronta=igual?Promise.resolve(salvo):rtcOperacao({acao:'sugestao',char:ctx.char,sugestao:payload});
    pronta.then(s=>{if(geracao!==rtcGeracao||escolha!==JSON.stringify([rodaModoVida,rtcRodaObjetivo,rtcTier]))return;
      id=s.id;rtcObservado.sugestao=s;botao.disabled=false;
      if(rtcObservado.confirmacao?.valida&&rtcObservado.confirmacao.sugestao_id===id)mensagem.textContent='Intenção de adoção registrada.';
    }).catch(e=>{if(geracao===rtcGeracao)mensagem.textContent=e.message;});
  }
  let rodaExibida,rodaEstado;
  function calcular(tipo){
    const alvo=tipo==='rtc'?rtcResultado:rodaResultado;
    const aviso=tipo==='rtc'?rtcIntegradoUI.rtcAviso:rtcIntegradoUI.rodaAviso;
    const pronto=()=>{alvo.removeAttribute('aria-busy');alvo.inert=false;aviso.hidden=true;};
    const aguardar=mensagem=>{alvo.setAttribute('aria-busy','true');alvo.inert=true;aviso.textContent=mensagem;aviso.hidden=false;};
    if(tipo==='roda'){
      const id=HuntRodasPreparadas.id(rtcRodaObjetivo,rodaModoVida,rtcTier),r=rodas?.resultados[id];
      const estado=rodas?.erros[id]||(ctx.total==null?'Aguardando o total de pontos da roda.':'Preparando as rodas desta hunt… As opções ficam disponíveis assim que estiverem prontas.');
      if(r ? r===rodaExibida : estado===rodaEstado)return;
      rodaExibida=r;rodaEstado=estado;
      delete resultados.roda;conf.replaceChildren();
      if(r){pronto();resultados.roda=r;if(rtcIntegradoUI.rodaExibida!==r)rtcMostrarRoda(r,alvo,cat);rtcIntegradoUI.rodaExibida=r;confirmar();}
      else aguardar(estado+(alvo.childElementCount?' Abaixo, resultado anterior enquanto a atualização termina.':''));
      return;
    }
    const escolha=tipo==='rtc'?null:[rtcRodaObjetivo,rtcTier,rodaModoVida],chave=JSON.stringify([tipo,baseChave,escolha]);
    rtcWorkers.get(tipo)?.terminate();rtcWorkers.delete(tipo);delete resultados[tipo];conf.replaceChildren();
    const mostrar=r=>{pronto();resultados[tipo]=r;if(rtcIntegradoUI.rtcExibido!==r)rtcMostrarConfiguracao(r,alvo,ctx.observado);rtcIntegradoUI.rtcExibido=r;confirmar();};
    const salva=rtcObservado.sugestao,c=rtcObservado.confirmacao;
    
    if(rtcCacheIntegrado.has(chave)){mostrar(rtcCacheIntegrado.get(chave));return;}
    aguardar(alvo.childElementCount?'Atualizando magias e cura… Abaixo, resultado anterior.':'Calculando magias e cura…');
    const w=new Worker('/ui/rtc_worker.js?v=20261014_rodas_objetivos');rtcWorkers.set(tipo,w);
    w.onmessage=e=>{if(geracao!==rtcGeracao||rtcWorkers.get(tipo)!==w)return;w.terminate();rtcWorkers.delete(tipo);
      if(e.data.erro){aguardar('Não foi possível atualizar: '+e.data.erro);return;}
      rtcCacheIntegrado.set(chave,e.data.resultado);if(rtcCacheIntegrado.size>48)rtcCacheIntegrado.delete(rtcCacheIntegrado.keys().next().value);mostrar(e.data.resultado);
    };
    w.onerror=()=>{if(geracao===rtcGeracao){aguardar('Não foi possível calcular. Tente outra opção.');w.terminate();rtcWorkers.delete(tipo);}};
    w.postMessage({chave:geracao,modo:tipo==='rtc'?'rtc_independente':'roda_independente',catalogo:cat,magias,contexto:ctx,objetivo:rtcRodaObjetivo,tier:rtcTier,opcoes:{limite_ms:12000,finais:8,modo_vida:rodaModoVida}});
  }
  function controlesRoda(){
    const assinatura=JSON.stringify([rtcRodaObjetivo,rodaModoVida,rtcTier,ctx.total]);
    if(assinatura===rtcIntegradoUI.assinaturaControles){
      // Um resultado de outra combinação apenas habilita seu botão.
      for(const b of rodaControles.querySelectorAll('button[data-roda-opcao]'))b.disabled=!rodas?.resultados[b.dataset.rodaOpcao];
      return;
    }
    rtcIntegradoUI.assinaturaControles=assinatura;
    const pronta=(objetivo,modo,tier)=>!!rodas?.resultados[HuntRodasPreparadas.id(objetivo,modo,tier)];
    rodaControles.replaceChildren(rtcEscolhas([['dano','Dano'],['cura','Cura']],rtcRodaObjetivo,id=>{rtcRodaObjetivo=id;rtcIntegradoUI.selecionarRoda();},'Foco da roda',id=>pronta(id,rodaModoVida,rtcTier)));
    if(rtcRodaObjetivo==='cura')rodaControles.append(HuntUI.el('p','nota','Como você vai jogar?'),rtcEscolhas([['vida','Vida'],['utamo','Utamo']],rodaModoVida,id=>{rodaModoVida=id;rtcIntegradoUI.selecionarRoda();},'Modo de jogo da roda',id=>pronta(rtcRodaObjetivo,id,rtcTier)));
    rodaControles.append(HuntUI.el('p','nota','Qualidade das gemas'));
    const gemas=HuntUI.el('div','rtc-gemas');
    for(const [tier,nome] of [[0,'Sem gemas'],[1,'Lesser'],[2,'Regular'],[3,'Greater']]){
      const b=rtcBotao('',()=>{rtcTier=tier;rtcIntegradoUI.selecionarRoda();});
      if(tier){const img=HuntUI.el('img','rtc-gema-icone');img.src=`/ui/gema_${rtcVoc.toLowerCase()}_${tier}.png`;img.alt='';img.width=32;img.height=32;b.append(img);}
      else b.append(HuntUI.el('span','rtc-gema-vazia','—'));
      b.append(HuntUI.el('span',null,nome));b.disabled=!pronta(rtcRodaObjetivo,rodaModoVida,tier);b.setAttribute('aria-pressed',String(tier===rtcTier));gemas.append(b);
    }rodaControles.append(gemas);
    if(ctx.total==null){
      const l=HuntUI.el('label','rtc-escolha','Qual é o total de pontos mostrado na roda?'),n=HuntUI.el('input');n.type='number';n.min='0';n.max='10000';n.step='1';l.append(n);const msg=HuntUI.el('p','nota');
      rodaControles.append(l,rtcBotao('Guardar total',async()=>{try{const v=Number(n.value);if(n.value===''||!Number.isInteger(v))throw Error('Informe o total de pontos.');const r=await rtcOperacao({acao:'pontos',char:ctx.char,valor:v});rtcObservado.pontos=r;rtcAssinatura='';renderMagiasRTC();}catch(e){msg.textContent=e.message;}}),msg);
    }
    const grupos=rodaControles.querySelectorAll('.rtc-classes');
    [...grupos[0].querySelectorAll('button')].forEach((b,i)=>b.dataset.rodaOpcao=HuntRodasPreparadas.id(['dano','cura'][i],rodaModoVida,rtcTier));
    if(grupos[1])[...grupos[1].querySelectorAll('button')].forEach((b,i)=>b.dataset.rodaOpcao=HuntRodasPreparadas.id(rtcRodaObjetivo,['vida','utamo'][i],rtcTier));
    [...gemas.children].forEach((b,i)=>b.dataset.rodaOpcao=HuntRodasPreparadas.id(rtcRodaObjetivo,rodaModoVida,i));
  }
  // Controles persistem entre consultas, mas usam o conjunto vigente.
  rtcIntegradoUI.selecionarRoda=()=>{controlesRoda();calcular('roda');};
  if(rodas)rtcRodaDesobservar=rodas.observar(()=>{if(geracao!==rtcGeracao)return;controlesRoda();calcular('roda');});
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
    char:atual.char,rtc:atual.rtc,cura:atual.cura,roda:atual.roda,pontos:atual.pontos,
    modelo:{combate_ml:atual.modelo?.combate_ml,feedback_cura:atual.modelo?.feedback_cura,feedback_roda:atual.modelo?.feedback_roda}
  }:null}:historica;
}
function iniciaPainelDano() {
  if(!RTC_DANO)return;
  document.body.classList.add('modo-dano');document.title='Magias e elementos · Hunt Analyzer';
  const pagina=HuntUI.el('section','dano-pagina');pagina.append(HuntUI.el('div','rotulo','— potência, RTC e roda'),HuntUI.el('h1',null,'Magias e elementos'));
  const campos=HuntUI.el('div','dano-sessao'),label=HuntUI.el('label',null,'Sessão da hunt'),select=HuntUI.el('select');
  const vivo=HuntUI.el('option',null,'Hunt atual');vivo.value='';select.append(vivo);label.append(select);campos.append(label);pagina.append(campos);
  const contexto=HuntUI.el('p','sub');contexto.id='danoContexto';pagina.append(contexto);
  pagina.append(document.querySelector('section.filtros'),HuntUI.$('#painelMagiasElementos'),HuntUI.$('#otimizacaoRTC'));document.querySelector('main').prepend(pagina);
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
    const img=HuntUI.el('img','rtc-classe-icone');img.src=voc==='MS'?'/ui/magia_hell_s_core.png':'/ui/magia_eternal_winter.png';img.alt='';img.width=44;img.height=44;
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
      .then(d=>{if(rtcObsSolicitada!==obsChave)return;rtcObservado=d;rtcObsChave=obsChave;renderMagiasRTC();}).catch(()=>{rtcObsSolicitada='';});
  }
  renderIntegradoRTC(opt);
  const assinatura=JSON.stringify([especies,rtcVoc,rtcAlvo,rtcCategoria,rtcDuracao,HuntApp.recorte,identidade,
    rtcObservado.rtc?.vocacao,rtcConteudoLeitura(rtcObservado.rtc?.slots),RTC_CATALOGO?.versao,Object.entries(HuntApp.catalogo).map(([n,m])=>[n,m.toma])]);
  if(assinatura===rtcAssinatura)return;
  const abertos=new Set([bloco,opt].flatMap(p=>[...p.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent)));
  const restaura=()=>{for(const p of [bloco,opt])for(const d of p.querySelectorAll('details'))if(abertos.has(d.querySelector('summary')?.textContent))d.open=true;};
  rtcAssinatura=assinatura;bloco.replaceChildren();
  // Um cálculo, duas instâncias do mesmo componente, com o mesmo HuntApp.recorte.
  const elementos=HuntRTC.elementos(especies,HuntApp.catalogo);
  HuntUI.$('#elementosHunt')?.replaceChildren(rtcBarras(elementos));
  if(RTC_DANO)HuntUI.$('#danoContexto').textContent=[HuntApp.dados.sessao?.hunt,identidade.char,HuntApp.dados.sessao?.data,HuntApp.recorte==='volta'?`Volta ${HuntApp.voltaEscolhida()?.n||'—'}`:`${rtcVoltas().length} voltas`].filter(Boolean).join(' · ');
  bloco.append(rtcClasses(),HuntUI.el('p','nota',`Vocação consultada: ${rtcVoc} · personagem observado: ${identidade.char||'não lido'}. A consulta não altera o perfil real.`));
  if(!RTC_CATALOGO){bloco.append(HuntUI.el('p','nota','Carregando o catálogo de magias…'));return;}
  if(!Object.keys(especies).length){bloco.append(HuntUI.el('p','nota','Aguardando criaturas nas voltas fechadas. Você também pode escolher uma sessão no histórico.'));restaura();return;}
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
  restaura();
}
Promise.all([fetch('/ui/magias.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}),fetch('/ui/roda_catalogo.json',{cache:'no-store'}).then(r=>r.ok?r.json():{})])
  .then(([magias,roda])=>{RTC_CATALOGO=magias;RTC_RODA=roda;rtcAssinatura='';renderMagiasRTC();})
  .catch(()=>{document.querySelector('#recomendacaoMagias').textContent='Catálogo indisponível. Reabra a tela para tentar novamente.';});
let rtcConsultando=false;
setInterval(async()=>{
  if(!HuntApp.dados||rtcConsultando)return;
  if(rtcObsChave!==JSON.stringify(rtcIdentidade())){renderMagiasRTC();return;}
  rtcConsultando=true;const identidade=rtcIdentidade(),chave=JSON.stringify(identidade);
  try{const d=await rtcCarregarObservacao(identidade);if(chave!==JSON.stringify(rtcIdentidade()))return;
    rtcObservado=d;rtcObsChave=chave;renderMagiasRTC();
  }catch{}finally{rtcConsultando=false;}
},5000);

root.HuntPlanejamento={renderizar:renderMagiasRTC,iniciar:iniciaPainelDano, get modoDano(){return RTC_DANO;}};
rtcPrepararPainel(HuntUI.$('#painelMagiasElementos'),'magias-elementos');
})(globalThis);
