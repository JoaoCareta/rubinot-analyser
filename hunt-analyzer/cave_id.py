"""Identifica a cave da sessao casando os m_ mais recentes contra as caves conhecidas.

Mesmo metodo do loe_track: m_ reduzido INTER_AREA p/ 1 px/tile, matchTemplate
colorido contra o stitch (PAL[idx]) de cada cave com array salvo. Score >= 0,85
= cave reconhecida; abaixo disso, so o DNA de cor (achar_loe.py) resolve.

Uso: python cave_id.py capture\\session_X [n_frames]
"""
import json
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image

from anchor_map import PAL

ZOOM = 2
CAVES = {
    "livraria_energy z12": ("loe_z12_color.npy", "loe_origem.json"),
    "livraria_energy z13": ("loe_z13_color.npy", "loe_origem.json"),
    "falcon_bastion z9": ("falcon_z9_color.npy", None),
    "ingol z8": ("ingol_color.npy", "ingol_origem.json"),
    "infernatil_hell z14": ("infernatil_color.npy", "infernatil_origem.json"),
}


def main():
    session = pathlib.Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    ms = sorted(session.glob("m_*.png"))[-n * 5::5] or sorted(session.glob("m_*.png"))[-n:]
    bigs = {k: (PAL[np.load(a)].astype(np.float32) / 255.0)[:, :, ::-1] for k, (a, _) in CAVES.items()}
    placar = {k: [] for k in CAVES}
    for f in ms:
        arr = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)[:, :, ::-1] / 255.0
        tpl = cv2.resize(arr, (arr.shape[1] // ZOOM, arr.shape[0] // ZOOM), interpolation=cv2.INTER_AREA)
        for k, big in bigs.items():
            if big.shape[0] < tpl.shape[0] or big.shape[1] < tpl.shape[1]:
                continue
            _, sc, _, _ = cv2.minMaxLoc(cv2.matchTemplate(big, tpl, cv2.TM_CCOEFF_NORMED))
            placar[k].append(float(sc))
    res = {k: round(float(np.median(v)), 3) for k, v in placar.items() if v}
    melhor = max(res, key=res.get) if res else None
    print(json.dumps({"frames": [f.name for f in ms], "scores": res,
                      "cave": melhor if melhor and res[melhor] >= 0.85 else "DESCONHECIDA"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
