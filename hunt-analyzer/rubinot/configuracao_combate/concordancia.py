"""Comparação pura entre sugerido e observado; não presume aplicação."""
def comparar(sugestao, observado, catalogo):
    diferencas, pendentes = [], []
    esperados = {(s.get('tipo'), s.get('slot')) for s in sugestao.get('rtc', {}).get('linhas', [])}
    for slot in observado.get('rtc', {}).get('slots', []):
        if (slot.get('tipo'), slot.get('slot')) not in esperados:
            if slot.get('id') and slot.get('atual') is not False:
                diferencas.append(f"RTC {slot.get('tipo')} {slot.get('slot')}: slot extra")
            elif slot.get('estado') != 'vazio_confirmado':
                pendentes.append(f"RTC {slot.get('tipo')} {slot.get('slot')}: conteúdo desconhecido")
    for campo, valor in sugestao.get('rtc', {}).get('opcoes', {}).items():
        lido = observado.get('rtc', {}).get('campos', {}).get(campo, {}).get('valor')
        if lido is None: pendentes.append('RTC opção '+campo)
        elif lido != valor: diferencas.append('RTC opção '+campo)
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
    componentes = {}
    for tipo in ('rtc','cura','roda'):
        ds = [d for d in diferencas if d.lower().startswith(tipo) or tipo=='roda' and d.startswith('gema')]
        ps = [p for p in pendentes if p.lower().startswith(tipo) or tipo=='roda' and p.startswith('gema')]
        componentes[tipo] = {'estado':'divergente' if ds else 'parcial' if ps else 'confere',
                            'diferencas':ds, 'pendentes':ps}
    campos = []
    for linha in sugestao.get('rtc', {}).get('linhas', []):
        candidatos = [s for s in observado.get('rtc', {}).get('slots', []) if s.get('id')==linha.get('id') and s.get('atual') is not False and s.get('ativo') is not False and observado.get('rtc',{}).get('atual') is not False]
        slot = candidatos[0] if len(candidatos)==1 else {}
        for campo in ('creatures','prioridade','mana_percent'):
            if campo not in linha:
                continue
            valor = slot.get(campo)
            campos.append({'id':linha.get('id'),'campo':campo,'sugerido':linha[campo],
                'observado':valor,'estado':'parcial' if valor is None else 'confere' if valor==linha[campo] else 'divergente',
                'instante':slot.get('instante',observado.get('rtc',{}).get('instante')),
                'prova':slot.get('prova'), 'uso_automatico':observado.get('uso_componentes',{}).get('rtc',{}).get('estado','uso_desconhecido')})
    return {'estado': 'divergente' if diferencas else 'parcial' if pendentes else 'confere',
            'diferencas': diferencas, 'pendentes': pendentes, 'componentes':componentes, 'campos':campos}

