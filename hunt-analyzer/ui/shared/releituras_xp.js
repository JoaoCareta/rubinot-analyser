const HuntReleiturasXP=(()=>{
  function aplicar(dados,registros){
    const id=dados.estado?.sessao||dados.sessoes_origem?.[0];
    const revisao=registros?.[id];if(!revisao)return dados;
    dados.voltas=(dados.voltas||[]).map(v=>{
      const r=revisao.voltas?.[`${v.n}|${v.ini}|${v.fim}`];
      if(r?.xp_origem!=='XP Analyser'||!r.provas?.length||!Number.isInteger(r.xp_raw)||r.xp_raw<0)return v;
      return {...v,xp_raw:r.xp_raw,xp_origem:'XP Analyser',xp_raw_15min:r.xp_raw_15min??null,xp_releitura:true};
    });
    return dados;
  }
  return {aplicar};
})();
if(typeof module!=='undefined')module.exports=HuntReleiturasXP;
