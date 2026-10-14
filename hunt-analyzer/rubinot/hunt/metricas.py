"""Contrato canônico de métricas; não depende de captura nem persistência."""
import collections
import math

PAUSA_S = 360   # volta de 6 min ou mais = refill/pausa: fora da média (a mesma constante da tela)


def taxas_intervalos(intervalos):
    """Deltas exclusivos por fonte; tempo de cada medida, sem ratear lacunas."""
    saida = {}
    for metrica, fonte in (('raw','XP Analyser'),('dano_proprio','Party Hunt'),('dano_pt','Party Hunt')):
        rows = sorted(intervalos, key=lambda r:r.get('inicio',0))
        total = segundos = 0
        fim = None
        provas = []
        for r in rows:
            a,b,v = r.get('inicio'),r.get('fim'),r.get(metrica)
            if not all(type(x) in (int,float) and math.isfinite(x) for x in (a,b,v)):
                continue
            if b<=a or v<0 or r.get('fontes',{}).get(metrica)!=fonte or r.get('reset') or r.get('mista'):
                continue
            if fim is not None and a<fim:
                continue
            total += v; segundos += b-a; fim=b; provas.extend(r.get('provas',[]))
        saida[metrica] = {'total':total if segundos else None,'tempo_s':segundos,
                         'por_h':total*3600/segundos if segundos else None,'fonte':fonte,'provas':provas}
    return saida


def tempo_sessao(sessao):
    """Duração observada no Party Hunt; zero é válido, outras origens são lacuna."""
    valor = (sessao or {}).get('tempo_sessao_s')
    return int(valor) if ((sessao or {}).get('tempo_sessao_origem') == 'Party Hunt'
                         and type(valor) in (int,float) and math.isfinite(valor)
                         and 0 <= valor <= 9007199254740991 and valor == int(valor)) else None


def especies(voltas):
    """Espécies da hunt: {nome: mortes}, a mais morta primeiro — a MESMA lista na tela de hunt, no
    resumo guardado e nos bichos da capa do histórico (user, 24/09).

    O motor já tirou de `especies` o que não é bicho e o que é de outra hunt (`_volta`). Sessão em
    que nenhuma volta trouxe espécie cai para o `loots`: antes de 21/09 o loot ainda vinha pelo
    Server Log e era ele que dizia o que morreu.
    """
    vs = [v for v in voltas if (v.get("tipo") or "volta") == "volta"]
    campo = "especies" if any(v.get("especies") for v in vs) else "loots"
    conta = collections.Counter()
    for v in vs:
        conta.update(v.get(campo) or {})
    return dict(conta.most_common())


