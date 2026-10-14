"""Períodos e experimento prospectivo de XP; regras puras, sem cliente."""
import math

from rubinot.hunt.metricas import taxas_intervalos

CONTEXTO = ('char','hunt','pt','membros','hazard','roda','rota','interferencias')
POLITICA = {'min_voltas':3, 'cobertura_min':0.8, 'margem_relativa':0.02,
            'vida_critica_pct':30, 'max_gap_vida_s':2,
            'criterio':'XP primeiro, dano secundário, segurança sem piora'}


def twin(slots):
    rows = [s for s in slots if s.get('id') in ('ice_burst','terra_burst') and s.get('atual') is not False]
    if len(rows)!=1 or type(rows[0].get('creatures')) is not int:
        return None
    return rows[0]['creatures']


def conteudo(leitura):
    return {'slots':[{k:v for k,v in s.items() if k not in ('instante','prova')} for s in leitura.get('slots',[])],
            'campos':{k:v.get('valor') for k,v in leitura.get('campos',{}).items()}}


def periodos(leituras, recursos):
    """Mudança observada delimita fronteira incerta desde a última leitura igual."""
    eventos = [(l['instante'],0,l) for l in leituras if l.get('instante') is not None]
    eventos += [(r['instante'],1,r) for r in recursos if r.get('instante') is not None]
    estado = {}; contexto = {}; fases = []; ultimos = {}
    for instante,tipo,e in sorted(eventos,key=lambda x:(x[0],x[1])):
        incerto = None
        if tipo==0:
            componente=e.get('tipo')
            valor=conteudo(e)
            anterior=estado.get(componente)
            if anterior==valor:
                ultimos[componente]=instante
                continue
            if anterior is not None:
                incerto={'inicio':ultimos[componente],'fim':instante,'componente':componente}
            estado={**estado,componente:valor}
            ultimos[componente]=instante
        else:
            novo=e.get('contexto_twin',{})
            if novo==contexto:
                ultimos['contexto']=instante
                continue
            if contexto:
                incerto={'inicio':ultimos.get('contexto',instante),'fim':instante,'componente':'contexto'}
            contexto=novo
            ultimos['contexto']=instante
        fases.append({'inicio':instante,'fim':None,'twin':twin(estado.get('rtc',{}).get('slots',[])),
            'configuracoes':dict(estado),'contexto':dict(contexto),'fronteira':incerto})
    for a,b in zip(fases,fases[1:]):
        a['fim']=b['inicio']
    return fases


def fase_intervalo(fases, inicio, fim):
    if inicio is None or fim is None or fim<=inicio:
        return None
    if any(f.get('fronteira') and f['fronteira']['inicio']<fim and f['fronteira']['fim']>inicio for f in fases):
        return None
    return next((i for i,f in enumerate(fases) if f['inicio']<=inicio and (f['fim'] is None or fim<=f['fim'])),None)


def contador(recurso, metrica):
    paineis=recurso.get('paineis',{}).get('observacao',{}).get('paineis',{})
    if metrica=='raw':
        m=paineis.get('xp',{}).get('campos',{}).get('RawXPGain',{})
        return m.get('valor') if m.get('origem')=='XP Analyser' and m.get('estado')=='lido' else None
    party=paineis.get('party',{})
    if not party.get('membros_completos'):
        return None
    membros=party.get('membros',[])
    if metrica=='dano_proprio':
        membros=[m for m in membros if m.get('nome')==recurso.get('contexto_twin',{}).get('char')]
        if len(membros)!=1:
            return None
    valores=[m.get('dano',{}).get('valor') for m in membros]
    return sum(valores) if valores and all(type(v) in (int,float) for v in valores) else None


