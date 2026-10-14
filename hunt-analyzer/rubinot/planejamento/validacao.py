"""Políticas reservadas e validação cronológica da execução atual."""
import collections
import math
import statistics

from rubinot.planejamento.efetividade import dividir_temporal


def calibrar_politica(episodios, definida_em):
    particao = dividir_temporal(episodios)
    treino = particao['treino']; selecao = particao['selecao']; teste = particao['teste']
    out = {'versao': 'politica-pressao-1', 'definida_em': definida_em,
           'estado': 'coletando', 'promover': False, 'max_gap_s': 6,
           'origens': {k:[r['origem_id'] for r in particao[k]] for k in ('treino','selecao','teste')}}
    # Rótulo reservado vem de auditoria de provas, nunca do classificador.
    if particao['estado'] != 'separado' or any(len(rows) < 2 for rows in (treino,selecao,teste)):
        return out
    if any(r.get('rotulo_origem') != 'auditoria_provas' or r.get('vida_minima') is None
           or r.get('rotulo') not in ('tranquila','controlada','pouca_margem') for r in [*treino,*selecao,*teste]):
        return out
    criticos = [r['vida_minima'] for r in treino if r['rotulo'] == 'pouca_margem']
    esforco = [r.get('esforco_por_min') for r in treino if r['rotulo'] == 'tranquila']
    esforco = [v for v in esforco if v is not None]
    if not criticos or not esforco:
        return out
    limite = max(30, statistics.median(criticos))
    baixo = max(esforco)
    def classe(r):
        if r['vida_minima'] <= limite:
            return 'pouca_margem'
        return 'tranquila' if r.get('esforco_por_min') is not None and r['esforco_por_min'] <= baixo else 'controlada'
    def avaliar(rows):
        return {'n':len(rows), 'acertos':sum(classe(r)==r['rotulo'] for r in rows),
                'falsas_tranquilas':sum(classe(r)=='tranquila' and r['rotulo']!='tranquila' for r in rows)}
    s = avaliar(selecao)
    out.update(critico_pct=limite, esforco_baixo_por_min=baixo, selecao=s,
               exposicao_min_s=min(r['fim']-r['inicio'] for r in treino),
               margem_pratica=statistics.pstdev([r['vida_minima'] for r in treino]),
               definida_antes_teste=definida_em < min(r['inicio'] for r in teste))
    if s['falsas_tranquilas'] or s['acertos'] < s['n'] or not out['definida_antes_teste']:
        out['estado'] = 'rejeitada_na_selecao'; return out
    t = avaliar(teste); out['teste'] = t
    out['promover'] = not t['falsas_tranquilas'] and t['acertos'] == t['n']
    out['estado'] = 'validada_no_escopo' if out['promover'] else 'rejeitada_no_teste'
    return out


def classificar_pressao(medidas, politica, membros_esperados=None):
    """Pior integrante; esforço e mana faltantes impedem tranquilidade."""
    estados = {}; esperados = set(membros_esperados or medidas)
    for nome in esperados:
        m = medidas.get(nome, {}); limites = []
        if not politica.get('promover'): limites.append('politica_ainda_nao_validada')
        if m.get('cobertura_s', 0) < politica.get('exposicao_min_s', float('inf')):
            limites.append('exposicao_insuficiente')
        if m.get('fracao_coberta') != 1: limites.append('cobertura_parcial')
        vida = m.get('minimo_observado'); mana = m.get('mana_minima'); esforco = m.get('esforco_por_min')
        if any(v is None for v in (vida,mana,esforco)): limites.append('vida_mana_ou_esforco_ausente')
        estado = 'inconclusiva'
        if not limites:
            estado = 'pressionada_com_pouca_margem' if vida <= politica['critico_pct'] or mana < 5 else \
                'pressionada_mas_controlada' if esforco > politica['esforco_baixo_por_min'] else 'tranquila'
        estados[nome] = {'estado':estado, 'limites':limites, 'medidas':m}
    ordem = ['tranquila','pressionada_mas_controlada','inconclusiva','pressionada_com_pouca_margem']
    return {'versao':'pressao-interpretada-1', 'por_membro':estados,
            'classificacao':max((r['estado'] for r in estados.values()), key=ordem.index, default='inconclusiva'),
            'politica_versao':politica.get('versao')}


def validar_execucao(episodios, escopo, definida_em, anterior=None):
    """Escolhe hipótese na seleção, abre teste uma vez para a vencedora."""
    particao = dividir_temporal(episodios)
    out = {'versao':'execucao-validada-1', 'escopo':escopo, 'estado':'coletando', 'promover':False,
           'politica':{'definida_em':definida_em, 'criterio':'erro_selecao_menor_que_baselines_sem_violacoes'},
           'origens':{k:[r['origem_id'] for r in particao[k]] for k in ('treino','selecao','teste')}}
    if particao['estado'] != 'separado': return out
    def exemplos(rows):
        return [o for r in rows for o in r.get('oportunidades', [])
                if o.get('cobertura_completa') and o.get('origem_execucao') == 'rtc_declarado'
                and o.get('candidatas') and all(not c.get('desconhecidas') for c in o['candidatas'])]
    treino, selecao, teste = [exemplos(particao[k]) for k in ('treino','selecao','teste')]
    # Piso por graus de liberdade, registrado antes de inspecionar o teste.
    hipoteses = ('magia_desempata','runa_desempata')
    minimo = len(hipoteses)*5; out['politica']['minimo_oportunidades'] = minimo
    if any(len(rows) < minimo for rows in (treino,selecao,teste)): return out
    if definida_em >= min(r['inicio'] for r in particao['teste']): return out
    contagem = collections.Counter(o['escolhida'] for o in treino); baseline = contagem.most_common(1)[0][0]
    def prever(o, h):
        cs = [c for c in o['candidatas'] if not c.get('bloqueios')]
        if not cs: return None
        return min(cs, key=lambda c:(c.get('prioridade') or 1,
                   int(c.get('tipo') == ('runa' if h == 'magia_desempata' else 'magia')),
                   c.get('slot') or 0))['id']
    def erro(rows, h):
        return sum(prever(o,h) != o['escolhida'] for o in rows)/len(rows)
    h = min(hipoteses, key=lambda h:erro(selecao,h))
    baseline_erro = sum(o['escolhida'] != baseline for o in selecao)/len(selecao)
    if erro(selecao,h) >= baseline_erro:
        out.update(estado='sem_melhora_na_selecao', selecao_erro=erro(selecao,h)); return out
    e = erro(teste,h); base = sum(o['escolhida'] != baseline for o in teste)/len(teste)
    velho = erro(teste,anterior['hipotese']) if anterior and anterior.get('hipotese') in hipoteses else base
    # Incerteza binomial; melhoria precisa exceder a resolução da amostra.
    incerteza = math.sqrt(e*(1-e)/len(teste))
    aceita = e+incerteza < min(base,velho)
    out.update(estado='validado_no_escopo' if aceita else 'rejeitado_no_teste', promover=aceita,
               hipotese=h, selecao_erro=erro(selecao,h), teste_erro=e,
               teste_baseline_erro=base, teste_anterior_erro=velho,
               incerteza=incerteza, teste_n=len(teste), treino_n=len(treino), selecao_n=len(selecao))
    return out
