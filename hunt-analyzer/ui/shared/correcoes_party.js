/* Declarações do dono por sessão; nenhuma cura transforma alguém em aliado. */
const HuntCorrecoesParty=(()=>{
  const key=n=>String(n).replace(/\s+/g,'').toLowerCase();
  function corrigir(r,declaracoes){
    const d=declaracoes?.[r?.sessao];
    if(d?.origem!=='usuario'||!Array.isArray(d.aliados)||!d.aliados.length)return r;
    const k=structuredClone(r),aliados=new Set(d.aliados.map(key));
    k.party=[...new Set([...(k.party||[]),...d.aliados])];
    const releitura=d.relatorio_releitura;
    if(releitura?.origem==='releitura_paineis_e_console'&&releitura.provas?.length&&releitura.estatisticas_party){
      k.party_paineis=releitura.party_paineis;
      k.dano_hunt_observado=releitura.dano_hunt_observado;
      k.estatisticas_party=structuredClone(releitura.estatisticas_party);
    }
    k.correcao_party=d;
    k.episodios_reclassificados=k.episodios_reclassificados||[];
    k.episodios=(k.episodios||[]).filter(e=>{
      const nomes=Object.keys(e.dano?.fora||{});
      if(!nomes.length)return true;
      const original=structuredClone(e);
      for(const nome of nomes)if(aliados.has(key(nome))){
        e.dano.party=e.dano.party||{};
        e.dano.party[nome]=e.dano.fora[nome];delete e.dano.fora[nome];
      }
      if(Object.keys(e.dano.fora).length)return true;
      if(!k.episodios_reclassificados.some(a=>a.id===e.id))
        k.episodios_reclassificados.push({...original,motivo_reclassificacao:'aliado_confirmado_pelo_usuario'});
      return false;
    });
    for(const ep of d.episodios_recuperados||[]){
      if(ep.origem!=='releitura_server_log'||!ep.prova_inicio?.sha256_log_original||!Object.keys(ep.dano?.fora||{}).length)continue;
      if(Object.keys(ep.dano.fora).some(n=>aliados.has(key(n))||k.party.some(p=>key(p)===key(n))))continue;
      const golpes=new Set((ep.golpes_observados||[]).map(e=>e.id));
      if(k.episodios.some(e=>e.id===ep.id||(e.golpes_observados||[]).some(g=>golpes.has(g.id))||
        e.inicio<=ep.inicio&&(e.fim||e.ultimo_evento?.ts||e.inicio)>=ep.inicio&&Object.keys(ep.dano.fora||{}).some(n=>n in ep.dano.fora)))continue;
      k.episodios.push(structuredClone(ep));
    }
    const ocultos=new Set(d.episodios_baixo_impacto||[]);
    k.episodios_ocultos=k.episodios.filter(e=>ocultos.has(e.id));
    k.episodios=k.episodios.filter(e=>!ocultos.has(e.id));
    k.episodios.sort((a,b)=>String(a.inicio||'').localeCompare(String(b.inicio||'')));
    return k;
  }
  function aplicar(dados,declaracoes){
    if(!dados?.ks)return dados;
    if(dados.ks.sessoes){
      dados.ks.sessoes=dados.ks.sessoes.map(r=>corrigir(r,declaracoes));
      dados.ks.episodios=dados.ks.sessoes.flatMap(r=>r.episodios||[]);
      if(dados.ks.sessoes.length===1&&dados.ks.sessoes[0].correcao_party)
        dados.ks.estatisticas_party=dados.ks.sessoes[0].estatisticas_party;
    }else dados.ks=corrigir(dados.ks,declaracoes);
    const confirmado=declaracoes?.[dados.estado?.sessao]?.contexto_confirmado;
    if(confirmado?.origem==='usuario'&&Number.isInteger(confirmado.hazard)&&confirmado.hazard>=0&&confirmado.provas?.length)
      dados.estado.hazard_confirmado=structuredClone(confirmado);
    const estudos=declaracoes?.[dados.estado?.sessao]?.estudos_rtc;
    if(dados.estado&&Array.isArray(estudos))dados.estado.estudos_rtc=structuredClone(estudos);
    const curas=declaracoes?.[dados.estado?.sessao]?.sugestoes_cura;
    if(dados.estado&&Array.isArray(curas))dados.estado.sugestoes_cura=structuredClone(curas);
    if(dados.ks.correcao_party&&dados.sessao)dados.sessao.pt=`pt x${dados.ks.party.length}`;
    return dados;
  }
  function lista(sessoes,declaracoes){
    return sessoes.map(s=>{
      const resumo=declaracoes?._historico?.[s.id];
      if(typeof s.tem_ks==='boolean'||!s.fechada||resumo?.origem!=='relatorios_ks_efetivos')return s;
      return {...s,pt:resumo.pt||s.pt,tem_ks:resumo.tem_ks===true,ks_episodios:resumo.ks_episodios};
    });
  }
  return {corrigir,aplicar,lista};
})();
if(typeof module!=='undefined')module.exports=HuntCorrecoesParty;
