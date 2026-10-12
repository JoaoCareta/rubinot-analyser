"""Diagnostico do track: cobertura temporal + scores de frames que falharam."""
import json
import pathlib

import cv2
import numpy as np
from PIL import Image

from anchor_map import PAL
from lap_watch import fmt, fsec

session = pathlib.Path(r"capture\session_20260728_072106")
pts = [json.loads(l) for l in (session / "loe_track.jsonl").read_text(encoding="utf-8").splitlines()]
ts = [p["t"] for p in pts]
print(f"{len(pts)} pontos, {fmt(min(ts))} -> {fmt(max(ts))}")
gaps = [(a, b) for a, b in zip(ts, ts[1:]) if b - a > 20]
print(f"{len(gaps)} gaps >20s:", [(fmt(a), fmt(b)) for a, b in gaps[:12]])
porz = {}
for p in pts:
    porz[p["z"]] = porz.get(p["z"], 0) + 1
print("por andar:", porz)

bigs = {}
for z in (12, 13):
    idx = np.load(f"loe_z{z}_color.npy")
    big = PAL[idx].astype(np.float32) / 255.0
    bigs[z] = cv2.resize(big[:, :, ::-1], (idx.shape[1] * 2, idx.shape[0] * 2),
                         interpolation=cv2.INTER_NEAREST)

feitos = set(ts)
ms = [f for f in sorted(session.glob("m_*.png")) if fsec(f.name) >= 7 * 3600 + 22 * 60]
falhas = [f for f in ms if fsec(f.name) not in feitos][:: max(1, len(ms) // 200)][:10]
for f in falhas:
    arr = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)[:, :, ::-1] / 255.0
    scs = {}
    for z, big in bigs.items():
        res = cv2.matchTemplate(big, arr, cv2.TM_CCOEFF_NORMED)
        _, sc, _, _ = cv2.minMaxLoc(res)
        scs[z] = round(float(sc), 3)
    print(f.name, scs)
