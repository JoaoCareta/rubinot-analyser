/* Histórico factual independente do planejamento. Nenhum estado de modelo é renderizado. */
(() => {
  const id=new URLSearchParams(location.search).get('h');
  if(!id)return;
  const painel=document.getElementById('historicoCuras');
  painel.hidden=false;
  const {el}=HuntUI,conteudo=document.getElementById('historicoCurasConteudo'),totais=document.getElementById('historicoCurasResumo');
  const fmt=n=>n==null?'Sem leitura':n.toLocaleString('pt-BR',{maximumFractionDigits:2})+'%';
  const duracao=t=>{
    if(t==null)return '—';
    if(t>0&&t<1)return '< 1 s';
    const s=Math.floor(t),h=Math.floor(s/3600),m=Math.floor(s/60)%60;
    return [h?`${h} h`:null,m?`${m} min`:null,`${s%60} s`].filter(Boolean).join(' ');
  };
  const faixa=v=>v.leituras?`${fmt(v.minima)} – ${fmt(v.maxima)}`:'Sem leitura de vida';
  function magia(nome){
    const box=el('span','curas-magia'),img=el('img');
    img.src=nome==='Sio'?'/ui/magia_heal_friend.png':'/ui/magia_nature_s_embrace.png';
    img.alt='';img.width=32;img.height=32;box.append(img,el('span',null,nome));return box;
  }
  function tabela(cabecalhos,linhas){
    const box=el('div','curas-tabela'),t=el('table'),head=el('thead'),tr=el('tr'),body=el('tbody');
    for(const texto of cabecalhos){const th=el('th');th.append(texto);th.scope='col';tr.append(th);}
    head.append(tr);for(const linha of linhas){const row=el('tr');for(const v of linha){const td=el('td');td.append(v);row.append(td);}body.append(row);}
    t.append(head,body);box.append(t);return box;
  }
  function desenhar(dados){
    conteudo.replaceChildren();totais.replaceChildren();
    const opcoes=dados.trechos.flatMap(t=>t.membros.filter(m=>m.sio>0||m.gran_sio>0).map(m=>({...m,sessao:t.sessao})));
    if(!opcoes.length){totais.append(el('p','nota','Ainda não há registros de cura por jogador nesta hunt.'));painel.querySelector('details').hidden=true;return;}
    const jogadores=new Map();
    for(const m of opcoes){const total=jogadores.get(m.nome)||{nome:m.nome,sio:0,gran_sio:0};total.sio+=m.sio;total.gran_sio+=m.gran_sio;jogadores.set(m.nome,total);}
    totais.append(tabela(['Jogador',magia('Sio'),magia('Gran sio')],[...jogadores.values()].map(m=>[
      el('strong',null,m.nome),m.sio.toLocaleString('pt-BR'),m.gran_sio.toLocaleString('pt-BR')])));
    totais.append(el('p','nota','Lançamentos registrados por destinatário. Contagem parcial; não mede a vida recuperada.'));
    const label=el('label','curas-seletor','Integrante'),select=el('select');select.setAttribute('aria-label','Integrante da cura');
    for(const [i,m] of opcoes.entries()){const o=el('option',null,`${m.vocacao?m.vocacao+' · ':''}${m.nome}${dados.trechos.length>1?' · '+m.sessao.replace('session_',''):''}`);o.value=i;select.append(o);}
    label.append(select);const corpo=el('div');conteudo.append(label,corpo);
    select.onchange=()=>{
      const m=opcoes[Number(select.value)];corpo.replaceChildren();
      const resumo=el('div','curas-resumo');
      for(const [nome,valor] of [['Vida observada',faixa(m.vida)],['Sios registrados',String(m.sio)],['Gran sios registrados',String(m.gran_sio)]]){
        const item=el('div');item.append(el('span','nota',nome),el('strong',null,valor));resumo.append(item);
      }
      corpo.append(resumo);
      if(!m.permanencia){corpo.append(el('p','nota','Faixas de vida indisponíveis nesta versão.'));return;}
      const p=m.permanencia;
      const rows=p.faixas.map(f=>{
        const nome=el('div','curas-faixa'),titulo=`${f.de}% ${f.ate<100?'a <':'a'} ${f.ate}%`;
        const barra=el('progress');barra.max=Math.max(1,p.tempo_identificado_s);barra.value=f.tempo_s||0;
        barra.setAttribute('aria-label',`Tempo estimado em ${titulo}`);
        nome.append(el('strong',null,titulo),barra);
        return [nome,duracao(f.tempo_s),f.sio.toLocaleString('pt-BR'),f.gran_sio.toLocaleString('pt-BR')];
      });
      rows.push([el('span','nota','Sem leitura suficiente'),duracao(p.sem_vida.tempo_s),p.sem_vida.sio.toLocaleString('pt-BR'),p.sem_vida.gran_sio.toLocaleString('pt-BR')]);
      const bandas=tabela(['Faixa de vida','Tempo estimado',magia('Sio'),magia('Gran sio')],rows);
      bandas.classList.add('curas-faixas');
      corpo.append(el('h3',null,'Vida e curas por faixa'),bandas,
        el('p','nota','Tempo estimado entre leituras próximas (até 6 s), usando a vida do início do intervalo. Períodos sem leitura suficiente ficam separados; — indica tempo indisponível.'),
        el('p','nota','Sio e Gran sio são agrupados pela última vida lida até 1,5 s antes da magia. Sem essa leitura, entram na última linha. Zero indica nenhum lançamento registrado.'));
    };
    select.onchange();
  }
  async function carregar(){
    totais.replaceChildren(el('p','nota','Carregando curas…'));painel.querySelector('details').hidden=true;
    try{const r=await fetch(`/api/historico/${id.split('/').map(encodeURIComponent).join('/')}/curas`,{cache:'no-store'});if(!r.ok)throw Error();painel.querySelector('details').hidden=false;desenhar(await r.json());}
    catch{const tentar=el('button','botao discreto pequeno','Tentar novamente');tentar.type='button';tentar.onclick=carregar;totais.replaceChildren(el('p','nota','Não foi possível carregar as curas.'),tentar);}
  }
  carregar();
})();
