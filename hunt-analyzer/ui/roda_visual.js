/* Perímetros do catálogo validado, nunca setores ilustrativos ou inferência por cor. */
const HuntRodaVisual=(()=>{
  const svg=(tag,atributos={})=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(atributos))e.setAttribute(k,v);return e;};
  function montar(catalogo,pontos,total,atual={},prova=null){
    const validacao=HuntRTC.validarDistribuicao(catalogo,pontos,total);
    if(!validacao.ok)return {erro:validacao.erros.join(' · ')};
    if(!catalogo.viewBox||catalogo.fatias.some(f=>!f.perimetro||!f.caixa||!f.direcao_validada))return {erro:'Geometria e direção do preenchimento a validar.'};
    const raiz=document.createElement('div'),roda=svg('svg',{viewBox:catalogo.viewBox,role:'img','aria-label':'Distribuição calculada da roda'}),defs=svg('defs');
    roda.append(defs);
    roda.style.maxWidth='560px';roda.style.width='100%';roda.style.background='#11141b';
    const linhas=document.createElement('div'),elementos={},detalhes=document.createElement('details'),titulo=document.createElement('summary');
    titulo.textContent='Pontos por casa e diferenças';detalhes.append(titulo,linhas);detalhes.className='rtc-detalhes';
    const focar=id=>{for(const [chave,node] of Object.entries(elementos))node.setAttribute('stroke-width',chave===id?'5':'2');};
    for(const [i,f] of catalogo.fatias.entries()){
      const n=pontos[f.id]||0,[x,y,w,h]=f.caixa,clip=svg('clipPath',{id:`roda_fatia_${i}`});clip.append(svg('path',{d:f.perimetro}));defs.append(clip);
      if(n>0){const altura=h*n/f.limite;
        roda.append(svg('rect',{x,y:f.preenchimento==='cima_para_baixo'?y:y+h-altura,width:w,height:altura,fill:'#a582c7','fill-opacity':'.38','clip-path':`url(#roda_fatia_${i})`}));}
      const borda=svg('path',{d:f.perimetro,fill:'transparent',stroke:n>0?'#a582c7':'#ffffff22','stroke-width':2,tabindex:0,role:'button','aria-label':`${f.nome||f.id}: ${n} de ${f.limite} pontos`});
      borda.onclick=()=>focar(f.id);borda.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();focar(f.id);}};
      elementos[f.id]=borda;roda.append(borda);
      const title=svg('title');title.textContent=`${f.id} · ${f.nome}: ${n}/${f.limite}`;borda.append(title);
      // Ícones ficam sobre o preenchimento; suas coordenadas pertencem ao mesmo catálogo.
      if(f.icone && f.icone_caixa){const [ix,iy,iw,ih]=f.icone_caixa;roda.append(svg('image',{href:f.icone,x:ix,y:iy,width:iw,height:ih}));}
      if(f.icone_caixa){const [ix,iy,iw,ih]=f.icone_caixa,txt=svg('text',{x:ix+iw/2,y:iy+ih+10,'text-anchor':'middle',fill:'#ead3f9','font-size':9,'font-family':'monospace','pointer-events':'none'});txt.textContent=`${n}/${f.limite}`;roda.append(txt);}
    }
    for(const d of HuntRTC.diferencasRoda(atual,pontos)){
      if(!d.sugerido&&!d.atual)continue;
      const f=catalogo.fatias.find(f=>f.id===d.fatia),b=document.createElement('button');b.className='rtc-acao';
      b.textContent=`${f.id} · ${f.nome||d.fatia} · ${d.atual??'Não lido'} → ${d.sugerido} / ${f.limite} · ${d.acao}`;b.onclick=()=>focar(d.fatia);linhas.append(b);
    }
    raiz.append(roda);return {elemento:raiz,validacao};
  }return {montar};
})();
