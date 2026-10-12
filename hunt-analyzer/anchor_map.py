"""Ancora a trajetoria no MAPA REAL (.otmm) casando o mosaico das vistas.

Uma vista isolada do Map View e pequena e casa mal em cave escura. O MOSAICO de
uma volta inteira, porem, tem muito mais conteudo — casa com folga. Achado o
encaixe, todas as posicoes viram tiles absolutos e o traco cai nos corredores.
"""
import pathlib
import re

import numpy as np
from PIL import Image

from pin_detect import MAP_CROP, PIN_TIP_PX

def _pasta_minimapa():
    """Pasta do minimapa do cliente: a do instalador do RubinOT (registro, 21/09: amigo com o jogo
    fora do lugar padrao), senao a padrao."""
    import winreg
    chave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{7BB3430F-E0F5-41C1-84CF-5DA059E405A3}_is1"
    for raiz, vista in ((winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY), (winreg.HKEY_CURRENT_USER, 0)):
        try:
            with winreg.OpenKey(raiz, chave, 0, winreg.KEY_READ | vista) as k:
                p = pathlib.Path(winreg.QueryValueEx(k, "InstallLocation")[0]) / "bin" / "minimap"
            if p.is_dir():
                return p
        except OSError:
            pass
    return pathlib.Path(r"C:\Program Files (x86)\RubinOT 2.0\bin\minimap")


MMDIR = _pasta_minimapa()
ZOOM = 2.0