def seguranca_periodo(recursos, contexto, inicio, fim, mortes):
    """Cobertura por integrante; lacunas e baixas críticas bloqueiam propostas."""
    membros=contexto.get('membros') or []
    saida={}
    for nome in membros:
        rows=[]
        for r in recursos:
            t=r.get('instante')
            if t is None or not inicio<=t<=fim:
                continue
            vida=r.get('vida',{}) if nome==contexto.get('char') else r.get('aliados',{}).get(nome,{})
            v=(vida or {}).get('percentual')
            if type(v) in (int,float) and 0<=v<=100:
                rows.append((t,v))
        rows=sorted(dict(rows).items())
        tempo=sum(b[0]-a[0] for a,b in zip(rows,rows[1:]) if 0<b[0]-a[0]<=POLITICA['max_gap_vida_s'])
        minimo=min((v for _,v in rows),default=None)
        saida[nome]={'cobertura':tempo/(fim-inicio) if fim>inicio else 0,'minimo':minimo}
    mortes_trecho=[e for e in mortes if inicio<=e.get('instante',-1)<=fim]
    avaliada=bool(membros) and not mortes_trecho and all(m['cobertura']>=POLITICA['cobertura_min']
        and m['minimo'] is not None and m['minimo']>POLITICA['vida_critica_pct'] for m in saida.values())
    return {'avaliada':avaliada,'por_membro':saida,'mortes_confirmadas':len(mortes_trecho),
            'alcance':'seguranca_observacional_amostrada'}


def medir(leituras, recursos, voltas, vidas=(), mortes=()):
    fases=periodos(leituras,recursos)
    medidas=[[] for _ in fases]
    rows=sorted({r['instante']:r for r in recursos if r.get('instante') is not None}.values(),key=lambda r:r['instante'])
    for a,b in zip(rows,rows[1:]):
        i=fase_intervalo(fases,a['instante'],b['instante'])
        if i is None or b['instante']-a['instante']>30:
            continue
        valores={}
        for m in ('raw','dano_proprio','dano_pt'):
            x,y=contador(a,m),contador(b,m)
            valores[m]=y-x if type(x) in (int,float) and type(y) in (int,float) and y>=x else None
        medidas[i].append({'inicio':a['instante'],'fim':b['instante'],**valores,
            'fontes':{'raw':'XP Analyser','dano_proprio':'Party Hunt','dano_pt':'Party Hunt'},
            'provas':[a.get('prova',a.get('origem')),b.get('prova',b.get('origem'))]})
    for i,f in enumerate(fases):
        fim=f['fim'] if f['fim'] is not None else max((r['instante'] for r in rows),default=f['inicio'])
        vs=[v for v in voltas if v.get('completa') and fase_intervalo(fases,v.get('inicio'),v.get('fim'))==i]
        f.update(fim_observado=fim,tempo_s=max(0,fim-f['inicio']),voltas=len(vs),
                 taxas=taxas_intervalos(medidas[i]))
        f['cobertura']=f['taxas']['raw']['tempo_s']/f['tempo_s'] if f['tempo_s'] else 0
        f['raw_por_volta']=[taxas_intervalos([m for m in medidas[i] if v['inicio']<=m['inicio'] and m['fim']<=v['fim']])['raw']['por_h'] for v in vs]
        f['uso_confirmado']=bool(vs) and all(v.get('uso_confirmado') is True for v in vs)
        f['saude']=seguranca_periodo([*recursos,*vidas],f['contexto'],f['inicio'],fim,mortes)
        f['seguranca']=f['saude']['avaliada']
    return fases


def elegivel(f):
    ctx=f.get('contexto',{})
    pt=str(ctx.get('pt','')).lower().replace('pt','').replace('x','').strip()
    membros=ctx.get('membros') or []
    party_completa=pt.isdecimal() and int(pt)>=2 and len(membros)==int(pt) and len(set(membros))==len(membros) and ctx.get('char') in membros
    return (all(ctx.get(k) is not None for k in CONTEXTO) and bool(ctx.get('char'))
            and bool(ctx.get('hunt')) and party_completa and bool(ctx.get('roda'))
            and bool(ctx.get('rota')) and f.get('voltas',0)>=POLITICA['min_voltas']
            and f.get('cobertura',0)>=POLITICA['cobertura_min'] and f.get('uso_confirmado') is True
            and f.get('seguranca') is True and f.get('taxas',{}).get('raw',{}).get('por_h') is not None)


