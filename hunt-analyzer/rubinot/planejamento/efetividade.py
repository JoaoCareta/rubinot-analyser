"""Avaliação posterior de ajustes; unidade causal é o pacote adotado."""
import math
import statistics


def contraste_temporal(antes, depois, medida, direcao=1):
    """Sessões independentes, sem transformar quadros/voltas em réplicas."""
    def unicos(rows):
        return list({r['origem_id']:r for r in rows if r.get('origem_id') and
            isinstance(r.get('medidas', {}).get(medida), (int,float))}.values())
    a, b = unicos(antes), unicos(depois)
    if len(a)<2 or len(b)<2 or {r['origem_id'] for r in a}&{r['origem_id'] for r in b}:
        return {'estado':'inconclusivo', 'intervalo_ganho':None}
    if max(r.get('fim', float('inf')) for r in a) >= min(r.get('inicio', 0) for r in b):
        return {'estado':'inconclusivo', 'intervalo_ganho':None}
    contexto = a[0].get('contexto')
    if not contexto or any(r.get('contexto')!=contexto for r in [*a,*b]):
        return {'estado':'inconclusivo', 'intervalo_ganho':None}
    xs, ys = [r['medidas'][medida] for r in a], [r['medidas'][medida] for r in b]
    ganho = (statistics.mean(ys)-statistics.mean(xs))*direcao
    erro = math.sqrt(statistics.variance(xs)/len(xs)+statistics.variance(ys)/len(ys))
    # Faixa conservadora pelo tamanho da menor amostra; não fingir precisão
    # normal com apenas duas sessões de cada lado.
    fator = 12.71 if min(len(a),len(b))==2 else 4.31 if min(len(a),len(b))==3 else 3.18
    return {'estado':'contraste_observado', 'intervalo_ganho':[ganho-fator*erro,ganho+fator*erro],
            'origem_incerteza':'contraste_entre_sessoes_independentes',
            'antes_n':len(a),'depois_n':len(b),'ganho':ganho,
            'media_antes':statistics.mean(xs), 'media_depois':statistics.mean(ys)}


def dividir_temporal(episodios):
    """Identidade da origem evita cópias em conjuntos distintos."""
    unicos = {}
    for e in episodios:
        origem = e.get('origem_id')
        if not origem or e.get('inicio') is None or e.get('fim') is None: continue
        if origem not in unicos or e['inicio'] < unicos[origem]['inicio']: unicos[origem] = e
    rows = sorted(unicos.values(), key=lambda e: e['inicio'])
    n = len(rows); a = n//2; b = n*3//4
    treino, selecao, teste = rows[:a], rows[a:b], rows[b:]
    for anterior, posterior in ((treino, selecao), (selecao, teste)):
        if anterior and posterior and max(e['fim'] for e in anterior) >= min(e['inicio'] for e in posterior):
            return {'estado': 'inconclusivo_sobreposicao', 'treino': [], 'selecao': [], 'teste': []}
    return {'estado': 'separado' if treino and selecao and teste else 'exposicao_insuficiente',
            'treino': treino, 'selecao': selecao, 'teste': teste}


