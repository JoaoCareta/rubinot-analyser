importScripts('/ui/rtc.js?v=20261012_elementos_dry_v1','/ui/roda_motor.js?v=20261012_rtc_roda_ml_v1','/ui/temporal.js?v=20261012_rtc_roda_ml_v1','/ui/integracao.js?v=20261012_rtc_roda_ml_v1');
onmessage=e=>{try {const {chave,magias,cenario,opcoes,modo,catalogo,total,objetivo,tier}=e.data;
  const resultado=modo==='rtc_independente'?HuntIntegracao.calcularRTC(catalogo,magias,e.data.contexto,opcoes):modo==='roda_independente'?HuntIntegracao.calcularRoda(catalogo,magias,e.data.contexto,objetivo,tier,opcoes):modo==='integrado'?HuntIntegracao.calcular(catalogo,magias,e.data.contexto,objetivo,e.data.estrategia,tier,opcoes):modo==='roda'?HuntRodaMotor.otimizar(catalogo,total,objetivo,tier,magias,cenario,opcoes):HuntRTC.otimizar(magias,[],cenario,opcoes);
  postMessage({chave,resultado});
} catch(erro) {postMessage({chave:e.data.chave,erro:erro.message});}};
