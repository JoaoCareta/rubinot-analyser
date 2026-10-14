"""Diagnóstico de oportunidades observadas; não inventa turnos entre quadros."""


def reconstruir(eventos, recursos, slots, catalogo, desde):
    magias = {m['id']: m for m in catalogo}
    anteriores = {}; grupos = {}; saida = []
    casts = sorted({e['id']: e for e in eventos if e.get('id') and e.get('kind') == 'cast'
                    and e.get('qualidade') == 'identificada' and (e.get('instante') or 0) >= desde}.values(),
                   key=lambda e: (e['t'], e['id']))
    recursos = sorted(recursos, key=lambda q: q['t'])
    for cast in casts:
        t = cast['t']
        recurso = next((q for q in reversed(recursos) if 0 <= t-q['t'] <= q.get('precisao_s', 1)), {})
        candidatas = []
        for slot in slots:
            ident = slot.get('id'); m = magias.get(ident, {})
            if not ident or slot.get('atual') is False: continue
            bloqueios = []; desconhecidas = []
            grupo = m.get('grupo_id', 'cura' if m.get('tipo') == 'cura' else 'ataque')
            visual = recurso.get('prontidao', {}).get(ident, {})
            if visual.get('pronta') is False:
                bloqueios.append('cooldown_visual')
            if ident in anteriores and m.get('cd') is not None and t < anteriores[ident]+m['cd']:
                bloqueios.append('cooldown_individual')
            elif ident not in anteriores and visual.get('pronta') is not True: desconhecidas.append('prontidao_inicial')
            if grupo in grupos and t < grupos[grupo]: bloqueios.append('cooldown_grupo')
            secundario = m.get('grupo_secundario')
            if secundario and t < grupos.get('secundario:'+secundario, 0): bloqueios.append('cooldown_secundario')
            for campo, valor in (('mana_percent', (recurso.get('mana') or {}).get('percentual')),
                                 ('creatures', recurso.get('criaturas'))):
                limite = slot.get(campo)
                if campo == 'creatures' and slot.get('id') == 'sudden_death': continue
                if limite is None or valor is None: desconhecidas.append(campo)
                elif valor < limite: bloqueios.append(campo)
            # População visível não comprova alcance/orientação/alvos atingidos.
            geometria = recurso.get('geometria', {}).get(ident)
            if geometria is False: bloqueios.append('geometria')
            elif geometria is not True: desconhecidas.append('geometria')
            estado = 'escolhida_observada' if ident == cast.get('magia_id') else \
                     'bloqueada' if bloqueios else 'inconclusiva' if desconhecidas else 'elegivel_preterida'
            candidatas.append({'id': ident, 'estado': estado, 'bloqueios': bloqueios,
                               'desconhecidas': desconhecidas, 'prioridade': slot.get('prioridade'),
                               'slot':slot.get('slot'), 'tipo':slot.get('tipo', 'runa' if m.get('runa') else 'magia')})
        saida.append({'id': cast['id'], 't': t, 'instante': cast.get('instante'),
                      'escolhida': cast.get('magia_id'), 'candidatas': candidatas,
                      'origem_execucao': cast.get('origem_execucao', 'rtc_declarado_com_hotkey_nao_excluida'),
                      'cobertura_completa': bool(candidatas) and all(not c['desconhecidas'] for c in candidatas),
                      'prova': cast.get('origem'), 'precisao_s': cast.get('precisao_s'),
                      'tipo': 'oportunidade_com_cast_observado'})
        m = magias.get(cast.get('magia_id'), {})
        anteriores[cast.get('magia_id')] = t
        grupo = m.get('grupo_id', 'cura' if m.get('tipo') == 'cura' else 'ataque')
        if m.get('grupo') is not None: grupos[grupo] = t+m['grupo']
        if m.get('grupo_secundario') and m.get('cd_compartilhado') is not None:
            grupos['secundario:'+m['grupo_secundario']] = t+m['cd_compartilhado']
    return saida
