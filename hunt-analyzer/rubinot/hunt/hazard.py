"""Contexto de Gnomprona; coeficientes não publicados permanecem desconhecidos."""
import datetime
import unicodedata


def area(nome):
    texto = ''.join(c for c in unicodedata.normalize('NFD', str(nome or '').lower())
                    if not unicodedata.combining(c)).replace('_', ' ').strip()
    return {'carrinho 1': 'monster_graveyard', 'monster graveyard': 'monster_graveyard',
            'carrinho 2': 'crystal_enigma', 'crystal enigma': 'crystal_enigma',
            'carrinho 3': 'sparkling_pools', 'sparkling pools': 'sparkling_pools'}.get(texto)


def nivel(valor):
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0 else None


def regras(instante):
    data = datetime.datetime.fromtimestamp(instante).date() if instante else None
    atual = data is not None and data >= datetime.date(2026, 9, 1)
    return {'versao': 'global-20260901' if atual else 'global-historico-sem-coeficientes',
            'loot_bonus_por_hazard': 0 if atual else None,
            'xp_bonus_por_hazard': None, 'dano_por_hazard': None,
            'critico_por_hazard': None, 'dodge_por_hazard': None,
            'pods_por_hazard': None,
            'mecanicas': ['dano_ampliado', 'criticos_monstros', 'esquiva_monstros',
                          'primal_pods', 'fungosaurus', 'experiencia', 'plunder_patriarch'],
            'fonte': 'https://www.tibia.com/news/?id=8945&subtopic=newsarchive'}


def trecho(recursos, inicio, fim, char):
    """Exige cobertura contínua: um print não caracteriza uma volta inteira."""
    rows = sorted((r for r in recursos if isinstance(r.get('instante'), (int, float))
                   and inicio-6 <= r['instante'] <= fim), key=lambda r:r['instante'])
    niveis = set(); coberto = 0; provas = []
    for a, b in zip(rows, rows[1:]):
        dt = b['instante']-a['instante']; leitura = a.get('hazard') or {}
        n = nivel(leitura.get('nivel'))
        if not 0 < dt <= 6 or n is None or leitura.get('char', '').casefold() != char.casefold():
            continue
        dur = max(0, min(fim, b['instante'])-max(inicio, a['instante']))
        if dur:
            coberto += dur; niveis.add(n); provas.append(leitura.get('prova'))
    cobertura = coberto/(fim-inicio) if fim > inicio else 0
    conhecido = len(niveis) == 1 and cobertura >= .8
    return {'nivel': next(iter(niveis)) if conhecido else None,
            'estado': 'observado' if conhecido else 'misto' if len(niveis)>1 else 'sem_cobertura',
            'cobertura': cobertura, 'niveis_observados': sorted(niveis),
            'provas': sorted({p for p in provas if p})}
