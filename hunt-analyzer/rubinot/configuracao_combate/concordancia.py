"""Comparação pura entre sugerido e observado; não presume aplicação."""
def comparar(sugestao, observado, catalogo):
    diferencas, pendentes = [], []
    for linha in sugestao.get('rtc', {}).get('linhas', []):
        slot = next((s for s in observado.get('rtc', {}).get('slots', [])
                     if s.get('tipo') == linha.get('tipo') and s.get('slot') == linha.get('slot')), {})
        for campo in ('id', 'creatures', 'prioridade', *(() if linha.get('tipo') == 'runa' else ('mana_percent',))):
            if campo=='creatures' and linha.get('runa') and linha.get('alvos')==1:continue
            if slot.get(campo) is None or slot.get('atual') is False:
                pendentes.append(f"RTC {linha['slot']}: {campo}")
            elif slot[campo] != linha.get(campo):
                diferencas.append(f"RTC {linha['slot']}: {campo}")
    for linha in sugestao.get('cura',{}).get('linhas',[]):
        if linha.get('ativo') is False:continue
        slots=observado.get('cura',{}).get('slots',[])
        slot=next((s for s in slots if s.get('id')==linha.get('id') and (s.get('vocacao_destino')==linha.get('vocacao_destino') if linha.get('vocacao_destino') else s.get('tipo')=='autocura')),None)
        if not slot or slot.get('vida_percent') is None or linha.get('vida_percent') is None:pendentes.append('cura '+linha.get('id',''))
        elif slot['vida_percent']!=linha['vida_percent']:diferencas.append('cura '+linha['id']+': vida_percent')
    for fatia,pontos in sugestao.get('roda',{}).get('pontos',{}).items():
        valor=observado.get('roda',{}).get('campos',{}).get('fatias.'+fatia,{}).get('valor')
        if valor is None:pendentes.append('roda '+fatia)
        elif valor!=pontos:diferencas.append('roda '+fatia)
    for campo,lido in observado.get('roda',{}).get('campos',{}).items():
        if campo.startswith('fatias.') and lido.get('valor')!=sugestao.get('roda',{}).get('pontos',{}).get(campo[7:],0):
            if 'roda '+campo[7:] not in diferencas:diferencas.append('roda '+campo[7:])
    for gema in sugestao.get('roda',{}).get('gemas',[]):
        lida=observado.get('roda',{}).get('campos',{}).get('gemas.'+gema['dominio'],{}).get('valor')
        if not lida:pendentes.append('gema '+gema['dominio'])
        elif lida.get('tier')!=gema.get('tier'):diferencas.append('gema '+gema['dominio']+': qualidade')
        elif gema.get('mod') is not None and not any(m.get('mod')==gema['mod'] and m.get('grau')==gema.get('grau') for m in lida.get('modificadores',[])):pendentes.append('gema '+gema['dominio']+': modificador')
        if lida:
            for basico in gema.get('basicos',[]):
                if not any(m.get('mod')==basico['mod'] and m.get('grau')==basico['grau'] for m in lida.get('basicos',[])):pendentes.append('gema '+gema['dominio']+': básico')
    dominios={g['dominio'] for g in sugestao.get('roda',{}).get('gemas',[])}
    cat=catalogo;voc=sugestao.get('contexto',{}).get('vocacao','ED')
    campos_roda=observado.get('roda',{}).get('campos',{})
    ativos={f['dominio'] for f in cat.get('vocacoes',{}).get(voc,{}).get('fatias',[]) if 37<=f.get('conviction_id',0)<=40 and campos_roda.get('fatias.'+f['id'],{}).get('valor')==f['limite']}
    for dominio in ativos:
        g=campos_roda.get('gemas.'+dominio,{}).get('valor',{})
        if g.get('estado') not in ('vazio_confirmado','observado_completo'):pendentes.append('gema '+dominio+': equipamento não lido')
    for campo,lido in observado.get('roda',{}).get('campos',{}).items():
        if campo.startswith('gemas.') and campo[6:] not in dominios and lido.get('valor',{}).get('equipada'):diferencas.append('gema extra '+campo[6:])
    for tipo in ('cura','roda'):
        if not observado.get(tipo,{}).get('completo'):pendentes.append(tipo)
    return {'estado': 'divergente' if diferencas else 'parcial' if pendentes else 'confere',
            'diferencas': diferencas, 'pendentes': pendentes}

