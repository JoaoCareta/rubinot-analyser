"""Coach por BOX: segmenta pulls, localiza cada um no mapa e ranqueia os spots.

Responde: onde buscar mais bicho, onde esperar mais, onde cortar.

Uso: python box_coach.py capture\\session_X HH:MM:SS HH:MM:SS
"""
import collections
import json
import pathlib
import re
import sys

import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw
from pin_detect import MAP_CROP, PIN_TIP_PX

MMDIR = pathlib.Path(r"C:\Program Files (x86)\RubinOT 2.0\bin\minimap")
PAL = np.zeros((256, 3), dtype=np.uint8)
for _i in range(216):
    PAL[_i] = ((_i // 36) * 51, ((_i // 6) % 6) * 51, (_i % 6) * 51)

PULL_LO, PULL_HI = 2, 6          # vale <=2 ; pico >=6 define um pull
SPOT_RADIUS = 12                 # tiles: pulls dentro disso = mesmo spot


def stitch(z, X0, X1, Y0, Y1):
    W, H = X1 - X0, Y1 - Y0
    canvas = np.zeros((H, W), dtype=np.uint8)
    n = 0
    for f in MMDIR.glob(f"minimap1520_*_{z}.otmm"):
        m = re.match(r"minimap1520_(\d+)_(\d+)_", f.stem)
        bx, by = int(m.group(1)), int(m.group(2))
        if bx + 64 <= X0 or bx >= X1 or by + 64 <= Y0 or by >= Y1:
            continue
        data = f.read_bytes()
        if len(data) < 8216:
            continue
        blk = np.frombuffer(data[4120:8216], dtype=np.uint8).reshape(64, 64)
        xl, xh = max(bx, X0), min(bx + 64, X1)
        yl, yh = max(by, Y0), min(by + 64, Y1)
        canvas[yl - Y0 : yh - Y0, xl - X0 : xh - X0] = blk[yl - by : yh - by, xl - bx : xh - bx]
        n += 1
    return canvas, n


def register(big, small, step=3):
    bh, bw = big.shape
    sh, sw = small.shape
    s2 = small[::2, ::2]
    best = (9e9, 0, 0)
    for y in range(0, bh - sh, step):
        for x in range(0, bw - sw, step):
            d = float(((big[y : y + sh : 2, x : x + sw : 2] - s2) ** 2).mean())
            if d < best[0]:
                best = (d, x, y)
    _, bx, by = best
    for y in range(max(0, by - 3), min(bh - sh, by + 4)):
        for x in range(max(0, bx - 3), min(bw - sw, bx + 4)):
            d = float(((big[y : y + sh][:, x : x + sw] - small) ** 2).mean())
            if d < best[0]:
                best = (d, x, y)
    return best


def main():
    sess = pathlib.Path(sys.argv[1])
    t0 = lw.to_s(sys.argv[2])
    t1 = lw.to_s(sys.argv[3])

    # --- battle list por segundo ---
    counts = {}
    bfiles = [f for f in sorted(sess.glob("b_*.png")) if t0 <= lw.fsec(f.name) <= t1]
    for f in bfiles[::2]:
        counts[lw.fsec(f.name)] = lw.battle_count(f)
    secs = sorted(counts)
    print(f"battle list: {len(secs)} amostras de {lw.fmt(t0)} a {lw.fmt(t1)}")

    # --- segmenta pulls ---
    pulls, cur = [], None
    for s in secs:
        n = counts[s]
        if cur is None:
            if n >= PULL_HI:
                cur = {"t0": s, "peak": n}
        else:
            cur["peak"] = max(cur["peak"], n)
            if n <= PULL_LO:
                cur["t1"] = s
                if cur["t1"] - cur["t0"] >= 8:
                    pulls.append(cur)
                cur = None
    if cur and secs:
        cur["t1"] = secs[-1]
        pulls.append(cur)
    print(f"{len(pulls)} pulls detectados")

    # --- eventos por pull ---
    evs = [json.loads(l) for l in (sess / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    for p in pulls:
        p["kills"] = collections.Counter()
        p["dmg_in"] = 0
        p["xp"] = 0
        for e in evs:
            t = lw.to_s(e["ts"])
            if not (p["t0"] <= t <= p["t1"] + 6):
                continue
            if e["kind"] == "xp_gain":
                p["xp"] += e["value"]
                sp = lw.XP_SPECIES.get(e["value"], "outro")
                p["kills"][sp] += 1
            elif e["kind"] == "damage_taken":
                p["dmg_in"] += e["value"]

    # --- localiza cada pull ---
    frames = sorted(sess.glob("f_*.png"))
    fsecs = np.array([lw.fsec(f.name) for f in frames])
    X0, X1, Y0, Y1 = 33560, 33800, 32540, 32760
    best_floor, big = None, None
    probe = frames[int(np.argmin(np.abs(fsecs - (t0 + t1) // 2)))]
    crop = np.asarray(Image.open(probe).convert("L").crop(MAP_CROP), dtype=float) / 255.0
    small = np.asarray(Image.fromarray((crop * 255).astype(np.uint8)).resize((96, 88), Image.BILINEAR), dtype=float) / 255.0
    for z in (12, 13, 14, 11):
        cv_, n = stitch(z, X0, X1, Y0, Y1)
        if n == 0:
            continue
        g = PAL[cv_].astype(float).mean(axis=2) / 255.0
        d, x, y = register(g, small)
        print(f"  z{z}: {n} blocos, erro {d:.4f}")
        if best_floor is None or d < best_floor[0]:
            best_floor, big = (d, z), g
    print(f"andar: z{best_floor[1]} (erro {best_floor[0]:.4f})")

    for p in pulls:
        i = int(np.argmin(np.abs(fsecs - p["t0"])))
        crop = np.asarray(Image.open(frames[i]).convert("L").crop(MAP_CROP), dtype=float) / 255.0
        sm = np.asarray(Image.fromarray((crop * 255).astype(np.uint8)).resize((96, 88), Image.BILINEAR), dtype=float) / 255.0
        d, x, y = register(big, sm, step=4)
        p["score"] = d
        p["pos"] = (X0 + x + int(PIN_TIP_PX[0] / 2), Y0 + y + int(PIN_TIP_PX[1] / 2)) if d < 0.03 else None

    # --- agrupa em spots ---
    spots = []
    for p in sorted(pulls, key=lambda q: q["t0"]):
        if not p["pos"]:
            continue
        for s in spots:
            if abs(s["pos"][0] - p["pos"][0]) + abs(s["pos"][1] - p["pos"][1]) <= SPOT_RADIUS:
                s["pulls"].append(p)
                break
        else:
            spots.append({"pos": p["pos"], "pulls": [p]})

    print(f"\n{len(spots)} spots distintos ({sum(1 for p in pulls if p['pos'])} pulls localizados)\n")
    rows = []
    for i, s in enumerate(spots, 1):
        ps = s["pulls"]
        kills = sum(sum(p["kills"].values()) for p in ps)
        xp = sum(p["xp"] for p in ps)
        dur = sum(p["t1"] - p["t0"] for p in ps)
        din = sum(p["dmg_in"] for p in ps)
        peak = max(p["peak"] for p in ps)
        mix = collections.Counter()
        for p in ps:
            mix.update(p["kills"])
        rows.append({
            "id": i, "pos": s["pos"], "visitas": len(ps), "kills": kills,
            "kills_visita": kills / len(ps), "xp": xp, "dur": dur,
            "kills_min": kills / (dur / 60) if dur else 0,
            "xp_min": xp / (dur / 60) if dur else 0,
            "dmg_kill": din / kills if kills else 0, "peak": peak,
            "mix": mix.most_common(3),
            "saiu_com": [counts.get(p["t1"], 0) for p in ps],
        })
    rows.sort(key=lambda r: -r["xp_min"])
    print(f"{'#':>2} {'pos':>14} {'vis':>4} {'kills':>6} {'k/vis':>6} {'k/min':>6} {'XP/min':>9} {'dmg/kill':>9} {'pico':>5}  mix")
    for r in rows:
        mix = " ".join(f"{sp[:9]}:{n}" for sp, n in r["mix"])
        print(f"{r['id']:>2} {str(r['pos']):>14} {r['visitas']:>4} {r['kills']:>6} {r['kills_visita']:>6.1f} "
              f"{r['kills_min']:>6.1f} {r['xp_min']:>9,.0f} {r['dmg_kill']:>9,.0f} {r['peak']:>5}  {mix}")

    # --- sugestoes ---
    print("\n=== SUGESTOES POR BOX ===")
    if not rows:
        return
    med_xpmin = float(np.median([r["xp_min"] for r in rows]))
    tips = []
    for r in rows:
        if r["xp_min"] > med_xpmin * 1.4 and r["visitas"] >= 2:
            tips.append((3 + r["xp_min"] / med_xpmin,
                         f"ESPERE MAIS no spot #{r['id']} {r['pos']}: rende {r['xp_min']:,.0f} XP/min "
                         f"({r['xp_min'] / med_xpmin:.1f}x a mediana), {r['kills_visita']:.1f} kills por visita. "
                         f"Ficar +30s ali vale mais que andar."))
        if r["xp_min"] < med_xpmin * 0.6 and r["visitas"] >= 2:
            tips.append((2 + (med_xpmin / max(r["xp_min"], 1)),
                         f"CORTE/ENCURTE o spot #{r['id']} {r['pos']}: só {r['xp_min']:,.0f} XP/min "
                         f"({r['kills_visita']:.1f} kills/visita) e você gastou {r['dur']}s ali no total."))
        saiu = [n for n in r["saiu_com"] if n >= 3]
        if len(saiu) >= 2:
            tips.append((2.5, f"SOBROU BICHO no spot #{r['id']} {r['pos']}: em {len(saiu)} visitas você saiu "
                              f"com {max(saiu)} ainda na battle list. Termine o pull antes de andar."))
        if r["dmg_kill"] > 2200 and r["kills"] >= 5:
            tips.append((1.8, f"PERIGO no spot #{r['id']} {r['pos']}: {r['dmg_kill']:,.0f} de dano por kill "
                              f"(pico {r['peak']}). Puxe pra fora ou reduza o tamanho do pull ali."))
    tips.sort(key=lambda t: -t[0])
    for i, (_, t) in enumerate(tips[:8], 1):
        print(f"{i}. {t}")


if __name__ == "__main__":
    main()
