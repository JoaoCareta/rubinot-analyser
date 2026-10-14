"""Contexto medido, elegibilidade e calibração; sem atribuição por dano médio."""
import collections
import statistics


def chave_rtc(rtc):
    """Identidade dos campos/ícones, independente do instante de leitura."""
    return '|'.join(':'.join(str(s.get(k)) for k in
        ('tipo', 'slot', 'icone_hash', 'mana_percent', 'creatures', 'prioridade'))
        for s in sorted(rtc.get('slots', []), key=lambda s: (s.get('tipo', ''), s.get('slot', 0))))


def calibrar_ataque(char, sessao, eventos, magias, rtc, confirmado=False):
    """Intervalo efetivo por configuração; dano associado continua parcial.

    Espécie não identifica criatura. Nem linhas de dano nem console truncado
    provam cobertura completa, e cura simultânea não concorre com ataque.
    """
    por_id = {m['id']: m for m in magias}
    # Nunca misturar a execução anterior à configuração observada.
    origem = rtc.get('instante', 0)
    import datetime
    dt = datetime.datetime.fromtimestamp(origem) if origem else None
    desde = dt.hour*3600+dt.minute*60+dt.second+dt.microsecond/1e6 if dt else 0
    unicos = {e.get('id', str(i)): e for i, e in enumerate(eventos) if e.get('t', -1) >= desde}
    casts = sorted({(e['t'], e['magia_id']): e for e in unicos.values()
        if e.get('kind') == 'cast' and e.get('qualidade') == 'identificada'
        and por_id.get(e.get('magia_id'), {}).get('tipo') == 'ofensiva'
        and e.get('ator', char) == char}.values(), key=lambda e: e['t'])
    por_segundo = collections.defaultdict(list)
    for e in casts: por_segundo[e['t']].append(e)
    danos = collections.Counter()
    com_dano = set()
    for e in unicos.values():
        if e.get('kind') != 'damage_dealt' or e.get('ator', char) != char: continue
        candidatos = por_segundo[e['t']] + por_segundo[e['t']-1]
        if len(candidatos) != 1: continue
        cast = candidatos[0]
        danos[cast['magia_id']] += 1
        com_dano.add((cast['t'], cast['magia_id']))
    intervalos, medidas = {}, {}
    for ident in sorted({e['magia_id'] for e in casts}):
        ts = [e['t'] for e in casts if e['magia_id'] == ident]
        medidas[ident] = {'lancamentos': len(ts), 'com_dano_associado': sum((t, ident) in com_dano for t in ts),
            'linhas_dano_associadas': danos[ident], 'cobertura_completa': False,
            'origem': 'fala_propria_e_console_parcial', 'frequencia_completa': False}
        m = por_id[ident]
        # Atrasos/pausas não medem cooldown. O modo recorrente é uma previsão
        # de intervalo efetivo, nunca alteração do catálogo ou prova da roda.
        gaps = [b-a for a, b in zip(ts, ts[1:]) if m['grupo'] <= b-a <= m['cd']]
        if len(gaps) < 30: continue
        treino, teste = gaps[:-10], gaps[-10:]
        candidato, repeticoes = collections.Counter(treino).most_common(1)[0]
        # Espera/lure pode alongar o intervalo; validar violações de prontidão.
        suporte = sum(g >= candidato-1 for g in teste)
        erro = lambda v: statistics.mean(max(0, v-g-1) for g in teste)
        if candidato >= m['cd'] or repeticoes < len(treino)*.5 or suporte < 8 or erro(candidato) >= erro(m['cd'])*.9: continue
        intervalos[ident] = {'segundos': candidato, 'base_catalogo': m['cd'], 'treino': len(treino),
            'repeticoes': repeticoes, 'validacao': 10, 'suporte_validacao': suporte,
            'erro_antes': erro(m['cd']), 'erro_depois': erro(candidato),
            'origem': 'intervalo_efetivo_observado', 'precisao_s': 1}
    return {'versao': 1, 'escopo': {'char': char, 'sessao': sessao, 'preset': rtc.get('preset'),
            'rtc_chave': chave_rtc(rtc)}, 'confirmado_por_usuario': confirmado,
            'desde': desde, 'ate': max((e.get('t', 0) for e in unicos.values()), default=desde),
            'magias': medidas, 'intervalos_efetivos': intervalos, 'cobertura_completa': False}


def tempo_quadro(nome):
    partes=nome[2:].removesuffix('.png').split('_')
    return int(partes[0][:2])*3600+int(partes[0][2:4])*60+int(partes[0][4:6])+int(partes[1])/1000