def propor(referencia, anteriores, instante, candidato=4):
    if (referencia.get('twin') not in (4,5,6) or not elegivel(referencia) or instante<=referencia['fim_observado']
            or instante-referencia['fim_observado']>7*86400 or referencia['taxas']['raw']['por_h']<=0):
        return None
    if candidato not in (4,6) or candidato==referencia['twin']:
        return None
    if any(e.get('contexto')==referencia['contexto'] and e.get('candidato')==candidato and
           (e.get('referencia',{}).get('sessao'),e.get('referencia',{}).get('inicio'))==
           (referencia.get('sessao'),referencia.get('inicio')) for e in anteriores):
        return None
    if any(e.get('contexto')==referencia['contexto'] and e.get('estado') in ('proposto','configuracao_observada','em_avaliacao','promissor') for e in anteriores):
        return None
    valores=[v for v in referencia.get('raw_por_volta',[]) if v is not None]
    variacao=(max(valores)-min(valores))/2 if len(valores)>=3 else None
    if variacao is None:
        return None
    return {'instante':instante,'estado':'proposto','referencia':referencia,'contexto':referencia['contexto'],
        'candidato':candidato,'ajustes':[{'campo':'Twin.creatures','antes':referencia['twin'],'depois':candidato}],
        'politica':{**POLITICA,'definida_em':instante,'margem_raw_h':max(variacao,referencia['taxas']['raw']['por_h']*POLITICA['margem_relativa'])},
        'motivo':'Testar o equilíbrio entre oportunidades e espera da Twin, medindo primeiro raw XP/h.',
        'ganho_previsto':None,'aplicacao':'usuario_na_proxima_hunt'}


def avaliar(experimento, resultado, anteriores=()):
    out={'estado':'inconclusivo','manter':experimento['referencia']['twin'],'promover':False,'resultado':resultado}
    politica=experimento['politica'];ref=experimento['referencia']
    if (resultado.get('twin')!=experimento['candidato'] or resultado.get('inicio',0)<=experimento['instante']
            or politica.get('definida_em',float('inf'))>=resultado.get('inicio',0)):
        return out
    out['estado']='configuracao_observada'
    if resultado.get('saude',{}).get('mortes_confirmadas',0):
        out['estado']='pior'
        return out
    def controles(f):
        configuracoes=f.get('configuracoes',{})
        rtc=configuracoes.get('rtc',{})
        return {**configuracoes,'rtc':{**rtc,'slots':[
            {k:v for k,v in s.items() if not (k=='creatures' and s.get('id') in ('ice_burst','terra_burst'))}
            for s in rtc.get('slots',[])]}}
    if (not elegivel(resultado) or resultado.get('contexto')!=experimento['contexto']
            or controles(ref)!=controles(resultado)):
        out['estado']='em_avaliacao' if resultado.get('voltas',0)<3 else 'inconclusivo'
        return out
    # Piora de vida observada não pode ser trocada por XP/dano.
    if ref.get('saude') and any(m['minimo']<ref['saude']['por_membro'].get(nome,{}).get('minimo',101)
            for nome,m in resultado.get('saude',{}).get('por_membro',{}).items()):
        out['estado']='pior'
        return out
    ganho=resultado['taxas']['raw']['por_h']-ref['taxas']['raw']['por_h']
    valores=[v for v in resultado.get('raw_por_volta',[]) if v is not None and math.isfinite(v)]
    if len(valores)<3:
        out['estado']='inconclusivo'
        return out
    erro=(max(valores)-min(valores))/2
    out.update(ganho_raw_h=ganho,intervalo=[ganho-erro,ganho+erro])
    margem=politica['margem_raw_h']
    out['estado']='pior' if ganho+erro < -margem else 'promissor' if ganho-erro>margem else 'inconclusivo'
    # Outra hunt posterior; o resultado reservado anterior nunca conta de novo.
    if out['estado']=='promissor' and any(a.get('estado')=='promissor' and a.get('resultado',{}).get('sessao')!=resultado.get('sessao')
            and a.get('resultado',{}).get('fim_observado',float('inf'))<resultado['inicio'] for a in anteriores):
        out.update(estado='validado_posteriormente',promover=True,manter=experimento['candidato'])
    return out
