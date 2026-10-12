"""Analise de LURE: tempo de deslocamento entre boxes e o que ele rende.

Responde: o lure esta rapido demais? onde compensa puxar? onde nao compensa?

Metrica-chave = kills por minuto de CICLO (lure + luta), nao so da luta:
uma box de 12 kills que exige 60s de lure perde pra uma de 8 kills com 15s.
"""
import json
import pathlib
import sys

import numpy as np

import atlas_build as ab
import lap_watch as lw
import session_map as sm


def main():
    session = pathlib.Path(sys.argv[1])
    t0 = lw.to_s(sys.argv[2]) if len(sys.argv) > 2 else 0

    pts = sm.build_path(session, t0)
    laps = sm.find_laps(pts)
    pts = sm.close_loops(pts, laps)
    stops = sm.find_stops(pts)
    evs = [json.loads(l) for l in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    counts = sm.battle_series(session, int(pts[0, 0]), int(pts[-1, 0]))

    def kills_in(a, b):
        return sum(1 for e in evs if e["kind"] == "xp_gain" and a <= lw.to_s(e["ts"]) <= b)

    def xp_in(a, b):
        return sum(e["value"] for e in evs if e["kind"] == "xp_gain" and a <= lw.to_s(e["ts"]) <= b)

    def dmg_in(a, b):
        return sum(e["value"] for e in evs if e["kind"] == "damage_taken" and a <= lw.to_s(e["ts"]) <= b)

    def battle_at(t, w=6):
        v = [counts[s] for s in counts if abs(s - t) <= w]
        return float(np.mean(v)) if v else None

    for s in stops:
        s["kills"] = kills_in(s["t0"], s["t1"] + 6)
        s["xp"] = xp_in(s["t0"], s["t1"] + 6)
        s["dur"] = s["t1"] - s["t0"]

    # spots globais (mesmo criterio do session_map)
    spots = []
    for p in stops:
        for s in spots:
            if float(np.hypot(*(s["pos"] - p["pos"]))) <= sm.SPOT_RADIUS:
                s["stops"].append(p)
                s["pos"] = np.mean([q["pos"] for q in s["stops"]], axis=0)
                p["spot"] = s["id"]
                break
        else:
            spots.append({"id": len(spots) + 1, "pos": p["pos"], "stops": [p]})
            p["spot"] = spots[-1]["id"]

    # --- trechos de lure (entre boxes) ---
    print("=== TRECHOS DE LURE (entre uma box e a seguinte) ===")
    print(f"{'de':>4} {'para':>5} {'lure':>6} {'dist':>6} {'batalha ini':>12} {'fim':>6} {'juntou':>7} "
          f"{'kills destino':>14} {'kills/min ciclo':>16}")
    trans = []
    for a, b in zip(stops, stops[1:]):
        gap = b["t0"] - a["t1"]
        if gap <= 0 or gap > 240:
            continue
        d = float(np.hypot(*(b["pos"] - a["pos"])))
        b0, b1 = battle_at(a["t1"]), battle_at(b["t0"])
        ganho = (b1 - b0) if (b0 is not None and b1 is not None) else None
        ciclo = gap + b["dur"]
        kpm = b["kills"] / (ciclo / 60) if ciclo else 0
        trans.append({"de": a["spot"], "para": b["spot"], "lure": gap, "dist": d,
                      "b0": b0, "b1": b1, "ganho": ganho, "kills": b["kills"],
                      "kpm_ciclo": kpm, "xp": b["xp"], "dur": b["dur"]})
        print(f"S{a['spot']:>3} S{b['spot']:>4} {gap:>5}s {d:>5.0f} {str(round(b0,1) if b0 else '-'):>12} "
              f"{str(round(b1,1) if b1 else '-'):>6} {str(round(ganho,1) if ganho is not None else '-'):>7} "
              f"{b['kills']:>14} {kpm:>16.1f}")

    if not trans:
        print("sem trechos suficientes")
        return

    lures = [t["lure"] for t in trans]
    kk = [t["kills"] for t in trans]
    print(f"\nlure medio: {np.mean(lures):.0f}s (min {min(lures)}s, max {max(lures)}s, mediana {np.median(lures):.0f}s)")
    print(f"tempo total em lure: {sum(lures)}s de {int(pts[-1,0]-pts[0,0])}s "
          f"({sum(lures)/(pts[-1,0]-pts[0,0]):.0%} da hunt)")
    if np.std(lures) > 2 and np.std(kk) > 0:
        c = float(np.corrcoef(lures, kk)[0, 1])
        print(f"correlacao lure x kills no destino: {c:+.2f}")
    else:
        c = 0.0

    # --- ranking por spot: ciclo completo ---
    print("\n=== SPOTS: VALE A PENA PUXAR? (ciclo = lure ate ele + luta) ===")
    print(f"{'spot':>5} {'visitas':>8} {'kills/visita':>13} {'lure medio':>11} {'kills/min ciclo':>16} {'XP/min ciclo':>14}")
    rank = []
    for s in spots:
        ts = [t for t in trans if t["para"] == s["id"]]
        if not ts:
            continue
        kpm = float(np.mean([t["kpm_ciclo"] for t in ts]))
        xpm = float(np.mean([t["xp"] / ((t["lure"] + t["dur"]) / 60) for t in ts]))
        rank.append({"id": s["id"], "n": len(ts), "kills": float(np.mean([t["kills"] for t in ts])),
                     "lure": float(np.mean([t["lure"] for t in ts])), "kpm": kpm, "xpm": xpm})
    rank.sort(key=lambda r: -r["xpm"])
    for r in rank:
        print(f"S{r['id']:>4} {r['n']:>8} {r['kills']:>13.1f} {r['lure']:>10.0f}s {r['kpm']:>16.1f} {r['xpm']:>14,.0f}")

    print("\n=== VEREDITO ===")
    med = float(np.median([r["xpm"] for r in rank])) if rank else 0
    bons = [r for r in rank if r["xpm"] > med * 1.3]
    ruins = [r for r in rank if r["xpm"] < med * 0.7]
    if bons:
        print("COMPENSA puxar (XP/min de ciclo acima da mediana): " +
              ", ".join(f"S{r['id']} ({r['xpm']:,.0f} XP/min, lure {r['lure']:.0f}s)" for r in bons))
    if ruins:
        print("NAO compensa (custo de lure alto pro que rende): " +
              ", ".join(f"S{r['id']} ({r['xpm']:,.0f} XP/min, lure {r['lure']:.0f}s, {r['kills']:.0f} kills)" for r in ruins))
    if c > 0.35:
        print(f"\nLURE MAIS LONGO ESTA VALENDO (correlacao {c:+.2f}): puxar mais antes de parar "
              f"rende mais kills na box. Nao encurte.")
    elif c < -0.2:
        print(f"\nLURE ESTA LONGO DEMAIS (correlacao {c:+.2f}): trechos mais demorados rendem MENOS. "
              f"Encurte o caminho ou pare antes.")
    else:
        print(f"\nTempo de lure nao explica o rendimento (correlacao {c:+.2f}): o que manda e o "
              f"spot, nao o quanto voce anda ate ele.")


if __name__ == "__main__":
    main()
