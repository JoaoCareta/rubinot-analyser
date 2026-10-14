"""Projeção do histórico de cura; não expõe estudos, modelos ou provas locais."""
import bisect
import math

from rubinot.hunt.metricas import resumo_vida, permanencia_vida


def numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def segundos(v):
    if numero(v):
        return v
    if isinstance(v, str):
        partes = v.split(':')
        if len(partes) == 3 and all(p.isdigit() for p in partes):
            h, m, s = map(int, partes)
            if m < 60 and s < 60:
                return h * 3600 + m * 60 + s
    return None


def projetar(registro, sessao, char, party, inicio, fim):
    """Um trecho da captura, limitado à hunt guardada. Sem inferir destinatário."""
    eventos = [e for e in registro.ler(sessao, 'evento') if numero(e.get('t'))
               and not e.get('qa') and not e.get('sintetico')]
    membros = {p['nome']: dict(p) for p in party if p.get('identidade_confirmada') and p.get('nome')}
    # Vocação pode vir do look explícito, mas só para um membro confirmado.
    vocs = {'elite knight': 'EK', 'knight': 'EK', 'royal paladin': 'RP', 'paladin': 'RP',
            'elder druid': 'ED', 'druid': 'ED', 'master sorcerer': 'MS', 'sorcerer': 'MS'}
    nomes = {p.get('nome') for p in party}
    for e in eventos:
        nome = e.get('target') or e.get('alvo')
        voc = vocs.get(str(e.get('vocation', '')).casefold())
        if e.get('kind') == 'player_info' and nome in nomes and voc:
            membro = membros.setdefault(nome, {'nome': nome})
            membro.setdefault('vocacao', voc)
    por_t = {}
    for tipo in ('recurso', 'recurso_sio_revisado', 'recurso_cura'):
        for q in sorted(registro.ler(sessao, tipo), key=lambda q: q.get('processado_em') or q.get('instante') or 0):
            if numero(q.get('t')) and not q.get('qa') and not q.get('sintetico'):
                por_t[q['t']] = q
    recursos = sorted(por_t.values(), key=lambda q: q['t'])
    if inicio is None or fim is None or fim <= inicio:
        return {'sessao': sessao, 'membros': [], 'periodo_disponivel': False}
    casts = list({(e['t'], e.get('alvo'), e.get('magia_id')): e for e in eventos
                  if inicio <= e['t'] <= fim and e.get('kind') == 'cast' and e.get('ator') == char
                  and e.get('qualidade') == 'identificada' and e.get('magia_id') in
                  ('heal_friend', 'nature_s_embrace')}.values())
    saida = []
    for nome, membro in sorted(membros.items(), key=lambda item: (item[1].get('vocacao') or 'ZZ', item[0])):
        vida = []
        serie = []
        for q in recursos:
            v = q.get('aliados', {}).get(nome, {})
            p = v.get('percentual')
            if inicio <= q['t'] <= fim:
                valido = numero(p) and 0 <= p <= 100 and (
                    v.get('identidade_confirmada') or v.get('origem') == 'barra_nameplate_integral')
                serie.append({'t': q['t'], 'percentual': p if valido else None})
                if valido:
                    vida.append({'t': q['t'], 'percentual': p})
        tempos = [v['t'] for v in vida]
        curas = []
        for e in sorted((e for e in casts if e.get('alvo') == nome), key=lambda e: e['t']):
            i = bisect.bisect_right(tempos, e['t']) - 1
            antes = vida[i] if i >= 0 and e['t'] - vida[i]['t'] <= 1.5 else None
            curas.append({'t': e['t'], 'magia': 'sio' if e['magia_id'] == 'heal_friend' else 'gran sio',
                          'vida_antes': antes['percentual'] if antes else None,
                          'vida_em': antes['t'] if antes else None})
        trechos = []
        for indice in range(math.ceil((fim - inicio) / 300)):
            a, b = inicio + indice * 300, min(fim, inicio + (indice + 1) * 300)
            dentro = lambda t: a <= t < b or t == b == fim
            vs = [v['percentual'] for v in vida if dentro(v['t'])]
            cs = [c for c in curas if dentro(c['t'])]
            trechos.append({'inicio': a, 'fim': b, 'vida': resumo_vida(vs), 'curas': cs,
                            'sio': sum(c['magia'] == 'sio' for c in cs),
                            'gran_sio': sum(c['magia'] == 'gran sio' for c in cs)})
        permanencia = permanencia_vida(serie, inicio, fim)
        sem_vida = {'tempo_s': permanencia['tempo_sem_leitura_s'], 'sio': 0, 'gran_sio': 0}
        for f in permanencia['faixas']:
            f.update(sio=0, gran_sio=0)
        for c in curas:
            p = c['vida_antes']
            faixa = next((f for f in permanencia['faixas'] if p is not None and
                          (f['de'] <= p < f['ate'] or p == f['ate'] == 100)), sem_vida)
            faixa['sio' if c['magia'] == 'sio' else 'gran_sio'] += 1
        permanencia['sem_vida'] = sem_vida
        saida.append({'nome': nome, 'vocacao': membro.get('vocacao'), 'vida': resumo_vida([v['percentual'] for v in vida]),
                      'permanencia': permanencia,
                      'sio': sum(c['magia'] == 'sio' for c in curas),
                      'gran_sio': sum(c['magia'] == 'gran sio' for c in curas), 'trechos': trechos})
    return {'sessao': sessao, 'membros': saida, 'periodo_disponivel': True}
