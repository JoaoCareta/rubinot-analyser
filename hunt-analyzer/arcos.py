"""Divide a volta nos dois arcos do anel de Ingol e mede o custo de cada um.

Achado de 27/07 (voltas 4-8): mesma velocidade de kill nos dois arcos, mas o
NORTE (y <= 32588) cobra 24% mais HP por bicho. Este script acompanha, volta a
volta, se o tempo migrou para o arco barato — e um numero para o card.

Uso: python arcos.py capture\\session_X [volta_ini]
"""
import collections
import json
import pathlib
import sys

import numpy as np

import atlas_build as ab
import lap_watch as lw
import map_live
import mapa_ingol as mi

YCUT = 32588  # divisa dos arcos (tiles maiores = mais ao sul)


def sec(h):
    a, b, c = h.split(":")
    return int(a) * 3600 + int(b) * 60 + int(c)


def main():
    session = pathlib.Path(sys.argv[1])
    ini = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    laps = [L for L in laps if L["volta"] >= ini]
    walked = map_live.walked_update(session, mi.X0, mi.X1, mi.Y0, mi.Y1, mi.Z)
    wt = np.array([w[0] for w in walked])
    glyphs, gap = ab.load_atlas()

    print("volta  s_norte  s_sul  %sul   dano/kill_N  dano/kill_S  rhindeer_%_do_dano")
    for L in laps:
        t0, t1 = sec(L["inicio"]), sec(L["fim"])
        seg = [w for w in walked if t0 <= w[0] <= t1]
        tempo = collections.Counter()
        for i, (t, x, y) in enumerate(seg):
            passo = min(t - seg[i - 1][0], 10) if i else 2
            tempo["N" if y <= YCUT else "S"] += passo
        dano, kills, por_bicho = collections.Counter(), collections.Counter(), collections.Counter()
        for e in lw.lane_events(session, "c", t0, t1, glyphs, gap):
            t = sec(e["ts"])
            i = int(np.argmin(np.abs(wt - t)))
            if abs(wt[i] - t) > 12:
                continue
            arco = "N" if walked[i][2] <= YCUT else "S"
            if e["kind"] == "damage_taken":
                dano[arco] += e["value"]
                # o campo do atacante varia por padrao de mensagem
                quem = e.get("source") or e.get("actor") or e.get("by") or "?"
                por_bicho[quem] += e["value"]
            elif e["kind"] == "loot":
                kills[arco] += 1
        dt = sum(dano.values())
        rhin = 100 * por_bicho.get("rhindeer", 0) / max(1, dt)
        pct_sul = 100 * tempo["S"] / max(1, tempo["N"] + tempo["S"])
        print(f"{L['volta']:>5} {tempo['N']:>8} {tempo['S']:>6} {pct_sul:>6.0f}% "
              f"{dano['N'] / max(1, kills['N']):>12.0f} {dano['S'] / max(1, kills['S']):>12.0f} "
              f"{rhin:>17.0f}%")


if __name__ == "__main__":
    main()
