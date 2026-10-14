"""Correção regularizada e avaliação por sessões, sem IO nem alteração de regras."""
import collections
import hashlib
import json
import math
import statistics

VERSAO = 'residual-sessoes-1'


def chave(contexto):
    return json.dumps(contexto, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def validos(dados):
    unicos = {}
    for d in dados:
        if (d.get('qa') or d.get('sintetico') or not d.get('origem_id') or not d.get('sessao')
                or not d.get('contexto') or not d.get('grupo')):
            continue
        if not all(isinstance(d.get(k), (int, float)) and not isinstance(d[k], bool)
                   and math.isfinite(d[k]) for k in ('instante', 'previsto', 'observado')):
            continue
        if d['previsto'] <= 0 or d['observado'] <= 0:
            continue
        # Mesmo evento copiado continua sendo uma única origem.
        unicos.setdefault(d['origem_id'], d)
    return sorted(unicos.values(), key=lambda d:(d['instante'], d['origem_id']))


def ajustar(dados, regularizacao=3):
    """Cada sessão tem um voto; filhos encolhem para o grupo, não outro contexto."""
    grupos = collections.defaultdict(lambda: collections.defaultdict(list))
    filhos = collections.defaultdict(lambda: collections.defaultdict(list))
    for d in dados:
        k = chave([d['contexto'], d['grupo']])
        erro = math.log(d['observado']/d['previsto'])
        grupos[k][d['sessao']].append(erro)
        filhos[chave([d['contexto'], d['grupo'], d.get('faixa')])][d['sessao']].append(erro)
    pais = {k: statistics.median(statistics.median(v) for v in ss.values()) for k, ss in grupos.items()}
    perfis = {}
    for d in dados:
        k = chave([d['contexto'], d['grupo'], d.get('faixa')])
        if k in perfis:
            continue
        valores = [statistics.median(v) for v in filhos[k].values()]
        n = len(valores); pai = pais[chave([d['contexto'], d['grupo']])]
        media = (n*statistics.median(valores)+regularizacao*pai)/(n+regularizacao)
        perfis[k] = {'fator': math.exp(max(-3, min(3, media))), 'sessoes': n,
                     'dispersao_log': statistics.median(abs(v-media) for v in valores)}
    return perfis


def prever(perfis, d):
    p = perfis.get(chave([d['contexto'], d['grupo'], d.get('faixa')]))
    return d['previsto']*p['fator'] if p else d['previsto']


def avaliar(perfis, dados):
    por_sessao = collections.defaultdict(list)
    for d in dados:
        antes = abs(math.log(d['observado']/d['previsto']))
        depois = abs(math.log(d['observado']/prever(perfis, d)))
        por_sessao[d['sessao']].append((antes, depois))
    pares = [(statistics.mean(a for a, _ in rows), statistics.mean(b for _, b in rows))
             for rows in por_sessao.values()]
    ganhos = [a-b for a, b in pares]
    margem = 2*statistics.stdev(ganhos)/math.sqrt(len(ganhos)) if len(ganhos)>1 else None
    return {'sessoes': len(pares), 'erro_base': statistics.mean(a for a, _ in pares) if pares else None,
            'erro_modelo': statistics.mean(b for _, b in pares) if pares else None,
            'ganho_inferior': statistics.mean(ganhos)-margem if margem is not None else None}


def treinar(dados, anterior=None):
    dados = validos(dados)
    sessoes = collections.defaultdict(list)
    for d in dados:
        sessoes[d['sessao']].append(d)
    ordem = sorted(sessoes, key=lambda s:sessoes[s][0]['instante'])
    out = {'versao': VERSAO, 'estado': 'coletando', 'promover': False, 'perfis': {},
           'sessoes': len(ordem), 'amostras': len(dados), 'unidade': 'erro_log_relativo',
           'semantica': 'previsao_parcial_nao_beneficio_causal'}
    if len(ordem)<6:
        return out
    # Treino, seleção e pelo menos duas sessões futuras independentes.
    n = max(3, len(ordem)-max(3, math.ceil(len(ordem)*.4)))
    a, b = ordem[:n], ordem[n:-2]
    treino = [d for s in a for d in sessoes[s]]
    selecao = [d for s in b for d in sessoes[s]]
    teste = [d for s in ordem[-2:] for d in sessoes[s]]
    if not selecao or max(d['instante'] for d in treino)>=min(d['instante'] for d in selecao) or max(d['instante'] for d in selecao)>=min(d['instante'] for d in teste):
        out['estado'] = 'sessoes_sobrepostas'; return out
    # Nenhum hiperparâmetro escolhido no teste final.
    candidatos = [ajustar(treino, r) for r in (3, 6)]
    escolhido = min(candidatos, key=lambda p:avaliar(p, selecao)['erro_modelo'])
    escolha = avaliar(escolhido, selecao)
    out['selecao'] = escolha
    if escolha['erro_modelo']>=escolha['erro_base']*.95:
        out['estado'] = 'sem_melhoria_na_selecao'; return out
    teste_r = avaliar(escolhido, teste)
    aceita = teste_r['ganho_inferior'] is not None and teste_r['ganho_inferior']>0 and teste_r['erro_modelo']<teste_r['erro_base']*.95
    if anterior and anterior.get('perfis'):
        # Modelo anterior deve ser anterior ao teste, senão é comparação contaminada.
        if anterior.get('avaliado_ate', float('inf'))>=min(d['instante'] for d in teste):
            aceita = False
        else:
            out['teste_anterior'] = avaliar(anterior['perfis'], teste)
            aceita = aceita and teste_r['erro_modelo']<out['teste_anterior']['erro_modelo']
    out.update(estado='aprovado_previsao_parcial' if aceita else 'sem_melhoria_no_teste', promover=aceita,
               teste=teste_r, treino_sessoes=a, selecao_sessoes=b, teste_sessoes=ordem[-2:],
               treino_ate=max(d['instante'] for d in treino), avaliado_ate=max(d['instante'] for d in teste),
               origens=[d['origem_id'] for d in dados], perfis=escolhido if aceita else {})
    out['id'] = hashlib.sha256(chave(out).encode()).hexdigest()
    return out
