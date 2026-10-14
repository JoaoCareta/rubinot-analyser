importScripts('/ui/rtc.js?v=20261012_elementos_dry_v1','/ui/roda_motor.js?v=20261014_rodas_objetivos','/ui/temporal.js?v=20261014_feedback_cura','/ui/personalizacao.js?v=20261012','/ui/integracao.js?v=20261014_rodas_objetivos');
onmessage=e=>{try {const {chave,magias,cenario,opcoes,modo,catalogo,total,objetivo,tier}=e.data;
  if(modo==='rodas_preparadas'){
    for(const o of e.data.opcoes_roda){try{postMessage({id:o.id,resultado:HuntIntegracao.calcularRoda(catalogo,magias,e.data.contexto,o.objetivo,o.tier,{...opcoes,modo_vida:o.modo})});}catch(erro){postMessage({id:o.id,erro:erro.message});}}
    postMessage({fim:true});return;
  }
  const resultado=modo==='rtc_independente'?HuntIntegracao.calcularRTC(catalogo,magias,e.data.contexto,opcoes):modo==='roda_independente'?HuntIntegracao.calcularRoda(catalogo,magias,e.data.contexto,objetivo,tier,opcoes):modo==='integrado'?HuntIntegracao.calcular(catalogo,magias,e.data.contexto,objetivo,e.data.estrategia,tier,opcoes):modo==='roda'?HuntRodaMotor.otimizar(catalogo,total,objetivo,tier,magias,cenario,opcoes):HuntRTC.otimizar(magias,[],cenario,opcoes);
  postMessage({chave,resultado});
} catch(erro) {postMessage({chave:e.data.chave,erro:erro.message});}};
