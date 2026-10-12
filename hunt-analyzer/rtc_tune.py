"""Responde com NUMERO as duas perguntas de config do RTC.

1) Da para subir o sio do RP sem roubar turno do EK?
   -> varre limiares candidatos e conta as COLISOES (momentos em que o sio no RP
      dispararia enquanto o EK tambem estava abaixo do gatilho dele).

2) Os limiares "Creatures N+" dos spells batem com o tamanho real das box?
   -> distribuicao do tamanho das box x quantas vezes cada spell dispararia.

Ambas rodam em cima do que a hunt de amanha grava; nada aqui e chute.
"""
import collections

# config atual do Hetero (26/07)
SIO_EK = 80
SIO_RP = 40
GRAN_SIO_EK = 40
SPELLS = [  # (rotulo, creatures_min, prioridade)
    ("spell 1", 6, 1), ("spell 2", 4, 2), ("spell 3", 2, 3),
    ("spell 4", 4, 4), ("spell 5", 2, 6),
    ("runa A", 2, 5), ("runa B", 1, 1),
]


def colisoes_sio(hp_pct, ek, rp, limiares=(40, 50, 55, 60, 65, 70), sio_ek=SIO_EK,
                 janela=2):
    """hp_pct: {t_segundos: {membro: hp%}}. Devolve, por limiar do RP:

    disparos      quantas vezes o sio no RP entraria
    colisoes      quantos desses caem em cima de uma necessidade do EK
    pct_colisao   risco de roubar turno
    """
    ts = sorted(hp_pct)
    ek_precisa = {t for t in ts if (hp_pct[t].get(ek, 100)) <= sio_ek}
    out = []
    for lim in limiares:
        disparos, colide, ultimo = 0, 0, -99
        for t in ts:
            if hp_pct[t].get(rp, 100) > lim or t - ultimo < 3:
                continue
            disparos += 1
            ultimo = t
            if any(abs(t - e) <= janela for e in ek_precisa):
                colide += 1
        out.append({
            "limiar_rp": lim, "disparos": disparos, "colisoes": colide,
            "pct_colisao": round(100 * colide / disparos, 1) if disparos else 0.0,
        })
    return out


def cobertura_spells(tamanhos_box, spells=SPELLS):
    """tamanhos_box: lista com o pico de bichos de cada box.

    Diz quantas % das box cada spell alcanca com o limiar atual e qual seria a
    cobertura se o limiar descesse um degrau.
    """
    n = len(tamanhos_box) or 1
    out = []
    for rotulo, minimo, prio in spells:
        atual = sum(1 for t in tamanhos_box if t >= minimo)
        menor = sum(1 for t in tamanhos_box if t >= max(1, minimo - 1))
        out.append({
            "spell": rotulo, "prioridade": prio, "creatures_min": minimo,
            "cobertura_pct": round(100 * atual / n),
            "cobertura_se_menos_1": round(100 * menor / n),
            "ganho_pp": round(100 * (menor - atual) / n),
        })
    out.sort(key=lambda d: d["prioridade"])
    return out


def resumo_box(tamanhos_box):
    c = collections.Counter(tamanhos_box)
    tot = len(tamanhos_box) or 1
    return {
        "boxes": len(tamanhos_box),
        "mediana": sorted(tamanhos_box)[len(tamanhos_box) // 2] if tamanhos_box else 0,
        "distribuicao": {k: f"{100 * v / tot:.0f}%" for k, v in sorted(c.items())},
    }
