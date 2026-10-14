"""Vigência declarada por componente; leitura e aplicação são fatos distintos."""

TIPOS = ('rtc', 'cura', 'roda')


def resolver(declaracao, leituras, char, sessao, instante):
    valida = bool(declaracao and declaracao.get('char') == char
                  and declaracao.get('sessao') == sessao
                  and declaracao.get('confirmado_em', float('inf')) <= instante)
    saida = {}
    for tipo in TIPOS:
        s = leituras.get(tipo) or {}
        incluido = valida and declaracao.get('revisoes', {}).get(tipo) == s.get('id')
        confirmado = bool(incluido and s.get('id') and declaracao.get('resposta') == 'uso_confirmado')
        saida[tipo] = {'uso_confirmado': confirmado,
            'revisao': s.get('id'), 'completo': bool(s.get('completo')),
            'desde': declaracao.get('confirmado_em') if confirmado else None,
            'declaracao_id': declaracao.get('id') if incluido else None,
            'estado': 'uso_declarado' if confirmado else
                declaracao['resposta'] if valida and tipo == 'rtc' else 'uso_desconhecido'}
    return saida


def elegibilidade(componentes):
    def uso(tipo):
        return bool(componentes.get(tipo, {}).get('uso_confirmado'))
    return {'cadencia_ataque': uso('rtc'), 'selecao_ataque': uso('rtc'),
            'cura': uso('cura'), 'efeitos_roda': uso('rtc') and uso('roda'),
            'pressao_observada': True}