PAL = np.zeros((256, 3), dtype=np.uint8)
for _i in range(216):
    PAL[_i] = ((_i // 36) * 51, ((_i // 6) % 6) * 51, (_i % 6) * 51)


def stitch_floor(z, X0, X1, Y0, Y1):
    W, H = X1 - X0, Y1 - Y0
    idx = np.zeros((H, W), dtype=np.uint8)
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
        idx[yl - Y0 : yh - Y0, xl - X0 : xh - X0] = blk[yl - by : yh - by, xl - bx : xh - bx]
        n += 1
    return idx, n


def build_view_mosaic(frames, pts):
    """Mosaico COLORIDO das vistas (2px/tile) + origem em px. pts: [[t,x,y]] tiles.

    Cor importa: casar em tons de cinza confunde lava escura com agua escura.
    """
    px = pts[:, 1:] * ZOOM
    cw, ch = MAP_CROP[2] - MAP_CROP[0], MAP_CROP[3] - MAP_CROP[1]
    x0, y0 = px[:, 0].min() - cw, px[:, 1].min() - ch
    W = int(px[:, 0].max() - px[:, 0].min() + 3 * cw)
    H = int(px[:, 1].max() - px[:, 1].min() + 3 * ch)
    acc = np.zeros((H, W, 3), dtype=float)
    tmap = {int(t): (x, y) for t, x, y in pts}
    for f in frames:
        t = int(f.name[2:4]) * 3600 + int(f.name[4:6]) * 60 + int(f.name[6:8])
        if t not in tmap:
            continue
        X, Y = tmap[t]
        ox, oy = int(round(X * ZOOM - x0)), int(round(Y * ZOOM - y0))
        if not (0 <= ox < W - cw and 0 <= oy < H - ch):
            continue
        v = np.asarray(Image.open(f).convert("RGB").crop(MAP_CROP), dtype=float) / 255.0
        blk = acc[oy : oy + ch, ox : ox + cw]
        msk = (v.sum(axis=2) > 0.15) & (blk.sum(axis=2) == 0)
        msk[66:92, 38:62] = False  # nao colar o pin
        blk[msk] = v[msk]
    return acc, x0, y0


def register(big, small, step=2, pad=0):
    """Casa mosaico COLORIDO (small) dentro do mapa colorido (big). MSE em RGB."""
    bh, bw = big.shape[:2]
    sh, sw = small.shape[:2]
    if bh <= sh or bw <= sw:
        return (9e9, 0, 0)
    valid = small.sum(axis=2) > 0.05
    n = int(valid.sum())
    if n < 200:
        return (9e9, 0, 0)
    v3 = valid[:, :, None]

    def err(y, x):
        w = big[y : y + sh, x : x + sw]
        return float(((((w - small) ** 2) * v3).sum()) / (3 * n))

    best = (9e9, 0, 0)
    for y in range(0, bh - sh, step):
        for x in range(0, bw - sw, step):
            d = err(y, x)
            if d < best[0]:
                best = (d, x, y)
    _, bx, by = best
    for y in range(max(0, by - step), min(bh - sh, by + step + 1)):
        for x in range(max(0, bx - step), min(bw - sw, bx + step + 1)):
            d = err(y, x)
            if d < best[0]:
                best = (d, x, y)
    return best


def anchor(frames, pts, floors=(6, 7, 8, 5, 9, 4), pad=90, region=None):
    """Devolve (z, fn_abs, canvas_idx, X0, Y0, erro) — fn_abs: tiles DR -> tiles absolutos.

    region=(X0, X1, Y0, Y1) forca a area de busca (quando a heuristica de blocos
    recentes aponta pro lugar errado, ex.: viagem gravou blocos de outras zonas).
    """
    mos, mx0, my0 = build_view_mosaic(frames, pts)
    # corta o vazio em volta (mosaico cheio de preto casa em qualquer lugar)
    nz = np.nonzero(mos.sum(axis=2) > 0.06)
    if len(nz[0]):
        ry0, ry1 = nz[0].min(), nz[0].max() + 1
        rx0, rx1 = nz[1].min(), nz[1].max() + 1
        mos = mos[ry0:ry1, rx0:rx1]
        mx0 += rx0
        my0 += ry0
    small = mos[::2, ::2]  # 2px/tile -> 1px/tile
    print(f"  mosaico util: {small.shape[1]}x{small.shape[0]} tiles, "
          f"{(small.sum(axis=2) > 0.05).mean():.0%} preenchido")
    blocks = []
    for f in MMDIR.glob("minimap1520_*.otmm"):
        m = re.match(r"minimap1520_(\d+)_(\d+)_(\d+)", f.stem)
        blocks.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), f.stat().st_mtime))
    recent = sorted(blocks, key=lambda b: -b[3])[:120]

    best = None
    for z in floors:
        if region is not None:
            X0, X1, Y0, Y1 = region
            idx, n = stitch_floor(z, X0, X1, Y0, Y1)
            if n == 0:
                continue
            big = PAL[idx].astype(float) / 255.0
            d, ox, oy = register(big, small)
            print(f"  z{z}: {n} blocos, erro {d:.4f}")
            if best is None or d < best[0]:
                best = (d, z, idx, X0, Y0, ox, oy)
            continue
        bs = [(b[0], b[1]) for b in recent if b[2] == z]
        if not bs:
            continue
        # maior aglomerado espacial (blocos recentes vem de varias areas: viagem)
        groups = []
        for bx, by in bs:
            for gp in groups:
                if any(abs(bx - qx) <= 192 and abs(by - qy) <= 192 for qx, qy in gp):
                    gp.append((bx, by))
                    break
            else:
                groups.append([(bx, by)])
        gp = max(groups, key=len)
        xs = [b[0] for b in gp]
        ys = [b[1] for b in gp]
        # o canvas precisa ser MAIOR que o mosaico, senao nem da p/ casar
        need_x = max(pad, small.shape[1] // 2 + 40)
        need_y = max(pad, small.shape[0] // 2 + 40)
        X0, X1 = min(xs) - need_x, max(xs) + 64 + need_x
        Y0, Y1 = min(ys) - need_y, max(ys) + 64 + need_y
        if (X1 - X0) * (Y1 - Y0) > 4_000_000:
            continue
        idx, n = stitch_floor(z, X0, X1, Y0, Y1)
        if n == 0:
            continue
        big = PAL[idx].astype(float) / 255.0
        d, ox, oy = register(big, small)
        print(f"  z{z}: {n} blocos, erro {d:.4f}")
        if best is None or d < best[0]:
            best = (d, z, idx, X0, Y0, ox, oy)
    if best is None:
        raise RuntimeError("sem andar candidato")
    d, z, idx, X0, Y0, ox, oy = best

    def to_abs(p):
        """posicao DR (tiles) -> tile absoluto (ponta do pin)."""
        gx = (p[0] * ZOOM - mx0 + PIN_TIP_PX[0]) / 2.0
        gy = (p[1] * ZOOM - my0 + PIN_TIP_PX[1]) / 2.0
        return (X0 + ox + gx, Y0 + oy + gy)

    return z, to_abs, idx, X0, Y0, d