def elegibilidade(cast,sugestao,anterior,recursos,concordancia):
    if concordancia.get('estado')!='confere':return {'elegibilidade':'inconclusiva'}
    linhas=sugestao.get('rtc',{}).get('linhas',[])+sugestao.get('cura',{}).get('linhas',[])
    candidatos=[m for m in linhas if m['id']==cast.get('magia_id') and (not m.get('alvo') or m['alvo']==cast.get('alvo') or m['alvo']=='eu' and cast.get('alvo') in (None,sugestao['contexto']['char']))]
    if len(candidatos)!=1:return {'elegibilidade':'inconclusiva'}
    m=candidatos[0];mana=recursos.get('mana');t=cast['t']
    if not mana or t-recursos.get('t',-999)>4:return {'elegibilidade':'inconclusiva'}
    if mana['atual']<(m.get('mana') or 0) or mana['percentual']<(m.get('mana_percent') or 0):return {'elegibilidade':'condicao_ausente'}
    if m.get('tipo')=='cura':
        alvo=m.get('alvo','eu');vida=recursos.get('vida') if alvo=='eu' else recursos.get('aliados',{}).get(alvo)
        if not vida or vida.get('percentual') is None:return {'elegibilidade':'inconclusiva'}
        if vida['percentual']>(m.get('vida_percent') or 100):return {'elegibilidade':'condicao_ausente'}
    elif recursos.get('criaturas') is None:return {'elegibilidade':'inconclusiva'}
    elif recursos['criaturas']<(m.get('creatures') or 1):return {'elegibilidade':'condicao_ausente'}
    conhecidos=[e for e in anterior if e.get('kind')=='cast' and e.get('qualidade')=='identificada' and e['t']<t]
    mesmo=[e['t'] for e in conhecidos if e.get('magia_id')==m['id']]
    if not mesmo:return {'elegibilidade':'inconclusiva'} # prontidão anterior desconhecida
    por_id={v['id']:v for v in linhas};grupo=m.get('grupo_id') or ('cura' if m.get('tipo')=='cura' else 'ataque')
    prontas=[max(mesmo)+m['cd']]
    for e in conhecidos:
        outro=por_id.get(e['magia_id']);
        if not outro:continue
        if (outro.get('grupo_id') or ('cura' if outro.get('tipo')=='cura' else 'ataque'))==grupo:prontas.append(e['t']+outro['grupo'])
        if m.get('grupo_secundario') and outro.get('grupo_secundario')==m['grupo_secundario']:prontas.append(e['t']+(outro.get('cd_compartilhado') or 0))
    # Só a oportunidade conhecida no quadro anterior, depois de todos os relógios,
    # permite medir atraso. Não penalizar gaps, leitura parcial ou condição ausente.
    pronto=max(prontas)
    if pronto>t or recursos['t']>pronto or t-pronto>4:return {'elegibilidade':'inconclusiva'}
    return {'elegibilidade':'confirmada','elegivel_em':pronto}


