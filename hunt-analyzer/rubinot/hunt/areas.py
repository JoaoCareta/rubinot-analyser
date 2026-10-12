"""Áreas de caça: mudança sustentada de andar E composição, sem repartir medidas."""
from collections import Counter


def detectar(observacoes, janela_s=90):
    areas = []
    for i, ponto in enumerate(observacoes):
        t = ponto['t']
        janela = [p for p in observacoes[max(0, i-60):i+1] if t-janela_s <= p['t'] <= t and p.get('especies')]
        if len(janela) < 8 or janela[-1]['t']-janela[0]['t'] < 30:
            continue
        andar, quantidade = Counter(p['z'] for p in janela).most_common(1)[0]
        if quantidade / len(janela) < .75:
            continue
        nomes = Counter(n for p in janela if p['z'] == andar for n in p['especies'])
        dominantes = sorted(n for n, k in nomes.items() if k >= quantidade * .25)
        if not dominantes:
            continue
        if not areas:
            areas.append({'inicio': janela[0]['t'], 'andar': andar, 'especies': dominantes})
            continue
        anterior = areas[-1]
        if anterior['andar'] == andar:
            continue
        novas = set(dominantes)-set(anterior['especies'])
        presenca = [p for p in janela if p['z'] == andar and novas.intersection(p['especies'])]
        if not novas or len(presenca)/len(janela) < .75:
            continue
        areas.append({'inicio': presenca[0]['t'], 'andar': andar, 'especies': dominantes})
    return areas


def recortar(dados, areas):
    """Recorte ativo; volta atravessando troca é parcial, nunca rateada artificialmente."""
    if len(areas) < 2:
        return dados
    inicio = areas[-1]['inicio']
    voltas = []
    for original in dados.get('voltas', []):
        if original['fim'] <= inicio:
            continue
        v = dict(original)
        if v['ini'] < inicio:
            v.update(parcial=True, troca_area=True, ini=inicio, dur=v['fim']-inicio)
            for medida in ('xp_raw', 'profit', 'sup_pt', 'sup_eu', 'bichos'):
                v[medida] = None
        if v['fim']-inicio < 900:
            v.update(estabilizando=True, xp_raw_15min=None)
        v['especies'] = {n: k for n, k in v.get('especies', {}).items() if n in areas[-1]['especies']}
        voltas.append(v)
    return {**dados, 'voltas': voltas, 'amostras': [p for p in dados.get('amostras', []) if p[0] >= inicio],
            'areas_hunt': areas, 'area_atual': areas[-1]}
