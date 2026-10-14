const HuntIntegracao=(()=>{
  const estrategias=[
    ['dano','Dano'],['atual','Configuração atual'],['vida','Vida'],['utamo','Utamo'],['utamo_critica','Utamo + cura crítica'],
    ['vida_link99','Vida + Healing Link · sio EK 99%'],['vida_link','Vida + Healing Link'],
    ['vida_critica','Vida + cura crítica'],['vida_link_critica','Healing Link + cura crítica'],
    ['utamo_link_critica','Utamo + Link + cura crítica'],['vida_contingencia','Vida + utamo de contingência'],['mas_res','Ênfase em mas res']];
  const versao='integrado-20-rodas-por-objetivo';
  function vocacaoObservada(obs){
    const explicita=obs?.rtc?.vocacao||obs?.roda?.vocacao;if(explicita)return explicita;
    const campos=obs?.roda?.campos||{},vocs=new Set();
    for(const [voc,nomes] of Object.entries({ED:['Aug. Heal Friend','Aug. Strong Ice Wave','Twin Bursts','Blessing of the Grove'],MS:['Aug. Energy Wave','Aug. Great Fire Wave','Beam Mastery','Drain Body']}))
      if(nomes.some(n=>['conviction.','revelation.'].some(g=>campos[g+n]?.qualidade==='texto_integral')))vocs.add(voc);
    return vocs.size===1?[...vocs][0]:null;
  }
  function similaridadeRoda(cat,ref,candidata){
    // Semelhança dos benefícios observáveis, não igualdade de pontos/gemas nem adoção.
    const ranks=cat.vocacao==='ED'?[29,31,33]:[24,25],revs=cat.vocacao==='ED'?[10,11]:[];
    const a=ref.completa&&ref.gemas_completas?ref.efeitos:ref.observados,b=candidata.efeitos;
    const conferidos=[],diferencas=[],pendentes=[],variacoes=[];
    for(const [grupo,ids] of [['ranks',ranks],['revelation',revs]])for(const id of ids){
      const atual=a[grupo]?.[id],alvo=b[grupo]?.[id]||0,chave=grupo+'.'+id;
      if(atual==null){pendentes.push(chave);continue;}
      const mesmoEstagio=grupo==='ranks'&&id!==29;
      if(mesmoEstagio?atual!==alvo:!atual||!alvo||Math.abs(atual-alvo)>1)diferencas.push(chave);
      else {conferidos.push({chave,atual,candidata:alvo});if(atual!==alvo)variacoes.push({chave,atual,candidata:alvo});}
    }
    return {similar:!pendentes.length&&!diferencas.length&&conferidos.length>=4,conferidos,diferencas,pendentes,variacoes,
      escopo:'Benefícios principais conferidos na calibração; estágios de forks, Twin e Blessing, pontos e gemas podem diferir.'};
  }
  function rtcParaComparacao(rtc,magias){
    const slots=rtc?.slots||[];
    const conhecidos=slots.every(s=>s.atual!==false&&(s.estado==='vazio_confirmado'||s.id&&magias.some(m=>m.id===s.id)&&Number.isInteger(s.prioridade)&&(s.tipo==='runa'||Number.isFinite(s.mana_percent))&&(Number.isInteger(s.creatures)||magias.find(m=>m.id===s.id)?.alvos===1)));
    const grade=['magia:1','magia:2','magia:3','magia:4','magia:5','runa:1','runa:2'];
    const completa=slots.length===7&&grade.every(k=>slots.some(s=>`${s.tipo}:${s.slot}`===k));
    return {completo:!!rtc?.completo||completa&&conhecidos,slots:slots.filter(s=>s.id).map(s=>({...s,creatures:s.creatures??(magias.find(m=>m.id===s.id)?.alvos===1?1:null)}))};
  }
  function modalidade(pt){const s=String(pt??'').trim().toLowerCase();return /^(solo|x1|1|pt x1)$/.test(s)?'solo':/^(pt\s*)?x?[2-5]$/.test(s)?'party':'desconhecida';}
  function tamanhoParty(pt){return /^(?:pt\s*)?x?([2-9]\d*)$/.exec(String(pt??'').trim().toLowerCase())?.[1]||null;}
  function gemasObservadas(cat,campos){
    return Object.entries(campos).filter(([k,v])=>k.startsWith('gemas.')&&v.valor?.estado==='observado_completo'&&v.valor.equipada).map(([k,v])=>{
      const g=v.valor,sup=g.modificadores?.[0];return {...g,...sup,dominio:k.slice(6)};
    });
  }
  function referenciaRoda(cat,ctx){
    const roda=ctx.observado?.roda||{},campos=roda.campos||{},observados=efeitosRTCObservados(cat,ctx);
    const pontos=Object.fromEntries(Object.entries(campos).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
    const completa=!!roda.completo&&Number.isInteger(ctx.total)&&cat.fatias.every(f=>Number.isInteger(pontos[f.id]))&&HuntRTC.validarDistribuicao(cat,pontos,ctx.total+3).ok;
    const gemas=gemasObservadas(cat,campos),dominios=Object.entries(HuntRodaMotor.resumo(cat,pontos).vr).filter(([,n])=>n>0).map(([q])=>q);
    const gemasCompletas=completa&&dominios.every(q=>['observado_completo','vazio_confirmado'].includes(campos['gemas.'+q]?.valor?.estado));
    const numero=k=>{const c=campos[k];if(c?.qualidade!=='texto_integral'||!/^\+?\d+(?:[.,]\d+)?%?$/.test(String(c.valor)))return null;return Number(String(c.valor).replace('%','').replace(',','.'));};
    const fixoRevelacao=numero('revelation.Damage and Healing'),fixoVessels=numero('vessels.Damage and Healing');
    const bonusFrigo=numero('vessels.Strong Ice Wave'),bonusSio=numero('vessels.Heal Friend');
    if(!gemasCompletas){
      if(fixoRevelacao!=null&&fixoVessels!=null)observados.fixo_hp=fixoRevelacao+fixoVessels;
      observados.bp_gemas={...(bonusFrigo!=null?{strong_ice_wave:bonusFrigo/100}:{}),...(bonusSio!=null?{heal_friend:bonusSio/100}:{})};
    }
    const efeitos=HuntRodaMotor.efeitos(cat,completa?pontos:{},gemasCompletas?gemas:[],completa&&gemasCompletas?{}:observados);
    const lacunas=[];
    if(!completa)lacunas.push('Distribuição atual parcialmente lida');
    if(!gemasCompletas)lacunas.push('Gemas atuais: efeitos visíveis não identificam todos os modificadores, graus e domínios');
    return {pontos:completa?pontos:null,gemas:gemasCompletas?gemas:[],observados,efeitos,completa,gemas_completas:gemasCompletas,
      fixo_conhecido:gemasCompletas||observados.fixo_hp!=null,bonus_sio:bonusSio,bonus_frigo_conhecido:gemasCompletas||bonusFrigo!=null,lacunas,preset:roda.preset||null};
  }
  function feedbackRoda(cat,ctx){
    return (ctx.modelo?.feedback_roda||[]).filter(f=>f.origem==='usuario'&&f.tipo==='desempenho_insatisfatorio'&&f.vigente===true&&!f.qa&&!f.sintetico&&f.id&&f.provas?.length
      &&(f.objetivo||'dano')===(ctx.objetivo_roda||'dano')
      &&f.contexto?.char===ctx.char&&f.contexto?.hunt===ctx.hunt&&tamanhoParty(f.contexto?.pt)&&tamanhoParty(f.contexto.pt)===tamanhoParty(ctx.pt)
      &&(!f.contexto.vocacao||f.contexto.vocacao===cat.vocacao)
      &&(f.sessao===ctx.sessao||f.rejeitada===true&&f.escopo==='mesmo_contexto_proximas_hunts'
        &&Array.isArray(f.contexto.hazards)&&f.contexto.hazards.includes(ctx.hazard))).at(-1);
  }
  function rodaRejeitada(feedback,efeitos){
    const assinatura=feedback?.roda_rejeitada?.beneficios;
    if(!feedback?.rejeitada||!assinatura||!efeitos)return false;
    const campos=['ranks','revelation'].flatMap(grupo=>Object.entries(assinatura[grupo]||{}).map(([id,n])=>[grupo,id,n]));
    return campos.length>=4&&campos.every(([grupo,id,n])=>(efeitos[grupo]?.[id]||0)===n);
  }
  function compararRoda(cat,magias,ctx,candidata,opcoes={}){
    const ref=referenciaRoda(cat,ctx),e=candidata?.efeitos,modo=modalidade(ctx.pt),proteger=cat.vocacao==='ED'&&modo!=='solo';
    const feedback=feedbackRoda(cat,ctx);
    const lacunas=[...ref.lacunas],motivos=[],delta=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)?b-a:null;
    if(!e)return {estado:'Manter roda atual',recomendar:false,referencia:ref,lacunas,motivos:['Nenhuma candidata preservou os requisitos'],cenarios:[],magias:[]};
    if(rodaRejeitada(feedback,e))motivos.push('Roda reprovada pelo usuário nesta hunt; não repetir seus benefícios como sugestão');
    const atual=HuntRodaMotor.modificar(cat,ref.pontos||{},magias,ref.gemas,{temporal:true,efeitos_observados:ref.completa&&ref.gemas_completas?{}:ref.observados});
    const futura=HuntRodaMotor.modificar(cat,candidata.pontos,magias,candidata.gemas,{temporal:true});
    const atualRank=id=>ref.completa?ref.efeitos.ranks[id]||0:ref.observados.ranks[id]??null;
    const atualRev=id=>ref.completa&&ref.gemas_completas?ref.efeitos.revelation[id]||0:ref.observados.revelation[id]??null;
    const sioAntes=atualRank(33),sioDepois=e.ranks[33]||0;
    if(proteger&&sioDepois<2)motivos.push('Sio II é requisito para ED em PT; ganho ofensivo não autoriza reduzir a cura base do EK');
    if(proteger&&!(e.revelation[11]>0))motivos.push('Preservar a cura crítica do EK');
    const linhas=atual.filter(m=>HuntRTC.categoria(m)&&futura.some(n=>n.id===m.id)).map(a=>{
      const b=futura.find(n=>n.id===a.id),perk={strong_ice_wave:31,forked_glacier:29,forked_thorns:29,terra_wave:30}[a.id];
      const conhecido=ref.gemas_completas||(a.id==='strong_ice_wave'&&ref.bonus_frigo_conhecido&&atualRank(31)!=null);
      return {id:a.id,nome:a.nome,elemento:a.elemento,resistencia:Number.isFinite(a.resistencia)?a.resistencia:null,
        bonus_base_atual:conhecido?(a.multiplicador_base-1)*100:null,bonus_base_candidato:(b.multiplicador_base-1)*100,
        bonus_roda_atual:perk&&atualRank(perk)!=null?(HuntRodaMotor.efeitos(cat,{},[],{ranks:{[perk]:atualRank(perk)}}).bp[a.id]||0)*100:null,
        variacao_base_percent:conhecido?(b.bp/a.bp-1)*100:null,
        area_atual:perk&&atualRank(perk)==null?null:!!a.area_ampliada,area_candidata:!!b.area_ampliada,
        alvos_atual:ref.completa||perk&&atualRank(perk)!=null?a.alvos:null,alvos_candidato:b.alvos,
        cooldown_atual:ref.completa||perk&&atualRank(perk)!=null||a.familia==='bursts'&&atualRev(10)!=null?a.cd:null,cooldown_candidato:b.cd};
    });
    const alterouGeometria=linhas.some(m=>m.area_atual!==m.area_candidata||m.alvos_atual!==m.alvos_candidato);
    if(alterouGeometria)lacunas.push('Troca de área/alvos exige cobertura e posicionamento próprios de cada roda; os alvos da roda atual não comprovam os da candidata');
    const rtcLido=rtcParaComparacao(ctx.observado?.rtc,magias),slots=rtcLido.slots;
    if(!rtcLido.completo)lacunas.push('RTC atual parcialmente lido');
    if(!ctx.observado?.cura?.completo&&proteger)lacunas.push('Configuração de cura do EK parcialmente lida');
    const montar=(pool,ordem)=>ordem.map(s=>{const m=pool.find(m=>m.id===s.id);return m?{...m,...Object.fromEntries(['tipo','slot','prioridade','prioridade_execucao','creatures','mana_percent'].filter(k=>s[k]!=null).map(k=>[k,s[k]]))}:null;}).filter(Boolean);
    const ofensivas=pool=>pool.filter(m=>HuntRTC.categoria(m)).map(m=>({...m,resistencia:m.resistencia??100,ajustado:m.ajustado??m.bp}));
    const base=ofensivas(atual),nova=ofensivas(futura),otimizada=base.length?ataque(base,ctx,{...opcoes,larguraRTC:4}).linhas:[];
    // Mesma política otimizada nos dois braços: isola o efeito da roda e a interação.
    const planos=[['atual_atual','RTC atual + roda atual',base,slots,false],['rtc_atual','RTC otimizado + roda atual',base,otimizada,false],
      ['atual_roda','RTC atual + roda candidata',nova,slots,true],['rtc_roda','RTC otimizado + roda candidata',nova,otimizada,true]];
    const cenariosComparados=planos.map(([id,nome,pool,ordem,troca])=>{
      const ms=montar(pool,ordem),faltam=ordem.some(s=>!ms.some(m=>m.id===s.id));
      if(!ms.length||faltam)return {id,nome,indice_dano:null,cura_util_hp:null,ek:null,motivo:'Magia/configuração indisponível'};
      // Sem geometria candidata medida, não reutilizar alvos observados como prova.
      const contexto=troca&&alterouGeometria?{...ctx,janelas:(ctx.janelas||[]).map(j=>({...j,origem_alvos:'referencia',alvos:undefined}))}:ctx;
      const r=ataque(ms,contexto,{...opcoes,fixar:true});
      const c=ref.completa&&ref.gemas_completas&&ctx.observado?.cura?.completo?curar(cat,troca?candidata.pontos:ref.pontos,troca?candidata.gemas:ref.gemas,magias,ctx,'atual',{fixar_limiares:true}):null;
      let conjunto=null;
      if(c?.estado==='Previsto'){
        const js=[];for(const a of cenarios(contexto,ms))for(const v of c.janelas_modelo||[]){const t=Math.max(a.t,v.t),fim=Math.min(a.fim,v.fim);if(fim>t)js.push({...a,...v,alvos:a.alvos,origem_alvos:a.origem_alvos,t,fim,dano:t===v.t?v.dano:{},cura_externa:t===v.t?v.cura_externa:{}});}
        if(js.length)conjunto=HuntTemporal.simular([...ms,...c.linhas.filter(m=>m.ativo!==false)],{...ctx.cura,...ctx.atributos,modelo:ctx.modelo,nivel:ctx.nivel,janelas:js},{duracao:180,sem_critico:true});
      }
      const ekNome=ctx.cura?.aliados?.find(a=>a.vocacao==='EK')?.nome;
      const rtcConhecido=id.startsWith('atual_')?rtcLido.completo:true;
      return {id,nome,indice_dano:rtcConhecido?(conjunto?.score??r.score):null,faixa:r.faixa,casts:conjunto?.casts??r.casts,
        cura_util_hp:conjunto?.cura??null,excesso_hp:conjunto?.excesso??null,mana:conjunto?.manaGasta??null,
        ek:ekNome?conjunto?.saude?.[ekNome]??null:null,seguranca:conjunto?{saude:conjunto.saude}:null,
        origem:'simulacao',ganho_real_dano:null,ganho_real_cura:null};
    });
    const inicial=cenariosComparados[0];
    for(const row of cenariosComparados){row.delta_indice_dano=delta(inicial.indice_dano,row.indice_dano);row.delta_cura_util_hp=delta(inicial.cura_util_hp,row.cura_util_hp);}
    const sensibilidade=[];
    for(const [idWave,idFork] of [['strong_ice_wave','forked_glacier'],['terra_wave','forked_thorns']]){
      const wave=atual.find(m=>m.id===idWave),fork=futura.find(m=>m.id===idFork),nw=inicial.casts?.[idWave],nf=cenariosComparados[2].casts?.[idFork];
      if(!wave||!fork||!Number.isFinite(wave.resistencia)||!Number.isFinite(fork.resistencia)||!(nw>0&&nf>0))continue;
      // Análise de sensibilidade, sem fabricar geometria: custo de um alvo
      // perdido por wave versus ganho de um alvo adicional por fork no trecho.
      const custo=wave.bp*wave.resistencia/100*nw,ganho=fork.bp*fork.resistencia/100*nf;
      if(ganho>0)sensibilidade.push({wave:idWave,fork:idFork,casts_wave:nw,casts_fork:nf,
        alvos_extras_por_fork_para_compensar_um_por_wave:custo/ganho,origem:'sensibilidade_base_sem_criticos',
        limite:'Somente efeito de cobertura, nas frequências previstas. Não inclui demais trocas de bônus, crítico, mana ou segurança.'});
    }
    if(!ctx.janelas?.length||ctx.janelas.some(j=>j.origem_alvos!=='observado'))lacunas.push('Alvos efetivamente atingidos por turno ainda não medidos integralmente');
    if(proteger&&cenariosComparados.some(c=>!c.ek))lacunas.push('Conforto do EK sem comparação completa de HP mínimo, tempo crítico e cura útil');
    for(const row of cenariosComparados.slice(2))if(row.seguranca&&inicial.seguranca&&!HuntTemporal.naoPiora(row.seguranca,inicial.seguranca))motivos.push('Simulação piora a segurança de um integrante da party');
    const ganhos={sio_base_atual:sioAntes==null?null:(ref.efeitos.bp.heal_friend||0)*100,sio_base_candidato:(e.bp.heal_friend||0)*100,
      critico_atual:atualRev(11)==null?null:atualRev(11)>0,critico_candidato:e.revelation[11]>0,
      blessing_atual:atualRev(11),blessing_candidato:e.revelation[11]||0,
      fixo_atual:ref.fixo_conhecido?ref.efeitos.fixo_hp:null,fixo_candidato:e.fixo_hp,
      fixo_delta:ref.fixo_conhecido?e.fixo_hp-ref.efeitos.fixo_hp:null};
    const contextoCenario={modalidade:modo,hunt:ctx.hunt||null,hazard:ctx.hazard??null,
      criterio:modo==='solo'?'Solo: comparar acertos e turnos de posicionamento das waves com alvos e frequência das forks.':modo==='party'?'PT: comparar cobertura da box pelas waves, alcance das forks e segurança individual do EK.':'Modalidade não identificada: não transferir rendimento entre solo e PT.',
      gelo_terra:linhas.filter(m=>['strong_ice_wave','terra_wave','forked_glacier','forked_thorns'].includes(m.id)),
      retirada_area:'Gelo mais favorável não justifica retirar área do Frigo II. A troca depende dos acertos perdidos e do benefício comprado com os pontos.'};
    // Replay e regras não são um resultado observado depois da adoção.
    return {estado:motivos.length?'Troca bloqueada':feedback?'Reavaliada após seu relato · comparação parcial':lacunas.length?'Manter roda atual · comparação parcial':'Cenário simulado · ganho real ainda não comprovado',
      ...(feedback?{feedback:{id:feedback.id,origem:'usuario',beneficio_real_validado:false}}:{}),
      recomendar:false,ganho_real_dano:null,ganho_real_cura:null,referencia:{preset:ref.preset,completa:ref.completa,gemas_completas:ref.gemas_completas},
      similaridade:similaridadeRoda(cat,ref,candidata),ganhos,magias:linhas,cenarios:cenariosComparados,sensibilidade,contexto:contextoCenario,lacunas:[...new Set(lacunas)],motivos:[...new Set(motivos)],
      limite:'Valores de dano são índices previstos. Cura em HP só com potência calibrada e janelas comparáveis. Ganho real exige adoção comprovada e avaliação posterior no mesmo contexto.'};
  }
  function compararDano(a,b,priorizarSio=false){
    const diferenca=(a.rtc.robusto??0)-(b.rtc.robusto??0);
    if(Math.abs(diferenca)>1e-8)return diferenca;
    const nominal=(a.rtc.score??0)-(b.rtc.score??0);
    if(Math.abs(nominal)>1e-8)return nominal;
    return priorizarSio?(a.roda.efeitos.ranks[33]||0)-(b.roda.efeitos.ranks[33]||0):0;
  }
  function perfilCombate(m,ctx){
    let modelo=ctx.modelo?.combate_ml;
    if(!modelo||modelo.char!==ctx.char||modelo.regras_versao!==ctx.regras_versao)return null;
    const modo=modalidade(ctx.pt);
    if(modo!=='desconhecida'){
      const chaveContexto=JSON.stringify([modo,ctx.hunt||'',ctx.hazard??null]);
      const contextual=modelo.contextos?.[chaveContexto];
      if(!contextual)return null;
      modelo={...modelo,perfis:contextual.perfis,hazard:ctx.hazard};
    }
    if(ctx.hazard!=null&&modelo.hazard!==ctx.hazard)return null;
    const chave=`${m.id}|area:${Number(!!m.area_ampliada)}|extra:${Number(!!m.alvo_adicional)}|twin:${m.twin_estagio||0}`;
    const valida=p=>p?.treino>=30&&p.validacao>=8&&p.treino_ate<p.teste_desde;
    const perfil=modelo.perfis?.[chave];if(valida(perfil))return {...perfil,fator_regra_min:1,transferencia:false};
    // Área ampliada contém a normal; estágio maior de Twin conserva o dano do
    // menor. Só transferir esse limite inferior, sem inventar ganho de área/HP.
    for(const [k,p] of Object.entries(modelo.perfis||{})){
      const partes=/^(.+)\|area:([01])\|extra:([01])\|twin:(\d)$/.exec(k);
      if(!partes||partes[1]!==m.id||!valida(p)||+partes[2]>Number(!!m.area_ampliada)||+partes[3]>Number(!!m.alvo_adicional))continue;
      const anterior=+partes[4],atual=m.twin_estagio||0;if(!!anterior!==!!atual)continue;
      const fator=anterior&&atual<anterior?(1+[.2,.4,.6][atual-1])/(1+[.2,.4,.6][anterior-1]):1;
      return {...p,fator_regra_min:fator,transferencia:true};
    }
    return null;
  }
  function rendimentoAprendido(m,n,ctx){
    const p=perfilCombate(m,ctx);if(!p)return null;
    const populacao=Math.max(p.criaturas_min,Math.min(p.criaturas_max,n));
    return {central:Math.exp(p.coeficientes[0]+p.coeficientes[1]*Math.log1p(populacao))/p.escala_comum*p.fator_regra_min,
      incerteza:p.incerteza_log,origem:'rendimento_associado_parcial_ml',perfil:p};
  }
  function potenciaAprendida(m,n,ctx,conservadora=false){
    const r=rendimentoAprendido(m,n,ctx);
    // É um índice de rendimento, nunca uma contagem comprovada de criaturas.
    return r?m.ajustado*r.central*(conservadora?Math.exp(-r.incerteza):1):null;
  }
  function comAprendizado(janelas,magias,ctx,conservadora=false){
    return janelas.map(j=>j.origem_alvos==='observado'?j:({...j,potencia_ml:Object.fromEntries(magias.map(m=>[m.id,potenciaAprendida(m,j.criaturas,ctx,conservadora)]).filter(([,v])=>v!=null))}));
  }
  function chaveRTC(rtc){
    return (rtc?.slots||[]).slice().sort((a,b)=>a.tipo.localeCompare(b.tipo)||a.slot-b.slot)
      .map(s=>['tipo','slot','icone_hash','mana_percent','creatures','prioridade'].map(k=>s[k]==null?'None':String(s[k])).join(':')).join('|');
  }
  function calibracaoRTC(ctx){
    const c=ctx.modelo?.rtc_calibracao,e=c?.escopo;
    if(e){
      const cat=typeof RTC_RODA==='undefined'?null:RTC_RODA;
      const atual=cat?efeitosRTCObservados(cat,ctx):ctx.roda_efeitos;
      if(atual&&Object.values(atual).some(g=>Object.keys(g).length)&&JSON.stringify(e.roda_efeitos)!==JSON.stringify(atual))return null;
    }
    return e&&e.char===ctx.char&&e.sessao===ctx.sessao&&e.preset===ctx.preset
      &&e.rtc_chave===chaveRTC(ctx.observado?.rtc)?c:null;
  }
  function efeitosRTCObservados(cat,ctx){
    const campos=ctx.observado?.roda?.campos||{},saida={ranks:{},revelation:{}};
    for(const [grupo,chave] of [['conviction','ranks'],['revelation','revelation']])for(const [id,perk] of Object.entries(cat[grupo]||{})){
      if(!perk.Name)continue;
      const nomes=perk.Name.split('|'),campo=nomes.map(n=>campos[grupo+'.'+n]).find(c=>c?.qualidade==='texto_integral');
      if(!campo)continue;
      const texto=String(campo.valor).trim(),n=texto==='Locked'?0:grupo==='revelation'?Number(/^Stage ([1-3])$/.exec(texto)?.[1]):({I:1,II:2})[texto];
      if(Number.isInteger(n))saida[chave][id]=n;
    }
    return saida;
  }
  function contexto(dados,observado,voc){
    // O histórico descreve a hunt; a recomendação é para voltar lá com a roda
    // atual. Essa referência não é uma leitura retroativa nem leva consigo
    // janelas de cura, cooldowns calibrados ou confirmações de outra sessão.
    const atual=observado.referencia_atual;
    const usarAtual=!!dados.estado?.historico&&!!atual?.char&&atual.char===observado.char
      &&atual.char===(dados.sessao?.char||dados.estado?.char)
      &&vocacaoObservada(atual)===voc&&!!atual.roda;
    const roda=usarAtual?atual.roda:observado.roda;
    const pontos=usarAtual?atual.pontos:observado.pontos;
    const rtc=usarAtual?atual.rtc:observado.rtc;
    const mesmoPersonagem=!!dados.estado?.historico&&!!atual?.char&&atual.char===observado.char&&atual.char===(dados.sessao?.char||dados.estado?.char);
    const curaReferencia=mesmoPersonagem&&atual.cura?{...atual.cura,slots:(atual.cura.slots||[]).map(s=>{
      const anterior=observado.cura?.slots?.find(a=>a.id===s.id&&a.tipo===s.tipo&&a.destino_indice===s.destino_indice&&a.vocacao_destino===s.vocacao_destino);
      // Regra desabilitada pode esconder o percentual. O último percentual
      // legível da hunt continua referência, sem reativar a regra no cliente.
      return s.vida_percent==null&&anterior?.vida_percent!=null?{...s,vida_percent:anterior.vida_percent,percentual_referencia_id:observado.cura.id}:s;
    })}:observado.cura;
    const modelo={...(usarAtual?{...observado.modelo,combate_ml:atual.modelo?.combate_ml}:observado.modelo),
      ...(mesmoPersonagem?{feedback_cura:atual.modelo?.feedback_cura||observado.modelo?.feedback_cura,
        feedback_roda:atual.modelo?.feedback_roda||observado.modelo?.feedback_roda}:{})};
    const amostras=dados.amostras||[],intervalos=(dados.voltas||[]).map(v=>[v.t0??v.ini??v.inicio,v.t1??v.fim]).filter(x=>x.every(Number.isFinite));
    const hist={},janelas=[];let segundos=0;
    for(let i=0;i+1<amostras.length;i++){
      const a=amostras[i],b=amostras[i+1],t=a.t??a[0],fim=b.t??b[0],n=a.battle??a[4];
      if(!Number.isInteger(n)||n<1||fim-t<=0||fim-t>6)continue;
      if(!intervalos.some(([ini,ate])=>t>=ini&&fim<=ate))continue;
      const dt=fim-t;hist[n]=(hist[n]||0)+dt;segundos+=dt;janelas.push({t,fim,criaturas:n,posicao:{z:a.z??a[1],x:a.x??a[2],y:a.y??a[3]}});
    }
    const fim=janelas.at(-1)?.fim??0,desde=Math.max(0,fim-180);
    const temporal=janelas.filter(j=>j.fim>desde).map(j=>({...j,t:Math.max(j.t,desde)-desde,fim:j.fim-desde}));
    return {char:dados.sessao?.char||dados.estado?.char||observado.char||'',vocacao:voc,regras_versao:typeof RTC_RODA==='undefined'?null:RTC_RODA?.versao,
      hunt:dados.sessao?.hunt||dados.estado?.hunt||'',pt:dados.sessao?.pt??null,objetivo:dados.sessao?.objetivo??null,postura:observado.contexto?.cura?.postura??null,sessao:dados.estado?.sessao||dados.sessao?.origem||'',
      hazard:dados.estado?.hazard_confirmado?.hazard??observado.hazard_confirmado?.hazard??observado.hazard_observado?.nivel??null,hazard_leitura:dados.estado?.hazard_confirmado??observado.hazard_confirmado??observado.hazard_observado??null,
      preset:rtc?.preset??null,total:pontos?.valor??roda?.campos?.['pontos.total']?.valor??null,
      referencia_roda:usarAtual?'atual_para_proxima_hunt':'sessao',
      nivel:observado.contexto?.nivel??null,pronta:observado.contexto?.pronta,criaturas_histograma:hist,segundos_criaturas:segundos,estudos_rtc:dados.estado?.estudos_rtc||[],sugestoes_cura:dados.estado?.sugestoes_cura||[],
      estudo_sio:observado.estudo_sio||null,estudo_cura:observado.estudo_cura||null,configuracoes_informadas:observado.configuracoes_informadas||[],
      twin:observado.twin||null,
      elegibilidade_aprendizado:observado.elegibilidade_aprendizado||{cura:false},declaracao_uso_id:observado.declaracao_uso?.id,cobertura:observado.contexto?.cobertura??null,
      cura:observado.referencias_sio?.party?.length?{...observado.contexto?.cura,aliados:observado.referencias_sio.party}:observado.contexto?.cura||{},janelas:temporal,
      modelo:modelo||{},validacao_execucao:modelo?.validacao_execucao,perfis_efetividade:observado.perfis_efetividade||[],atributos:observado.contexto?.atributos||{},helper:rtc?.campos||{},
      observado:Object.fromEntries(['rtc','cura','roda'].map(k=>{const fonte=k==='roda'?roda:k==='rtc'?rtc:curaReferencia;return [k,{slots:fonte?.slots||[],campos:fonte?.campos||{},preset:fonte?.preset,completo:fonte?.completo??false,id:fonte?.id,instante:fonte?.instante}];}))};
  }
  function cenarios(ctx,magias){
    const hist=Object.entries(ctx.criaturas_histograma||{}).sort((a,b)=>+a[0]-+b[0]);
    if(!hist.length&&!ctx.janelas?.length)return [{t:0,fim:180,criaturas:1,origem:'referencia_inicial',alvos:Object.fromEntries(magias.map(m=>[m.id,1]))}];
    const total=hist.reduce((n,[,s])=>n+s,0),lista=[];
    let t=0;for(const [n,s] of hist){const fim=t+s/total*180;
      const alvos=Object.fromEntries(magias.map(m=>[m.id,Math.min(+n,m.alvos??+n)]));
      lista.push({t,fim,criaturas:+n,alvos});t=fim;
    }
    // Ordem temporal real quando fornecida tem precedência sobre distribuição agregada.
    // Uma mediana agregada de golpes não descreve a cobertura de cada box.
    // Só alvos associados à própria janela substituem a referência por população.
    return ctx.janelas?.length?ctx.janelas.map(j=>({...j,origem_alvos:j.origem_alvos==='observado'&&magias.every(m=>Number.isFinite(j.alvos?.[m.id]))?'observado':'referencia',alvos:Object.fromEntries(magias.map(m=>[m.id,j.alvos?.[m.id]??Math.min(j.criaturas,m.alvos??j.criaturas)]))})):lista;
  }
  function configurarAtaque(magias,fixar=false){
    const single=magias.find(m=>m.runa&&HuntRTC.categoria(m)==='Single');
    return magias.map((m,i)=>{
      // Listas distintas de campos, mas um turno de ataque compartilhado.
      // Runa 2º pronta disputa com magia 3º; não inventar uma fila 6º/7º.
      const prioridade=fixar?m.prioridade:m.runa?(m===single?1:2):1;
      return {...m,prioridade,prioridade_execucao:prioridade*100+(m.runa?50:0)+i,
        somente_alvo_isolado:m.runa&&m.alvos===1,
        creatures:fixar?m.creatures:Math.min(10,m.creatures_recomendado??(m.runa||m.alvos===1?1:HuntRTC.categoria(m)==='UE'?8:2)),
        ...(!m.runa?{mana_percent:fixar?m.mana_percent:5}:{})};
    });
  }
  function equalizarCriaturas(ordem,ctx){
    let linhas=configurarAtaque(ordem);
    // Espera exige a sequência das levas. Um histograma ordenado por tamanho
    // não permite concluir quanto tempo levaria para reunir mais criaturas.
    const janelas=cenarios(ctx,linhas),segundos=janelas.reduce((s,j)=>s+j.fim-j.t,0);
    if(!ctx.janelas?.length||segundos<90)return {linhas,estado:'referencia_inicial',comparadas:0};
    const inicio=janelas[0].t,fim=janelas.at(-1).fim,corte=inicio+(fim-inicio)/2,reserva=inicio+(fim-inicio)*3/4;
    const treino=janelas.filter(j=>j.t<corte).map(j=>({...j,fim:Math.min(j.fim,corte)})),selecao=janelas.filter(j=>j.fim>corte&&j.t<reserva).map(j=>({...j,t:Math.max(j.t,corte)-corte,fim:Math.min(j.fim,reserva)-corte}));
    const trechos=[treino,treino,selecao];
    if(trechos.slice(1).some(js=>js.reduce((s,j)=>s+j.fim-j.t,0)<25))return {linhas,estado:'referencia_inicial',comparadas:0};
    let comparadas=0;
    const avaliar=lista=>trechos.map(js=>{
      const contexto={janelas:comAprendizado(js,lista,ctx),pronta:ctx.pronta||Object.fromEntries(lista.map(m=>[m.id,m.cd])),modelo:ctx.modelo,nivel:ctx.nivel,...ctx.atributos};
      const alta=HuntTemporal.simular(lista,contexto,{duracao:180});comparadas++;
      const completa=js.every(j=>j.origem_alvos==='observado');
      const baixa=completa?alta:HuntTemporal.simular(lista,{...contexto,janelas:comAprendizado(js.map(j=>({...j,alvos:Object.fromEntries(lista.map(m=>[m.id,Math.min(ctx.cobertura?.[m.id]??1,j.alvos[m.id])]))})),lista,ctx,true)},{duracao:180});
      // Equilibrar ativações e potência por alvo, preservando a incerteza da
      // cobertura. O cooldown real entra no replay, não numa regra '+2'.
      return {alta,baixa,utilidade:Math.sqrt(Math.max(0,baixa.score*alta.score))};
    });
    const inicial=avaliar(linhas);let melhor=inicial;
    const max=Math.max(...janelas.map(j=>j.criaturas));
    for(let rodada=0;rodada<2;rodada++)for(let i=0;i<linhas.length;i++){
      const m=linhas[i];if(m.alvos===1)continue;
      const min=HuntRTC.categoria(m)==='UE'?8:m.runa?1:2,limite=Math.min(10,max,m.alvos??max);
      let escolha=linhas,resultado=melhor;
      for(let n=min;n<=limite;n++){
        if(n===m.creatures)continue;
        const tentativa=linhas.map((s,k)=>k===i?{...s,creatures:n}:s),r=avaliar(tentativa);
        if(!(r[0].alta.casts[m.id]>0))continue;
        // Ganho no treino precisa sobreviver ao trecho posterior. Não elevar
        // um limiar para silenciar a magia ou vencer por ruído de um turno.
        if(r[0].utilidade>resultado[0].utilidade*1.005&&r[1].utilidade>melhor[1].utilidade*1.005&&r[2].utilidade>=melhor[2].utilidade*.995){escolha=tentativa;resultado=r;}
      }
      linhas=escolha;melhor=resultado;
    }
    const teste=janelas.filter(j=>j.fim>reserva).map(j=>({...j,t:Math.max(j.t,reserva)-reserva,fim:j.fim-reserva}));
    const scoreTeste=lista=>HuntTemporal.simular(lista,{janelas:teste,pronta:ctx.pronta,modelo:ctx.modelo,...ctx.atributos},{duracao:fim-reserva}).score;
    const aceitaTeste=scoreTeste(linhas)>=scoreTeste(configurarAtaque(ordem));
    if(!aceitaTeste){linhas=configurarAtaque(ordem);melhor=inicial;}
    return {linhas:linhas.map(m=>({...m,creatures_recomendado:m.creatures})),estado:'replay_validado',comparadas,
      origem_alvos:janelas.every(j=>j.origem_alvos==='observado')?'observado':'referencia_parcial',
      potencia_antes:inicial[0].alta.score,potencia_depois:melhor[0].alta.score,
      equilibrio_antes:inicial[0].utilidade,equilibrio_depois:melhor[0].utilidade,
      magias:linhas.map(m=>({id:m.id,creatures:m.creatures,cd:m.cd,ativacoes_antes:inicial[0].alta.casts[m.id]||0,ativacoes_depois:melhor[0].alta.casts[m.id]||0})),
      validacao:'trecho_final_separado',particao:'treino_selecao_teste_separados',teste_aceito:aceitaTeste};
  }
  function ataque(magias,ctx,opcoes={}){
    const janelas=cenarios(ctx,magias);
    if(!janelas.length)return {estado:'Aguardando hunt',linhas:[],motivo:'Ainda não há criaturas observadas no período.'};
    const ns=janelas.map(j=>j.criaturas),med=ns.slice().sort((a,b)=>a-b)[Math.floor(ns.length/2)];
    // Uma configuração completa conserva os papéis de combate. A busca anterior
    // preferia um prefixo de duas waves e apagava UE/fork/runa como se não existissem.
    const base=opcoes.fixar?{ordem:magias,comparadas:1}:comporAtaque(magias,med,ctx);
    if(base.erro)return {estado:'A calibrar',linhas:[],motivo:base.erro};
    const equalizacao=opcoes.fixar?null:equalizarCriaturas(base.ordem,ctx);
    const ordem=equalizacao?.linhas??configurarAtaque(base.ordem,opcoes.fixar);
    const avaliar=lista=>{
      const pronta=ctx.pronta||Object.fromEntries(lista.map(m=>[m.id,m.cd]));
      const alta=HuntTemporal.simular(lista,{janelas:comAprendizado(janelas,lista,ctx),pronta,modelo:ctx.modelo,nivel:ctx.nivel,...ctx.atributos},{duracao:180});
      if(janelas.every(j=>j.origem_alvos==='observado'&&lista.every(m=>Number.isFinite(j.alvos?.[m.id]))))return {...alta,robusto:alta.score};
      const baixa=HuntTemporal.simular(lista,{pronta,modelo:ctx.modelo,nivel:ctx.nivel,...ctx.atributos,janelas:comAprendizado(janelas.map(j=>({...j,alvos:Object.fromEntries(lista.map(m=>[m.id,Math.min(ctx.cobertura?.[m.id]??1,j.alvos[m.id])]))})),lista,ctx,true)},{duracao:180});
      // Cobertura incompleta continua sendo um intervalo, não uma calibração completa.
      return {...alta,robusto:baixa.score,faixa:[baixa.score,alta.score]};
    };
    const r=avaliar(ordem);
    const slots={magia:0,runa:0};
    const ordemConhecida=opcoes.fixar||calibracaoRTC(ctx)?.prioridade_entre_tipos==='prioridade_global_magia_desempata';
    return {...r,estado:'Recomendado',origem_ordem:'prioridade_compartilhada_com_fallback',linhas:ordem.map(m=>{const tipo=m.runa?'runa':'magia';return {...m,tipo,slot:++slots[tipo],frequencia:!ordemConhecida||janelas.every(j=>j.origem==='referencia_inicial')?null:r.frequencia[m.id],origem_frequencia:'previsão',mana_percent:m.runa?null:5};}),
      faixa:r.faixa??[r.score,r.score],comparadas:base.comparadas,equalizacao};
  }
  function comporAtaque(magias,alvos,ctx){
    const validas=magias.filter(m=>m.ajustado>0&&(!Number.isFinite(ctx.nivel)||!m.nivel||ctx.nivel>=m.nivel));
    const fork=m=>m.id?.startsWith('forked_'),area=m=>!m.runa&&!fork(m)&&HuntRTC.categoria(m)==='Área';
    const valor=m=>m.ajustado*Math.min(alvos,m.alvos??alvos)/Math.max(m.cd,m.grupo);
    const ordenar=lista=>lista.slice().sort((a,b)=>valor(b)-valor(a)||a.id.localeCompare(b.id));
    const ue=ordenar(validas.filter(m=>HuntRTC.categoria(m)==='UE'))[0],
      especial=ordenar(validas.filter(m=>['bursts','beams'].includes(m.familia)||HuntRTC.categoria(m)==='Beam'))[0],
      onda=ordenar(validas.filter(area))[0],garfo=ordenar(validas.filter(fork))[0],
      runa=ordenar(validas.filter(m=>m.runa&&HuntRTC.categoria(m)==='Runa'))[0];
    const essenciais=[ue,especial,garfo,onda].filter(Boolean),extras=ordenar(validas.filter(m=>!m.runa&&!essenciais.some(e=>e.id===m.id)&&(fork(m)||area(m))));
    const adicionais=[[]];const vagas=5-essenciais.length;
    if(!extras.length||!vagas){}
    else if(vagas===1)for(const m of extras)adicionais.push([m]);
    else for(let i=0;i<extras.length;i++){
      if(extras.length===1)adicionais.push([extras[i]]);
      for(let j=i+1;j<extras.length;j++)adicionais.push([extras[i],extras[j]]);
    }
    let melhor=null,comparadas=0;
    for(const extra of adicionais){
      const ordem=[...essenciais,...extra].slice(0,5);
      if(runa)ordem.push(runa);
      // Single é um único recurso de alvo isolado, sem retirar a runa de área.
      if(!ordem.some(m=>HuntRTC.categoria(m)==='Single')){
        const single=ordenar(validas.filter(m=>m.runa&&HuntRTC.categoria(m)==='Single'))[0];
        if(single)ordem.push(single);
      }
      // Comparar também quem pega os turnos livres. A composição completa
      // não basta quando a primeira fork impede as waves de executar.
      // UE e especial desbloqueado têm oportunidades espaçadas. Colocá-los
      // depois de duas magias de 4 s impediria sua execução indefinidamente.
      const inicio=ordem.filter(m=>HuntRTC.categoria(m)==='UE'||m===especial),resto=ordem.filter(m=>!m.runa&&!inicio.includes(m)),runas=ordem.filter(m=>m.runa);
      const variantes=[ordem,...resto.map(primeira=>[...inicio,primeira,...resto.filter(m=>m!==primeira),...runas])];
      const vistas=new Set();
      for(const candidata of variantes){
        const chave=candidata.map(m=>m.id).join('|');if(vistas.has(chave))continue;vistas.add(chave);
        const configuradas=configurarAtaque(candidata),janelas=cenarios(ctx,configuradas),contexto={janelas:comAprendizado(janelas,configuradas,ctx),pronta:ctx.pronta||Object.fromEntries(configuradas.map(m=>[m.id,m.cd])),modelo:ctx.modelo,nivel:ctx.nivel,...ctx.atributos};
        const r=HuntTemporal.simular(configuradas,contexto,{duracao:180});comparadas++;
        // Cobertura parcial é uma faixa. Não eleger ordem que só vence
        // presumindo que toda criatura da Battle List tomou a magia.
        const completo=janelas.every(j=>j.origem_alvos==='observado');
        const conservador=completo?r.score:HuntTemporal.simular(configuradas,{...contexto,janelas:comAprendizado(janelas.map(j=>({...j,alvos:Object.fromEntries(configuradas.map(m=>[m.id,Math.min(1,j.alvos[m.id])]))})),configuradas,ctx,true)},{duracao:180}).score;
        if(!melhor||conservador>melhor.conservador+1e-8||Math.abs(conservador-melhor.conservador)<1e-8&&(r.score>melhor.score+1e-8||Math.abs(r.score-melhor.score)<1e-8&&candidata.length<melhor.ordem.length))melhor={...r,conservador,ordem:candidata};
      }
    }
    return melhor?{...melhor,comparadas}:{erro:'Sem magias elegíveis no catálogo.'};
  }
  // Ponto de partida recomendado, não leitura nem desempenho medido. A observação
  // interna pode substituir os limiares depois; nunca bloqueia a configuração inicial.
  function percentualInicial(m,estrategia){
    const contingencia=estrategia==='utamo'||estrategia.includes('critica');
    if(m.vocacao_destino){
      if(m.id==='nature_s_embrace')return m.vocacao_destino==='EK'?45:40;
      if(m.vocacao_destino==='EK')return estrategia==='vida_link99'?99:estrategia.includes('link')?90:80;
      return estrategia.includes('link')?85:75;
    }
    if(m.id==='mass_healing')return contingencia?59:estrategia==='mas_res'?100:95;
    if(m.id==='restoration')return contingencia?30:60;
    if(m.id==='ultimate_healing')return contingencia?45:80;
    return contingencia?55:90;
  }
  function feedbackCura(ctx){
    // Intervenção do usuário é evidência de risco, não validação causal de ganho.
    // Fora da sessão original, somente contexto completo e igual pode reutilizá-la.
    const hunt=n=>String(n||'').split(' · ')[0];
    return (ctx.modelo?.feedback_cura||[]).filter(f=>{
      const c=f.contexto||{};
      if(f.origem!=='usuario'||f.tipo!=='disputa_turno_cura'||f.vigente!==true||!f.id||!f.provas?.length||f.qa||f.sintetico)return false;
      if(!c.char||c.char!==ctx.char||!c.hunt||hunt(c.hunt)!==hunt(ctx.hunt)||!tamanhoParty(c.pt)||tamanhoParty(c.pt)!==tamanhoParty(ctx.pt))return false;
      if(!Array.isArray(f.ajustes)||!f.ajustes.length||f.ajustes.length>2||new Set(f.ajustes.map(a=>a.id)).size!==f.ajustes.length)return false;
      if(f.ajustes.some(a=>!['mass_healing','ultimate_healing','restoration'].includes(a.id)||a.alvo!=='eu'||!Number.isInteger(a.anterior)||!Number.isInteger(a.vida_percent)||a.vida_percent<1||a.vida_percent>=a.anterior||a.anterior>100))return false;
      return !!f.sessao&&f.sessao===ctx.sessao||Number.isInteger(c.hazard)&&c.hazard===ctx.hazard&&!!c.postura&&c.postura===ctx.postura;
    }).sort((a,b)=>(a.registrado_em||0)-(b.registrado_em||0)).at(-1)||null;
  }
  function curaInicial(linhas,estrategia,feedback=null){
    const recomendadas=linhas.map(m=>({...m,vida_percent:m.vida_percent!=null&&m.origem_percentual!=='recomendado'?m.vida_percent:percentualInicial(m,estrategia),
      origem_percentual:m.vida_percent!=null&&m.origem_percentual!=='recomendado'?'observado':'recomendado',frequencia:null}));
    if(feedback&&estrategia!=='atual')for(const m of recomendadas){
      const ajuste=feedback.ajustes.find(a=>a.id===m.id&&!m.vocacao_destino&&m.alvo==='eu');
      if(!ajuste)continue;
      // Não elevar um gatilho já menor (por exemplo em Utamo). A referência
      // emergencial limita a busca; não é ensinada como percentual ótimo.
      m.limiar_maximo_feedback=ajuste.vida_percent;
      if(m.vida_percent>ajuste.vida_percent){m.vida_percent=ajuste.vida_percent;m.origem_percentual='feedback_usuario';m.vida_percent_anterior=ajuste.anterior;}
      m.feedback_id=feedback.id;
    }
    // Referência comparativa em BP; jamais HP fabricado. Cada oportunidade consome
    // o relógio individual e o grupo comum, inclusive gran sio entre EK e RP.
    const prontas={},grupos={};let t=0,cursor=0,indice_base=0;
    const pool=recomendadas.filter(m=>m.ativo!==false);
    while(pool.length&&t<180){
      let escolhida=null;
      for(let n=0;n<pool.length;n++){const i=(cursor+n)%pool.length,m=pool[i];if((prontas[m.id]||0)<=t&&(grupos[m.grupo_id||'cura']||0)<=t){escolhida=m;cursor=(i+1)%pool.length;break;}}
      if(!escolhida){t=Math.max(t+.001,Math.min(...pool.map(m=>Math.max(prontas[m.id]||0,grupos[m.grupo_id||'cura']||0))));continue;}
      const m=escolhida;indice_base+=m.bp*(m.link&&m.vocacao_destino?1+m.link:1);prontas[m.id]=t+m.cd;grupos[m.grupo_id||'cura']=t+m.grupo;t+=m.grupo;
    }
    return {estado:'Recomendado',linhas:recomendadas,indice_base,unidade_indice:'Base Power em oportunidades compartilhadas',metricas:null,origem:'politica_inicial',
      ...(feedback?{feedback:{id:feedback.id,origem:'usuario',estado:'restricao_por_risco_relatado',beneficio_real_validado:false}}:{})};
  }
  function curar(cat,pontos,gemas,magias,ctx,estrategia,opcoes={}){
    const feedback=opcoes.aprender?feedbackCura(ctx):null;
    const e=HuntRodaMotor.efeitos(cat,pontos,gemas,opcoes.efeitos_observados),modificadas=HuntRodaMotor.modificar(cat,pontos,magias,gemas,{alvos:1,temporal:true,efeitos_observados:opcoes.efeitos_observados}),observado=ctx.observado?.cura?.slots||[];
    const selfpool=modificadas.filter(m=>m.tipo==='cura'&&['propria','party_e_propria'].includes(m.destino)&&(!Number.isFinite(ctx.nivel)||!m.nivel||ctx.nivel>=m.nivel));
    const preferidas=cat.vocacao==='ED'?['mass_healing','ultimate_healing','restoration','intense_healing']:['ultimate_healing','restoration','intense_healing'];
    const self=selfpool.sort((a,b)=>preferidas.indexOf(a.id)-preferidas.indexOf(b.id)).slice(0,3);
    const selecionadas=estrategia==='atual'?selfpool.filter(m=>observado.some(s=>s.tipo==='autocura'&&s.id===m.id)):self;
    const linhas=selecionadas.map(m=>({...m,alvo:'eu',vida_percent:observado.find(s=>s.tipo==='autocura'&&s.id===m.id)?.vida_percent??null,
      cura_hp:ctx.cura?.potencia_hp?.[m.id]!=null?ctx.cura.potencia_hp[m.id]*m.multiplicador_base/(ctx.cura?.base_multiplicadores?.[m.id]??1):null,link:e.ranks[28]?.25:0,blessing:[0,.05,.075,.10][e.revelation[11]||0],critico_habilitado:(e.revelation[11]||0)>0}));
    if(cat.vocacao==='ED')for(const voc of ['EK','RP'])for(const id of ['heal_friend','nature_s_embrace']){
      const m=modificadas.find(m=>m.id===id);if(!m||Number.isFinite(ctx.nivel)&&m.nivel>ctx.nivel)continue;
      const aliado=(ctx.cura?.aliados||[]).find(a=>a.vocacao===voc),obs=observado.find(s=>s.id===id&&s.vocacao_destino===voc);
      linhas.push({...m,alvo:aliado?.nome||voc,vocacao_destino:voc,ativo:aliado?obs?.ativo!==false:false,vida_percent:estrategia==='vida_link99'&&id==='heal_friend'&&voc==='EK'?99:obs?.vida_percent??null,
        limiar_fixo:estrategia==='vida_link99'&&id==='heal_friend'&&voc==='EK',
        cura_hp:ctx.cura?.potencia_hp?.[m.id]!=null?ctx.cura.potencia_hp[m.id]*m.multiplicador_base/(ctx.cura?.base_multiplicadores?.[m.id]??1):null,link:e.ranks[28]?.25:0,blessing:[0,.05,.075,.10][e.revelation[11]||0],critico_habilitado:(e.revelation[11]||0)>0});
    }
    for(const m of linhas)if(m.vida_percent==null){m.vida_percent=percentualInicial(m,estrategia);m.origem_percentual='recomendado';}
    if(opcoes.aprender&&ctx.elegibilidade_aprendizado?.cura===false)return curaInicial(linhas,estrategia,feedback);
    if(opcoes.aprender){
      // A política inicial continua pronta. O aprendizado usa a roda observada,
      // nunca os controles de uma distribuição futura, e conserva EK/RP separados.
      const inicial=curaInicial(linhas,estrategia,feedback),ativas=inicial.linhas.filter(m=>m.ativo!==false);
      for(const m of ativas)if(ctx.cura?.qualidade?.[m.id]?.unidade==='HP_sem_bonus_de_roda')m.cura_fixa_hp=e.fixo_hp;
      const r=HuntTemporal.aprenderCura(ativas,{...ctx.cura,...ctx.atributos,modelo:ctx.modelo,nivel:ctx.nivel},opcoes);
      return {...inicial,...r,linhas:inicial.linhas.map(m=>r.linhas.find(l=>l.id===m.id&&l.alvo===m.alvo)||m)};
    }
    if(ctx.cura?.janelas?.length&&linhas.filter(m=>m.ativo!==false).every(m=>m.cura_hp!=null)){
      const ativas=linhas.filter(m=>m.ativo!==false);
      const atualPontos=Object.fromEntries(Object.entries(ctx.observado?.roda?.campos||{}).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
      const dominiosAtuais=Object.entries(HuntRodaMotor.resumo(cat,atualPontos).vr).filter(([,n])=>n>0).map(([q])=>q),campos=ctx.observado?.roda?.campos||{};
      const gemasConhecidas=dominiosAtuais.every(q=>['vazio_confirmado','observado_completo'].includes(campos['gemas.'+q]?.valor?.estado));
      const gemasObservadas=dominiosAtuais.map(q=>campos['gemas.'+q]?.valor).filter(g=>g?.equipada).map(g=>({...g,...g.modificadores?.[0]}));
      const efeitoAtual=ctx.observado?.roda?.completo&&gemasConhecidas?HuntRodaMotor.efeitos(cat,atualPontos,gemasObservadas):null;
      const janelas=ctx.cura.janelas.map(j=>({...j,vida:Object.fromEntries(Object.entries(j.vida||{}).map(([alvo,v])=>{
        if(alvo!=='eu'||!efeitoAtual)return [alvo,v];const delta=e.recursos.vida-efeitoAtual.recursos.vida;return [alvo,{...v,maxima:Math.max(1,v.maxima+delta),atual:Math.max(0,v.atual+delta)}];
      }))}));
      for(const j of janelas)if(efeitoAtual&&Number.isFinite(j.mana_maxima)){
        const delta=e.recursos.mana-efeitoAtual.recursos.mana;j.mana_maxima=Math.max(1,j.mana_maxima+delta);if(Number.isFinite(j.mana))j.mana=Math.max(0,j.mana+delta);
      }
      const contextoCura={...ctx.cura,...ctx.atributos,modelo:ctx.modelo,nivel:ctx.nivel,janelas};
      // Resistência só transforma dano quando o elemento e a defesa original
      // estão conhecidos. O restante permanece dado observado, sem ganho presumido.
      if(efeitoAtual)for(const j of janelas)for(const [alvo,tipos] of Object.entries(j.dano_elementos||{})){
        if(alvo!=='eu'||!ctx.cura.resistencias_base)continue;
        j.dano={...j.dano,[alvo]:Object.entries(tipos).reduce((n,[tipo,hp])=>{
          const base=ctx.cura.resistencias_base[tipo];if(!Number.isFinite(base))return n+hp;
          const antiga=Math.min(.95,base+(efeitoAtual.resistencias[tipo]||0)),nova=Math.min(.95,base+(e.resistencias[tipo]||0));return n+hp*(1-nova)/(1-antiga);
        },0)};
      }
      if(efeitoAtual)for(const m of ativas){m.cura_fixa_hp=ctx.cura.qualidade?.[m.id]?.unidade==='HP_sem_bonus_de_roda'?e.fixo_hp:e.fixo_hp-efeitoAtual.fixo_hp;
        if(ctx.cura.coeficiente_ml?.[m.id]!=null)m.cura_hp+=ctx.cura.coeficiente_ml[m.id]*(e.magic_level-efeitoAtual.magic_level);}
      let r=HuntTemporal.limiares(ativas,contextoCura,{...opcoes,fixar_limiares:opcoes.fixar_limiares||estrategia==='atual'});
      // As três casas do helper são um limite, não três magias fixadas pelo histórico.
      if(!opcoes.fixar_limiares&&estrategia!=='atual')for(const m of selfpool.filter(m=>ctx.cura.potencia_hp[m.id]!=null&&!self.some(s=>s.id===m.id))){
        for(const atual of r.linhas.filter(l=>l.alvo==='eu')){
          const teste=r.linhas.map(l=>l===atual?{...m,alvo:'eu',vida_percent:atual.vida_percent,cura_hp:ctx.cura.potencia_hp[m.id]*m.multiplicador_base/(ctx.cura.base_multiplicadores?.[m.id]??1),blessing:[0,.05,.075,.10][e.revelation[11]||0],critico_habilitado:(e.revelation[11]||0)>0}:l);
          const alternativa=HuntTemporal.limiares(teste,contextoCura,{...opcoes,rodadas:1});if(HuntTemporal.comparar(alternativa.seguranca,r.seguranca)>0)r=alternativa;
        }
      }
      return {...r,janelas_modelo:janelas,linhas:[...r.linhas,...linhas.filter(m=>m.ativo===false).map(m=>({...m,frequencia:null}))],postura:estrategia.startsWith('utamo')?'utamo':estrategia==='vida_contingencia'?'vida com utamo de contingência':'vida',
        contingencia_executavel:estrategia!=='vida_contingencia'||ctx.observado?.cura?.campos?.['cura.utamo_automatico']?.valor===true};
    }
    return curaInicial(linhas,estrategia);
  }
  function gemas(cat,pontos,tier,magias,objetivo,ctx={}){
    if(tier===0)return [[]];const s=HuntRodaMotor.resumo(cat,pontos),qs=Object.keys(s.vr).filter(q=>s.vr[q]>=tier),lista=[];
    const pesoBasico=mod=>{const efeitos=cat.basicos_normalizados?.[mod]?.graus?.[cat.vocacao]?.[1]||[];return efeitos.reduce((s,e)=>s+(e.tipo==='Hit Points'?e.valor/100:e.tipo==='Mana'?e.valor/600:e.tipo==='Mitigation Multiplier'?e.valor:e.tipo.endsWith(' Resistance')?e.valor*(ctx.cura?.danos_elementos?.[e.tipo.slice(0,-11).toLowerCase()]||0):0),0);};
    const primeiro=Object.keys(cat.basicos_normalizados||{}).sort((a,b)=>pesoBasico(b)-pesoBasico(a)).slice(0,3),segundo=Object.keys(cat.basicos_normalizados||{}).filter(k=>(cat.basicos_normalizados[k].graus[cat.vocacao][1]||[]).every(e=>e.tipo.endsWith(' Resistance')&&e.valor>=0)).sort((a,b)=>pesoBasico(b)-pesoBasico(a)).slice(0,2);
    for(const q of qs){const simples={dominio:q,tier,qualidade:cat.tiers[tier].qualidade,nome:cat.tiers[tier].qualidade,grau:null,equipada:false,
      basicos:primeiro.length?[{mod:+primeiro[0],grau:1},...(tier>=2&&segundo.length?[{mod:+segundo[0],grau:1}]:[])]:[]};
      if(tier<3){lista.push([simples]);continue;}
      const rev=cat.revelation[cat.dominios.find(d=>d.dominio===q).revelation_id]?.Name;
      const mods=HuntRodaMotor.gemasPossiveis(cat,objetivo,magias,1).filter(g=>!g.revelation_nome||g.revelation_nome===rev);
      lista.push([simples],...mods.map(g=>[{...simples,...g,grau:1}]));
    }
    for(const [q,nivel] of Object.entries(s.vr))if(nivel>0&&!qs.includes(q)){
      const qualidade=Math.min(nivel,2),adicional={dominio:q,tier:qualidade,qualidade:cat.tiers[qualidade].qualidade,nome:cat.tiers[qualidade].qualidade,grau:null,basicos:primeiro.length?[{mod:+primeiro[0],grau:1},...(qualidade===2&&segundo.length?[{mod:+segundo[0],grau:1}]:[])]:[],equipada:false};
      for(const combo of lista.slice(0,12))lista.push([...combo,adicional]);
    }
    // Misturas legais em domínios distintos; limitar comparações, sem supor ótimo global.
    const principais=lista.filter(g=>g[0].mod!=null).slice(0,8);
    for(let i=0;i<principais.length;i++)for(let j=i+1;j<principais.length;j++)if(principais[i][0].dominio!==principais[j][0].dominio)lista.push([...principais[i],...principais[j]]);
    // Alternativas básicas entram na avaliação temporal, sem converter qualidade
    // em grau. Manter graus I explícitos até existir evidência dos outros graus.
    const alternativas=[];
    for(const combo of lista.slice(0,24))for(const a of primeiro)for(const b of tier>=2?segundo:[null])alternativas.push(combo.map((g,i)=>i?g:{...g,basicos:[{mod:+a,grau:1},...(b!=null?[{mod:+b,grau:1}]:[])]}));
    return [...lista,...alternativas].filter((v,i,a)=>a.findIndex(x=>JSON.stringify(x)===JSON.stringify(v))===i).slice(0,128);
  }
  function calcular(cat,magias,ctx,objetivo='dano',estrategia='utamo_critica',tier=0,opcoes={}){
    ctx={...ctx,objetivo_roda:objetivo,regras_versao:cat.versao,roda_efeitos:efeitosRTCObservados(cat,ctx)};
    if(!estrategias.some(([id])=>id===estrategia)||![0,1,2,3].includes(tier))throw Error('Escolha inválida');
    const inicio=Date.now(),regras=cat.versao;
    const base={versao:2,regras_versao:regras,modelo_versao:versao,objetivo,estrategia,tier,
      contexto:Object.fromEntries(Object.entries(ctx).filter(([k])=>k!=='observado')),rtc:{estado:'A calibrar',linhas:[]},cura:{estado:'A calibrar',linhas:[]},roda:{estado:'Total não lido',pontos:{},gemas:[]}};
    const ofensivas=magias.filter(m=>HuntRTC.categoria(m)).map(m=>m.ajustado==null?{...m,ajustado:m.bp,resistencia:100,cobertura:0,origem_potencia:'base_global'}:m).filter(m=>Number.isFinite(m.ajustado)&&m.ajustado>0);
    const referenciaBase=referenciaRoda(cat,ctx),efeitosIniciais=referenciaBase.observados;
    const preservarReferencia=objetivo==='dano'&&feedbackRoda(cat,ctx)?.rejeitada&&!rodaRejeitada(feedbackRoda(cat,ctx),referenciaBase.efeitos);
    const efeitosMinimos=preservarReferencia?{ranks:Object.fromEntries(Object.entries(efeitosIniciais.ranks||{}).filter(([id])=>[29,31,33].includes(+id))),revelation:Object.fromEntries(Object.entries(efeitosIniciais.revelation||{}).filter(([id])=>[10,11].includes(+id)))}:null;
    const observadas=HuntRodaMotor.modificar(cat,referenciaBase.pontos||{},ofensivas,referenciaBase.gemas,{temporal:true,efeitos_observados:referenciaBase.completa&&referenciaBase.gemas_completas?{}:efeitosIniciais});
    const slotsAtuais=(ctx.observado?.rtc?.slots||[]).filter(s=>s.id&&observadas.some(m=>m.id===s.id));
    const rtcBase=opcoes.roda_independente?(slotsAtuais.length?ataque(slotsAtuais.map(s=>({...observadas.find(m=>m.id===s.id),...s})),ctx,{fixar:true}):calcularRTC(cat,magias,ctx).rtc):null;
    const referenciaRTC=rtcBase?.linhas||null;
    const maiorUso=Math.max(1,...Object.values(rtcBase?.casts||{}));
    const pesosMagias=referenciaRTC?Object.fromEntries(referenciaRTC.map(m=>[m.id,(rtcBase.casts?.[m.id]||0)/maiorUso])):null;
    const usadasIds=new Set(referenciaRTC?.map(m=>m.id)||[]);
    const convictionsUteis=cat.fatias.filter(f=>[29,31,25,24,30].includes(f.conviction_id))
      .map(f=>f.conviction_id).filter(id=>id===31&&usadasIds.has('strong_ice_wave')||id===30&&usadasIds.has('terra_wave')||id===29&&['forked_glacier','forked_thorns'].some(id=>usadasIds.has(id))||id===25&&usadasIds.has('energy_wave')||id===24&&usadasIds.has('great_fire_wave'));
    const valorRoda=objetivo==='dano'&&referenciaRTC?p=>{
      const lista=HuntRodaMotor.modificar(cat,p,ofensivas,[],{temporal:true});
      return lista.reduce((s,m)=>s+(pesosMagias[m.id]||0)*(potenciaAprendida(m,Math.max(1,...Object.keys(ctx.criaturas_histograma||{}).map(Number)),ctx,true)??m.ajustado)/Math.max(2,m.cd),0);
    }:null;
    if(!Number.isInteger(ctx.total))return {...base,estado:'Total não lido',rtc:ataque(ofensivas,ctx,opcoes),cura:curar(cat,{},[],magias,ctx,estrategia)};
    if(estrategia==='atual'&&!ctx.observado?.roda?.completo)return {...base,estado:'Distribuição atual a calibrar',cura:curar(cat,{},[],magias,ctx,estrategia)};
    if(estrategia==='atual'&&(!ctx.observado?.rtc?.completo||!ctx.observado?.cura?.completo))return {...base,estado:'Configuração atual a calibrar',cura:curar(cat,{},[],magias,ctx,estrategia)};
    let gemasAtuais=[];
    if(estrategia==='atual'){
      const pontos=Object.fromEntries(Object.entries(ctx.observado.roda.campos).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
      for(const [dom,nivel] of Object.entries(HuntRodaMotor.resumo(cat,pontos).vr))if(nivel>0){
        const g=ctx.observado.roda.campos['gemas.'+dom]?.valor;
        if(!g||!['vazio_confirmado','observado_completo'].includes(g.estado))return {...base,estado:'Gemas atuais a calibrar',cura:curar(cat,pontos,[],magias,ctx,estrategia)};
        if(g.equipada){const sup=g.modificadores?.[0];gemasAtuais.push({...g,...sup,magias:sup?magias.filter(m=>m.nome===cat.gemas_normalizadas?.[sup.mod]?.graus?.[sup.grau]?.magias_nome).map(m=>m.id):[]});}
      }
    }
    const priorizarSio=cat.vocacao==='ED'&&modalidade(ctx.pt)!=='solo'&&objetivo==='dano';
    const busca=estrategia==='atual'?{estado:'Calculado',expansoes:0,distribuicoes:[Object.fromEntries(Object.entries(ctx.observado.roda.campos).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]))]}:HuntRodaMotor.candidatas(cat,ctx.total,tier,estrategia,objetivo,{...opcoes,priorizar_sio:priorizarSio,exigir_sio_critico:opcoes.roda_independente&&cat.vocacao==='ED'&&modalidade(ctx.pt)!=='solo',pesos_magias:pesosMagias,valor_roda:valorRoda,efeitos_iniciais:efeitosIniciais,efeitos_minimos:efeitosMinimos,pontos_iniciais:referenciaBase.pontos,convictions_uteis:convictionsUteis,revelations_uteis:['ice_burst','terra_burst'].some(id=>usadasIds.has(id))?[10]:[]});let melhor=null,avaliadas=0;
    if(!busca.distribuicoes.length)return {...base,estado:busca.estado,rtc:ataque(ofensivas,ctx,opcoes),roda:{...base.roda,estado:busca.estado},cura:curar(cat,{},[],magias,ctx,estrategia)};
    const finalistas=[];
    const comparar=(a,b)=>{
      const ac=a.cura.estado==='Previsto',bc=b.cura.estado==='Previsto';
      // Segurança individual tem precedência em ambos os focos quando medível.
      if(ac&&bc){const seguro=HuntTemporal.comparar(a.cura.seguranca,b.cura.seguranca);if(seguro)return seguro;}
      if(objetivo==='cura'){
        if(ac!==bc)return ac?1:-1;
        if(ac){const c=HuntTemporal.comparar(a.cura.seguranca,b.cura.seguranca);if(c)return c;}
        else return (a.cura.indice_base??0)-(b.cura.indice_base??0)||b.roda.investidos-a.roda.investidos; // Base de cura, nunca dano como substituto.
      }
      const conservar=x=>convictionsUteis.reduce((s,id)=>s+Math.min(x.roda.efeitos.ranks[id]||0,efeitosIniciais.ranks[id]||0),0)+Math.min(x.roda.efeitos.revelation[10]||0,efeitosIniciais.revelation[10]||0);
      return compararDano(a,b,priorizarSio)
        ||a.roda.efeitos.fixo_hp-b.roda.efeitos.fixo_hp
        ||(objetivo==='dano'?conservar(a)-conservar(b):0)||b.roda.investidos-a.roda.investidos;
    };
    const gemasDaBusca=p=>{
      const alternativas=gemas(cat,p,tier,magias,objetivo,ctx);
      if(referenciaBase.gemas_completas&&tier>0&&referenciaBase.gemas.every(g=>(g.tier??3)<=tier))alternativas.unshift(referenciaBase.gemas);
      return alternativas;
    };
    buscaCompleta:for(const p of busca.distribuicoes)for(const gs of estrategia==='atual'?[gemasAtuais]:gemasDaBusca(p)){
      const efeitos=HuntRodaMotor.efeitos(cat,p,gs);
      if(rodaRejeitada(feedbackRoda(cat,ctx),efeitos))continue;
      if(opcoes.roda_independente&&cat.vocacao==='ED'&&modalidade(ctx.pt)!=='solo'&&((efeitos.ranks[33]||0)<2||!efeitos.revelation[11]))continue;
      if(estrategia.includes('link')&&!efeitos.ranks[28]||estrategia.includes('critica')&&!(efeitos.revelation[11]>0))continue;
      const lista=HuntRodaMotor.modificar(cat,p,ofensivas,gs,{alvos:Math.max(1,...Object.keys(ctx.criaturas_histograma||{}).map(Number)),temporal:true});
      if(referenciaRTC?.some(s=>s.requer_roda&&!lista.some(m=>m.id===s.id)))continue;
      const usadas=referenciaRTC?referenciaRTC.map(s=>({...lista.find(m=>m.id===s.id),prioridade:s.prioridade,prioridade_execucao:s.prioridade_execucao,creatures:s.creatures,mana_percent:s.mana_percent})).filter(m=>m.cd):estrategia==='atual'?ctx.observado.rtc.slots.filter(s=>s.id).map(s=>({...lista.find(m=>m.id===s.id),...s})).filter(m=>m.cd):lista;
      const rtc=ataque(usadas,ctx,{...opcoes,fixar:estrategia==='atual'||!!referenciaRTC,larguraRTC:4}),cura=curar(cat,p,gs,magias,ctx,estrategia,{fixar_limiares:true});avaliadas++;
      const item={...base,estado:rtc.linhas.length?'Calculado':'Aguardando hunt',rtc,cura,roda:{estado:'Calculado',pontos:p,gemas:gs,efeitos,investidos:efeitos.investidos,livres:ctx.total-efeitos.investidos},valor:objetivo==='cura'?cura.cura??cura.indice_base??null:rtc.robusto??null};
      finalistas.push(item);finalistas.sort((a,b)=>comparar(b,a));if(finalistas.length>3)finalistas.pop();
      if(!melhor||comparar(item,melhor)>0)melhor=item;
      if(Date.now()-inicio>(opcoes.limite_ms??18000)&&melhor)break buscaCompleta;
    }
    for(const item of finalistas)if(item.cura.estado==='Previsto')item.cura=curar(cat,item.roda.pontos,item.roda.gemas,magias,ctx,estrategia,{rodadas:1});
    for(const item of finalistas)if(item.cura.estado==='Previsto'){
      const ataqueJ=cenarios(ctx,item.rtc.linhas),janelas=[];
      for(const a of ataqueJ)for(const c of item.cura.janelas_modelo||[]){const t=Math.max(a.t,c.t),fim=Math.min(a.fim,c.fim);if(fim>t)janelas.push({...a,...c,t,fim,dano:t===c.t?c.dano:{},cura_externa:t===c.t?c.cura_externa:{}});}
      if(janelas.length){const linhas=[...item.rtc.linhas,...item.cura.linhas.filter(m=>m.ativo!==false)],contexto={...ctx.cura,...ctx.atributos,modelo:ctx.modelo,nivel:ctx.nivel,janelas};
        const conjunta=HuntTemporal.simular(linhas,contexto,{duracao:180}),segura=HuntTemporal.simular(linhas,contexto,{duracao:180,sem_critico:true});
        item.metricas_conjunto=conjunta;item.cura.seguranca=segura;item.cura.cura=conjunta.cura;
        item.rtc.robusto=janelas.every(j=>j.origem_alvos==='observado')?conjunta.score:HuntTemporal.simular(linhas,{...contexto,janelas:janelas.map(j=>({...j,alvos:Object.fromEntries(item.rtc.linhas.map(m=>[m.id,Math.min(ctx.cobertura?.[m.id]??1,j.alvos[m.id])]))}))},{duracao:180}).score;
        item.rtc.linhas=item.rtc.linhas.map(m=>({...m,frequencia:estrategia==='atual'||ctx.modelo?.prioridade_entre_tipos==='magias_primeiro'?conjunta.frequencia[m.id]:null}));
        item.cura.linhas=item.cura.linhas.map(m=>({...m,frequencia:m.ativo===false?null:conjunta.segundos_validos?(conjunta.castsAlvos[m.id+'|'+(m.alvo||'')]||0)/conjunta.segundos_validos*60:null}));
      }
    }
    finalistas.sort((a,b)=>comparar(b,a));melhor=finalistas[0]||melhor;
    if(melhor){melhor.roda.prioridade_sio={ativa:priorizarSio,estagio:melhor.roda.efeitos.ranks[33]||0,
      criterio:'Preferir sio maior em potência ofensiva equivalente; segurança medida tem precedência.',
      origem:'preferencia_do_usuario',beneficio_real_validado:false};melhor.roda.comparacao_bonus={bonus_fixo_hp:melhor.roda.efeitos.fixo_hp,
      beneficios:melhor.roda.efeitos.beneficios,unidade:'HP_por_aplicacao',
      criterio:'Potência e segurança primeiro; bônus fixo desempata potência igual. HP e Base Power não são somados.',
      alternativas:finalistas.filter(a=>a!==melhor).map(a=>({pontos:a.roda.pontos,bonus_fixo_hp:a.roda.efeitos.fixo_hp,beneficios:a.roda.efeitos.beneficios,potencia:a.rtc.robusto}))};}
    const inicial=melhor||{...base,estado:'Pontos insuficientes para esta estratégia',rtc:ataque(ofensivas,ctx,opcoes),cura:curar(cat,{},[],magias,ctx,estrategia),roda:{...base.roda,estado:'Pontos insuficientes para esta estratégia'}};
    return {...inicial,modelo_versao:ctx.modelo?.versao||versao,personalizada:!!ctx.modelo?.prioridade_entre_tipos&&ctx.janelas?.length>0&&ctx.janelas.every(j=>j.origem_alvos==='observado'&&melhor?.rtc.linhas.every(m=>Number.isFinite(j.alvos?.[m.id])))&&melhor?.cura.estado==='Previsto'&&ctx.modelo?.latencia_s!=null&&['rtc','cura','roda'].every(k=>ctx.observado?.[k]?.completo)&&melhor.cura.linhas.filter(m=>m.ativo!==false).every(m=>(ctx.cura.qualidade?.[m.id]?.validacao||0)>=4),diagnostico:{avaliadas,expansoes:busca.expansoes,tempo_ms:Date.now()-inicio,alcance:'Melhor entre combinações avaliadas; busca limitada',cura_pendente:melhor?.cura.estado!=='Previsto',criterio_cura:'sobrevivência sem crítico, cura efetiva, excesso e mana',reavaliacoes:finalistas.length}};
  }
  // Sugestões independentes: o RTC usa somente a roda já lida do jogo.
  // A roda avalia a configuração sugerida do RTC; seus controles não a alteram.
  function calcularRTC(cat,magias,ctx,opcoes={}){
    ctx={...ctx,regras_versao:cat.versao,roda_efeitos:efeitosRTCObservados(cat,ctx)};
    const pontosLidos=Object.fromEntries(Object.entries(ctx.observado?.roda?.campos||{}).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
    const pontos=ctx.observado?.roda?.completo&&HuntRTC.validarDistribuicao(cat,pontosLidos,ctx.total).ok?pontosLidos:{};
    const gemasLidas=Object.entries(ctx.observado?.roda?.campos||{}).filter(([k])=>k.startsWith('gemas.')).map(([,v])=>v.valor)
      .filter(g=>g?.equipada&&g.estado==='observado_completo').map(g=>({...g,...g.modificadores?.[0]}));
    const gemas=Object.keys(pontos).length?gemasLidas:[];
    const ofensivas=magias.filter(m=>HuntRTC.categoria(m)).map(m=>m.ajustado==null?{...m,ajustado:m.bp,resistencia:100,origem_potencia:'base_global'}:m).filter(m=>m.ajustado>0);
    const calibracao=calibracaoRTC(ctx);
    const lista=HuntRodaMotor.modificar(cat,pontos,ofensivas,gemas,{alvos:Math.max(1,...Object.keys(ctx.criaturas_histograma||{}).map(Number)),temporal:true,efeitos_observados:Object.keys(pontos).length?{}:efeitosRTCObservados(cat,ctx)})
      .map(m=>({...m,categoria:HuntRTC.categoria(m),cadencia_observada:calibracao?.intervalos_efetivos?.[m.id]||null}));
    const efeitos_observados=Object.keys(pontos).length?{}:efeitosRTCObservados(cat,ctx);
    const e=HuntRodaMotor.efeitos(cat,pontos,gemas,efeitos_observados);
    const modo=ctx.cura?.postura==='utamo'?'utamo':'vida';
    const estrategia=modo==='utamo'?'utamo':e.ranks[28]?'vida_link':'vida';
    let cura=curar(cat,pontos,gemas,magias,ctx,estrategia,{aprender:true,efeitos_observados});
    const estudoSio=ctx.estudo_sio?.sessao===ctx.sessao&&ctx.estudo_sio?.contexto?.char===ctx.char&&ctx.estudo_sio?.contexto?.hazard===ctx.hazard?ctx.estudo_sio:null;
    const aprendidas=estudoSio?.sugestoes||[];
    const sugestoes=[...(ctx.sugestoes_cura||[]),...aprendidas].filter(s=>['feedback_analisado','aprendizado_sio_parcial'].includes(s.origem)&&s.sessao===ctx.sessao&&s.hazard===ctx.hazard&&s.provas?.length&&Number.isInteger(s.vida_percent)&&s.vida_percent>=1&&s.vida_percent<=100);
    cura={...cura,estudo_sio:estudoSio,linhas:cura.linhas.map(m=>{const s=sugestoes.findLast(s=>s.id===m.id&&s.vocacao_destino===m.vocacao_destino);return s?{...m,vida_percent:s.vida_percent,vida_percent_anterior:s.anterior,origem_percentual:s.origem,motivo:s.motivo}:m;})};
    // Informação do usuário é a referência da próxima sugestão; horário
    // desconhecido não a transforma em configuração aplicada no replay antigo.
    cura={...cura,linhas:cura.linhas.map(m=>{const informada=(ctx.configuracoes_informadas||[]).find(s=>s.origem==='usuario'&&s.componente==='cura'&&s.id===m.id&&s.vocacao_destino===m.vocacao_destino&&Number.isInteger(s.vida_percent)&&s.vida_percent>=1&&s.vida_percent<=100);
      return informada?{...m,vida_percent:informada.vida_percent,origem_percentual:'informado_usuario'}:m;})};
    let rtc=ataque(lista,ctx,opcoes);
    if(typeof HuntPersonalizacao!=='undefined'){
      const slots=ctx.observado?.rtc?.slots||[];
      const atual=slots.filter(s=>s.id&&lista.some(m=>m.id===s.id)).map(s=>({...lista.find(m=>m.id===s.id),...s}));
      const pessoal=HuntPersonalizacao.buscar(atual,lista,ctx,HuntTemporal.simular);
      rtc={...rtc,personalizacao:pessoal};
      if(pessoal.personalizada)rtc={...ataque(pessoal.linhas,ctx,{fixar:true}),personalizacao:pessoal,personalizada:true,alteracoes:pessoal.alteracoes,expectativa:pessoal.expectativa};
    }
    const rodaChave=JSON.stringify(Object.entries(ctx.observado?.roda?.campos||{}).filter(([k])=>/^(conviction|revelation)\./.test(k)).map(([k,v])=>[k,v.valor]).sort(([a],[b])=>a.localeCompare(b)));
    const estudo=(ctx.estudos_rtc||[]).find(e=>e.origem==='replay_configuracao_observada'&&e.provas?.length>=2&&e.sessao===ctx.sessao&&e.hazard===ctx.hazard&&e.roda_chave===rodaChave&&e.rtc_chave===chaveRTC(ctx.observado?.rtc));
    if(estudo){
      const atual=(ctx.observado?.rtc?.slots||[]).filter(s=>s.id&&lista.some(m=>m.id===s.id)).map(s=>({...lista.find(m=>m.id===s.id),...s}));
      const base=estudo.resultados?.find(r=>r.limiar===estudo.limiar_atual);
      const melhor=estudo.resultados?.filter(r=>Number.isInteger(r.limiar)&&r.limiar>=1&&r.limiar<=10&&r.score>0&&r.score_conservador>0).sort((a,b)=>b.score-a.score)[0];
      if(base&&melhor&&melhor.score>base.score&&melhor.score_conservador>=base.score_conservador&&atual.some(m=>m.id===estudo.id&&m.creatures===estudo.limiar_atual)){
        rtc={...ataque(atual.map(m=>m.id===estudo.id?{...m,creatures:melhor.limiar}:m),ctx,{fixar:true}),estudo};
      }
    }
    const estudoCura=ctx.estudo_cura?.sessao===ctx.sessao&&ctx.estudo_cura?.contexto?.char===ctx.char?ctx.estudo_cura:null;
    if(estudoCura){
      const compativel=estudoCura.referencia?.every(s=>cura.linhas.some(m=>m.id===s.id&&m.vocacao_destino===s.vocacao_destino&&m.vida_percent===s.vida_percent))
        &&(estudoCura.estado!=='sugestao_para_testar'||Number.isInteger(estudoCura.avaliacao?.hazard)&&estudoCura.avaliacao.hazard===ctx.hazard);
      cura={...cura,estudo_cura:estudoCura,referencia_estudo_compativel:compativel};
      if(compativel&&cura.aprendizado?.estado!=='aprendizado_validado'&&estudoCura.estado==='sugestao_para_testar'){
        const ajustes=estudoCura.sugestoes||[];
        if(ajustes.length<=2)cura={...cura,linhas:cura.linhas.map(m=>{const s=ajustes.find(s=>s.id===m.id&&s.vocacao_destino===m.vocacao_destino&&s.anterior===m.vida_percent&&s.provas?.length&&Number.isInteger(s.vida_percent)&&s.vida_percent>=30&&s.vida_percent<=99);
          return s?{...m,vida_percent:s.vida_percent,vida_percent_anterior:m.vida_percent,origem_percentual:'estudo_cura_observacional',motivo:s.motivo}:m;})};
      }
    }
    const twinLimiar=ctx.twin?.proposta?.candidato??ctx.twin?.referencia;
    if([4,5,6].includes(twinLimiar)&&ctx.vocacao==='ED'){
      const observados=ctx.observado?.rtc?.slots||[];
      const linhas=ctx.twin?.proposta&&ctx.observado.rtc.completo?observados.filter(s=>s.id).map(s=>({...lista.find(m=>m.id===s.id),...s})):rtc.linhas;
      rtc={...ataque(linhas.map(m=>['ice_burst','terra_burst'].includes(m.id)?{...m,creatures:twinLimiar}:m),ctx,{fixar:true}),
        referencia_xp:true,ganho_xp_validado:!!ctx.twin?.resultado&&ctx.twin.resultado.estado==='validado_posteriormente'};
      if(ctx.twin?.proposta)cura={...cura,linhas:cura.linhas.map(m=>{const s=ctx.observado.cura.slots.find(s=>s.id===m.id&&s.vocacao_destino===m.vocacao_destino);return s&&s.vida_percent!=null?{...m,vida_percent:s.vida_percent,origem_percentual:'observado'}:m;})};
    }
    return {rtc:{...rtc,aprendizado:diagnosticoML(ctx)},cura:{...cura,postura:modo}};
  }
  function personalizarPacote(cat,magias,ctx,objetivo){
    if(typeof HuntPersonalizacao==='undefined'||!ctx.validacao_execucao?.promover)return null;
    if(!['rtc','cura','roda'].every(k=>ctx.observado?.[k]?.completo))return null;
    const pontos=Object.fromEntries(Object.entries(ctx.observado.roda.campos).filter(([k])=>k.startsWith('fatias.')).map(([k,v])=>[k.slice(7),v.valor]));
    if(!HuntRTC.validarDistribuicao(cat,pontos,ctx.total).ok)return null;
    const gemas=Object.entries(ctx.observado.roda.campos).filter(([k])=>k.startsWith('gemas.')).map(([,v])=>v.valor).filter(g=>g?.equipada&&g.estado==='observado_completo').map(g=>({...g,...g.modificadores?.[0]}));
    const pool=magias.filter(m=>HuntRTC.categoria(m)).map(m=>({...m,categoria:HuntRTC.categoria(m),resistencia:m.resistencia??100,ajustado:m.ajustado??m.bp}));
    const modificadas=HuntRodaMotor.modificar(cat,pontos,pool,gemas,{temporal:true});
    const rtc=ctx.observado.rtc.slots.filter(s=>s.id).map(s=>({...modificadas.find(m=>m.id===s.id),...s}));
    if(rtc.some(m=>!m.cd))return null;
    const cura=curar(cat,pontos,gemas,magias,ctx,'atual',{fixar_limiares:true}).linhas||[];
    const base={rtc,cura,pontos},pacotes=[];
    for(const linhas of HuntPersonalizacao.candidatas(rtc,modificadas))pacotes.push({...base,rtc:linhas});
    const curas=[];
    for(let i=0;i<cura.length;i++)for(const delta of [-5,5]){
      const pct=cura[i].vida_percent+delta;if(!Number.isFinite(pct)||pct<30||pct>99)continue;
      const linhas=cura.map((m,j)=>i===j?{...m,vida_percent:pct}:m);curas.push(linhas);pacotes.push({...base,cura:linhas});
    }
    for(const p of pacotes.slice(0,80))if(HuntPersonalizacao.alteracoesPacote(base,p).length===1)for(const linhas of curas)pacotes.push({...p,cura:linhas});
    // Redistribuições são dois campos concretos, nunca esconder muitos ajustes
    // sob o nome de uma única troca de pacote.
    for(const de of cat.fatias)for(const para of cat.fatias)if(de.id!==para.id&&(pontos[de.id]||0)>=5){
      const p={...pontos,[de.id]:(pontos[de.id]||0)-5,[para.id]:(pontos[para.id]||0)+5};
      if(HuntRTC.validarDistribuicao(cat,p,ctx.total).ok)pacotes.push({...base,pontos:p});
    }
    const janelas=ctx.janelas.map(j=>{const v=ctx.cura?.janelas?.find(v=>v.t<=j.t&&v.fim>=j.fim);return v?{...v,...j,vida:v.vida,mana:v.mana,mana_maxima:v.mana_maxima,dano:v.dano,cura_externa:v.cura_externa}:j;});
    const avaliar=(pacote,js)=>{
      const atuais=HuntRodaMotor.modificar(cat,pacote.pontos,pool,gemas,{temporal:true});
      const ataque=pacote.rtc.map(s=>({...atuais.find(m=>m.id===s.id),...Object.fromEntries(['tipo','slot','prioridade','prioridade_execucao','creatures','mana_percent'].map(k=>[k,s[k]]))}));
      const curaMod=curar(cat,pacote.pontos,gemas,magias,ctx,'atual',{fixar_limiares:true}).linhas||[];
      const linhasCura=curaMod.map(m=>({...m,vida_percent:pacote.cura.find(s=>s.id===m.id&&s.alvo===m.alvo)?.vida_percent??m.vida_percent}));
      return HuntTemporal.simular([...ataque,...linhasCura],{...ctx,...ctx.cura,...ctx.atributos,pronta:ctx.pronta,janelas:js.prefixo},{inicio:js.desde,duracao:js.ate,sem_critico:true});
    };
    return {...HuntPersonalizacao.buscarPacote(base,pacotes.slice(0,512),{...ctx,objetivo,janelas},avaliar),gemas};
  }
  function diagnosticoML(ctx){return {estado:ctx.modelo?.combate_ml?.estado||'coletando',amostras:ctx.modelo?.combate_ml?.amostras||0,perfis:Object.keys(ctx.modelo?.combate_ml?.perfis||{}),referencia_inicial:ctx.modelo?.combate_ml?.referencia_inicial?.id,cobertura_completa:false};}
  function calcularRoda(cat,magias,ctx,objetivo='dano',tier=0,opcoes={}){
    if(!['dano','cura'].includes(objetivo))throw Error('Escolha Dano ou Cura.');
    ctx={...ctx,objetivo_roda:objetivo};
    const modo=objetivo==='cura'?(opcoes.modo_vida??'vida'):null;
    if(modo&&!['vida','utamo'].includes(modo))throw Error('Escolha Vida ou Utamo na roda.');
    const estrategia=objetivo==='dano'?'dano':cat.vocacao==='ED'?(modo==='utamo'?'utamo_critica':modalidade(ctx.pt)==='solo'?'vida_link':'vida_critica'):modo;
    const r=calcular(cat,magias,ctx,objetivo,estrategia,tier,{...opcoes,roda_independente:true,preencher:true,modo_vida:modo});
    const pessoal=personalizarPacote(cat,magias,ctx,objetivo);
    if(pessoal?.personalizada){const efeitos=HuntRodaMotor.efeitos(cat,pessoal.pacote.pontos,pessoal.gemas);
      if(!rodaRejeitada(feedbackRoda(cat,ctx),efeitos)&&(cat.vocacao!=='ED'||modalidade(ctx.pt)==='solo'||efeitos.ranks[33]>=2&&efeitos.revelation[11]>0)){r.roda={...r.roda,pontos:pessoal.pacote.pontos,efeitos,investidos:efeitos.investidos,livres:ctx.total-efeitos.investidos,gemas:pessoal.gemas,personalizada:true,alteracoes:pessoal.alteracoes,expectativa:pessoal.expectativa};r.cura={...r.cura,linhas:pessoal.pacote.cura};}
    }
    r.roda.comparacao_atual=compararRoda(cat,magias,ctx,r.roda,opcoes);
    const cmp=r.roda.comparacao_atual;
    // Mesmo a política validada precisa da referência inteira, sem piora do EK.
    cmp.recomendar=!!r.roda.personalizada&&!cmp.lacunas.length&&!cmp.motivos.length&&(r.roda.alteracoes?.length||0)<=2;
    if(!cmp.recomendar)r.roda.personalizada=false;
    const feedback=feedbackRoda(cat,ctx);
    if(feedback?.rejeitada&&!cmp.recomendar){
      const ref=referenciaRoda(cat,ctx);
      // Exibir a distribuição calculada e suas gemas como proposta. Uma
      // referência parcial não vira pontos observados nem prova de ganho.
      r.roda={...r.roda,personalizada:false,
        referencia:ref,referencia_reprovada:rodaRejeitada(feedback,ref.efeitos),
        comparacao_atual:{...cmp,estado:'Proposta de dano após seu feedback',recomendar:false,
          feedback:{id:feedback.id,origem:'usuario',beneficio_real_validado:false},referencia:{preset:ref.preset,completa:ref.completa,gemas_completas:ref.gemas_completas}},
        rejeicao:{preset:feedback.roda_rejeitada?.preset||null,sessao:feedback.sessao,
          motivo:'Desempenho insatisfatório relatado na hunt',melhoria_demonstrada:false}};
    }
    return {roda:{...r.roda,personalizacao:pessoal,aprendizado:diagnosticoML(ctx)},cura:{...r.cura,postura:modo},contexto:r.contexto,regras_versao:r.regras_versao,modelo_versao:r.modelo_versao,objetivo,tier,modo,estrategia};
  }
  return {estrategias,versao,contexto,calcular,ataque,curar,cenarios,calcularRTC,calcularRoda,equalizarCriaturas,perfilCombate,rendimentoAprendido,compararDano,referenciaRoda,compararRoda,modalidade,vocacaoObservada,similaridadeRoda,rtcParaComparacao,feedbackRoda,rodaRejeitada};
})();
if(typeof module!=='undefined')module.exports=HuntIntegracao;
