"""Avaliação observacional dos gatilhos de cura, em percentual de vida.

Compara condições de disparo, não inventa dano/HP nem um contrafactual de
sobrevivência. Uma candidata aprovada aqui é um teste para a próxima hunt.
"""
import bisect
import hashlib
import json
import math
import statistics
from collections import Counter

VERSAO = 'cura-observacional-1'


def numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def percentual(v):
    p = (v or {}).get('percentual')
    return p if numero(p) and 0 <= p <= 100 else None


def avaliar(linhas, episodios):
    """Unidades: oportunidades observadas, nunca mortes ou turnos evitados."""
    faltas = Counter(); disputas = 0
    for e in episodios:
        elegiveis = {alvo: any(m['alvo']==alvo and e['antes'][alvo]<=m['vida_percent']
                              for m in linhas) for alvo in e['antes']}
        for alvo, urgente in e['urgente'].items():
            if urgente and not elegiveis[alvo]:
                faltas[alvo] += 1
        if elegiveis.get('eu') and not e['urgente']['eu'] and any(
                elegiveis.get(n) and e['antes'][n]<60 for n in e['antes'] if n!='eu'):
            disputas += 1
    return {'urgencias_sem_gatilho':dict(faltas), 'condicoes_concorrentes':disputas,
            'episodios':len(episodios)}


def melhor(a, b):
    nomes = set(a['urgencias_sem_gatilho']) | set(b['urgencias_sem_gatilho'])
    if any(a['urgencias_sem_gatilho'].get(n,0)>b['urgencias_sem_gatilho'].get(n,0) for n in nomes):
        return False
    return (sum(a['urgencias_sem_gatilho'].values()), a['condicoes_concorrentes']) < (
        sum(b['urgencias_sem_gatilho'].values()), b['condicoes_concorrentes'])


