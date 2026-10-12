"""Acha a Livraria de Energy nos blocos .otmm (metodo 3 passos validado no Infernatil):
1. DNA de cor de frames m_ da hunt; 2. varre TODOS os blocos pelo DNA;
3. matchTemplate colorido do m_ no stitch dos clusters candidatos, zoom 1-4.

Ancora CADA frame independente (a livraria tem 2 andares — frames de andares
diferentes casam com blocos diferentes). Salva loe_anchor.json por andar.

Uso: python achar_loe.py capture\\session_20260728_072106
"""
import collections
import json
import pathlib
import re
import sys

import cv2
import numpy as np
from PIL import Image

from anchor_map import MMDIR, PAL, stitch_floor
from lap_watch import fsec

ALVOS = ("072230", "072330", "072430", "072530", "072630", "072730")
if len(sys.argv) > 2:
    ALVOS = tuple(sys.argv[2:])
MIN_SCORE = 0.85


def rgb_to_idx(arr):
    """RGB (paleta from8bit exata) -> indice: r/51*36 + g/51*6 + b/51."""
    q = (arr.astype(int) + 25) // 51
    return (q[:, :, 0] * 36 + q[:, :, 1] * 6 + q[:, :, 2]).astype(np.uint8)


def dna(idx):
    vals, counts = np.unique(idx[idx != 0], return_counts=True)
    tot = counts.sum()
    return {int(v): float(c) / tot for v, c in zip(vals, counts)} if tot else {}


def main():
    session = pathlib.Path(sys.argv[1])
    frames = []
    for alvo in ALVOS:
        t = int(alvo[:2]) * 3600 + int(alvo[2:4]) * 60 + int(alvo[4:6])
        ms = sorted(session.glob("m_*.png"))
        if ms:
            frames.append(min(ms, key=lambda p: abs(fsec(p.name) - t)))
    frames = sorted(set(frames))
    print(f"{len(frames)} frames m_:", [f.name for f in frames], flush=True)

    # passo 2: varre todos os blocos uma vez so, guarda contagem de indices
    blocos = []
    for f in MMDIR.glob("minimap1520_*.otmm"):
        data = f.read_bytes()
        if len(data) < 8216:
            continue
        m = re.match(r"minimap1520_(\d+)_(\d+)_(\d+)", f.stem)
        blk = np.frombuffer(data[4120:8216], dtype=np.uint8)
        vals, counts = np.unique(blk[blk != 0], return_counts=True)
        if counts.sum() < 400:  # bloco quase vazio nao ancora nada
            continue
        blocos.append((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                       dict(zip(vals.tolist(), counts.tolist())), int(counts.sum())))
    print(f"{len(blocos)} blocos legiveis", flush=True)

    resultados = {}
    for f in frames:
        arr = np.asarray(Image.open(f).convert("RGB"))
        idx = rgb_to_idx(arr)
        d = dna(idx)
        chave = sorted(d.items(), key=lambda kv: -kv[1])[:4]
        print(f"\n{f.name} DNA: {[(k, round(v, 3)) for k, v in chave]}", flush=True)
        if not chave:
            continue
        # candidatos: bloco com os 2 indices dominantes em share >= metade do frame
        cands = []
        for bx, by, z, cnt, tot in blocos:
            ok = all(cnt.get(k, 0) / tot >= v * 0.5 for k, v in chave[:2])
            if ok:
                cands.append((bx, by, z))
        print(f"  {len(cands)} blocos candidatos", flush=True)
        # clusters espaciais por andar
        porz = collections.defaultdict(list)
        for bx, by, z in cands:
            porz[z].append((bx, by))
        best = None
        tpl_f = arr.astype(np.float32) / 255.0
        for z, bs in sorted(porz.items(), key=lambda kv: -len(kv[1])):
            grupos = []
            for bx, by in sorted(bs):
                for gp in grupos:
                    if any(abs(bx - qx) <= 256 and abs(by - qy) <= 256 for qx, qy in gp):
                        gp.append((bx, by))
                        break
                else:
                    grupos.append([(bx, by)])
            for gp in sorted(grupos, key=len, reverse=True)[:6]:
                xs, ys = [b[0] for b in gp], [b[1] for b in gp]
                X0, X1 = min(xs) - 32, max(xs) + 96
                Y0, Y1 = min(ys) - 32, max(ys) + 96
                if (X1 - X0) * (Y1 - Y0) > 2_500_000:
                    continue
                sidx, n = stitch_floor(z, X0, X1, Y0, Y1)
                big = (PAL[sidx].astype(np.float32) / 255.0)[:, :, ::-1]
                for zoom in (1, 2, 3, 4):
                    h, w = arr.shape[0] // zoom, arr.shape[1] // zoom
                    if h < 12 or w < 12 or big.shape[0] <= h or big.shape[1] <= w:
                        continue
                    tpl = cv2.resize(tpl_f[:, :, ::-1], (w, h), interpolation=cv2.INTER_AREA)
                    res = cv2.matchTemplate(big, tpl, cv2.TM_CCOEFF_NORMED)
                    _, sc, _, loc = cv2.minMaxLoc(res)
                    if best is None or sc > best[0]:
                        best = (float(sc), z, X0 + loc[0], Y0 + loc[1], zoom, f.name)
        if best:
            print(f"  MELHOR: score {best[0]:.3f} z{best[1]} tile ({best[2]},{best[3]}) "
                  f"zoom {best[4]}", flush=True)
            if best[0] >= MIN_SCORE:
                resultados[f.name] = {"score": best[0], "z": best[1], "x": best[2],
                                      "y": best[3], "zoom": best[4]}

    out = pathlib.Path("loe_anchor.json")
    out.write_text(json.dumps(resultados, indent=1), encoding="utf-8")
    print(f"\n{len(resultados)} frames ancorados -> {out}", flush=True)


if __name__ == "__main__":
    main()
