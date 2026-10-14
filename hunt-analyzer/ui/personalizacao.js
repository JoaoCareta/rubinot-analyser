/* Busca limitada: seleção separada do teste e até dois campos para próxima hunt. */
const HuntPersonalizacao=(()=>{
  function coberturaParty(ctx,janelas){
    const nomes=(ctx.cura?.aliados||[]).map(p=>p.nome).filter(Boolean);
    if(![1,'x1','solo'].includes(ctx.pt)&&!nomes.length)return false;
    return janelas.every(j=>nomes.every(n=>j.vida?.[n]?.maxima>0));
  }
  function perfil(ajustes,ctx){
    const chave=xs=>JSON.stringify(xs.slice().sort((a,b)=>String(a?.campo??a).localeCompare(String(b?.campo??b))));
    const contexto=Object.fromEntries(['char','hunt','pt','objetivo','postura','hazard'].map(k=>[k,ctx[k]??null]));
    return (ctx.perfis_efetividade||[]).find(p=>Object.entries(contexto).every(([k,v])=>(p.contexto?.[k]??null)===v)&&chave(p.alteracoes||[])===chave(ajustes));
  }
  function dividir(janelas){
    if(!janelas?.length)return null;
    const inicio=janelas[0].t,fim=janelas.at(-1).fim,a=inicio+(fim-inicio)/2,b=inicio+(fim-inicio)*3/4;
    const trecho=(ini,ate)=>{const rows=janelas.filter(j=>j.t<ate&&j.fim>ini).map(j=>({...j,t:Math.max(ini,j.t)-ini,fim:Math.min(ate,j.fim)-ini}));
      rows.prefixo=janelas.filter(j=>j.t<ate).map(j=>({...j,t:j.t-inicio,fim:Math.min(ate,j.fim)-inicio}));rows.desde=ini-inicio;rows.ate=ate-inicio;return rows;};
    return {treino:trecho(inicio,a),selecao:trecho(a,b),teste:trecho(b,fim)};
  }
  function alteracoes(antes,depois){
    const out=[];const ch=s=>`${s.tipo|| (s.runa?'runa':'magia')}:${s.slot}`;
    const a=new Map(antes.map(s=>[ch(s),s])),b=new Map(depois.map(s=>[ch(s),s]));
    for(const k of new Set([...a.keys(),...b.keys()])){
      if(!b.has(k)){out.push({campo:k,antes:a.get(k).id,depois:null});continue;}
      if(!a.has(k)){out.push({campo:k,antes:null,depois:b.get(k).id});continue;}
      for(const campo of ['id','prioridade','creatures','mana_percent'])if(a.get(k)[campo]!==b.get(k)[campo])out.push({campo:`${k}.${campo}`,antes:a.get(k)[campo],depois:b.get(k)[campo]});
    }
    return out;
  }
  function candidatas(atual,pool){
    const todas=[atual];const vistas=new Set([JSON.stringify(atual)]);
    function expandir(linhas){
      const propostas=[];
      for(let i=0;i<linhas.length;i++){
        const m=linhas[i];
        if(linhas.length>1)propostas.push(linhas.filter((_,j)=>j!==i));
        for(const prioridade of [1,2,3])if(prioridade!==m.prioridade)propostas.push(linhas.map((s,j)=>j===i?{...s,prioridade,prioridade_execucao:prioridade*100+(s.runa?50:0)+i}:s));
        const min=m.runa||m.alvos===1?1:m.categoria==='UE'||m.familia==='ue'?8:2;
        for(const creatures of [min,min+1,min+2])if(creatures!==m.creatures)propostas.push(linhas.map((s,j)=>j===i?{...s,creatures}:s));
        for(const outra of pool)if(!!outra.runa===!!m.runa&&!linhas.some(s=>s.id===outra.id))propostas.push(linhas.map((s,j)=>j===i?{...outra,tipo:m.tipo,slot:m.slot,prioridade:m.prioridade,prioridade_execucao:m.prioridade_execucao,creatures:m.creatures,mana_percent:m.mana_percent}:s));
      }
      return propostas;
    }
    for(let nivel=0,inicio=0;nivel<2;nivel++){
      const fim=todas.length;
      for(let n=inicio;n<fim;n++)for(const p of expandir(todas[n])){
        if(p.filter(m=>m.runa).length>2||p.filter(m=>!m.runa).length>5||p.filter(m=>m.alvos===1).length>1||alteracoes(atual,p).length>2)continue;
        const chave=JSON.stringify(p);if(!vistas.has(chave)){vistas.add(chave);todas.push(p);}
        if(todas.length>=256)return todas;
      }
      inicio=fim;
    }
    return todas;
  }
  function buscar(atual,pool,ctx,simular){
    const v=ctx.validacao_execucao,partes=dividir(ctx.janelas);
    const out={estado:'coletando',linhas:atual,alteracoes:[],personalizada:false};
    if(!atual.length||!v?.promover||!partes||!ctx.elegibilidade_aprendizado?.selecao_ataque||v.escopo?.char!==ctx.char||v.escopo?.sessao!==ctx.sessao)return out;
    if(atual.some(m=>!Number.isFinite(ctx.pronta?.[m.id])))return out;
    if(v.escopo.declaracao_uso_id!==ctx.declaracao_uso_id)return out;
    if(ctx.hazard!=null&&v.escopo.hazard!==ctx.hazard)return out;
    if(Object.values(partes).some(js=>!js.length||js.some(j=>j.origem_alvos!=='observado'||!j.vida||!j.mana_maxima)))return out;
    if(!coberturaParty(ctx,ctx.janelas))return out;
    const avaliar=(lista,js)=>simular(lista,{...ctx,...ctx.cura,janelas:js.prefixo,pronta:ctx.pronta},{inicio:js.desde,duracao:js.ate});
    const seguro=(r,b)=>Object.keys(b.saude||{}).length>0&&r.mortes<=b.mortes&&r.tempo_critico<=b.tempo_critico&&Object.entries(b.saude||{}).every(([n,x])=>r.saude?.[n]?.vida_minima>=x.vida_minima&&r.saude[n].cobertura_s>=x.cobertura_s)&&r.manaGasta<=b.manaGasta;
    const baseTreino=avaliar(atual,partes.treino),baseSelecao=avaliar(atual,partes.selecao);
    let melhor=atual,score=baseSelecao.score,comparadas=0;
    for(const candidata of candidatas(atual,pool)){
      if(candidata.some(m=>!Number.isFinite(ctx.pronta?.[m.id])))continue;
      const historico=perfil(alteracoes(atual,candidata),ctx);if(historico?.estado==='resultado_misto_ou_piora')continue;
      const treino=avaliar(candidata,partes.treino);if(!seguro(treino,baseTreino)||treino.score<baseTreino.score)continue;
      const r=avaliar(candidata,partes.selecao);comparadas++;
      if(!seguro(r,baseSelecao)||!candidata.every(m=>(r.casts[m.id]||0)>0))continue;
      if(r.score>score||r.score===score&&historico?.promover){melhor=candidata;score=r.score;}
    }
    // A vencedora fica congelada antes de abrir o último conjunto.
    const base=avaliar(atual,partes.teste),teste=avaliar(melhor,partes.teste);
    if(!seguro(teste,base)||teste.score<=base.score)return {...out,estado:'rejeitada_no_teste',comparadas};
    return {estado:'prevista_validada_no_escopo',linhas:melhor,alteracoes:alteracoes(atual,melhor),personalizada:true,comparadas,
      expectativa:{antes:base.score,depois:teste.score,unidade:'potencia_prevista',ganho:teste.score-base.score},
      limites:['Replay é previsão; benefício depende de uma hunt posterior comparável.'],
      validacao:{treino:partes.treino.length,selecao:partes.selecao.length,teste:partes.teste.length,testes_abertos:1}};
  }
  function alteracoesPacote(a,b){
    const out=alteracoes(a.rtc,b.rtc);
    const chave=m=>m.id+'|'+(m.alvo||m.vocacao_destino||'eu');
    for(const m of b.cura||[]){const antes=(a.cura||[]).find(x=>chave(x)===chave(m));
      if(antes&&antes.vida_percent!==m.vida_percent)out.push({campo:`cura.${chave(m)}.vida_percent`,antes:antes.vida_percent,depois:m.vida_percent});}
    for(const k of new Set([...Object.keys(a.pontos||{}),...Object.keys(b.pontos||{})]))if((a.pontos[k]||0)!==(b.pontos[k]||0))out.push({campo:`roda.${k}`,antes:a.pontos[k]||0,depois:b.pontos[k]||0});
    return out;
  }
  function buscarPacote(base,pacotes,ctx,avaliar){
    const v=ctx.validacao_execucao,p=dividir(ctx.janelas),out={personalizada:false,estado:'coletando',pacote:base,alteracoes:[]};
    if(ctx.hazard!=null&&v?.escopo?.hazard!==ctx.hazard)return out;
    if(!v?.promover||v.escopo?.char!==ctx.char||v.escopo?.sessao!==ctx.sessao||!ctx.elegibilidade_aprendizado?.cura||!ctx.elegibilidade_aprendizado?.efeitos_roda||!p)return out;
    if([...base.rtc,...base.cura].some(m=>!Number.isFinite(ctx.pronta?.[m.id])))return out;
    if(v.escopo.declaracao_uso_id!==ctx.declaracao_uso_id)return out;
    if(Object.values(p).some(js=>!js.length||js.some(j=>j.origem_alvos!=='observado'||!j.vida||!j.mana_maxima)))return out;
    if(!coberturaParty(ctx,ctx.janelas))return out;
    const seguro=(r,b)=>r.mortes===0&&Object.keys(b.saude||{}).length>0&&Object.entries(b.saude).every(([n,x])=>r.saude?.[n]?.mortes===0&&r.saude[n].tempo_critico<=x.tempo_critico&&r.saude[n].vida_minima>=x.vida_minima&&r.saude[n].cobertura_s>=x.cobertura_s);
    const valor=r=>ctx.objetivo==='cura'?r.cura-r.excesso:r.score;
    const treinoBase=avaliar(base,p.treino),selecaoBase=avaliar(base,p.selecao);let melhor=base,score=valor(selecaoBase),comparadas=0;
    for(const pacote of pacotes){if(alteracoesPacote(base,pacote).length>2)continue;
      if([...pacote.rtc,...pacote.cura].some(m=>!Number.isFinite(ctx.pronta?.[m.id])))continue;
      const historico=perfil(alteracoesPacote(base,pacote),ctx);if(historico?.estado==='resultado_misto_ou_piora')continue;
      const treino=avaliar(pacote,p.treino);if(!seguro(treino,treinoBase)||valor(treino)<valor(treinoBase))continue;
      const selecao=avaliar(pacote,p.selecao);comparadas++;
      if(seguro(selecao,selecaoBase)&&(valor(selecao)>score||valor(selecao)===score&&historico?.promover)){melhor=pacote;score=valor(selecao);}
    }
    const testeBase=avaliar(base,p.teste),teste=avaliar(melhor,p.teste);
    if(!seguro(teste,testeBase)||valor(teste)<=valor(testeBase))return {...out,estado:'rejeitada_no_teste',comparadas};
    return {personalizada:true,estado:'prevista_validada_no_escopo',pacote:melhor,alteracoes:alteracoesPacote(base,melhor),comparadas,
      expectativa:{antes:valor(testeBase),depois:valor(teste),ganho:valor(teste)-valor(testeBase),unidade:'previsao_conjunta'},
      validacao:{testes_abertos:1,treino:p.treino.length,selecao:p.selecao.length,teste:p.teste.length},
      limites:['Mudança de dano pode alterar duração e pressão; benefício precisa de confirmação posterior.']};
  }
  return {dividir,alteracoes,candidatas,buscar,alteracoesPacote,buscarPacote};
})();
if(typeof module!=='undefined')module.exports=HuntPersonalizacao;