def estudar(eventos, recursos, contexto, party, slots):
    """Dados QA nunca entram em estudo real; identidade não usa aproximação OCR."""
    char = contexto.get('char')
    membros = [p for p in party if p.get('identidade_confirmada') and p.get('nome')
               and p.get('vocacao') in ('EK','RP')]
    linhas = []
    for s in slots:
        if s.get('ativo') is False or not numero(s.get('vida_percent')):
            continue
        destinos = [p['nome'] for p in membros if p['vocacao']==s.get('vocacao_destino')]
        alvo = 'eu' if s.get('tipo')=='autocura' else destinos[0] if len(destinos)==1 else None
        if alvo and s.get('id') in ('mass_healing','ultimate_healing','restoration','heal_friend','nature_s_embrace'):
            linhas.append({k:v for k,v in {**s,'alvo':alvo}.items()
                           if k in ('id','alvo','vocacao_destino','vida_percent')})
    eventos = [e for e in eventos if not e.get('qa') and not e.get('sintetico')]
    recursos = sorted({q.get('id',str(q.get('t'))):q for q in recursos
        if numero(q.get('t')) and not q.get('qa') and not q.get('sintetico')}.values(), key=lambda q:q['t'])
    casts = [e for e in eventos if e.get('kind')=='cast' and e.get('ator')==char
             and e.get('qualidade')=='identificada' and e.get('magia_id') in
             ('mass_healing','ultimate_healing','restoration','heal_friend','nature_s_embrace')]
    tempos = sorted(e['t'] for e in casts if numero(e.get('t')))
    alvos = ['eu',*[p['nome'] for p in membros]]
    def vidas(q):
        return {'eu':percentual(q.get('vida')), **{p['nome']:percentual(q.get('aliados',{}).get(p['nome'])) for p in membros}}
    contagens = Counter(); minimos = {}; episodios = []; ultimo = -math.inf
    for q in recursos:
        for n,p in vidas(q).items():
            if p is not None:
                contagens[n] += 1; minimos[n] = min(minimos.get(n,100),p)
    for a,b in zip(recursos,recursos[1:]):
        # Espaçar episódios reduz duplicação de quadros da mesma queda.
        if not 0<b['t']-a['t']<=1.5 or a['t']-ultimo<6:
            continue
        antes, depois = vidas(a), vidas(b)
        if any(antes[n] is None or depois[n] is None for n in alvos):
            continue
        if not a.get('fase_id') or a.get('fase_id')!=b.get('fase_id') or a.get('vigencia_inconclusiva') or b.get('vigencia_inconclusiva'):
            continue
        hz = (a.get('hazard') or {}).get('nivel')
        if hz is None or hz != (b.get('hazard') or {}).get('nivel'):
            continue
        # Prova de combate próximo evita aprender uma política com a cidade.
        i = bisect.bisect_left(tempos,a['t']-2)
        if i==len(tempos) or tempos[i]>b['t']+2:
            continue
        provas = list(dict.fromkeys(p for q in (a,b) if (p:=q.get('prova'))))
        if len(provas)<2:
            continue
        episodios.append({'id':a.get('id'), 't':a['t'],'fim':b['t'],'fase':a['fase_id'],
            'hazard':hz,'antes':antes,'depois':depois,
            'urgente':{n:depois[n]<30 or depois[n]<60 and antes[n]-depois[n]>=15 for n in alvos},
            'provas':provas})
        ultimo = b['t']
    lacunas = []
    if not membros: lacunas.append('Identidade e vocação do EK/RP ainda não confirmadas.')
    if any(s.get('tipo')=='party' and s.get('ativo') is not False and
           len([p for p in membros if p['vocacao']==s.get('vocacao_destino')])!=1 for s in slots):
        lacunas.append('Falta vincular cada regra ativa de cura a um integrante com identidade e vocação confirmadas.')
    if not linhas: lacunas.append('Configuração de cura de referência ainda não lida.')
    elif any(not any(m['alvo']==n for m in linhas) for n in alvos):
        lacunas.append('Faltam gatilhos de cura identificados para algum integrante.')
    if any(contagens[n]==0 for n in alvos): lacunas.append('Vida própria e dos aliados não foi lida para todos os destinos.')
    if len(episodios)<30: lacunas.append(f'Somente {len(episodios)} episódios sincronizados com provas; mínimo de 30 para separar treino, seleção e teste.')
    intervalos = [b['t']-a['t'] for a,b in zip(recursos,recursos[1:]) if b['t']>a['t']]
    if intervalos and statistics.median(intervalos)>1.5:
        lacunas.append('As imagens estão espaçadas demais para avaliar quedas rápidas de vida; a nova coleta precisa registrar a sequência a cada segundo.')
    resultado = {'versao':VERSAO,'contexto':contexto,'sessao':contexto.get('sessao'),
        'estado':'dados_insuficientes','referencia':linhas,'party':membros,'sugestoes':[], 'lacunas':lacunas,
        'configuracao_referencia':[{k:v for k,v in s.items() if k in
            ('id','tipo','ativo','vida_percent','vocacao_destino','destino_indice')} for s in slots],
        'observado':{'recursos':len(recursos),'casts':dict(Counter(e['magia_id'] for e in casts)),
                    'vida_amostras':dict(contagens),'vida_minima':minimos,'episodios':len(episodios),
                    'intervalo_mediano_s':statistics.median(intervalos) if intervalos else None},
        'beneficio_real_validado':False,'unidade':'condicoes_de_disparo_em_episodios_observados',
        'limite':'Condições simultâneas não comprovam turno perdido. Vida posterior pertence à configuração usada; não é previsão de HP com a candidata. Testar na próxima hunt.'}
    if lacunas: return resultado
    # Não misturar Hazard/fase ao certificar uma candidata; cada fase tem seu
    # próprio treino/seleção/teste. A referência atual é avaliada, não retroagida.
    grupos = {}
    for e in episodios: grupos.setdefault((e['fase'],e['hazard']),[]).append(e)
    elegiveis = [es for es in grupos.values() if len(es)>=30]
    if not elegiveis:
        resultado['lacunas'].append('Nenhuma fase contínua tem 30 episódios comparáveis.'); return resultado
    es = max(elegiveis,key=lambda es:es[-1]['t'])
    n = len(es); treino, selecao, teste = es[:n//2],es[n//2:n*3//4],es[n*3//4:]
    candidatas = [linhas]; base_treino = avaliar(linhas,treino)
    for i,m in enumerate(linhas):
        # Gran sio/Restoration são contingência preservada neste estudo parcial.
        if m['id'] not in ('mass_healing','ultimate_healing','heal_friend'): continue
        for delta in (-10,-5,5,10):
            pct = m['vida_percent']+delta
            if 30<=pct<=99:
                cand = [dict(s,vida_percent=pct) if j==i else s for j,s in enumerate(linhas)]
                if melhor(avaliar(cand,treino),base_treino): candidatas.append(cand)
    # Uma mudança por proposta nesta avaliação observacional. O replay completo
    # pode propor duas; não inventar segurança ao combinar ajustes separados.
    pontuar = lambda ms: (sum(avaliar(ms,selecao)['urgencias_sem_gatilho'].values()),
                         avaliar(ms,selecao)['condicoes_concorrentes'],
                         sum(abs(a['vida_percent']-b['vida_percent']) for a,b in zip(ms,linhas)))
    cand = min(candidatas,key=pontuar)
    antes, depois = avaliar(linhas,teste),avaliar(cand,teste)
    aceita = cand!=linhas and melhor(avaliar(cand,selecao),avaliar(linhas,selecao)) and melhor(depois,antes)
    resultado.update(estado='sugestao_para_testar' if aceita else 'sem_melhoria_demonstrada',
        avaliacao={'treino':len(treino),'selecao':len(selecao),'teste':len(teste),
            'treino_ate':treino[-1]['fim'],'teste_desde':teste[0]['t'],
            'hazard':es[0]['hazard'],'fase':es[0]['fase'],'antes':antes,'candidata':depois,
            'teste_ids':[e['id'] for e in teste]})
    if aceita:
        resultado['sugestoes'] = [{**m,'anterior':a['vida_percent'],'origem':'estudo_cura_observacional',
            'sessao':contexto.get('sessao'),'provas':list(dict.fromkeys(p for e in teste for p in e['provas'])),
            'motivo':f"No teste separado: condições concorrentes {antes['condicoes_concorrentes']} → {depois['condicoes_concorrentes']}; sem aumentar urgências sem gatilho em nenhum integrante.",
            'beneficio_real_validado':False} for a,m in zip(linhas,cand) if a!=m]
    return resultado


def identidade(estudo):
    return hashlib.sha256(json.dumps(estudo,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
