"""Recupera voltas de uma janela e grava em laps.jsonl (com rotacao automatica).

Uso: python catchup.py capture\\session_X HH:MM:SS [HH:MM:SS]
"""
import json
import pathlib
import sys

import atlas_build as ab
import lap_watch as lw
import rotations as rot
import session_map as sm


def main():
    s = pathlib.Path(sys.argv[1])
    t0 = lw.to_s(sys.argv[2])
    t1 = lw.to_s(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
    g, gap = ab.load_atlas()

    pts = sm.build_path(s, t0, refine=False)
    pts = pts[pts[:, 0] <= t1]
    laps = sm.find_laps(pts)
    laps_p = s / "laps.jsonl"
    prev = [json.loads(l) for l in laps_p.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if laps_p.exists() else []
    n0 = max([p.get("volta", 0) for p in prev], default=0)
    print(f"{len(laps)} voltas entre {lw.fmt(t0)} e {lw.fmt(int(pts[-1,0]))}\n")

    rows = []
    for k, (i0, i1) in enumerate(laps, n0 + 1):
        a, b = int(pts[i0, 0]), int(pts[i1, 0])
        path = [(x - pts[i0, 1], y - pts[i0, 2]) for _, x, y in pts[i0 : i1 + 1]]
        label, _d, why = rot.classify(path, prev)
        summ = lw.lap_summary(s, a, b, g, gap)
        info = rot.summarize_path(path)
        out = {"volta": k, "rotacao": label, "rotacao_motivo": why, "inicio": lw.fmt(a),
               "fim": lw.fmt(b), "dur_s": b - a, **info, **summ,
               "path": [[round(x, 1), round(y, 1)] for x, y in path]}
        prev.append(out)
        rows.append(out)
        kk = out["kills_total"] or 1
        print(f"volta {k} [{label}] {lw.fmt(a)}-{lw.fmt(b)} ({(b-a)//60}m{(b-a)%60:02d}s)")
        print(f"   {kk} kills {dict(out['kills'])}")
        print(f"   XP {out['xp']:,} | profit {out.get('profit')} | dmg/kill {out['dmg_in']/kk:,.0f} "
              f"| pack {out['battle_medio']}/{out['battle_pico']} | raio {info.get('raio_max_tiles')}")
        print(f"   rotacao: {why}\n")

    with laps_p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"gravadas {len(rows)} voltas")


if __name__ == "__main__":
    main()
