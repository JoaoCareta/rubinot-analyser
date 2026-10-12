"""Salva color/walk de uma regiao do minimapa p/ qualquer hunt (generaliza loe_arrays.py).

Uso: python arrays_hunt.py <prefixo> <X0> <X1> <Y0> <Y1> <z> [z2 ...]
Gera <prefixo>_z<z>_color.npy / _walk.npy e <prefixo>_origem.json.
Folga: matchTemplate so alcanca ate (Y1 - altura_do_template) -> deixar >= 100 tiles de sobra.
"""
import json
import re
import sys

import numpy as np

from anchor_map import MMDIR

prefixo = sys.argv[1]
X0, X1, Y0, Y1 = (int(v) for v in sys.argv[2:6])
zs = [int(z) for z in sys.argv[6:]]

for z in zs:
    W, H = X1 - X0, Y1 - Y0
    color = np.zeros((H, W), dtype=np.uint8)
    walk = np.zeros((H, W), dtype=np.uint8)
    n = 0
    for f in MMDIR.glob(f"minimap1520_*_{z}.otmm"):
        m = re.match(r"minimap1520_(\d+)_(\d+)_", f.stem)
        bx, by = int(m.group(1)), int(m.group(2))
        if bx + 64 <= X0 or bx >= X1 or by + 64 <= Y0 or by >= Y1:
            continue
        data = f.read_bytes()
        if len(data) < 8216:
            continue
        cblk = np.frombuffer(data[4120:8216], dtype=np.uint8).reshape(64, 64)
        wblk = np.frombuffer(data[24:4120], dtype=np.uint8).reshape(64, 64)
        xl, xh = max(bx, X0), min(bx + 64, X1)
        yl, yh = max(by, Y0), min(by + 64, Y1)
        color[yl - Y0:yh - Y0, xl - X0:xh - X0] = cblk[yl - by:yh - by, xl - bx:xh - bx]
        walk[yl - Y0:yh - Y0, xl - X0:xh - X0] = wblk[yl - by:yh - by, xl - bx:xh - bx]
        n += 1
    np.save(f"{prefixo}_z{z}_color.npy", color)
    np.save(f"{prefixo}_z{z}_walk.npy", walk)
    vals, cnts = np.unique(walk[color > 0], return_counts=True)
    top = sorted(zip(vals.tolist(), cnts.tolist()), key=lambda t: -t[1])[:6]
    print(f"z{z}: {n} blocos, walk bytes (cor>0): {top}")
json.dump({"X0": X0, "Y0": Y0, "zs": zs}, open(f"{prefixo}_origem.json", "w"))
print(f"arrays salvos + {prefixo}_origem.json")
