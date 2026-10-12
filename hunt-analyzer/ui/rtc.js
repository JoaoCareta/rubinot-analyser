/* Unidade: Base Power ajustada, nunca HP. Regras temporais são referências declaradas. */
const HuntRTC = (() => {
  const numero = v => typeof v === 'number' && Number.isFinite(v) && v >= 0;
  const id = m => m.id || m.nome;
  const categoriasDe = v => ['Runa', 'Área', v === 'MS' ? 'Beam' : 'Twin', 'UE', 'Single'];
  function categoria(m) {
    if (m.tipo === 'cura' || m.tipo==='suporte' || m.nome === 'Ice Wave' || m.palavras === 'exevo frigo hur' || m.periodico || m.nome === 'Death Echo') return null;
    if (m.runa) return m.alvos === 1 ? 'Single' : 'Runa';
    if(m.nome?.endsWith('Beam'))return 'Beam';
    return ({ue:'UE', bursts:'Twin', beams:'Beam'})[m.familia] || (m.alvos === 1 ? 'Single' : 'Área');
  }
  function populacao(especies, catalogo, elementos) {
    const presentes = Object.entries(especies).filter(([,n]) => numero(n) && n > 0);
    const completas = Object.fromEntries(presentes.filter(([nome]) => elementos.every(e => numero(catalogo[nome]?.toma?.[e]))));
    return {completas, total: presentes.reduce((s,[,n]) => s+n,0), peso: Object.values(completas).reduce((s,n) => s+n,0),
      faltam: presentes.filter(([n]) => !Object.hasOwn(completas,n)).map(([n]) => n)};
  }
  function resistencia(especies, catalogo, elemento) {
    let peso=0, soma=0, total=0;
    for (const [nome,n] of Object.entries(especies)) {
      if (!numero(n) || !n) continue;
      total+=n; const r=catalogo[nome]?.toma?.[elemento];
      if (numero(r)) { peso+=n; soma+=n*r; }
    }
    return {valor: peso ? soma/peso : null, peso, total};
  }
  function elementos(especies,catalogo){
    const nomes=['físico','fogo','terra','energia','gelo','sagrado','morte'];
    for(const nome of Object.keys(especies))for(const e of Object.keys(catalogo[nome]?.toma||{}))if(e!=='cura'&&!nomes.includes(e))nomes.push(e);
    const p=populacao(especies,catalogo,nomes.filter(e=>Object.keys(especies).some(n=>numero(catalogo[n]?.toma?.[e]))));
    const linhas=nomes.map(e=>({e,...resistencia(p.completas,catalogo,e)})).sort((a,b)=>(b.valor??-1)-(a.valor??-1));
    return {...p,linhas,max:Math.max(100,...linhas.map(r=>r.valor??0))};
  }
  const regras = m => numero(m.cd) && m.cd>0 && numero(m.grupo) && m.grupo>0;
  function simular(ordem, runas=[], cenario={alvos:1}, duracao=180) {
    if (!numero(duracao) || !duracao || !numero(cenario.alvos) || !cenario.alvos) throw Error('Cenário inválido');
    const candidatas=[...ordem,...runas].map((m,i)=>({...m,_ordem:i})).sort((a,b)=>(a.prioridade??a._ordem+1)-(b.prioridade??b._ordem+1)||a._ordem-b._ordem);
    if (candidatas.some(m => !regras(m) || !numero(m.ajustado))) throw Error('Potência ou cooldown desconhecido');
    if (candidatas.filter(m => categoria(m)==='Single').length>1) throw Error('Uma única opção Single por RTC');
    const pronta={}, grupo={}, casts={}, sequencia=[];
    const alvos = m => Math.min(cenario[id(m)] ?? cenario[m.nome] ?? cenario.alvos, m.alvos ?? Infinity);
    const elegivel = m => cenario.alvos >= (m.creatures || 1) && (cenario.mana_percent??100)>=(m.mana_percent??0) && alvos(m)>0;
    const prontaEm = m => Math.max(pronta[id(m)]||0, grupo[m.familia]||0);
    let t=0, score=0;
    while (t<duracao-1e-9) {
      const m=candidatas.find(m => elegivel(m) && prontaEm(m)<=t+1e-9);
      if (!m) {
        const proximo=Math.min(...candidatas.filter(elegivel).map(prontaEm));
        sequencia.push({t,fim:Math.min(duracao,proximo),espera:true});
        if (!Number.isFinite(proximo) || proximo>=duracao || proximo<=t) break;
        t=proximo; continue;
      }
      const potencia=m.ajustado*alvos(m); score+=potencia; casts[id(m)]=(casts[id(m)]||0)+1;
      sequencia.push({t,id:id(m),nome:m.nome,potencia,alvos:alvos(m)});
      pronta[id(m)]=t+m.cd;
      if(m.reduz_outros_cd>0)for(const outra of candidatas)if(!outra.runa&&id(outra)!==id(m)&&pronta[id(outra)]>t)pronta[id(outra)]=Math.max(t,pronta[id(outra)]-m.reduz_outros_cd);
      if (m.cd_compartilhado>0) grupo[m.familia]=t+m.cd_compartilhado;
      t+=m.grupo;
    }
    return {score,porSegundo:score/duracao,casts,sequencia,duracao};
  }
  function compararCategoria(magias, especies, catalogo, voc, cat, duracao=30) {
    const selecionadas=magias.filter(m => m.vocs.includes(voc) && categoria(m)===cat);
    const p=populacao(especies,catalogo,[...new Set(selecionadas.map(m => m.elemento))]);
    const linhas=selecionadas.map(m => {
      const r=resistencia(p.completas,catalogo,m.elemento);
      const ajustado=numero(m.bp) && r.valor!=null ? m.bp*r.valor/100 : null;
      const simulacao=ajustado!=null && regras(m) ? simular([{...m,ajustado}],[],{alvos:1},duracao) : null;
      return {...m,resistencia:r.valor,ajustado,simulacao,usos:simulacao?.casts[id(m)]??null,total:simulacao?.score??null};
    }).sort((a,b) => (b.total??-1)-(a.total??-1) || id(a).localeCompare(id(b)));
    const max=linhas[0]?.total;
    const vencedoras=p.peso>0 && p.peso===p.total && linhas.every(m => m.total!=null) && max>0
      ? linhas.filter(m => Math.abs(m.total-max)<1e-9).map(id) : [];
    return {...p,linhas,vencedoras,duracao,empate:vencedoras.length>1};
  }
  function comparar(magias,especies,catalogo,voc) {
    const ofensivas=magias.filter(m => m.vocs.includes(voc) && categoria(m));
    const p=populacao(especies,catalogo,[...new Set(ofensivas.map(m => m.elemento))]);
    return ofensivas.map(m => {const r=resistencia(p.completas,catalogo,m.elemento);
      return {...m,cobertura:p.total?p.peso/p.total:0,resistencia:r.valor,ajustado:numero(m.bp)&&r.valor!=null?m.bp*r.valor/100:null};});
  }
  function elegibilidade(m,ctx={}) {
    if (!categoria(m)) return {estado:'excluida',motivo:'Fora da comparação ofensiva'};
    if (numero(ctx.nivel) && ctx.nivel<m.nivel) return {estado:'impossivel',motivo:`Exige nível ${m.nivel}`};
    if (m.requer_roda && ctx.desbloqueios?.[id(m)]===false) return {estado:'impossivel',motivo:'Bloqueada na roda lida'};
    const p=[];
    if (!numero(ctx.nivel) && m.nivel>0) p.push('nível não lido');
    if (m.requer_roda && ctx.desbloqueios?.[id(m)]!==true) p.push('liberação na roda não lida');
    return {estado:p.length?'cenario':'confirmada',motivo:p.join(' · ')};
  }
  function otimizar(magias,runas,cenario,opcoes={}) {
    const slots=opcoes.slots??5, largura=opcoes.largura??48, duracao=opcoes.duracao??180;
    const capacidade=opcoes.capacidadeRTC;
    const todas=[...magias,...runas].filter(m => categoria(m) && regras(m) && numero(m.ajustado));
    let feixe=[{ordem:[],score:0}], melhor=null, comparadas=0;
    for (let d=0;d<Math.min(slots,todas.length);d++) {
      const novos=[];
      for (const ramo of feixe) for (const m of todas) {
        if (ramo.ordem.some(x => id(x)===id(m))) continue;
        if (capacidade && ramo.ordem.filter(x=>!!x.runa===!!m.runa).length >= (m.runa?capacidade.runas:capacidade.magias)) continue;
        if (categoria(m)==='Single' && ramo.ordem.some(x => categoria(x)==='Single')) continue;
        const ordem=[...ramo.ordem,m], r=simular(ordem,[],cenario,duracao); comparadas++;
        const item={...r,ordem}; novos.push(item);
        if (!melhor || r.score>melhor.score+1e-9) melhor=item;
      }
      novos.sort((a,b) => b.score-a.score || a.ordem.map(id).join().localeCompare(b.ordem.map(id).join()));
      feixe=novos.slice(0,largura); if (!feixe.length) break;
    }
    return melhor ? {...melhor,comparadas,alcance:`${todas.length} candidatas; busca em feixe de ${largura} ordens por nível; ${capacidade?`até ${capacidade.magias} magias e ${capacidade.runas} runas (interface de referência)`:`até ${slots} slots assumidos`}. Máximo global não comprovado.`}
      : {erro:'Sem candidatas calculáveis.'};
  }
  function conferirRTC(m,sugerida,observado) {
    const slot=observado?.slots?.find(s => s.id===id(m) && (!s.tipo || s.tipo===(m.runa?'runa':'magia')));
    if (!slot) return {estado:'Não lido',diferencas:[]};
    if (slot.atual===false) return {estado:'No RTC · leitura anterior',diferencas:[],pendentes:['leitura atual']};
    const diferencas=[],pendentes=[];
    for (const k of ['slot','prioridade','creatures',...(sugerida && Object.hasOwn(sugerida,'mana_percent')?['mana_percent']:[])]) {
      if (sugerida?.[k]==null || slot[k]==null) pendentes.push(k);
      else if (sugerida[k]!==slot[k]) diferencas.push(`${k}: ${slot[k]} → ${sugerida[k]}`);
    }
    return {estado:diferencas.length?'Ajustar':!pendentes.length?(observado.aplicado_confirmado?'Conforme sugestão':'Campos conferem · aplicação pendente'):'No RTC',diferencas,pendentes};
  }
  function viabilidadeRoda(cat,total,objetivo,tier) {
    const orcamento=numero(total)?Math.max(0,total-3):null, regra=cat?.cenarios?.find(c => c.objetivo===objetivo && c.tier===tier);
    if (orcamento==null || !cat?.validado_rubinot || !regra?.validado || !numero(regra.custo_minimo))
      return {estado:'A validar',orcamento,motivo:'Total, caminhos, requisitos ou tier sem validação.'};
    return {estado:orcamento<regra.custo_minimo?'Pontos insuficientes':'Cabe nos pontos',orcamento,regra};
  }
  function validarDistribuicao(cat,pontos,total) {
    if (!cat?.validado_rubinot || !numero(total)) return {ok:false,erros:['Catálogo ou total a validar']};
    const erros=[],fatias=cat.fatias||[],mapa=Object.fromEntries(fatias.map(f => [f.id,f])); let soma=0;
    if(!fatias.length || fatias.some(f=>!Number.isInteger(f.limite)||f.limite<0 ||
      (f.conexoes||[]).some(x=>!mapa[x]) || (f.requisitos||[]).some(r=>!mapa[r.id]||!Number.isInteger(r.pontos)||r.pontos<0)))
      return {ok:false,erros:['Limites ou grafo incompletos']};
    for (const [chave,n] of Object.entries(pontos)) {
      const f=mapa[chave];
      if (!f || !Number.isInteger(n) || n<0 || n>f.limite) {erros.push(`Limite inválido: ${chave}`);continue;}
      soma+=n;
      if (n>0 && (f.requisitos||[]).some(r => (pontos[r.id]||0)<r.pontos)) erros.push(`Pré-requisito ausente: ${chave}`);
    }
    const conectadas=new Set(fatias.filter(f => f.raiz && (pontos[f.id]||0)>0).map(f => f.id)); let mudou=true;
    while (mudou) { mudou=false; for (const f of fatias) if ((pontos[f.id]||0)>0 && !conectadas.has(f.id) && (f.conexoes||[]).some(x => conectadas.has(x) && pontos[x]===mapa[x].limite)) {conectadas.add(f.id);mudou=true;} }
    for (const [f,n] of Object.entries(pontos)) if (n>0 && !conectadas.has(f)) erros.push(`Fatia desconectada: ${f}`);
    if (soma>Math.max(0,total-3)) erros.push('Reserva mínima de 3 pontos não respeitada');
    return {ok:!erros.length,erros,investidos:soma,livres:total-soma};
  }
  function otimizarRoda(cat,total,objetivo,tier,avaliar) {
    const v=viabilidadeRoda(cat,total,objetivo,tier);
    if(v.estado!=='Cabe nos pontos')return {...v,alternativas:[],avaliadas:0};
    // O catálogo precisa oferecer caminhos/distribuições auditados. Nada de inventar grafo.
    if(!Array.isArray(v.regra.distribuicoes)||!v.regra.distribuicoes.length)
      return {...v,estado:'A validar',motivo:'Distribuições e efeitos compatíveis ainda não catalogados.',alternativas:[],avaliadas:0};
    const resultados=[];let avaliadas=0;
    for(const distribuicao of v.regra.distribuicoes){
      if(!validarDistribuicao(cat,distribuicao.pontos,total).ok)continue;
      if(!distribuicao.tiers_ativados?.includes(tier))continue;
      if(!distribuicao.efeitos_validados)continue;
      const metricas=avaliar(distribuicao);avaliadas++;
      if(!metricas || Object.values(metricas).some(x=>!numero(x)))continue;
      resultados.push({...distribuicao,metricas});
    }
    // Cura própria/party sem pesos: conservar alternativas não dominadas.
    const alternativas=resultados.filter(a=>!resultados.some(b=>b!==a &&
      Object.keys(a.metricas).every(k=>b.metricas[k]>=a.metricas[k]) &&
      Object.keys(a.metricas).some(k=>b.metricas[k]>a.metricas[k])));
    return {...v,estado:alternativas.length?'Calculado':'A validar',alternativas,avaliadas,
      alcance:'Melhores entre distribuições auditadas; inventário não filtra cenários. Máximo global não comprovado.'};
  }
  function diferencasRoda(atual,sugerida) {
    return Object.entries(sugerida).map(([fatia,pontos])=>{
      const n=atual[fatia];const delta=numero(n)?pontos-n:null;
      return {fatia,atual:n??null,sugerido:pontos,delta,acao:delta==null?'Não lido':delta>0?`Adicionar ${delta}`:delta<0?`Retirar ${-delta}`:'Manter'};
    });
  }
  function avaliarRoda(distribuicao,magias,objetivo,cenario,opcoes={}) {
    const e=distribuicao.efeitos;
    if(!e?.base_power_validado || !e?.condicionais_resolvidas)return null;
    const modificadas=magias.map(m=>{
      const multiplicador=e.bp_multiplicadores?.[id(m)]??1;
      if(!numero(multiplicador)||!numero(m.bp))return null;
      const bp=m.bp*multiplicador,ajustado=m.tipo==='cura'?bp:bp*m.resistencia/100;
      return {...m,bp,ajustado,cd:e.cooldowns?.[id(m)]??m.cd};
    }).filter(Boolean);
    if(objetivo==='dano'){
      const ofensivas=modificadas.filter(m=>categoria(m) && (!m.requer_roda || distribuicao.liberacoes?.[id(m)]===true));
      if(!ofensivas.length||ofensivas.some(m=>!numero(m.ajustado)||m.cobertura<1))return null;
      const r=otimizar(ofensivas,[],cenario,opcoes);return r.erro?null:{dano:r.score};
    }
    const curas=modificadas.filter(m=>m.tipo==='cura' && m.unidade==='Base Power' && numero(m.cd)&&m.cd>0&&numero(m.grupo)&&m.grupo>0);
    const propria=curas.filter(m=>m.destino==='propria'),party=curas.filter(m=>m.destino==='party');
    // Magia mista exige divisão validada; não duplicar Mass Healing nas duas métricas.
    if(!propria.length||!party.length||curas.some(m=>m.destino==='party_e_propria'))return null;
    const melhor=lista=>Math.max(...lista.map(m=>simular([m],[],{alvos:1},opcoes.duracao??180).score));
    return {cura_propria:melhor(propria),cura_party:melhor(party)};
  }
  return {id,numero,categoriasDe,categoria,populacao,resistencia,elementos,compararCategoria,comparar,simular,elegibilidade,otimizar,conferirRTC,viabilidadeRoda,validarDistribuicao,otimizarRoda,diferencasRoda,avaliarRoda};
})();
if (typeof module!=='undefined') module.exports=HuntRTC;
