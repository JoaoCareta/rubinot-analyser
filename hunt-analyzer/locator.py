"""Localizacao absoluta: registra o Map View contra o mosaico .otmm.

Descobre andar e bbox sozinho a partir de um frame-sonda, entao serve pra
qualquer cave sem configuracao manual.
"""
import pathlib
import re

import numpy as np
from PIL import Image

from pin_detect import MAP_CROP, PIN_TIP_PX

MMDIR = pathlib.Path(r"C:\Program Files (x86)\RubinOT 2.0\bin\minimap")
ZOOM = 2.0  # px por tile no Map View (setting do cliente)

PAL = np.zeros((256, 3), dtype=np.uint8)
for _i in range(216):
    PAL[_i] = ((_i // 36) * 51, ((_i // 6) % 6) * 51, (_i % 6) * 51)


def recent_blocks(since_ts):
    """Blocos .otmm escritos depois de since_ts -> [(x, y, z)]."""
    out = []
    for f in MMDIR.glob("*.otmm"):
        if f.stat().st_mtime < since_ts:
            continue
        m = re.match(r"minimap1520_(\d+)_(\d+)_(\d+)", f.stem)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return out


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
    return PAL[canvas].astype(float).mean(axis=2) / 255.0, n


def small_of(frame_png):
    crop = np.asarray(Image.open(frame_png).convert("L").crop(MAP_CROP), dtype=float) / 255.0
    img = Image.fromarray((crop * 255).astype(np.uint8))
    w, h = int(img.width / ZOOM), int(img.height / ZOOM)
    return np.asarray(img.resize((w, h), Image.BILINEAR), dtype=float) / 255.0


def register(big, small, step=3):
    bh, bw = big.shape
    sh, sw = small.shape
    if bh <= sh or bw <= sw:
        return (9e9, 0, 0)
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


class Locator:
    """Mosaico + registro. Descobre andar/bbox pelo frame-sonda."""

    def __init__(self, probe_frame, since_ts, pad=140):
        blocks = recent_blocks(since_ts)
        if not blocks:
            raise RuntimeError("nenhum bloco .otmm recente")
        small = small_of(probe_frame)
        floors = collections_counter(b[2] for b in blocks)
        best = None
        for z, _n in floors:
            xs = [b[0] for b in blocks if b[2] == z]
            ys = [b[1] for b in blocks if b[2] == z]
            X0, X1 = min(xs) - pad, max(xs) + 64 + pad
            Y0, Y1 = min(ys) - pad, max(ys) + 64 + pad
            big, nb = stitch(z, X0, X1, Y0, Y1)
            if nb == 0:
                continue
            d, x, y = register(big, small)
            if best is None or d < best[0]:
                best = (d, z, big, X0, Y0)
        if best is None or best[0] > 0.05:
            raise RuntimeError(f"registro fraco: {best[0] if best else '?'}")
        self.score0, self.z, self.big, self.X0, self.Y0 = best

    def position(self, frame_png, max_err=0.03):
        """(x, y) em tiles absolutos da PONTA DO PIN, ou None."""
        try:
            small = small_of(frame_png)
        except OSError:
            return None
        d, x, y = register(self.big, small, step=4)
        if d > max_err:
            return None
        return (self.X0 + x + PIN_TIP_PX[0] / ZOOM, self.Y0 + y + PIN_TIP_PX[1] / ZOOM)


def collections_counter(it):
    c = {}
    for v in it:
        c[v] = c.get(v, 0) + 1
    return sorted(c.items(), key=lambda kv: -kv[1])
