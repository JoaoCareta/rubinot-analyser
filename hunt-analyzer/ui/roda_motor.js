/* Catálogo factual do Planner; busca limitada declarada, sem supor ML, críticos ou HP. */
const HuntRodaMotor=(()=>{
  const selecionar=(cat,voc)=>({...cat,...cat.vocacoes[voc],vocacao:voc});
  const dominios=['TL','TR','BL','BR'];
  const estagio=n=>n>=1000?3:n>=500?2:n>=250?1:0;
  function beneficios(cat,e){
    return cat.dominios.filter(d=>e.revelation[d.revelation_id]>0).map(d=>({
      dominio:d.dominio,id:d.revelation_id,nome:cat.revelation[d.revelation_id]?.Name,
      estagio:e.revelation[d.revelation_id],bonus_fixo_hp:cat.composicao.revelation_bonus_hp[e.revelation[d.revelation_id]],
      uso:/Avatar|Gift of Life/.test(cat.revelation[d.revelation_id]?.Name)?'ativacao_ou_contingencia':'condicional'}));
  }
  function importarCodigo(cat,codigo,total){
    codigo=codigo.trim().split('code=').pop().split('&')[0];
    if(!/^[DS]0[-_A-Za-z0-9]{3,90}$/.test(codigo))throw Error('Use o código atual do planejador ou do cliente (D0/S0).');
    if((codigo[0]==='D'?'ED':'MS')!==cat.vocacao)throw Error('O código pertence a outra vocação.');
    const texto=codigo.slice(2).replace(/-/g,'+').replace(/_/g,'/');
    const bytes=fflate.inflateSync(Uint8Array.from(atob(texto),c=>c.charCodeAt(0)));
    if(bytes.length!==48)throw Error('Formato de código não reconhecido.');
    const pontos=Object.fromEntries(cat.fatias.map(f=>[f.id,bytes[f.indice]]));
    const validacao=HuntRTC.validarDistribuicao(cat,pontos,total);
    if(!validacao.ok)throw Error(validacao.erros.join(' · '));
    return {pontos,codigo,origem:'Código importado pelo usuário',gemas_lidas:false};
  }
  function exportarCodigo(cat,pontos){
    const bytes=new Uint8Array(48).fill(255);cat.fatias.forEach(f=>{bytes[f.indice]=pontos[f.id]||0;});
    const payload=fflate.deflateSync(bytes),b64=btoa(String.fromCharCode(...payload)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    return (cat.vocacao==='ED'?'D0':'S0')+b64;
  }
  function resumo(cat,pontos){
    const ranks={},porDominio=Object.fromEntries(dominios.map(q=>[q,0])),vr={...porDominio};let investidos=0;
    for(const f of cat.fatias){const n=pontos[f.id]||0;investidos+=n;porDominio[f.dominio]+=n;
      if(n===f.limite){ranks[f.conviction_id]=(ranks[f.conviction_id]||0)+1;if(f.conviction_id>=37&&f.conviction_id<=40)vr[f.dominio]++;}}
    const revelation=Object.fromEntries(cat.dominios.map(q=>[q.revelation_id,estagio(porDominio[q.dominio])]));
    return {ranks,porDominio,vr,revelation,investidos};
  }
  function viabilidade(cat,total,tier){
    const orcamento=Number.isInteger(total)&&total>=0?Math.max(0,total-3):null;
    if(tier===0)return {estado:orcamento==null?'Total não lido':'Cabe nos pontos',orcamento,custo_minimo:0,caminhos:[{tier:0,custo:0,pontos:{}}]};
    const caminhos=cat.caminhos_minimos.filter(c=>c.tier===tier),minimo=Math.min(...caminhos.map(c=>c.custo));
    return {estado:orcamento==null?'Total não lido':orcamento<minimo?'Pontos insuficientes':'Cabe nos pontos',orcamento,custo_minimo:minimo,caminhos};
  }
  const nomesPorBonus={24:['great_fire_wave'],25:['energy_wave'],26:['lightning','strong_energy_strike','strong_flame_strike'],27:['hell_s_core','rage_of_the_skies'],29:['forked_glacier','forked_thorns'],30:['terra_wave'],31:['strong_ice_wave'],32:['mass_healing'],33:['heal_friend'],36:['death_echo']};
  function efeitos(cat,pontos,gemas=[],observados={}){
    const s=resumo(cat,pontos),bp={},cd={},alvos={},notas=[],critico_extra={},life_leech={},mana={},resistencias={},recursos={vida:0,mana:0,capacidade:0,mitigacao:0},globais={critico_extra:0,life_leech:0,mana_leech:0,dodge:0};
    // Um benefício visível não depende de ler todas as fatias da roda.
    for(const [id,n] of Object.entries(observados.ranks||{}))if(cat.conviction[id]&&Number.isInteger(n)&&n>=1&&n<=2)s.ranks[id]=n;
    for(const [id,n] of Object.entries(observados.revelation||{}))if(cat.revelation[id]&&Number.isInteger(n)&&n>=1&&n<=3)s.revelation[id]=n;
    let magic_level=0,fixo_hp=0;
    for(const f of cat.fatias){const n=pontos[f.id]||0;if(!n)continue;
      const d=cat.dedication_normalizada?.[f.dedication_id];
      if(d?.tipo==='vida')recursos.vida+=n*f.dedication_por_ponto;
      if(d?.tipo==='mana')recursos.mana+=n*f.dedication_por_ponto;
      if(d?.tipo==='vida_mana'){recursos.vida+=n*f.dedication_por_ponto;recursos.mana+=n*f.dedication_secundario;}
      if(d?.tipo==='capacidade')recursos.capacidade+=n*f.dedication_por_ponto;
      if(d?.tipo==='mitigacao_multiplicador')recursos.mitigacao+=n*d.por_ponto;
      if(n===f.limite){
        if(f.conviction_id===34)magic_level+=f.conviction_valor;
        if(f.conviction_id===5)globais.mana_leech+=f.conviction_valor/10000;
        if(f.conviction_id===6)globais.life_leech+=f.conviction_valor/10000;
      }
    }
    for(const g of gemas){if(s.vr[g.dominio]<3||(g.tier??3)!==3||(g.basicos||[]).length!==2||(g.basicos||[]).some(b=>(b.grau??1)<(g.grau??1)))continue;const mod=cat.gemas_normalizadas?.[g.mod]?.graus?.[g.grau??1],domain=cat.dominios.find(d=>d.dominio===g.dominio);
      if(mod?.tipo==='revelation_virtual'&&domain&&cat.revelation[domain.revelation_id]?.Name===mod.revelation_nome)s.revelation[domain.revelation_id]=estagio(s.porDominio[g.dominio]+mod.valor);}
    const somar=(lista,n)=>lista.forEach(id=>{bp[id]=(bp[id]||0)+n;});
    if(s.ranks[24]>=2)somar(nomesPorBonus[24],.05);
    if(s.ranks[24])critico_extra.great_fire_wave=.15;
    if(s.ranks[25]>=2)somar(nomesPorBonus[25],.10);
    if(s.ranks[26]){nomesPorBonus[26].forEach(id=>cd[id]=-4);if(s.ranks[26]>=2)somar(nomesPorBonus[26],.50);}
    if(s.ranks[27]){somar(nomesPorBonus[27],.05);if(s.ranks[27]>=2)nomesPorBonus[27].forEach(id=>cd[id]=-4);}
    if(s.ranks[29]){nomesPorBonus[29].forEach(id=>cd[id]=-2);if(s.ranks[29]>=2)nomesPorBonus[29].forEach(id=>alvos[id]=1);}
    if(s.ranks[30])somar(nomesPorBonus[30],.065);
    if(s.ranks[30]>=2)life_leech.terra_wave=.10;
    if(s.ranks[31])somar(nomesPorBonus[31],.06);
    if(s.ranks[32])somar(nomesPorBonus[32],.04);
    if(s.ranks[33])somar(nomesPorBonus[33],s.ranks[33]>=2?.10:.04);
    for(const g of gemas){
      const qualidade=g.tier??({Lesser:1,Regular:2,Greater:3}[g.qualidade]??3),nivel=s.vr[g.dominio]||0;
      if(nivel===qualidade)fixo_hp+=cat.composicao?.ressonancia_bonus?.[qualidade]??(qualidade===3?2:1);
      for(const [i,b] of (g.basicos||[]).entries()){
        if(i>=nivel||i>=Math.min(2,qualidade))continue;
        for(const effect of cat.basicos_normalizados?.[b.mod]?.graus?.[cat.vocacao]?.[b.grau??1]||[]){
          if(effect.tipo.endsWith(' Resistance')){const el=effect.tipo.slice(0,-11).toLowerCase();resistencias[el]=(resistencias[el]||0)+effect.valor;}
          else if(effect.tipo==='Hit Points')recursos.vida+=effect.valor;
          else if(effect.tipo==='Mana')recursos.mana+=effect.valor;
          else if(effect.tipo==='Capacity')recursos.capacidade+=effect.valor;
          else if(effect.tipo==='Mitigation Multiplier')recursos.mitigacao+=effect.valor;
        }
      }
      const grau=g.grau??1;
      if(nivel<3||qualidade!==3||(g.basicos||[]).length!==2||(g.basicos||[]).some(b=>(b.grau??1)<grau))continue;
      const mod=cat.gemas_normalizadas?.[g.mod],e=mod?.graus?.[grau];if(!e)continue;
      const ids=g.magias?.length?g.magias:Object.entries(nomesPorBonus).filter(([id])=>cat.conviction[id]?.Name?.split('|').some(n=>n.replace(/^Augmented |^Aug\. /,'')===e.magias_nome)).flatMap(([,ids])=>ids);
      if(e.tipo==='base_percent')somar(ids,e.valor);else if(e.tipo==='cooldown_delta')ids.forEach(id=>cd[id]=(cd[id]||0)+e.valor);
      else if(e.tipo==='critico_extra'){if(ids.length)ids.forEach(id=>critico_extra[id]=(critico_extra[id]||0)+e.valor);else globais.critico_extra+=e.valor;}
      else if(e.tipo==='life_leech'){if(ids.length)ids.forEach(id=>life_leech[id]=(life_leech[id]||0)+e.valor);else globais.life_leech+=e.valor;}
      else if(e.tipo==='mana_leech')globais.mana_leech+=e.valor;
      else if(e.tipo==='dodge')globais.dodge+=e.valor;
      notas.push(`${g.dominio}: ${mod.nome} · ${e.descricao}`);
    }
    fixo_hp+=Object.values(s.revelation).reduce((n,rank)=>n+(cat.composicao?.revelation_bonus_hp?.[rank]||0),0);
    // Resumo observado permite comparar benefícios sem inventar a distribuição
    // ou a identidade das gemas. Não acumular esse resumo com gemas completas.
    if(!gemas.length)for(const [id,n] of Object.entries(observados.bp_gemas||{}))if(Number.isFinite(n))bp[id]=(bp[id]||0)+n;
    if(Number.isFinite(observados.fixo_hp))fixo_hp=observados.fixo_hp;
    return {...s,bp,cd,alvos,notas,critico_extra,life_leech,mana,resistencias,recursos,magic_level,fixo_hp,globais,
      beneficios:beneficios(cat,s),unidade_bonus_fixo:'HP_por_aplicacao'};
  }
  function modificar(cat,pontos,magias,gemas=[],cenario={alvos:1}){
    const e=efeitos(cat,pontos,gemas,cenario.efeitos_observados);
    return magias.filter(m=>!m.requer_roda||(m.familia==='bursts'&&e.revelation[10]>0)||(m.familia==='beams'&&e.revelation[8]>0)).map(m=>{
      let cd=Math.max(m.grupo||1,m.cd*(cat.composicao?.cooldown_minimo_fracao??.5),m.cd+(e.cd[m.id]||0)),bp=m.bp*(1+(e.bp[m.id]||0));
      if(m.familia==='bursts'){cd=[22,18,14][e.revelation[10]-1];}
      const beam=HuntRTC.categoria(m)==='Beam'&&(e.revelation[7]||0);
      if(beam&&!cenario.temporal)bp*=1+[.10,.12,.14][beam-1]*Math.min(3,cenario.alvos);
      const alvos=m.alvos==null?null:m.alvos+(e.alvos[m.id]||0);
      return {...m,bp,bp_original:m.bp,multiplicador_base:bp/m.bp,ajustado:m.tipo==='cura'?bp:bp*m.resistencia/100,cd,alvos,
        dano_fixo_hp:m.tipo==='cura'?0:e.fixo_hp,
        area_ampliada:!!((m.id==='mass_healing'&&e.ranks[32]>=2)||(m.id==='energy_wave'&&e.ranks[25])||(m.id==='strong_ice_wave'&&e.ranks[31]>=2)),
        alvo_adicional:!!e.alvos[m.id],twin_estagio:m.familia==='bursts'?e.revelation[10]:0,
        critico_extra:e.critico_extra[m.id]||0,life_leech:e.life_leech[m.id]||0,
        lord_destruction:e.revelation[8]||0,
        twin_bonus:m.familia==='bursts'?[.2,.4,.6][e.revelation[10]-1]:0,
        focus_bonus:e.ranks[23]?.35:0,
        beam_por_alvo:beam&&cenario.temporal?[.10,.12,.14][beam-1]:0,
        beam_lateral:beam?[.25,.4,.7][beam-1]:0,
        reduz_outros_cd:beam&&!cenario.temporal?Math.min(3,cenario.alvos):0,cd_compartilhado:m.cd_compartilhado?Math.min(cd,m.cd_compartilhado):null};
    });
  }
  function cura(cat,pontos,gemas=[]){
    const e=efeitos(cat,pontos,gemas),sio=100*(1+(e.bp.heal_friend||0)),mas=100*(1+(e.bp.mass_healing||0));
    // Índice por uso, cada magia com seu próprio valor base 100; não são HP nem curas somadas.
    return cat.vocacao==='ED'?{sio:sio,mas_res:mas,autocura_por_sio:e.ranks[28]?sio*.25:0}:{autocura:100};
  }
  function gemasPossiveis(cat,objetivo,magias,grau=1){
    const elegiveis=[];
    for(const [key,mod] of Object.entries(cat.gemas_supremas)){
      if(!mod||typeof mod!=='object'||!mod.EffectInfo)continue;
      const text=mod.EffectInfo[String(grau-1)]||'',nome=(mod.Name||'').split('|')[0].replace(/^Augmented /,'');
      const lista=magias.filter(m=>m.nome===nome||(nome==='Forked Spells'&&m.nome.startsWith('Forked ')));
      if(/^\+\d+ (Twin Bursts|Beam Mastery|Blessing of the Grove)$/.test(text)){elegiveis.push({mod:+key,nome:text,grau,magias:[],revelation_nome:cat.gemas_normalizadas?.[key]?.graus?.[grau]?.revelation_nome});continue;}
      if(!lista.length){if(cat.gemas_normalizadas?.[key]?.graus?.[grau]&&['critico_extra','life_leech','mana_leech','dodge'].includes(cat.gemas_normalizadas[key].graus[grau].tipo))elegiveis.push({mod:+key,nome:cat.gemas_normalizadas[key].nome,grau,magias:[]});continue;}
      if(!(objetivo==='cura'?lista.some(m=>m.tipo==='cura'):lista.some(m=>m.tipo!=='cura')))continue;
      elegiveis.push({mod:+key,nome,grau,magias:lista.map(m=>m.id)});
    }
    return elegiveis;
  }
  function otimizar(cat,total,objetivo,tier,magias,cenario,opcoes={}){
    const v=viabilidade(cat,total,tier);if(v.estado!=='Cabe nos pontos')return {...v,alternativas:[]};
    if(objetivo==='cura'&&cat.vocacao==='MS')return {...v,estado:'Calculado',alternativas:[],motivo:'A roda de MS não oferece aumento incondicional de Base Healing. ML e críticos ficam fora deste índice.'};
    const fatias=cat.fatias,limites=Object.fromEntries(fatias.map(f=>[f.id,f.limite])),largura=opcoes.larguraRoda||96;
    const liberadas=p=>fatias.filter(f=>(p[f.id]||0)<f.limite&&(f.raiz||f.conexoes.some(k=>p[k]===limites[k])));
    const chave=p=>fatias.map(f=>p[f.id]||0).join(',');
    const avaliadas=new Map();let expansoes=0;
    const pesos=objetivo==='cura'?{28:35,32:8,33:12}:{24:5,25:10,26:10,27:6,29:8,30:6.5,31:6};
    function heuristica(p){const r=resumo(cat,p);let score=Object.entries(r.ranks).reduce((s,[k,n])=>s+(pesos[k]||0)*n,0);
      score+=Math.max(...Object.values(r.vr).map(n=>Math.min(n,tier)))*12;
      if(objetivo==='dano')score+=(r.revelation[10]||r.revelation[7]||0)*18;
      // Reservar diversidade de caminhos: progresso de cada domínio, sem fingir bônus de BP.
      score+=Math.max(...Object.values(r.porDominio))*.002;return score;}
    let feixe=[{} ,...v.caminhos.filter(c=>c.custo<=v.orcamento).map(c=>c.pontos)];
    for(let depth=0;depth<Math.min(36,Math.floor(v.orcamento/50)+1);depth++){
      const novos=new Map();
      for(const p of feixe){const r=resumo(cat,p);if(Math.max(...Object.values(r.vr))>=tier)avaliadas.set(chave(p),p);
        for(const f of liberadas(p)){
          const sobra=v.orcamento-r.investidos,restante=f.limite-(p[f.id]||0);if(sobra<=0)continue;
          const quantidades=new Set([Math.min(sobra,restante)]);
          for(const alvo of [250,500,1000]){const n=alvo-r.porDominio[f.dominio];if(n>0&&n<=restante&&n<=sobra)quantidades.add(n);}
          for(const n of quantidades){const next={...p,[f.id]:(p[f.id]||0)+n};expansoes++;novos.set(chave(next),next);}
        }
      }
      feixe=[...novos.values()].sort((a,b)=>heuristica(b)-heuristica(a)||resumo(cat,a).investidos-resumo(cat,b).investidos).slice(0,largura);
      if(!feixe.length)break;
    }
    const candidates=[...avaliadas.values()].sort((a,b)=>heuristica(b)-heuristica(a)).slice(0,24),resultados=[];
    const mods=gemasPossiveis(cat,objetivo,magias);
    for(const p of candidates){if(!HuntRTC.validarDistribuicao(cat,p,total).ok)continue;
      const s=resumo(cat,p),qs=dominios.filter(q=>s.vr[q]>=tier);let combinations=[[]];
      if(tier===3){const choices=[null,...mods];combinations=qs.flatMap(q=>choices.filter(g=>!g?.revelation_nome||cat.revelation[cat.dominios.find(d=>d.dominio===q).revelation_id].Name===g.revelation_nome).map(g=>g?[{...g,dominio:q}]:[]));}
      for(const gems of combinations){const e=efeitos(cat,p,gems);let metricas,rotacao=null;
        if(objetivo==='dano'){
          const ofensivas=modificar(cat,p,magias,gems,cenario).filter(m=>HuntRTC.categoria(m)&&m.ajustado!=null&&m.cobertura===1);
          if(!ofensivas.length)continue;
          rotacao=HuntRTC.otimizar(ofensivas,[],cenario,{...opcoes,largura:16});if(rotacao.erro)continue;metricas={dano:rotacao.score};
        }else metricas=cura(cat,p,gems);
        resultados.push({pontos:Object.fromEntries(fatias.map(f=>[f.id,p[f.id]||0])),metricas,gemas:gems.length?gems:qs.map(q=>({dominio:q,nome:cat.tiers[tier].qualidade+' gem',grau:null})),efeitos:e,rotacao});
      }
    }
    const pareto=resultados.filter(a=>!resultados.some(b=>b!==a&&Object.keys(a.metricas).every(k=>b.metricas[k]>=a.metricas[k])&&Object.keys(a.metricas).some(k=>b.metricas[k]>a.metricas[k])));
    const iguais=new Map();
    for(const a of pareto.sort((a,b)=>a.efeitos.investidos-b.efeitos.investidos))if(!iguais.has(JSON.stringify(a.metricas)))iguais.set(JSON.stringify(a.metricas),a);
    const unicas=[...iguais.values()].slice(0,6);
    return {...v,estado:unicas.length?'Calculado':'Sem comparação',alternativas:unicas,avaliadas:resultados.length,expansoes,
      alcance:`Busca em feixe de ${largura} distribuições; ${expansoes} expansões; ${resultados.length} comparações finais. Melhor entre as avaliadas; máximo global não comprovado.`,
      premissas:'Busca legada comparativa. Modificadores em grau I explícito; inventário não restringe. Avaliação integrada temporal disponível no motor integrado.'};
  }
  function caminho(cat,destino,existentes={}){
    const fila=cat.fatias.filter(f=>f.raiz||(existentes[f.id]||0)===f.limite).map(f=>({id:f.id,custo:f.limite-(existentes[f.id]||0),pontos:{...existentes,[f.id]:f.limite}})),vistos=new Set();
    while(fila.length){fila.sort((a,b)=>a.custo-b.custo);const p=fila.shift();if(vistos.has(p.id))continue;vistos.add(p.id);if(p.id===destino)return p.pontos;
      for(const f of cat.fatias.filter(f=>f.conexoes.includes(p.id)))if(!vistos.has(f.id))fila.push({id:f.id,custo:p.custo+f.limite-(existentes[f.id]||0),pontos:{...p.pontos,[f.id]:f.limite}});
    }return null;
  }
  function alternativasSio(cat,pontos,total){
    if(cat.vocacao!=='ED')return [];
    const base=efeitos(cat,pontos),orcamento=total-3,saida=[];
    // Preservar estágios, ressonâncias e perks já ativos. Pontos incompletos
    // podem financiar sio sem serem tratados como leech ativado.
    const preservar=p=>{const e=efeitos(cat,p);
      return dominios.every(q=>e.vr[q]===base.vr[q])&&Object.entries(base.revelation).every(([id,n])=>e.revelation[id]===n)
        &&Object.entries(base.ranks).every(([id,n])=>id==='33'||e.ranks[id]>=n)
        &&e.magic_level>=base.magic_level&&e.fixo_hp>=base.fixo_hp;};
    const validar=p=>HuntRTC.validarDistribuicao(cat,p,Math.max(total,10000)).ok;
    let sementes=[{...pontos}];
    for(const de of cat.fatias.filter(f=>f.conviction_id>=37&&f.conviction_id<=40&&pontos[f.id]===f.limite)){
      for(const para of cat.fatias.filter(f=>f.dominio===de.dominio&&f.conviction_id===de.conviction_id&&f.limite<de.limite&&!pontos[f.id])){
        sementes.push({...pontos,[de.id]:0,[para.id]:para.limite});
      }
    }
    for(const s of sementes){let p={...s};
      for(const f of cat.fatias.filter(f=>f.conviction_id===33))if(p[f.id]!==f.limite)p=caminho(cat,f.id,p)||p;
      if(!validar(p)||!preservar(p))continue;
      for(let passo=0;passo<36&&resumo(cat,p).investidos>orcamento;passo++){
        const falta=resumo(cat,p).investidos-orcamento;let escolhido=null;
        for(const f of cat.fatias.filter(f=>f.conviction_id!==33&&(p[f.id]||0)>0)){
          for(let n=Math.min(falta,p[f.id]);n>0;n--){const q={...p,[f.id]:p[f.id]-n};
            if(validar(q)&&preservar(q)){const e=efeitos(cat,q);
              const perda=Math.max(0,base.recursos.mana-e.recursos.mana)+Math.max(0,base.recursos.vida-e.recursos.vida)*5;
              if(!escolhido||perda<escolhido.perda||perda===escolhido.perda&&n>escolhido.n)escolhido={p:q,perda,n};break;}
          }
        }
        if(!escolhido)break;p=escolhido.p;
      }
      const e=efeitos(cat,p);
      if(e.investidos===orcamento&&e.ranks[33]>(base.ranks[33]||0)&&e.recursos.vida>=base.recursos.vida&&e.recursos.mana>=base.recursos.mana&&e.recursos.mitigacao>=base.recursos.mitigacao&&HuntRTC.validarDistribuicao(cat,p,total).ok)saida.push(p);
    }
    return [...new Map(saida.map(p=>[JSON.stringify(p),p])).values()];
  }
  function candidatas(cat,total,tier,estrategia,objetivo,opcoes={}){
    const v=viabilidade(cat,total,tier);if(v.estado!=='Cabe nos pontos')return {...v,distribuicoes:[]};
    const link=estrategia.includes('link'),critico=estrategia.includes('critica'),dom=cat.dominios.find(d=>d.revelation_id===11)?.dominio;
    if(cat.vocacao==='MS'&&(link||critico))return {...v,estado:'Estratégia exclusiva de ED',distribuicoes:[]};
    const l=cat.fatias.find(f=>f.conviction_id===28),requisito=link?caminho(cat,l.id):{};
    const merge=(a,b)=>Object.fromEntries(cat.fatias.map(f=>[f.id,Math.max(a?.[f.id]||0,b?.[f.id]||0)]));
    let seeds=v.caminhos.filter(c=>c.custo<=v.orcamento).map(c=>link?caminho(cat,l.id,c.pontos):merge(c.pontos,requisito));
    const resumoDe=p=>resumo(cat,p),limites=Object.fromEntries(cat.fatias.map(f=>[f.id,f.limite]));
    function completarDominio(p,q,n){p={...p};for(let i=0;i<36&&resumoDe(p).porDominio[q]<n;i++){
      const f=cat.fatias.find(f=>f.dominio===q&&(p[f.id]||0)<f.limite&&(f.raiz||f.conexoes.some(k=>p[k]===limites[k])));if(!f)return null;
      p[f.id]=(p[f.id]||0)+Math.min(f.limite-(p[f.id]||0),n-resumoDe(p).porDominio[q]);}return p;}
    if(critico)seeds=seeds.map(p=>completarDominio(p,dom,250)).filter(Boolean);
    // Enumerar combinações de limiares ANTES da poda. Entre 500 e 999 pontos
    // o próximo ponto no mesmo domínio não aproxima o bônus de outro domínio.
    // A expansão gulosa por fatia perdia II+I em favor de um II incompleto.
    const combinacoes=[];
    function combinar(i,alvos,custo){
      if(i===dominios.length){combinacoes.push(alvos);return;}
      for(const n of [0,250,500,1000])if(custo+n<=v.orcamento)combinar(i+1,[...alvos,n],custo+n);
    }
    combinar(0,[],0);
    for(const alvos of combinacoes)for(const c of v.caminhos){
      let p=link?caminho(cat,l.id,c.pontos):{...c.pontos};
      for(let i=0;p&&i<dominios.length;i++)if(alvos[i])p=completarDominio(p,dominios[i],alvos[i]);
      if(p&&critico)p=completarDominio(p,dom,250);
      if(p&&resumoDe(p).investidos<=v.orcamento)seeds.push(p);
    }
    // Partir dos efeitos comprovados da roda atual. Isto reconstrói caminhos
    // válidos para a busca; não declara conhecidas as fatias ainda não lidas.
    let inicial={};
    for(const [id,n] of Object.entries((opcoes.efeitos_minimos||opcoes.efeitos_iniciais)?.ranks||{})){
      if(!opcoes.efeitos_minimos&&!opcoes.convictions_uteis?.includes(+id))continue;
      const candidatos=cat.fatias.filter(f=>f.conviction_id===+id).sort((a,b)=>Object.values(caminho(cat,a.id,inicial)||{}).reduce((s,n)=>s+n,0)-Object.values(caminho(cat,b.id,inicial)||{}).reduce((s,n)=>s+n,0));
      for(const f of candidatos.slice(0,n))inicial=caminho(cat,f.id,inicial)||inicial;
    }
    for(const [id,n] of Object.entries((opcoes.efeitos_minimos||opcoes.efeitos_iniciais)?.revelation||{})){
      const d=cat.dominios.find(d=>d.revelation_id===+id);
      if(n&&d&&(opcoes.efeitos_minimos||opcoes.revelations_uteis?.includes(+id)))inicial=completarDominio(inicial,d.dominio,[0,250,500,1000][n])||inicial;
    }
    if(Object.keys(inicial).length)seeds.push(...v.caminhos.map(c=>merge(c.pontos,inicial)));
    // Reconstruir sobre cada caminho de ressonância evita somar dois caminhos
    // mínimos incompatíveis e gastar pontos em acessos redundantes.
    if(opcoes.efeitos_minimos)for(const c of [...v.caminhos,...cat.caminhos_minimos.filter(c=>c.tier>tier)]){
      let bases=[{...c.pontos}];
      for(const [id,n] of Object.entries(opcoes.efeitos_minimos.ranks||{})){
        const proximas=[];
        for(const base of bases){
          const fatias=cat.fatias.filter(f=>f.conviction_id===+id);
          for(const primeira of fatias){let p=caminho(cat,primeira.id,base);
            if(n>1)for(const f of fatias)if(p)p=caminho(cat,f.id,p);
            if(p&&resumoDe(p).investidos<=v.orcamento)proximas.push(p);
          }
        }
        bases=proximas;
      }
      for(let p of bases){
        for(const [id,n] of Object.entries(opcoes.efeitos_minimos.revelation||{})){
          const d=cat.dominios.find(d=>d.revelation_id===+id);
          if(p&&d)p=completarDominio(p,d.dominio,[0,250,500,1000][n]);
        }
        if(p&&opcoes.exigir_sio_critico)p=completarDominio(p,dom,250);
        if(p&&resumoDe(p).investidos<=v.orcamento)seeds.push(p);
      }
    }
    // Pacotes completos: reconstruir do zero permite retirar blocos da roda
    // atual e alcançar desbloqueios que a expansão ponto a ponto perde.
    const uteis=new Set(opcoes.convictions_uteis||[]);
    if(cat.vocacao==='ED'){uteis.add(33);uteis.add(32);}
    const marcos=cat.fatias.filter(f=>uteis.has(f.conviction_id));
    const nucleos=[{},inicial];
    for(const id of opcoes.revelations_uteis||[]){
      const q=cat.dominios.find(d=>d.revelation_id===id);
      if(q)for(const n of [250,500,1000])if(n<=v.orcamento){
        const p=completarDominio({},q.dominio,n);if(p)nucleos.push(p);
      }
    }
    const pacotes=new Map();
    for(const core of nucleos)for(const f of marcos){
      const p=caminho(cat,f.id,core);if(!p)continue;
      for(const outro of [null,...marcos.filter(g=>g.id!==f.id)]){
        const a=outro?caminho(cat,outro.id,p):p;
        if(!a||resumoDe(a).investidos>v.orcamento)continue;
        for(const c of v.caminhos){const b=merge(a,c.pontos);
          if(resumoDe(b).investidos<=v.orcamento)pacotes.set(cat.fatias.map(g=>b[g.id]||0).join(','),b);
        }
      }
    }
    seeds.push(...pacotes.values());
    if(opcoes.pontos_iniciais)seeds.push({...opcoes.pontos_iniciais});
    if(opcoes.exigir_sio_critico&&cat.vocacao==='ED'){
      let suporte={};
      for(const f of cat.fatias.filter(f=>f.conviction_id===33))suporte=caminho(cat,f.id,suporte)||suporte;
      suporte=completarDominio(suporte,dom,250);
      if(suporte)for(const c of v.caminhos){const p=merge(suporte,c.pontos);if(resumoDe(p).investidos<=v.orcamento)seeds.push(p);}
      // As prioridades de dano não podem podar o requisito de suporte antes
      // da expansão; inclui também marcos ofensivos sobre a base protegida.
      if(suporte)for(const f of marcos){const p=caminho(cat,f.id,suporte);if(p&&resumoDe(p).investidos<=v.orcamento)seeds.push(...v.caminhos.map(c=>merge(p,c.pontos)));}
    }
    const requisitoOk=p=>{const s=resumoDe(p);return ['ranks','revelation'].every(g=>Object.entries(opcoes.efeitos_minimos?.[g]||{}).every(([id,n])=>(s[g][id]||0)>=n))&&(!link||s.ranks[28])&&(!critico||s.revelation[11]>0)&&Math.max(...Object.values(s.vr))>=tier;};
    const key=p=>cat.fatias.map(f=>p[f.id]||0).join(',');
    const pesos=opcoes.pesos_magias,peso=id=>pesos?pesos[id]||0:1;
    const valor=p=>{if(opcoes.valor_roda)return opcoes.valor_roda(p);const s=resumoDe(p),e=efeitos(cat,p),bonus=Object.entries(e.bp).reduce((n,[id,v])=>n+v*peso(id),0),cadencia=pesos?Object.entries(e.cd).reduce((n,[id,v])=>n+Math.max(0,-v)*peso(id),0):0;
      const especial=pesos?(s.revelation[10]||0)*(peso('ice_burst')+peso('terra_burst'))+(s.revelation[7]||0)*(peso('energy_beam')+peso('great_energy_beam')):(s.revelation[10]||s.revelation[7]||0);
      return bonus*100+cadencia*4+(objetivo==='cura'?(s.ranks[28]||0)*25+(s.revelation[11]||0)*18:especial*18)+Math.max(...Object.values(s.vr))*4+e.fixo_hp;};
    seeds=seeds.filter(p=>HuntRTC.validarDistribuicao(cat,p,total).ok&&requisitoOk(p)&&(!opcoes.exigir_sio_critico||(resumoDe(p).ranks[33]>=2&&resumoDe(p).revelation[11]>0)));
    seeds=[...new Map(seeds.map(p=>[key(p),p])).values()];
    let feixe=seeds.slice().sort((a,b)=>valor(b)-valor(a)).slice(0,opcoes.larguraRoda??48),distribuicoes=new Map(seeds.map(p=>[key(p),p]));
    for(let passo=0;passo<20&&feixe.length;passo++){
      const next=new Map();for(const p of feixe){const s=resumoDe(p),sobra=v.orcamento-s.investidos;if(sobra<=0)continue;
        for(const f of cat.fatias){if((p[f.id]||0)>=f.limite||!f.raiz&&!f.conexoes.some(k=>p[k]===limites[k]))continue;
          const max=Math.min(sobra,f.limite-(p[f.id]||0)),ns=new Set([max]);for(const alvo of [250,500,1000]){const n=alvo-s.porDominio[f.dominio];if(n>0&&n<=max)ns.add(n);}
          for(const n of ns){const a={...p,[f.id]:(p[f.id]||0)+n};next.set(key(a),a);}}
      }
      feixe=[...next.values()].sort((a,b)=>valor(b)-valor(a)).slice(0,opcoes.larguraRoda??48);feixe.forEach(p=>distribuicoes.set(key(p),p));
    }
    let lista=[...distribuicoes.values()].sort((a,b)=>valor(b)-valor(a)).slice(0,opcoes.finais??12);
    // Incluir sementes de caminhos distintos; não perder Link+Blessing por pesos de dano.
    // Diversidade por benefício alcançado conserva sio/proteção e cada estágio.
    const grupos=new Map();
    for(const p of seeds){const s=resumoDe(p),g=JSON.stringify([s.revelation,s.ranks[33]||0,!!s.ranks[32],!!s.ranks[28],s.vr]);
      if(!grupos.has(g)||valor(p)>valor(grupos.get(g)))grupos.set(g,p);}
    for(const p of grupos.values())if(!lista.some(a=>key(a)===key(p)))lista.push(p);
    if(opcoes.preencher){
      // Completar ANTES da avaliação temporal/gemas: desenho e efeitos usam
      // a distribuição inteira, nunca um preenchimento acrescentado na saída.
      const alvo=Math.min(v.orcamento,cat.fatias.reduce((s,f)=>s+f.limite,0));
      const completar=p=>{
        p={...p};
        for(let passo=0;passo<cat.fatias.length&&resumoDe(p).investidos<alvo;passo++){
          const sobra=alvo-resumoDe(p).investidos,e0=efeitos(cat,p);
          const op=cat.fatias.filter(f=>(p[f.id]||0)<f.limite&&(f.raiz||f.conexoes.some(k=>p[k]===limites[k]))).map(f=>{
            const n=Math.min(sobra,f.limite-(p[f.id]||0)),a={...p,[f.id]:(p[f.id]||0)+n},e=efeitos(cat,a);
            const recurso=opcoes.modo_vida==='utamo'?'mana':'vida';
            return {p:a,ganho:(valor(a)-valor(p))/n+(e.recursos[recurso]-e0.recursos[recurso])/n/100};
          }).sort((a,b)=>b.ganho-a.ganho);
          if(!op.length)break;p=op[0].p;
        }
        return p;
      };
      lista=[...new Map(lista.map(completar).filter(p=>resumoDe(p).investidos===alvo&&HuntRTC.validarDistribuicao(cat,p,total).ok&&requisitoOk(p)).map(p=>[key(p),p])).values()];
    }
    // Rodízio entre perfis de Revelation; o limite de tempo não deve consumir
    // todas as avaliações em variações de uma única concentração de pontos.
    const perfis=new Map();
    for(const p of lista){const k=JSON.stringify(resumoDe(p).revelation);if(!perfis.has(k))perfis.set(k,[]);perfis.get(k).push(p);}
    const filas=[...perfis.values()].map(ps=>ps.sort((a,b)=>valor(b)-valor(a)))
      .sort((a,b)=>efeitos(cat,b[0]).fixo_hp-efeitos(cat,a[0]).fixo_hp||valor(b[0])-valor(a[0]));
    lista=[];while(filas.some(ps=>ps.length))for(const ps of filas)if(ps.length)lista.push(ps.shift());
    if(opcoes.priorizar_sio){
      const extras=lista.filter(p=>(resumo(cat,p).ranks[33]||0)<2).flatMap(p=>alternativasSio(cat,p,total));
      lista=[...new Map([...lista,...extras].map(p=>[key(p),p])).values()];
      // Intercalar com sio II antes de variações equivalentes: um limite de
      // tempo não pode consumir a busca antes de avaliar o suporte ao EK.
      lista.sort((a,b)=>(resumo(cat,b).ranks[33]||0)-(resumo(cat,a).ranks[33]||0));
    }
    return {...v,estado:lista.length?'Calculado':'Pontos insuficientes para a estratégia',distribuicoes:lista,expansoes:distribuicoes.size,perfis_revelation:perfis.size};
  }
  return {selecionar,resumo,viabilidade,efeitos,beneficios,modificar,cura,otimizar,importarCodigo,exportarCodigo,gemasPossiveis,candidatas,caminho,alternativasSio};
})();
if(typeof module!=='undefined')module.exports=HuntRodaMotor;
