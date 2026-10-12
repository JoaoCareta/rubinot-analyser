"""Coach da hunt SOLO: onde o dano tomado sai mais caro por kill.

Em Ingol o user nao para — puxa trem e corre o anel. Entao o coach de
"posicao parada errada" (party) nao se aplica: o que da pra corrigir e o
RITMO por trecho do anel. Metrica = dano tomado por kill em cada box.

Uso: python coach_solo.py capture\\session_X [volta_ini volta_fim]
"""
import collections
import json
import pathlib
import sys

import numpy as np

import atlas_build as ab
import lap_watch as lw
import map_live
import mapa_ingol

RAIO = 8.0  # tiles: entorno da box


def sec(h):
    a, b, c = h.split(":")
    return int(a) * 3600 + int(b) * 60 + int(c)


def main():
    session = pathlib.Path(sys.argv[1])
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(sys.argv) > 3:
        laps = [L for L in laps if int(sys.argv[2]) <= L["volta"] <= int(sys.argv[3])]
    t0, t1 = sec(laps[0]["inicio"]), sec(laps[-1]["fim"])

    walked = map_live.walked_update(session, mapa_ingol.X0, mapa_ingol.X1,
                                   mapa_ingol.Y0, mapa_ingol.Y1, mapa_ingol.Z)
    walked = [w for w in walked if t0 <= w[0] <= t1]
    wt = np.array([w[0] for w in walked])
    print(f"rota: {len(walked)} pontos")

    glyphs, gap = ab.load_atlas()
    dano, kills, stance = [], [], []
    for L in laps:
        for e in lw.lane_events(session, "c", sec(L["inicio"]), sec(L["fim"]), glyphs, gap):
            if e["kind"] == "damage_taken":
                dano.append((sec(e["ts"]), e["value"]))
            elif e["kind"] in ("xp_gain", "loot"):
                kills.append(sec(e["ts"]))
        for e in lw.lane_events(session, "s", sec(L["inicio"]), sec(L["fim"]), glyphs, gap):
            if "utito dru" in (e.get("text") or "") or "utura sio" in (e.get("text") or ""):
                stance.append((e["ts"], e.get("text")))
    print(f"dano: {len(dano)} linhas | kills: {len(kills)} | stance: {stance[:4]}")

    def pos_em(t):
        i = int(np.argmin(np.abs(wt - t)))
        return walked[i][1:] if abs(wt[i] - t) <= 12 else None

    boxes = mapa_ingol.kills_posicionados(session, walked, laps)
    centros = []
    for _, x, y, _, _ in boxes:
        for c in centros:
            if ((x - c["x"]) ** 2 + (y - c["y"]) ** 2) ** 0.5 <= 5:
                c["n"] += 1
                c["x"] = (c["x"] * (c["n"] - 1) + x) / c["n"]
                c["y"] = (c["y"] * (c["n"] - 1) + y) / c["n"]
                break
        else:
            centros.append({"x": x, "y": y, "n": 1, "dano": 0, "kills": 0, "dwell": 0})
    centros = [c for c in centros if c["n"] >= 4]

    def perto(x, y):
        melhor, dm = None, RAIO
        for c in centros:
            dd = ((x - c["x"]) ** 2 + (y - c["y"]) ** 2) ** 0.5
            if dd <= dm:
                melhor, dm = c, dd
        return melhor

    for t, v in dano:
        p = pos_em(t)
        if p and (c := perto(*p)):
            c["dano"] += v
    for t in kills:
        p = pos_em(t)
        if p and (c := perto(*p)):
            c["kills"] += 1
    for i, (t, x, y) in enumerate(walked):
        passo = min(t - walked[i - 1][0], 10) if i else 2
        if c := perto(x, y):
            c["dwell"] += passo

    print("\n  trecho (x,y)        kills  dano tomado  dano/kill  seg parado  kills/min")
    linhas = [c for c in centros if c["kills"] >= 3]
    for c in sorted(linhas, key=lambda c: -(c["dano"] / max(1, c["kills"]))):
        print(f"  ({c['x']:.0f},{c['y']:.0f}) {c['kills']:>10} {c['dano']:>12} "
              f"{c['dano'] / max(1, c['kills']):>10.0f} {c['dwell']:>11} "
              f"{60 * c['kills'] / max(1, c['dwell'] + 30):>10.1f}")
    tot_d = sum(c["dano"] for c in linhas)
    tot_k = sum(c["kills"] for c in linhas)
    print(f"  MEDIA DA HUNT: {tot_d / max(1, tot_k):.0f} de dano por kill")


if __name__ == "__main__":
    main()
