"""Placar entre rotacoes a partir de laps.jsonl."""
import collections
import json
import pathlib
import sys

import numpy as np

p = pathlib.Path(sys.argv[1])
laps = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
laps = [l for l in laps if l.get("rotacao")]
agg = collections.defaultdict(list)
for l in laps:
    agg[l["rotacao"]].append(l)

print(f"{'rot':>4} {'voltas':>7} {'XP/h':>12} {'kills/min':>10} {'profit/h':>11} "
      f"{'dmg/kill':>9} {'pack':>6} {'raio':>6} {'dur medio':>10}")
res = {}
for r, ls in sorted(agg.items()):
    dur = sum(l["dur_s"] for l in ls)
    k = sum(l["kills_total"] for l in ls) or 1
    xp = sum(l["xp"] for l in ls)
    pr = sum(l.get("profit") or 0 for l in ls)
    din = sum(l["dmg_in"] for l in ls)
    pack = sum(l["battle_medio"] * l["dur_s"] for l in ls) / dur
    raio = float(np.mean([l.get("raio_max_tiles", 0) for l in ls]))
    res[r] = dict(xph=xp / (dur / 3600), kpm=k / (dur / 60), prh=pr / (dur / 3600),
                  dpk=din / k, pack=pack, raio=raio, n=len(ls), dur=dur / len(ls))
    v = res[r]
    print(f"{r:>4} {v['n']:>7} {v['xph']:>12,.0f} {v['kpm']:>10.1f} {v['prh']:>11,.0f} "
          f"{v['dpk']:>9,.0f} {v['pack']:>6.1f} {v['raio']:>6.0f} {v['dur']/60:>9.1f}m")

if len(res) >= 2:
    base = max(res, key=lambda r: res[r]["xph"])
    print(f"\nmelhor rotacao ate agora: {base} ({res[base]['xph']:,.0f} XP/h)")
    for r, v in res.items():
        if r == base:
            continue
        b = res[base]
        print(f"  {r} vs {base}: XP/h {(v['xph']/b['xph']-1):+.1%} | kills/min {(v['kpm']/b['kpm']-1):+.1%} | "
              f"profit/h {(v['prh']/b['prh']-1):+.1%} | dano/kill {(v['dpk']/b['dpk']-1):+.1%}")
        if v["n"] < 2 or res[base]["n"] < 2:
            print(f"     (amostra pequena: {r}={v['n']} volta(s), {base}={b['n']})")