def construir(char,sessao,eventos,quadros,party,magias,modelo=None):
    """Cura só ganha magnitude com cast explícito e HP faltante suficiente."""
    casts=[e for e in eventos if e.get('kind')=='cast' and e.get('qualidade')=='identificada']
    # Vocação somente da informação explícita do cliente. O nome e a magia
    # recebida não permitem adivinhar EK/RP; conservar essa distinção.
    conhecidos={p['nome'].casefold():dict(p) for p in party if p.get('nome')}
    destinos={e.get('alvo','').casefold() for e in casts if e.get('magia_id') in ('heal_friend','nature_s_embrace')}
    vocs={'elite knight':'EK','knight':'EK','royal paladin':'RP','paladin':'RP','elder druid':'ED','druid':'ED','master sorcerer':'MS','sorcerer':'MS'}
    for e in eventos:
        nome=e.get('target') or e.get('alvo');voc=vocs.get(e.get('vocation','').casefold())
        if e.get('kind')=='player_info' and nome and voc and (nome.casefold() in conhecidos or nome.casefold() in destinos):
            conhecidos[nome.casefold()]={'nome':nome,'vocacao':voc,'origem':'look_do_cliente','instante':e['t'],'identidade_confirmada':True}
    party=list(conhecidos.values())
    potencias=collections.defaultdict(list);cobertura=collections.defaultdict(list)
    por_id={m['id']:m for m in magias}
    for e in eventos:
        if e.get('kind') not in ('heal_self','heal_other','damage_dealt'):continue
        tipo = 'ofensiva' if e['kind']=='damage_dealt' else 'cura'
        perto=[p for p in casts if por_id.get(p.get('magia_id'),{}).get('tipo')==tipo
               and 0<=e['t']-p['t']<=1 and (not p.get('alvo') or p['alvo']==e.get('alvo'))]
        if len(perto)!=1:continue
        magia=por_id.get(perto[0]['magia_id']);
        if not magia:continue
        if e['kind']=='damage_dealt':
            # O console usa nome de ESPÉCIE e perde linhas. Só uma medida
            # explícita e completa de instâncias pode alimentar cobertura.
            if e.get('cobertura_completa') and isinstance(e.get('alvos_atingidos'), int):
                cobertura[magia['id']].append(e['alvos_atingidos'])
        else:
            prev=next((r for r in reversed(quadros) if r['t']<=perto[0]['t'] and perto[0]['t']-r['t']<=4),None)
            vida=(prev or {}).get('vida') if e.get('alvo')==char else (prev or {}).get('aliados',{}).get(e.get('alvo'))
            if not vida or vida.get('maxima') is None or vida.get('atual') is None or vida['maxima']-vida['atual']<=e.get('value',0):continue
            if e.get('crit'):continue
            if magia.get('tipo')=='cura' and perto[0].get('base_multiplicador'):
                potencia=(e['value']-perto[0].get('fixo_hp',0))/perto[0]['base_multiplicador']
                if potencia>0:potencias[magia['id']].append(potencia)
    # Modelo disponível somente após amostra repetida, validado fora do ajuste.
    hp={};qualidade={}
    for ident,valores in potencias.items():
        if len(valores)<12:continue
        treino=valores[:-4];teste=valores[-4:];med=statistics.median(treino)
        if statistics.mean(abs(v-med)/max(1,med) for v in teste)>.30:continue
        hp[ident]=med;qualidade[ident]={'treino':len(treino),'validacao':4,'origem':'cast_e_cura_identificados_build_conferida','unidade':'HP_sem_bonus_de_roda'}
    janelas=[]
    ult=quadros[-1]['t'] if quadros else 0;desde=max(0,ult-180)
    for a,b in zip(quadros,quadros[1:]):
        if a['t']<desde or not 0<b['t']-a['t']<=6 or not a.get('vida'):continue
        vida={'eu':a['vida'],**{n:v for n,v in a.get('aliados',{}).items() if v.get('atual') is not None and v.get('maxima') is not None}}
        eventos_janela=[e for e in eventos if a['t']<=e['t']<b['t']]
        dano=collections.Counter();externa=collections.Counter()
        for e in eventos_janela:
            n=e.get('value',0);alvo='eu' if e.get('alvo')==char else e.get('alvo')
            if e.get('kind') in ('damage_taken','damage_condition','damage_taken_player','damage_plain_player') and alvo in vida:dano[alvo]+=n
            if e.get('kind') in ('healed','healed_player') and alvo in vida:externa[alvo]+=n
        janelas.append({'t':a['t']-desde,'fim':b['t']-desde,'vida':vida,'dano':dict(dano),'cura_externa':dict(externa),
                        'modo_vida':'contrafactual','mana':a.get('mana',{}).get('atual'),'mana_maxima':a.get('mana',{}).get('maxima'),
                        'alcancaveis':list(a.get('aliados',{})),'cobertos':a.get('cobertos',[]),'criaturas':a.get('criaturas')})
    atributos={}
    for q in quadros:atributos.update(q.get('atributos',{}))
    posturas=[e['magia_id'] for e in casts if e['magia_id'] in ('shared_conservation','elemental_synthesis','master_of_flames','master_of_thunder','master_of_decay')]
    if posturas:atributos['postura']=posturas[-1]
    primeiro=next((q for q in quadros if q['t']>=desde),{})
    pronta={ident:max(0,primeiro['t']-desde+v['restante_s']) for ident,v in primeiro.get('prontidao',{}).items()
            if isinstance(v.get('restante_s'),(int,float))}
    return {'versao':2,'char':char,'sessao':sessao,'modelo_versao':(modelo or {}).get('versao'),
            'pronta':pronta,
            'nivel':atributos.get('nivel'),'atributos':atributos,
            'cobertura':{m:statistics.median(v) for m,v in cobertura.items() if len(v)>=12} or None,
            'cura':{'potencia_hp':hp,'qualidade':qualidade,'janelas':janelas,'aliados':party,'postura':atributos.get('postura'),'critico_chance':atributos.get('critico_chance'),'critico_extra':atributos.get('critico_extra')},
            'periodo':{'desde':desde,'ate':ult},'estado':'medido_parcial','fontes':['console_identificado','barras_visuais']}