def taxas(voltas):
    """Os números de um conjunto de voltas — a MESMA conta em toda a tela (user, 24/09: "as fórmulas
    e dados devem ser os mesmos tanto no histórico quanto nas análises").

    Esta é a fonte da verdade; `ui/taxas.js` é a cópia que a tela usa para poder recalcular ao vivo
    e na prévia, e o `_demo` compara as duas com o node para elas nunca desandarem.

    Regras:
      · volta limpa = fechada, não parcial e com menos de PAUSA_S (a volta do refill fica de fora,
        como já ficava na volta média, na mais rápida e na mais lenta)
      · XP raw/h = MEDIANA das voltas limpas com a raw consolidada (15 min × 4 = o número do XP
        Analyser, CLAUDE.md); sem nenhuma consolidada, soma da raw lida ÷ o tempo dessas voltas
      · profit, supplies e bichos = só as voltas em que a medida FOI LIDA, por volta (media) e por
        hora (taxa), numerador e denominador das mesmas voltas — volta sem leitura é lacuna, nunca
        zero (foi o que fez o gráfico dizer 12,10 kk/h numa hunt de 13,90)
    """
    # Math.round da tela arredonda empates para cima; round do Python usa pares.
    arredonda = lambda x: math.floor(x + 0.5)
    vs = [v for v in voltas if (v.get("dur") or 0) > 0 and (v.get("tipo") or "volta") == "volta"]
    limpas = [v for v in vs if not v.get("parcial") and v["dur"] < PAUSA_S]
    est = sorted(v["xp_raw_15min"] * 4 for v in limpas if v.get("xp_raw_15min"))
    com_raw = [v for v in limpas if v.get("xp_raw") is not None]
    seg_raw = sum(v["dur"] for v in com_raw)

    def lidas(k):
        ok = [v for v in limpas if v.get(k) is not None]
        return ok, sum(v["dur"] for v in ok)

    def media(k):
        ok, _ = lidas(k)
        return arredonda(sum(v[k] for v in ok) / len(ok)) if ok else None

    def taxa(k):
        ok, seg = lidas(k)
        return arredonda(sum(v[k] for v in ok) * 3600 / seg) if seg else None

    raw_h = est[len(est) // 2] if est else (arredonda(sum(v["xp_raw"] for v in com_raw) * 3600 / seg_raw) if seg_raw else None)
    return {"voltas": len(limpas), "total": len(vs),
            "parciais": sum(1 for v in vs if v.get("parcial")),
            "refil": len(vs) - len(limpas) - sum(1 for v in vs if v.get("parcial")),
            "dur_s": sum(v["dur"] for v in limpas),
            "dur_media": arredonda(sum(v["dur"] for v in limpas) / len(limpas)) if limpas else None,
            "raw_h": raw_h, "raw_de": "15min" if est else ("soma" if seg_raw else None),
            "voltas_raw": len(com_raw), "voltas_15min": len(est),
            "media": {k: media(j) for k, j in (("profit", "profit"), ("sup_pt", "sup_pt"),
                                               ("sup_eu", "sup_eu"), ("bichos", "bichos"))},
            "taxa": {"profit_h": taxa("profit"), "sup_pt_h": taxa("sup_pt"),
                     "sup_eu_h": taxa("sup_eu"), "bichos_h": taxa("bichos")}}



def pressao(recursos, max_gap_s=6, recuperacao_s=2):
    """Descrição em combate conhecido; gap/pausa não vira tempo seguro."""
    rows = sorted(recursos, key=lambda r: r.get('t', 0))
    faixas = {str(n): 0 for n in (70, 50, 30)}
    cobertura = combate = protegido = exposto = 0
    episodios = []; episodio = None; recuperando = None
    queda = minimo = None
    for a, b in zip(rows, rows[1:]):
        dt = b['t']-a['t']
        valido = 0 < dt <= max_gap_s and a.get('combate') is True and b.get('combate') is True
        if not valido:
            if episodio:
                episodio['incompleto'] = True
                episodios.append(episodio); episodio = None
            recuperando = None
            continue
        combate += dt
        escudo = a.get('escudo')
        if escudo is True: protegido += dt
        elif escudo is False: exposto += dt
        pa = (a.get('vida') or {}).get('percentual')
        pb = (b.get('vida') or {}).get('percentual')
        if pa is None or pb is None or not 0 <= pa <= 100 or not 0 <= pb <= 100:
            if episodio:
                episodio['incompleto'] = True
                episodios.append(episodio); episodio = None
            recuperando = None
            continue
        cobertura += dt
        minimo = min(pa, pb, minimo if minimo is not None else 100)
        queda = max(0, (pa-pb)/dt, queda or 0)
        for n in faixas:
            if pa < int(n): faixas[n] += dt
        if pa < 70 or pb < 70:
            if episodio is None:
                episodio = {'inicio': a['t'], 'fim': b['t'], 'minimo': min(pa,pb), 'incompleto': pa < 70}
            episodio['fim'] = b['t']; episodio['minimo'] = min(episodio['minimo'],pa,pb)
            recuperando = None
        elif episodio:
            if recuperando is None: recuperando = a['t']
            episodio['fim'] = b['t']
            if b['t']-recuperando >= recuperacao_s:
                episodios.append(episodio); episodio = None; recuperando = None
    if episodio:
        episodio['incompleto'] = True
        episodios.append(episodio)
    return {'versao': 'pressao-descritiva-1', 'combate_observavel_s': combate,
            'vida_cobertura_s': cobertura, 'vida_minima_observada': minimo,
            'abaixo_faixa_s': faixas, 'queda_max_pct_s': queda, 'episodios': episodios,
            'escudo_com_s': protegido, 'escudo_sem_s': exposto,
            'escudo_desconhecido_s': combate-protegido-exposto,
            'escudo_cobertura_pct': (protegido+exposto)/combate*100 if combate else None,
            'escudo_protegido_pct': protegido/(protegido+exposto)*100 if protegido+exposto else None}


def consumo_itens(leituras):
    """Contadores de uso por item; inventário não comprova consumo."""
    anteriores = {}; saida = []
    for r in sorted(leituras, key=lambda x: x['t']):
        chave = (r.get('char'), r.get('item'), r.get('serie'), r.get('unidade'))
        anterior = anteriores.get(chave)
        valor = r.get('valor')
        if (r.get('origem') != 'contador_uso' or not r.get('char') or not r.get('item')
                or not isinstance(valor, int) or isinstance(valor, bool) or valor < 0):
            anteriores.pop(chave, None); continue
        anteriores[chave] = r
        if not anterior or not r.get('continuidade') or not r.get('serie') or r.get('unidade') != 'unidades': continue
        dt = r['t']-anterior['t']; delta = valor-anterior['valor']
        if dt <= 0 or delta < 0: continue
        saida.append({'char':r.get('char'), 'item':r.get('item'), 'serie':r['serie'],
                      'inicio':anterior['t'], 'fim':r['t'], 'quantidade':delta,
                      'duracao_s':dt, 'por_minuto':60*delta/dt, 'unidade':'unidades',
                      'denominador':'intervalo_entre_contadores', 'provas':[anterior.get('prova'),r.get('prova')]})
    return saida


def variacoes_estoque(leituras, max_gap_s=6):
    """Estimativas segregadas dos contadores de uso. Refill não é consumo."""
    anteriores = {}; saida = []
    for r in sorted(leituras, key=lambda x:x['t']):
        k = (r.get('char'), r.get('item'), r.get('serie'))
        a = anteriores.get(k); v = r.get('valor')
        if (r.get('origem')!='estoque_hotkey' or not all(k) or r.get('unidade')!='unidades'
                or not isinstance(v,int) or isinstance(v,bool) or v<0):
            anteriores.pop(k,None); continue
        anteriores[k] = r
        if not a:
            continue
        dt = r['t']-a['t']; delta = a['valor']-v
        estado = 'reposicao_ou_movimentacao' if delta<0 else 'queda_de_estoque' if delta else 'estoque_estavel'
        if not 0<dt<=max_gap_s or a.get('local')!=r.get('local'):
            estado = 'lacuna_ou_layout_alterado'
        estimativa = delta if estado=='queda_de_estoque' else 0 if estado=='estoque_estavel' else None
        preco = r.get('preco_observado') or {}
        unitario = preco.get('gold')
        custo = estimativa*unitario if estimativa is not None and isinstance(unitario,(int,float)) and unitario>=0 and preco==a.get('preco_observado') else None
        saida.append({'item':r['item'], 'char':r['char'],'inicio':a['t'],'fim':r['t'],
            'estado':estado,'estoque_antes':a['valor'],'estoque_depois':v,
            'quantidade_estimada':estimativa,'consumo_confirmado':None,
            'custo_estimado_gold':custo,'preco_origem':preco.get('origem'),
            'por_minuto_estimado':60*estimativa/dt if estimativa is not None else None,
            'duracao_s':dt,'provas':[a.get('prova'),r.get('prova')],
            'limite':'Queda de estoque pode ser movimentação; não somar ao contador de uso nem ao Supplies.'})
    return saida


def balanco_cura(janelas):
    """Mesmo intervalo e unidade; lacunas de dano/cura nunca viram zero."""
    comparaveis = []
    for j in janelas:
        dur = j.get('fim', 0)-j.get('inicio', 0)
        dano = j.get('dano_hp'); sio = j.get('sio_hp')
        numero = lambda n: isinstance(n, (int, float)) and not isinstance(n, bool) and 0 <= n < float('inf')
        if dur <= 0 or not numero(dano) or not numero(sio):
            continue
        outras = j.get('outras_hp')
        total = sio+outras if numero(outras) else None
        comparaveis.append({**j, 'duracao_s':dur, 'dano_hp_s':dano/dur,
            'sio_hp_s':sio/dur, 'saldo_sio_hp':sio-dano,
            'razao_sio_dano':sio/dano if dano else None,
            'recuperacao_total_hp':total, 'saldo_total_hp':total-dano if total is not None else None})
    dano = sum(j['dano_hp'] for j in comparaveis)
    sio = sum(j['sio_hp'] for j in comparaveis)
    dur = sum(j['duracao_s'] for j in comparaveis)
    return {'versao':'balanco-cura-1', 'unidade':'HP', 'janelas':comparaveis,
        'comparaveis':len(comparaveis), 'lacunas':len(janelas)-len(comparaveis),
        'duracao_comparavel_s':dur,
        'dano_hp':dano if comparaveis else None, 'sio_hp':sio if comparaveis else None,
        'razao_sio_dano':sio/dano if dano else None,
        'deficits':sum(j['saldo_sio_hp']<0 for j in comparaveis),
        'cobertura_completa':bool(comparaveis) and len(comparaveis)==len(janelas) and all(j.get('cobertura_completa') is True for j in comparaveis),
        'limite':'Déficit no recorte observado; outras recuperações e lacunas impedem concluir insuficiência da hunt inteira.'}
def resumo_vida(valores):
    """Distribuição de leituras, nunca percentual de tempo ou HP interpolado."""
    valores = [v for v in valores if isinstance(v, (int, float)) and
               not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 100]
    limites = [(0, 30), (30, 50), (50, 70), (70, 90), (90, 100)]
    return {'leituras': len(valores), 'minima': min(valores, default=None),
            'maxima': max(valores, default=None),
            'faixas': [{'de': a, 'ate': b, 'leituras': sum(a <= v < b or v == b == 100 for v in valores)}
                       for a, b in limites]}


def permanencia_vida(leituras, inicio, fim, max_gap_s=6):
    """Estima intervalos curtos pela leitura à esquerda; não preenche lacunas.

    Leituras inválidas interrompem a continuidade. Não extrapola antes da
    primeira ou depois da última leitura, nem interpola quedas/recuperações.
    """
    numero = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    faixas = [{**f, 'tempo_s': 0} for f in resumo_vida([])['faixas']]
    por_t = {r['t']: r for r in leituras if numero(r.get('t')) and inicio <= r['t'] <= fim}
    rows = [por_t[t] for t in sorted(por_t)]
    valida = lambda r: numero(r.get('percentual')) and 0 <= r['percentual'] <= 100
    for r in rows:
        if valida(r):
            next(f for f in faixas if f['de'] <= r['percentual'] < f['ate'] or r['percentual'] == f['ate'] == 100)['leituras'] += 1
    for a, b in zip(rows, rows[1:]):
        dt = b['t'] - a['t']
        if valida(a) and valida(b) and 0 < dt <= max_gap_s:
            next(f for f in faixas if f['de'] <= a['percentual'] < f['ate'] or a['percentual'] == f['ate'] == 100)['tempo_s'] += dt
    conhecido = sum(f['tempo_s'] for f in faixas)
    if not conhecido:
        for f in faixas:
            f['tempo_s'] = None
    return {'faixas': faixas, 'tempo_identificado_s': conhecido,
            'tempo_sem_leitura_s': max(0, fim - inicio - conhecido)}

