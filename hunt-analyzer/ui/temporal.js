/* Relógios independentes; vida, potência e pontos têm unidades distintas. */
const HuntTemporal=(()=>{
 const valido=v=>typeof v==='number'&&Number.isFinite(v);
 const grupo=m=>m.grupo_id||(m.tipo==='cura'?'cura':'ataque');
 const secundario=m=>m.grupo_secundario||(m.cd_compartilhado>0?m.familia:null);
 const chave=m=>m.id+'|'+(m.alvo||'');
 function naoPiora(a,b){
  const nomes=new Set([...Object.keys(a.saude||{}),...Object.keys(b.saude||{})]);
  if(!nomes.size)return false;
  for(const nome of nomes){const x=a.saude?.[nome],y=b.saude?.[nome];
   if(!x||!y||x.cobertura_s<=0||y.cobertura_s<=0||x.mortes>y.mortes||x.tempo_critico>y.tempo_critico+1e-8||x.vida_minima<y.vida_minima-1e-8)return false;}
  return true;
 }
 function comparar(a,b){
  for(const [k,dir] of [['mortes',-1],['tempo_critico',-1],['vida_minima',1],['cura',1],['excesso',-1],['manaGasta',-1]]){
   const d=(a[k]??0)-(b[k]??0);if(Math.abs(d)>1e-8)return d*dir;
  }return 0;
 }
 function simular(magias,contexto={},opcoes={}){
  const duracao=opcoes.duracao??Math.max(180,...(contexto.janelas||[]).map(j=>j.fim||0)),inicio=opcoes.inicio??0;
  if(!(duracao>0)||magias.some(m=>!valido(m.cd)||m.cd<=0||!valido(m.grupo)||m.grupo<=0))throw Error('Cooldown desconhecido');
  const estados=(contexto.janelas||[{t:0,fim:duracao,...contexto}]).filter(s=>s.valida!==false).sort((a,b)=>a.t-b.t);
  const pronta={...contexto.pronta},grupos={...contexto.grupos},casts={},castsAlvos={},efeitos={},sequencia=[],vida={},saude={};
  let score=0,bonusFixoHp=0,cura=0,excesso=0,manaGasta=0,validos=0,mortes=0,tempo_critico=0,vida_minima=100,mana=null,ultimaJanela=-Infinity,focusAte=-Infinity,converter=null;
  const latencias=[],recuperacoes=[],inicioDano={},latencia=Math.max(0,contexto.modelo?.latencia_s??contexto.latencia_s??0);
  const membro=nome=>saude[nome]??(saude[nome]={mortes:0,tempo_critico:0,vida_minima:100,cobertura_s:0});
  const medir=(desde,ate)=>{const dt=Math.max(0,ate-Math.max(desde,inicio));if(dt)for(const [nome,v] of Object.entries(vida)){const pct=v.atual/v.maxima*100,r=membro(nome);r.cobertura_s+=dt;r.vida_minima=Math.min(r.vida_minima,pct);vida_minima=Math.min(vida_minima,pct);if(pct<30){tempo_critico+=dt;r.tempo_critico+=dt;}}};
  for(const s of estados){
   const ini=Math.max(0,s.t),fim=Math.min(duracao,s.fim??duracao);if(fim<=ini)continue;
   if(ini<ultimaJanela-1e-9)throw Error('Janelas sobrepostas');
   validos+=Math.max(0,fim-Math.max(ini,inicio));const novoTrecho=ini>ultimaJanela+1e-6;
   for(const nome of Object.keys(vida))if(!s.vida?.[nome]||!valido(s.vida[nome].atual)||!valido(s.vida[nome].maxima))delete vida[nome];
   for(const [alvo,v] of Object.entries(s.vida||{}))if(valido(v.maxima)&&v.maxima>0){
    if(!vida[alvo]||novoTrecho||s.modo_vida!=='contrafactual'){if(valido(v.atual))vida[alvo]={...v};}
    else if(vida[alvo].maxima!==v.maxima){vida[alvo].atual*=v.maxima/vida[alvo].maxima;vida[alvo].maxima=v.maxima;}
   }
   for(const [alvo,n] of Object.entries(s.dano||{}))if(vida[alvo]&&valido(n)&&n>=0){
    const v=vida[alvo],dano=n*(1-(contexto.defesa?.[alvo]??0));if(v.atual===v.maxima)inicioDano[alvo]=ini;
    if(v.atual>0&&v.atual-dano<=0&&ini>=inicio){mortes++;membro(alvo).mortes++;}v.atual=Math.max(0,v.atual-dano);
    if(ini>=inicio){vida_minima=Math.min(vida_minima,v.atual/v.maxima*100);membro(alvo).vida_minima=Math.min(membro(alvo).vida_minima,v.atual/v.maxima*100);}
   }
   for(const [alvo,n] of Object.entries(s.cura_externa||{}))if(vida[alvo]&&valido(n))vida[alvo].atual=Math.min(vida[alvo].maxima,vida[alvo].atual+n);
   if(valido(s.mana)&&(s.modo_mana!=='contrafactual'||mana===null||novoTrecho))mana=s.mana;
   if(mana!==null&&valido(s.mana_delta))mana=Math.max(0,mana+s.mana_delta);
   let t=ini,ultimoT=ini;
   const apta=m=>{
    if(m.ativo===false||s.disponiveis?.[m.id]===false||s.manual===true)return false;
    if(valido(contexto.nivel)&&valido(m.nivel)&&contexto.nivel<m.nivel)return false;
    if(valido(m.alcance)&&valido(s.distancias?.[m.alvo])&&s.distancias[m.alvo]>m.alcance)return false;
    if(m.exige_orientacao&&s.orientacao_compativel?.[m.id]===false)return false;
    if(m.tipo==='cura'){
     const v=vida[m.alvo||'eu'];if(!v||v.morta||v.atual>=v.maxima||v.atual/v.maxima*100>(m.vida_percent??100)||!valido(m.cura_hp))return false;
     if(m.alvo&&m.alvo!=='eu'&&s.alcancaveis&&!s.alcancaveis.includes(m.alvo))return false;
    }else if(!valido(s.criaturas)||s.criaturas<(m.creatures??1)||m.somente_alvo_isolado&&s.criaturas!==1||!valido(m.ajustado)||!valido(s.alvos?.[m.id])||s.alvos[m.id]<=0)return false;
    const pct=mana!==null&&valido(s.mana_maxima)?mana/s.mana_maxima*100:s.mana_percent;
    return !(valido(pct)&&pct<(m.mana_percent??0)||mana!==null&&valido(m.mana)&&mana<m.mana);
   };
   const prontaEm=m=>Math.max(pronta[m.id]||0,grupos[grupo(m)]||0,grupos[secundario(m)]||0),elegiveis=new Map();
   while(t<fim-1e-9){
    const aptas=magias.map((m,i)=>({m,i})).filter(({m})=>apta(m));
    for(const {m} of aptas)if(!elegiveis.has(chave(m)))elegiveis.set(chave(m),Math.max(ini,prontaEm(m)));
    const candidatas=aptas.filter(({m})=>prontaEm(m)+latencia<=t+1e-9).sort((a,b)=>(a.m.prioridade_execucao??a.m.prioridade??a.i+1)-(b.m.prioridade_execucao??b.m.prioridade??b.i+1)||a.i-b.i);
    if(!candidatas.length){
     const next=Math.min(...aptas.map(({m})=>prontaEm(m)+latencia).filter(n=>n>t+1e-9));
     if(!Number.isFinite(next)||next>=fim)break;medir(ultimoT,next);t=next;ultimoT=t;continue;
    }
    const {m}=candidatas[0];let valor=0,util=0;
    if(m.tipo==='cura'){
     const alvos=m.destino==='party_e_propria'?Object.keys(vida).filter(a=>a==='eu'||s.cobertos?.includes(a)):[m.alvo||'eu'];
     for(const alvo of alvos){const v=vida[alvo];if(!v||v.morta)continue;
      const hp=v.atual/v.maxima*100,bonus=m.blessing?m.blessing*(hp<30?2:hp<60?1:0):0;
      const crit=opcoes.sem_critico!==true&&valido(contexto.critico_chance)&&valido(contexto.critico_extra)&&m.critico_habilitado?contexto.critico_chance*contexto.critico_extra:0;
      const compartilhada=contexto.postura==='shared_conservation'&&alvo==='eu'?1.1:1;
      const bruto=m.cura_hp*(1+bonus)*(1+crit)*compartilhada+(m.cura_fixa_hp||0),real=Math.max(0,Math.min(bruto,v.maxima-v.atual));
      v.atual+=real;if(t>=inicio){cura+=real;excesso+=bruto-real;util+=real;efeitos[alvo]=(efeitos[alvo]||0)+real;}
      if(alvo!=='eu'&&m.link&&['heal_friend','nature_s_embrace'].includes(m.id)&&vida.eu){const eu=vida.eu,link=Math.max(0,Math.min(eu.maxima-eu.atual,real*m.link));eu.atual+=link;if(t>=inicio){cura+=link;util+=link;efeitos.eu=(efeitos.eu||0)+link;}}
      if(contexto.postura==='shared_conservation'&&['heal_friend','nature_s_embrace'].includes(m.id)){
       const outro=s.secundario_cura?.[m.id];if(outro&&outro!==alvo&&vida[outro]&&s.alcancaveis?.includes(outro)){
        const transferida=Math.max(0,Math.min(vida[outro].maxima-vida[outro].atual,real*.3));vida[outro].atual+=transferida;
        if(t>=inicio){cura+=transferida;util+=transferida;efeitos[outro]=(efeitos[outro]||0)+transferida;}
       }
      }
      if(v.atual/v.maxima>=.8&&inicioDano[alvo]!=null){if(t>=inicio)recuperacoes.push(t-inicioDano[alvo]);delete inicioDano[alvo];}
     }
    }else{
     const n=Math.min(s.alvos[m.id],m.alvos??Infinity),principal=s.alvos_centrais?.[m.id]??n,lateral=s.alvos_laterais?.[m.id]??0;
     let bonus=m.twin_bonus&&valido(s.alvos_acima60?.[m.id])?1+m.twin_bonus*s.alvos_acima60[m.id]/Math.max(1,n):1;
     if(m.focus_bonus&&m.familia!=='ue'&&t<=focusAte)bonus*=1+m.focus_bonus;
     const beam=m.beam_por_alvo?1+m.beam_por_alvo*Math.min(3,principal):1;
     const elemento=converter&&converter!==m.elemento?converter:m.elemento;
     const resistencia=contexto.resistencias?.[elemento];
     const ajustado=valido(resistencia)?m.bp*resistencia/100:m.ajustado;
     // O rendimento aprendido é parcial e já inclui área/HP da build observada.
     // Não multiplicar de novo por alvos ou pelo bônus Twin da mesma amostra.
     valor=valido(s.potencia_ml?.[m.id])?s.potencia_ml[m.id]:ajustado*(principal+lateral*(m.beam_lateral||0))*bonus*beam;
     // Bônus nominal em HP é uma dimensão separada do índice Base Power.
     // Sem fórmula/calibração de HP não somar os dois nem prometer dano real.
     if(t>=inicio)bonusFixoHp+=(m.dano_fixo_hp||0)*n;
     const lord=m.lord_destruction||0,postura=contexto.postura;
     let chance=contexto.critico_chance,extra=contexto.critico_extra;
     if(postura==='master_of_flames'&&elemento==='fire')valor*=1+.04+[0,.02,.03,.04][lord];
     if(postura==='master_of_thunder'&&elemento==='energy'&&valido(chance))chance=Math.min(1,chance+.04+[0,.02,.03,.04][lord]);
     if(postura==='master_of_decay'&&elemento==='death'&&valido(extra))extra+=.30+[0,.15,.225,.30][lord];
     const posturaEl={master_of_flames:'fire',master_of_thunder:'energy',master_of_decay:'death'}[postura];
     if(posturaEl)converter=elemento===posturaEl?posturaEl:null;
     if(valido(chance)&&valido(extra))valor*=1+chance*(extra+(m.critico_extra||0));
     if(contexto.atribuir_leech&&valido(s.dano_hp?.[m.id])){
      const leech=s.dano_hp[m.id]*(m.life_leech||contexto.life_leech||0)*(contexto.life_leech_chance??0);
      if(vida.eu){const aplicada=Math.max(0,Math.min(vida.eu.maxima-vida.eu.atual,leech));vida.eu.atual+=aplicada;if(t>=inicio)cura+=aplicada;}
      if(mana!==null)mana=Math.min(s.mana_maxima??Infinity,mana+s.dano_hp[m.id]*(contexto.mana_leech||0)*(contexto.mana_leech_chance??0));
     }
     if(t>=inicio)score+=valor;
     if(m.familia==='ue'&&m.focus_bonus)focusAte=t+12;else if(m.focus_bonus&&t<=focusAte)focusAte=-Infinity;
    }
    pronta[m.id]=t+m.cd;grupos[grupo(m)]=t+m.grupo;
    if(m.cd_compartilhado>0)grupos[secundario(m)]=t+m.cd_compartilhado;
    const reducao=m.beam_por_alvo?Math.min(3,s.alvos_centrais?.[m.id]??s.alvos[m.id]):m.reduz_outros_cd||0;
    if(reducao>0)for(const outra of magias)if(outra.id!==m.id&&!outra.runa)pronta[outra.id]=Math.max(t,(pronta[outra.id]||0)-reducao);
    if(mana!==null&&valido(m.mana))mana-=m.mana;
    if(t>=inicio){casts[m.id]=(casts[m.id]||0)+1;castsAlvos[chave(m)]=(castsAlvos[chave(m)]||0)+1;manaGasta+=m.mana||0;
     const elegivel=elegiveis.get(chave(m));latencias.push(Math.max(0,t-elegivel));sequencia.push({t,id:m.id,alvo:m.alvo,potencia:valor,cura:util,elegivel_em:elegivel});}
    elegiveis.delete(chave(m));
   }
   medir(ultimoT,fim);ultimaJanela=fim;
  }
  return {score,bonus_fixo_hp_nominal:bonusFixoHp,cura,excesso,manaGasta,efeitos,casts,castsAlvos,sequencia,mortes,tempo_critico,vida_minima,saude,
   recuperacao_media:recuperacoes.length?recuperacoes.reduce((a,b)=>a+b)/recuperacoes.length:null,
   atraso_medio:latencias.length?latencias.reduce((a,b)=>a+b)/latencias.length:null,
   duracao:duracao-inicio,segundos_validos:validos,frequencia:Object.fromEntries(magias.map(m=>[m.id,validos?(casts[m.id]||0)/validos*60:null])),porSegundo:validos?score/validos:null};
 }
 function limiares(magias,contexto,opcoes={}){
  if(!contexto.janelas?.some(j=>Object.keys(j.vida||{}).length))return {estado:'A calibrar',linhas:magias.map(m=>({...m,vida_percent:null,frequencia:null})),motivo:'Vida, alcance e cura identificada ainda não observados.'};
  let linhas=magias.map((m,i)=>({...m,prioridade:m.prioridade??i+1,vida_percent:m.vida_percent??99}));
  const avaliar=lista=>simular(lista,contexto,{...opcoes,sem_critico:true});let melhor=avaliar(linhas);
  if(!opcoes.fixar_limiares)for(let rodada=0;rodada<(opcoes.rodadas??2);rodada++)for(let i=0;i<linhas.length;i++){
   if(!linhas[i].limiar_fixo)for(let pct=1;pct<=100;pct++){const teste=linhas.map((m,k)=>k===i?{...m,vida_percent:pct}:m),r=avaliar(teste);if(comparar(r,melhor)>0){linhas=teste;melhor=r;}}
   for(let destino=0;destino<linhas.length;destino++){const teste=linhas.slice(),[m]=teste.splice(i,1);teste.splice(destino,0,m);const ordem=teste.map((m,k)=>({...m,prioridade:k+1})),r=avaliar(ordem);if(comparar(r,melhor)>0){linhas=ordem;melhor=r;}}
  }
  const esperada=simular(linhas,contexto,opcoes);
  return {estado:'Previsto',...esperada,seguranca:melhor,linhas:linhas.map(m=>({...m,origem_percentual:'calculado',frequencia:esperada.segundos_validos?(esperada.castsAlvos[chave(m)]||0)/esperada.segundos_validos*60:null}))};
 }
 // Aprendizado de política por minimização do risco no replay de vida/dano.
 // O treino escolhe os limiares; o trecho futuro só aceita ou rejeita o conjunto.
 // Não aprende a imitar o percentual configurado nem usa silêncio como cura zero.
 function aprenderCura(magias,contexto,opcoes={}){
  const originais=magias.map((m,i)=>({...m,prioridade:m.prioridade??i+1}));
  const aprendizado={versao:'cura-politica-1',algoritmo:'busca_de_politica_com_validacao_temporal',estado:'coletando',ajustes:[],cobertura_completa:false};
  const inicial=()=>({estado:'Recomendado',linhas:originais.map(m=>({...m,frequencia:null})),aprendizado});
  if(!originais.length||originais.some(m=>!valido(m.cura_hp)||m.cura_hp<=0||(contexto.qualidade?.[m.id]?.validacao||0)<4))return inicial();
  const janelas=(contexto.janelas||[]).filter(j=>j.valida!==false).slice().sort((a,b)=>a.t-b.t);
  // Não descartar apenas as janelas ruins: isso enviesaria a avaliação de perigo.
  if(janelas.length<30||janelas.some((j,i)=>!valido(j.t)||!valido(j.fim)||j.fim<=j.t||j.fim-j.t>6||i&&Math.abs(j.t-janelas[i-1].fim)>.001||!j.dano||originais.some(m=>{
   const v=j.vida?.[m.alvo||'eu'];return !v||!valido(v.atual)||!valido(v.maxima)||v.maxima<=0||v.atual<0||v.atual>v.maxima;
  })))return inicial();
  const corte=janelas[Math.floor(janelas.length/2)].t,testeDesde=janelas[Math.floor(janelas.length*3/4)].t,fim=janelas.at(-1).fim;
  if(corte-janelas[0].t<60||testeDesde-corte<30||fim-testeDesde<30)return inicial();
  const treino=janelas.filter(j=>j.fim<=corte),ctxTreino={...contexto,janelas:treino};
  const avaliar=linhas=>simular(linhas,ctxTreino,{duracao:corte,sem_critico:true});
  let linhas=originais,melhor=avaliar(linhas);const baseTreino=melhor;
  // No máximo dois campos por entrega. A ordem do helper não é um campo sugerido.
  for(let rodada=0;rodada<2;rodada++){
   let escolhidas=linhas,resultado=melhor;
   for(let i=0;i<linhas.length;i++)if(!linhas[i].limiar_fixo)for(let pct=1;pct<=100;pct++){
    if(valido(linhas[i].limiar_maximo_feedback)&&pct>linhas[i].limiar_maximo_feedback)continue;
    if(pct===linhas[i].vida_percent)continue;
    const teste=linhas.map((m,k)=>k===i?{...m,vida_percent:pct}:m);
    if(teste.filter((m,k)=>m.vida_percent!==originais[k].vida_percent).length>2)continue;
    const r=avaliar(teste);if(comparar(r,resultado)>0){escolhidas=teste;resultado=r;}
   }
   if(escolhidas===linhas)break;linhas=escolhidas;melhor=resultado;
  }
  // O prefixo aquece HP/cooldowns; só o período posterior entra nas métricas.
  const selecionar=lista=>simular(lista,{...contexto,janelas:janelas.filter(j=>j.fim<=testeDesde)},{inicio:corte,duracao:testeDesde,sem_critico:true});
  const selecaoAntes=selecionar(originais),selecaoDepois=selecionar(linhas);
  if(comparar(selecaoDepois,selecaoAntes)<=0||!naoPiora(selecaoDepois,selecaoAntes))linhas=originais;
  const validar=lista=>simular(lista,{...contexto,janelas},{inicio:testeDesde,duracao:fim,sem_critico:true});
  const antes=validar(originais),depois=validar(linhas);
  const aceita=comparar(melhor,baseTreino)>0&&comparar(depois,antes)>0
   &&naoPiora(depois,antes);
  const metricas=r=>Object.fromEntries(['mortes','tempo_critico','vida_minima','cura','excesso','manaGasta','segundos_validos'].map(k=>[k,r[k]]));
  Object.assign(aprendizado,{estado:aceita?'aprendizado_validado':'validado_sem_melhoria',treino:treino.length,selecao:janelas.filter(j=>j.t>=corte&&j.fim<=testeDesde).length,validacao:janelas.filter(j=>j.t>=testeDesde).length,treino_ate:corte,selecao_ate:testeDesde,teste_desde:testeDesde,
   antes:metricas(antes),depois:metricas(depois),criterio:'sobrevivencia_sem_critico_cura_util_excesso_mana'});
  if(!aceita)linhas=originais;
  else aprendizado.ajustes=linhas.flatMap((m,i)=>m.vida_percent===originais[i].vida_percent?[]:[{id:m.id,alvo:m.alvo,vocacao_destino:m.vocacao_destino,antes:originais[i].vida_percent,depois:m.vida_percent}]);
  const prevista=simular(linhas,{...contexto,janelas},{duracao:fim});
  return {estado:'Previsto',...prevista,seguranca:aceita?depois:antes,aprendizado,linhas:linhas.map((m,i)=>({...m,
   origem_percentual:aceita&&m.vida_percent!==originais[i].vida_percent?'aprendizado_validado':m.origem_percentual,
   frequencia:prevista.segundos_validos?(prevista.castsAlvos[chave(m)]||0)/prevista.segundos_validos*60:null}))};
 }
 return {simular,limiares,comparar,aprenderCura,naoPiora};
})();
if(typeof module!=='undefined')module.exports=HuntTemporal;
