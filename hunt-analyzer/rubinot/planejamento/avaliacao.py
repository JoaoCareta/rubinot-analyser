"""Regras puras de cobertura e segurança por integrante."""

def saude_party(recursos, eventos, politica=None):
    """Descreve barras sem estimar HP máximo, cura útil ou risco em lacunas."""
    membros = {}; politica = politica or {}; gap = politica.get('max_gap_s', 6)
    for q in sorted(recursos, key=lambda r:r.get('instante') or 0):
        for nome, v in {'eu': q.get('vida'), **q.get('aliados', {})}.items():
            if not v or v.get('percentual') is None: continue
            if nome != 'eu' and not v.get('identidade_confirmada'): continue
            p = v['percentual']
            if not isinstance(p, (int,float)) or not 0 <= p <= 100: continue
            membros.setdefault(nome, []).append((q.get('instante'), p))
    saida = {}
    for nome, rows in membros.items():
        intervalos = [(a,b) for a,b in zip(rows,rows[1:]) if a[0] is not None and b[0] is not None and 0 < b[0]-a[0] <= gap]
        limite = politica.get('por_membro',{}).get(nome,{}).get('critico_pct')
        episodios = []; corrente = None
        for a,b in intervalos:
            if limite is not None and a[1] <= limite:
                if corrente and corrente['fim'] == a[0]: corrente['fim'] = b[0]
                else:
                    corrente = {'inicio':a[0], 'fim':b[0], 'minimo':a[1], 'origem':'barra_observada'}
                    episodios.append(corrente)
                corrente['minimo'] = min(corrente['minimo'], a[1])
            else: corrente = None
        saida[nome] = {'amostras':len(rows), 'minimo_observado':min(p for _,p in rows),
            'cobertura_s':sum(b[0]-a[0] for a,b in intervalos),
            'queda_max_pct_s':max((max(0,a[1]-b[1])/(b[0]-a[0]) for a,b in intervalos),default=None),
            'episodios':episodios if limite is not None else None,
            'critico_s':sum(e['fim']-e['inicio'] for e in episodios) if limite is not None else None,
            'politica_versao':politica.get('versao'), 'seguranca':'inconclusiva'}
    return saida


def comparar_resultados(antes, depois, margens):
    """Margens pré-definidas; segurança de cada membro precede eficiência."""
    motivos = []; piora = False
    for nome in set(antes.get('saude',{})) | set(depois.get('saude',{})):
        a = antes.get('saude',{}).get(nome,{}); b = depois.get('saude',{}).get(nome,{})
        if a.get('critico_s') is None or b.get('critico_s') is None or not a.get('cobertura_s') or not b.get('cobertura_s'):
            motivos.append('saude_sem_cobertura:'+nome); continue
        if a.get('politica_versao') != b.get('politica_versao'):
            motivos.append('politica_incompativel:'+nome); continue
        if b['critico_s']/b['cobertura_s'] > a['critico_s']/a['cobertura_s'] + margens.get('risco',0):
            piora = True
    if depois.get('operacional',{}).get('mortes_confirmadas'):
        piora = True
    if not antes.get('saude') or not depois.get('saude'): motivos.append('saude_ausente')
    return {'estado':'resultado_misto' if piora else 'inconclusivo',
        'promover':False, 'piora_seguranca':piora, 'limites':motivos,
        'motivo':'Associação observada; promoção exige sessões posteriores compatíveis.'}
