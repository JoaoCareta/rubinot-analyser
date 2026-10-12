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
function rtcImagem(m,classe='dano-icone') {const img=el('img',classe);img.src=m.imagem;img.alt=m.nome;img.width=38;img.height=38;return img;}
function rtcBotao(texto,acao) {const b=el('button','rtc-acao',texto);b.type='button';b.onclick=acao;return b;}
function rtcDetalhes(titulo) {const d=el('details','rtc-detalhes');d.append(el('summary',null,titulo));return d;}
function rtcUrlDano() {const q=new URLSearchParams(location.search);q.set('dano','');if(q.get('h')==='')q.delete('h');return '/hunt?'+q;}
function rtcVoltas() {return recorte==='volta' && voltaEscolhida()?[voltaEscolhida()]:voltasVisiveis();}
function rtcIdentidade() {return {char:D?.sessao?.char||D?.estado?.char||rtcObservado.char||'',sessao:D?.estado?.sessao||D?.sessao?.origem||'',historico:!!HIST};}
async function rtcCarregarObservacao(identidade){
  const ler=async parametros=>{const r=await fetch('/api/configuracoes?'+new URLSearchParams(parametros),{cache:'no-store'});if(!r.ok)throw Error('Configuração indisponível.');return r.json();};
  const [historica,atual]=await Promise.all([
    ler({char:identidade.char,sessao:identidade.sessao,historico:String(identidade.historico)}),
    identidade.historico?ler({char:identidade.char}).catch(()=>null):null
  ]);
  // Preserva os snapshots usados pelos selos de leitura da sessão.
  return identidade.historico?{...historica,referencia_atual:atual?{
    char:atual.char,rtc:{vocacao:atual.rtc?.vocacao},roda:atual.roda,pontos:atual.pontos,
    modelo:{combate_ml:atual.modelo?.combate_ml}
  }:null}:historica;
}
function iniciaPainelDano() {
  if(!RTC_DANO)return;
  document.body.classList.add('modo-dano');document.title='Magias e elementos · Hunt Analyzer';
  const pagina=el('section','dano-pagina');pagina.append(el('div','rotulo','— potência, RTC e roda'),el('h1',null,'Magias e elementos'));
  const campos=el('div','dano-sessao'),label=el('label',null,'Sessão da hunt'),select=el('select');
  const vivo=el('option',null,'Hunt atual');vivo.value='';select.append(vivo);label.append(select);campos.append(label);pagina.append(campos);
  const contexto=el('p','sub');contexto.id='danoContexto';pagina.append(contexto);
  pagina.append(document.querySelector('section.filtros'),$('#recomendacaoMagias'),$('#otimizacaoRTC'));document.querySelector('main').prepend(pagina);
  select.onchange=()=>{const q=new URLSearchParams();q.set('dano','');if(select.value)q.set('h',select.value);location.href='/hunt?'+q;};
  fetch('/api/historico',{cache:'no-store'}).then(r=>r.json()).then(r=>{
    for(const s of r.sessoes||[]) {const o=el('option',null,`${s.hunt} · ${s.data||s.id} · ${s.char||''}`);o.value=s.id;select.append(o);}
    const h=new URLSearchParams(location.search).get('h');if(h && ![...select.options].some(o=>o.value===h)){const o=el('option',null,h);o.value=h;select.append(o);}select.value=h||'';
  }).catch(()=>{contexto.textContent='Não foi possível carregar as sessões.';});
}
function rtcClasses() {
  const grupo=el('div','rtc-classes');grupo.setAttribute('aria-label','Vocação consultada');
  for(const [voc,nome] of [['MS','Master Sorcerer'],['ED','Elder Druid']]) {
    const b=rtcBotao('',()=>{rtcVoc=voc;if(!HuntRTC.categoriasDe(voc).includes(rtcCategoria))rtcCategoria=voc==='MS'?'Beam':'Twin';rtcAssinatura='';renderMagiasRTC();});
    b.setAttribute('aria-pressed',String(voc===rtcVoc));
    const img=el('img','rtc-classe-icone');img.src=`/ui/voc_${voc.toLowerCase()}.png`;img.alt='';img.width=44;img.height=44;
    const texto=el('span');texto.append(el('strong',null,voc),el('small',null,nome));b.append(img,texto);grupo.append(b);
  }return grupo;
}
function rtcBarras(p) {
  const {linhas,max}=p,bloco=el('div','rtc-barras');
  bloco.append(el('h3','rotulo','Elementos que a hunt recebe'));
  if(!p.total){bloco.append(el('p','nota','Aguardando criaturas nas voltas fechadas.'));return bloco;}
  for(const r of linhas) {
    const barra=el('div','rtc-barra'),fill=el('div','rtc-barra-fill'),texto=el('div','rtc-barra-texto');
    const valor=r.valor,distancia=valor==null?0:Math.min(1,Math.abs(valor-100)/100);
    fill.style.width=(valor==null?0:valor/max*100)+'%';
    fill.style.background=valor==null||valor===100?'#454752':valor>100?`hsl(143 35% ${30-12*distancia}%)`:`hsl(0 40% ${32-13*distancia}%)`;
    const referencia=el('i','rtc-barra-ref');referencia.style.left=(100/max*100)+'%';
    const nome=el('span','rtc-elemento-nome');
    const icones={'físico':'fisico.png','fogo':'fogo.png','terra':'terra.png','energia':'energia.png','gelo':'gelo.png','sagrado':'sagrado.png','morte':'morte.png'};
    if(icones[r.e]){const icone=el('img','rtc-elemento-icone');icone.src='/ui/elemento_'+icones[r.e];icone.alt='';icone.width=18;icone.height=18;nome.append(icone);}
    nome.append(el('span',null,r.e));
    texto.append(nome,el('strong',null,valor==null?'Não lido':rtcFmt(valor)+'%'));
    barra.append(fill,referencia,texto);bloco.append(barra);
  }
  if(p.peso<p.total)bloco.append(el('p','nota',`População comum: ${rtcFmt(p.total?p.peso/p.total*100:0)}% das criaturas. Elementos incompletos permanecem pendentes.`));
  return bloco;
}
function rtcTabela(resultados) {
  const rolagem=el('div','rtc-rolagem'),t=el('table','rtc-tabela'),head=el('thead'),cab=el('tr');
  ['Categoria / magia','Base Power','Base ajustada','Cooldown','Usos','Total'].forEach(v=>cab.append(el('th',null,v)));head.append(cab);t.append(head);
  const body=el('tbody');for(const [cat,r] of Object.entries(resultados))for(const m of r.linhas){
    const tr=el('tr'),nome=el('td');if(m.imagem)nome.append(rtcImagem(m));nome.append(el('span',null,rtcNome(m)),el('small',null,cat));tr.append(nome);
    [m.bp,m.ajustado,m.cd,m.usos,m.total].forEach((v,i)=>{const td=el('td',i===4&&r.vencedoras.includes(HuntRTC.id(m))?'rtc-vencedor':'',rtcFmt(v)+(i===2?' s':''));tr.append(td);});body.append(tr);
  }t.append(body);rolagem.append(t);return rolagem;
}
function renderMagiasRTC() {
  if(!D)return;
  const bloco=$('#recomendacaoMagias'),opt=$('#otimizacaoRTC'),especies=especiesDe(rtcVoltas());
  const identidade=rtcIdentidade(),obsChave=JSON.stringify(identidade);
  if(obsChave!==rtcObsChave && obsChave!==rtcObsSolicitada){
    rtcObsSolicitada=obsChave;rtcObservado={};
    rtcCarregarObservacao(identidade)
      .then(d=>{if(rtcObsSolicitada!==obsChave)return;rtcObservado=d;rtcObsChave=obsChave;rtcAssinatura='';renderMagiasRTC();}).catch(()=>{rtcObsSolicitada='';});
  }
  const assinatura=JSON.stringify([especies,rtcVoc,rtcAlvo,rtcCategoria,rtcDuracao,recorte,selN,identidade,[rtcObservado.rtc,rtcObservado.cura,rtcObservado.roda,rtcObservado.pontos,rtcObservado.contexto,rtcObservado.modelo,rtcObservado.referencia_atual],Object.entries(CATALOGO).map(([n,m])=>[n,m.toma])]);
  if(assinatura===rtcAssinatura)return;
  const abertos=new Set([bloco,opt].flatMap(p=>[...p.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent)));
  const restaura=()=>{for(const p of [bloco,opt])for(const d of p.querySelectorAll('details'))if(abertos.has(d.querySelector('summary')?.textContent))d.open=true;};
  rtcAssinatura=assinatura;rtcGeracao++;rtcWorker?.terminate();rtcWorker=null;rtcCancelaCalculos();bloco.replaceChildren();opt.replaceChildren();
  // Um cálculo, duas instâncias do mesmo componente, com o mesmo recorte.
  const elementos=HuntRTC.elementos(especies,CATALOGO);
  $('#elementosHunt')?.replaceChildren(rtcBarras(elementos));
  if(RTC_DANO)$('#danoContexto').textContent=[D.sessao?.hunt,identidade.char,D.sessao?.data,recorte==='volta'?`Volta ${voltaEscolhida()?.n||'—'}`:`${rtcVoltas().length} voltas`].filter(Boolean).join(' · ');
  bloco.append(rtcClasses(),el('p','nota',`Vocação consultada: ${rtcVoc} · personagem observado: ${identidade.char||'não lido'}. A consulta não altera o perfil real.`));
  if(!RTC_CATALOGO){bloco.append(el('p','nota','Carregando o catálogo de magias…'));return;}
  if(!Object.keys(especies).length){bloco.append(el('p','nota','Aguardando criaturas nas voltas fechadas. Você também pode escolher uma sessão no histórico.'));renderIntegradoRTC(opt);restaura();return;}
  const amostra=especies;bloco.append(rtcBarras(elementos));
  const resultados=Object.fromEntries(HuntRTC.categoriasDe(rtcVoc).map(c=>[c,HuntRTC.compararCategoria(RTC_CATALOGO.magias,amostra,CATALOGO,rtcVoc,c,rtcDuracao)]));
  const tabs=el('div','rtc-tabs');tabs.setAttribute('aria-label','Categorias');
  for(const [c,r] of Object.entries(resultados)){
    const b=rtcBotao('',()=>{rtcCategoria=c;renderMagiasRTC();[...$('#recomendacaoMagias').querySelectorAll('.rtc-tabs button')].find(x=>x.getAttribute('aria-label')===c)?.focus();});
    b.setAttribute('aria-label',c);b.title=c;b.setAttribute('aria-pressed',String(c===rtcCategoria));
    const m=r.linhas.find(m=>r.vencedoras.includes(HuntRTC.id(m)));
    if(m?.imagem)b.append(rtcImagem(m,'rtc-tab-icone'));else b.append(el('span','rtc-tab-icone','—'));
    const nome=el('span','rtc-tab-nome',c);b.append(nome);tabs.append(b);
  }
  const r=resultados[rtcCategoria],res=el('div','rtc-comparativo');res.setAttribute('aria-live','polite');
  res.append(tabs,el('div','rotulo',`${RTC_DANO?'Tabela limpa':'Categoria em foco'} · ${rtcCategoria}`),el('p','nota',`Potência comparativa em ${rtcDuracao} s · um alvo comum`));
  if(!r.linhas.length)res.append(el('p','nota','Categoria indisponível no catálogo desta vocação.'));
  const opcoes=el('div','rtc-opcoes');
  for(const m of r.linhas.slice(0,2)){const card=el('article','rtc-opcao'),venceu=r.vencedoras.includes(HuntRTC.id(m));
    card.append(el('div','rtc-recomendado',venceu?(r.empate?'Empate no cenário':'Recomendado no cenário'):''));
    if(m.imagem)card.append(rtcImagem(m));card.append(el('strong',null,rtcNome(m)),el('small',null,m.elemento));
    card.append(el('div',venceu?'rtc-total rtc-vencedor':'rtc-total',rtcFmt(m.total)),el('small',null,'potência na janela'),
      el('p','nota',`${rtcFmt(m.ajustado)} por uso`));
    const observado=rtcObservado.rtc?.vocacao===rtcVoc?rtcObservado.rtc:null;
    const selo=HuntRTC.conferirRTC(m,null,observado);card.append(el('span',selo.estado==='No RTC'?'rtc-selo':'nota',selo.estado));opcoes.append(card);
  }res.append(opcoes);
  if(r.peso<r.total)res.append(el('p','nota',`Cobertura comum: ${rtcFmt(r.total?r.peso/r.total*100:0)}%. Sem vencedora definitiva. Faltam: ${r.faltam.join(', ')}.`));
  if(r.linhas.length&&r.linhas.every(m=>m.total===0))res.append(el('p','nota','Todos os elementos desta categoria são imunes na população lida. Sem recomendação.'));
  bloco.append(res);
  if(r.linhas.length>2)res.append(el('p','nota rtc-comparativo-nota',`${r.linhas.length} opções comparadas. As duas melhores estão acima.`));
  renderIntegradoRTC(opt);restaura();
}
Promise.all([fetch('/ui/magias.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}),fetch('/ui/roda_catalogo.json',{cache:'no-store'}).then(r=>r.ok?r.json():{})])
  .then(([magias,roda])=>{RTC_CATALOGO=magias;RTC_RODA=roda;rtcAssinatura='';renderMagiasRTC();})
  .catch(()=>{document.querySelector('#recomendacaoMagias').textContent='Catálogo indisponível. Reabra a tela para tentar novamente.';});
setInterval(async()=>{
  if(!D)return;const identidade=rtcIdentidade(),chave=JSON.stringify(identidade);
  try{const d=await rtcCarregarObservacao(identidade);if(chave!==JSON.stringify(rtcIdentidade()))return;
    const relevantes=x=>JSON.stringify([x.char,x.rtc,x.cura,x.roda,x.pontos,x.contexto,x.modelo,x.referencia_atual]);const mudou=relevantes(d)!==relevantes(rtcObservado);rtcObservado=d;rtcObsChave=chave;if(mudou){rtcAssinatura='';renderMagiasRTC();}
  }catch{}
},5000);
