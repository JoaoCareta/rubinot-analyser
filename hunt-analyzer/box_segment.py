"""Segmenta as sessoes em boxes (rajadas de combate) e mede kills/bichos por box.

Uso:  python box_segment.py capture\\session_A [capture\\session_B ...]

Box = sequencia de eventos de combate sem silencio maior que GAP_S segundos.
Kills por box = eventos de XP na janela. Bichos simultaneos = battle list (b_*.png).
"""
import collections
import json
import pathlib
import sys

import numpy as np
from PIL import Image

import atlas_build as ab

GAP_S = 12
MIN_EVENTS = 8
COMBAT = {"damage_dealt", "damage_taken", "damage_dealt_player", "damage_taken_player", "dodge"}
BATTLE_X_MAX = 175   # corta o vazamento da coluna de equipamento a direita
BATTLE_Y_MIN = 18    # pula a barra de titulo "Battle List"


def to_s(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def fmt(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def load_events(dirs):
    evs, last = [], ""
    for d in dirs:
        for line in (pathlib.Path(d) / "events.jsonl").read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if last and e["ts"] <= last:
                continue  # cauda da sessao anterior re-exibida no 1o frame
            evs.append(e)
        if evs:
            last = evs[-1]["ts"]
    return evs


def battle_series(dirs):
    """seg -> contagem de criaturas na battle list (max entre frames do segundo)."""
    series = {}
    for d in dirs:
        for f in sorted(pathlib.Path(d).glob("b_*.png")):
            binary = ab.binarize(f)
            binary[:BATTLE_Y_MIN, :] = False
            binary[:, BATTLE_X_MAX:] = False
            n = sum(1 for y0, y1 in ab.find_bands(binary) if 6 <= y1 - y0 <= 15)
            name = f.name  # b_HHMMSS_mmm.png
            sec = int(name[2:4]) * 3600 + int(name[4:6]) * 60 + int(name[6:8])
            series[sec] = max(series.get(sec, 0), n)
    return series


def segment(events):
    combat = sorted(to_s(e["ts"]) for e in events if e["kind"] in COMBAT)
    boxes, cur = [], []
    for t in combat:
        if cur and t - cur[-1] > GAP_S:
            if len(cur) >= MIN_EVENTS:
                boxes.append((cur[0], cur[-1]))
            cur = []
        cur.append(t)
    if len(cur) >= MIN_EVENTS:
        boxes.append((cur[0], cur[-1]))
    return boxes


def main():
    dirs = sys.argv[1:]
    events = load_events(dirs)
    boxes = segment(events)
    battle = battle_series(dirs)

    xp_ts = sorted(to_s(e["ts"]) for e in events if e["kind"] == "xp_gain")
    loot_ts = sorted(to_s(e["ts"]) for e in events if e["kind"] == "loot")
    dmg = [(to_s(e["ts"]), e["kind"], e["value"]) for e in events
           if e["kind"] in ("damage_dealt", "damage_taken", "damage_dealt_player") and "value" in e]

    print(f"{len(events)} eventos, {len(boxes)} boxes (gap>{GAP_S}s, min {MIN_EVENTS} eventos)\n")
    print("  #  inicio    fim      dur   kills  loot  dmg_out  dmg_in  battle_pico")
    rows = []
    prev_end = None
    for i, (t0, t1) in enumerate(boxes, 1):
        kills = sum(1 for t in xp_ts if t0 <= t <= t1 + 4)
        loot = sum(1 for t in loot_ts if t0 <= t <= t1 + 8)
        out_ = sum(v for t, k, v in dmg if k in ("damage_dealt", "damage_dealt_player") and t0 <= t <= t1)
        in_ = sum(v for t, k, v in dmg if k == "damage_taken" and t0 <= t <= t1)
        counts = [battle[s] for s in range(t0, t1 + 1) if s in battle]
        peak = max(counts) if counts else None
        gap_prev = t0 - prev_end if prev_end else None
        prev_end = t1
        rows.append((t0, t1, kills, loot, peak, gap_prev))
        peak_s = f"{peak}" if peak is not None else "-"
        print(f"{i:3}  {fmt(t0)}  {fmt(t1)}  {t1 - t0:4}s  {kills:4}  {loot:4}  {out_:7}  {in_:6}  {peak_s:>4}")

    if not rows:
        return
    durs = [r[1] - r[0] for r in rows]
    kills_l = [r[2] for r in rows]
    gaps = [r[5] for r in rows if r[5] is not None and r[5] < 180]
    peaks = [r[4] for r in rows if r[4] is not None]
    span = rows[-1][1] - rows[0][0]
    med_gap = f"  intervalo entre boxes={sum(gaps) / len(gaps):.0f}s" if gaps else ""
    print(f"\nmedias: dur={sum(durs) / len(durs):.0f}s  kills/box={sum(kills_l) / len(rows):.1f}{med_gap}")
    if peaks:
        print(f"battle list (boxes cobertas: {len(peaks)}): pico medio={sum(peaks) / len(peaks):.1f}  pico max={max(peaks)}")
    print(f"ritmo: {len(rows) / (span / 3600):.1f} boxes/h no intervalo {fmt(rows[0][0])}-{fmt(rows[-1][1])}")

    gaps_all = sorted(
        (b[0] - a[1] for a, b in zip(boxes, boxes[1:])), reverse=True)
    print(f"maiores intervalos sem combate: {[f'{g}s' for g in gaps_all[:8]]}")


if __name__ == "__main__":
    main()