def avaliar_ajuste(recomendacao, antes, depois, politica):
    """A margem e a exposição são registradas antes do resultado posterior."""
    limites = []
    alteracoes = recomendacao.get('alteracoes', [])
    saida = {'versao': 'efetividade-1', 'recomendacao_id': recomendacao.get('id'),
             'objetivo_declarado': recomendacao.get('objetivo_declarado'),
             'expectativa': recomendacao.get('expectativa'), 'adocao': recomendacao.get('adocao'),
             'unidade_avaliada': 'pacote' if len(alteracoes) != 1 else 'ajuste',
             'alteracoes': alteracoes, 'resultados': {}, 'incerteza': {},
             'limites_atribuicao': limites, 'estado': 'inconclusivo', 'promover': False}
    if len(alteracoes) > 1: limites.append('alteracoes_simultaneas_sem_atribuicao_individual')
    if not alteracoes: limites.append('nenhuma_alteracao_adotada')
    adocao = recomendacao.get('adocao') or {}
    if not adocao.get('uso_confirmado'): limites.append('adocao_desconhecida')
    if antes.get('contexto') != depois.get('contexto') or not antes.get('contexto'):
        limites.append('contextos_nao_comparaveis')
    if not antes.get('fim') or not depois.get('inicio') or antes['fim'] >= depois['inicio']:
        limites.append('resultado_nao_posterior')
    if not politica.get('definida_em') or politica['definida_em'] >= depois.get('inicio', 0):
        limites.append('politica_nao_reservada_antes_da_avaliacao')
    minimo = politica.get('exposicao_min_s')
    if minimo is None or min(antes.get('exposicao_s', 0), depois.get('exposicao_s', 0)) < minimo:
        limites.append('exposicao_insuficiente')
    if depois.get('seguranca') != 'avaliada_sem_piora': limites.append('seguranca_nao_certificada')
    if depois.get('vigencia_estavel') is False: limites.append('resultado_com_fases_mistas_ou_anteriores_adocao')
    medida = politica.get('medida'); a = antes.get('medidas', {}).get(medida); b = depois.get('medidas', {}).get(medida)
    margem = politica.get('margem_pratica'); faixa = depois.get('intervalo_ganho')
    if a is None or b is None or margem is None or not faixa or len(faixa) != 2:
        limites.append('medida_margem_ou_incerteza_ausente')
    if limites and any(x != 'alteracoes_simultaneas_sem_atribuicao_individual' for x in limites): return saida
    ganho = (b-a)*politica.get('direcao', 1)
    saida['resultados'] = {'medida': medida, 'antes': a, 'depois': b, 'ganho': ganho}
    saida['incerteza'] = {'intervalo_ganho': faixa, 'origem': depois.get('origem_incerteza')}
    if faixa[1] < -margem: saida['estado'] = 'resultado_misto_ou_piora'
    elif faixa[0] > margem: saida['estado'] = 'beneficio_relevante'; saida['promover'] = True
    elif faixa[0] > 0: saida['estado'] = 'beneficio_moderado'
    elif faixa[0] >= -margem and faixa[1] <= margem: saida['estado'] = 'sem_ganho_relevante_detectavel'
    return saida


def contribuicao_bonus(casts, bonus):
    """Casts conhecidos e elegíveis; dano total não vira ganho incremental."""
    unicos = {e['id']: e for e in casts if e.get('id') and e.get('kind') == 'cast'
              and e.get('qualidade') == 'identificada' and e.get('magia_id') == bonus.get('magia_id')}
    elegiveis = [e for e in unicos.values() if e.get('bonus_elegivel') is True]
    aplicados = [e for e in elegiveis if bonus.get('tipo') == 'passivo' or e.get('bonus_ativado') is True]
    incrementos = [e['contribuicao_incremental'] for e in aplicados if e.get('contribuicao_incremental') is not None]
    return {'magia_id': bonus.get('magia_id'), 'casts_identificados': len(unicos),
            'usos_elegiveis': len(elegiveis), 'aplicacoes_identificadas_ou_derivadas': len(aplicados),
            'contribuicao_incremental': sum(incrementos) if len(incrementos) == len(aplicados) and aplicados else None,
            'origem_aplicacoes': 'derivada_passiva' if bonus.get('tipo') == 'passivo' else 'ativacao_identificada',
            'cobertura_completa': False, 'custo_investimento': bonus.get('custo_investimento')}


def uso_bonus_por_magia(casts, beneficios, declaracao_id):
    """Efeitos normativos identificados; nunca reparte o dano total medido."""
    saida = []
    for bonus in beneficios:
        exemplos = [{**e, 'bonus_elegivel':True} for e in casts
            if e.get('declaracao_uso_id') == declaracao_id and declaracao_id]
        r = contribuicao_bonus(exemplos, bonus)
        r.update(atributo=bonus.get('atributo'), estagio=bonus.get('estagio'),
                 modificador_normativo=bonus.get('modificador'),
                 unidade_modificador=bonus.get('unidade'),
                 limite_atribuicao='Incremento real depende da base, alvos e outras fontes conhecidos.')
        saida.append(r)
    return saida
