"""Card por volta a partir do voltas.jsonl do vigia.

Ponte: vigia da o TEMPO da volta; lap_summary da as metricas; party_card formata.
Imprime o card das voltas pedidas (ou de todas que ainda nao sairam).

Uso: python cards_vigia.py capture/session_X [volta]
"""
import json
import pathlib
import sys

import atlas_build as ab
import lap_watch as lw
import party_card
import pt_card


XP_RAW_POR_BICHO = 6516  # mix Falcon 64% FK (6300) / 36% FP (6900), sessao 25/07

# alvos do coach da volta 10 (06:00): parar dentro do raio = correcao NAO aplicada
COACH_DESDE = 11
COACH_ALVOS = [
    {"nome": "miolo", "xy": (33302, 31297), "raio": 6, "custo": 12848},
    {"nome": "fundo da quina SW", "xy": (33294, 31316), "raio": 4, "custo": 5844},
]
PARADA_S = 8       # mesmos limiares do vigia
PARADA_TILES = 2.0


def hms(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + int(sec)


def paradas_ruins(session, t0, t1):
    """Paradas >=PARADA_S dentro do raio de um alvo do coach, na janela da volta."""
    import math
    p = session / "walked_live.json"
    if not p.exists():
        return []
    pts = [q for q in json.loads(p.read_text()) if t0 <= q[0] <= t1]
    ruins, aberto = [], None
    for i in range(len(pts)):
        jan = [q for q in pts if pts[i][0] - PARADA_S <= q[0] <= pts[i][0]]
        if len(jan) < 4:
            continue
        desl = sum(math.hypot(jan[k][1] - jan[k - 1][1], jan[k][2] - jan[k - 1][2])
                   for k in range(1, len(jan)))
        alvo = next((a for a in COACH_ALVOS
                     if math.hypot(jan[-1][1] - a["xy"][0], jan[-1][2] - a["xy"][1]) <= a["raio"]),
                    None)
        if desl <= PARADA_TILES and alvo:
            if aberto is None:
                aberto = alvo["nome"]
                ruins.append(alvo)
        else:
            aberto = None
    return ruins


def main():
    session = pathlib.Path(sys.argv[1])
    alvo = int(sys.argv[2]) if len(sys.argv) > 2 else None
    lw.CHAR_NAME = "Traps the cat"
    a = json.loads(pathlib.Path("atlas.json").read_text(encoding="utf-8"))
    glyphs, gap = (a["glyphs"], a.get("space_gap", 5)) if "glyphs" in a else (a, 5)
    voltas = [json.loads(l) for l in (session / "voltas.jsonl").open(encoding="utf-8")
              if l.strip()]
    laps = []
    for v in voltas:
        s = lw.lap_summary(session, hms(v["inicio"]), hms(v["fim"]), glyphs, gap)
        s.update(volta=v["volta"], dur_s=v["dur_s"], inicio=v["inicio"], fim=v["fim"])
        # chat de 3 linhas perde ~80% dos loots -> bichos pelo PAINEL:
        # XP raw da volta / XP raw por falcon (FK 6300 / FP 6900, mix 64/36)
        if s.get("xp_raw_painel"):
            s["kills_chat"] = s.get("kills_total")
            s["kills_total"] = round(s["xp_raw_painel"] / XP_RAW_POR_BICHO)
        if v["volta"] >= COACH_DESDE:
            ruins = paradas_ruins(session, hms(v["inicio"]), hms(v["fim"]))
            s["coach_status"] = ("corrigida" if not ruins
                                 else "parcial" if len(ruins) == 1 else "repetiu")
            custo = sum(a["custo"] for a in ruins)
            s["coach_impacto"] = (f"-{custo // 1000}k HP ({ruins[0]['nome']})"
                                  if ruins else "0 paradas ruins")
        laps.append(s)
    for lap in laps:  # 21/09: raw so estabiliza 15 min depois de comecar (mesma regra do pt_card)
        lap["estabilizando"], lap["xp_raw_15min"] = pt_card.raw_15min(session, glyphs, gap, laps, lap)
    # persiste p/ caminho_comum/mapa_volta/coach (formato do lap_watch)
    with (session / "laps.jsonl").open("w", encoding="utf-8") as fh:
        for lap in laps:
            fh.write(json.dumps(lap, ensure_ascii=False) + "\n")
    for i, lap in enumerate(laps):
        if alvo is not None and lap["volta"] != alvo:
            continue
        print(party_card.card(lap, laps[i - 1] if i else None,
                              hunt="Falcon Bastion", emoji="🦅🏰"))
        print()


if __name__ == "__main__":
    main()
