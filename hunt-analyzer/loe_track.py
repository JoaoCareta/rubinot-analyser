"""Trajetoria absoluta na Livraria: casa cada m_ nos stitches z12/z13 (2px/tile).

Melhor score decide o ANDAR e a posicao; ponta do pin -> tile do jogador.
Grava loe_track.jsonl: {"t": seg, "ts": "HH:MM:SS", "z": 12, "x": tile, "y": tile,
"score": s}. Incremental: pula timestamps ja gravados (rodar de novo so anexa).

Uso: python loe_track.py capture\\session_20260728_072106 [step_s]
"""
import json
import os
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image

from anchor_map import PAL
from lap_watch import fmt, fsec
from pin_detect import PIN_TIP_PX

# 18/09: generalizado por hunt — HUNT_PREFIX=fogo usa fogo_origem.json / fogo_z*_color.npy
PREFIX = os.environ.get("HUNT_PREFIX", "loe")
_orig = json.load(open(f"{PREFIX}_origem.json"))
X0, Y0 = _orig["X0"], _orig["Y0"]
ZS = tuple(_orig.get("zs", (12, 13)))
ZOOM = 2
_ini = os.environ.get("INICIO", "07:21:24")
INICIO = sum(int(p) * m for p, m in zip(_ini.split(":"), (3600, 60, 1)))
MIN_SCORE = 0.88


def main():
    session = pathlib.Path(sys.argv[1])
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    out = session / f"{PREFIX}_track.jsonl"
    feitos = set()
    if out.exists():
        feitos = {json.loads(l)["t"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}

    # casar em 1 px/tile com o m_ REDUZIDO (INTER_AREA) — igual ao achar_loe;
    # upscale NEAREST do mapa + m_ original falha com a fase sub-tile do Map View
    bigs = {}
    for z in ZS:
        idx = np.load(f"{PREFIX}_z{z}_color.npy")
        bigs[z] = (PAL[idx].astype(np.float32) / 255.0)[:, :, ::-1]

    ms = [f for f in sorted(session.glob("m_*.png")) if fsec(f.name) >= INICIO]
    ultimo = -step
    novos = 0
    with out.open("a", encoding="utf-8") as fh:
        for f in ms:
            t = fsec(f.name)
            if t - ultimo < step or t in feitos:
                continue
            ultimo = t
            arr = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)[:, :, ::-1] / 255.0
            tpl = cv2.resize(arr, (arr.shape[1] // ZOOM, arr.shape[0] // ZOOM),
                             interpolation=cv2.INTER_AREA)
            best = None
            for z, big in bigs.items():
                res = cv2.matchTemplate(big, tpl, cv2.TM_CCOEFF_NORMED)
                _, sc, _, loc = cv2.minMaxLoc(res)
                if best is None or sc > best[0]:
                    best = (float(sc), z, loc)
            sc, z, loc = best
            if sc < MIN_SCORE:
                continue
            x = X0 + loc[0] + PIN_TIP_PX[0] / ZOOM
            y = Y0 + loc[1] + PIN_TIP_PX[1] / ZOOM
            fh.write(json.dumps({"t": t, "ts": fmt(t), "z": z, "x": round(x, 1),
                                 "y": round(y, 1), "score": round(sc, 3)}) + "\n")
            novos += 1
    print(f"{novos} pontos novos em {out}", flush=True)


if __name__ == "__main__":
    main()
