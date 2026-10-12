"""Trajetoria por dead reckoning: soma o deslocamento entre frames consecutivos.

Funciona em minimapa escuro/pouco explorado (onde casar contra o mosaico falha),
porque frames vizinhos (4s) tem enorme sobreposicao. A saida e RELATIVA ao ponto
inicial — o suficiente para saber se o jogador voltou ao ponto de partida.
"""
import pathlib

import numpy as np
from PIL import Image

from pin_detect import MAP_CROP

ZOOM = 2.0       # 26/07 11:45+: Map View em "adaptacao" = 2px/tile paleta classica
                 # (NCC 0.972; o modo HD puro de 11:35-11:44 era 4px/tile)
MAX_SHIFT = 34   # px entre frames (lane m_ a 1s: corrida ~15px)
MIN_TEX = 0.004  # variancia minima: mapa liso demais nao da shift confiavel


def crop_gray(png):
    img = Image.open(png).convert("L")
    if pathlib.Path(png).name.startswith("m_"):
        return np.asarray(img, dtype=float) / 255.0  # lane m_ ja vem recortada
    return np.asarray(img.crop(MAP_CROP), dtype=float) / 255.0


def shift_between(a, b, maxs=MAX_SHIFT):
    """Deslocamento (dx, dy) que leva 'a' em 'b', em px. None se pouco confiavel."""
    m = maxs + 2
    core = a[m:-m, m:-m]
    if core.var() < MIN_TEX:
        return None
    best = (9e9, 0, 0)
    second = 9e9
    for dy in range(-maxs, maxs + 1, 2):
        for dx in range(-maxs, maxs + 1, 2):
            w = b[m + dy : b.shape[0] - m + dy, m + dx : b.shape[1] - m + dx]
            d = float(((core - w) ** 2).mean())
            if d < best[0]:
                second = best[0]
                best = (d, dx, dy)
            elif d < second:
                second = d
    _, bx, by = best
    for dy in range(by - 1, by + 2):
        for dx in range(bx - 1, bx + 2):
            if abs(dx) > maxs or abs(dy) > maxs:
                continue
            w = b[m + dy : b.shape[0] - m + dy, m + dx : b.shape[1] - m + dx]
            d = float(((core - w) ** 2).mean())
            if d < best[0]:
                best = (d, dx, dy)
    d, dx, dy = best
    if d > 0.02 or second < d * 1.15:  # ruim ou ambiguo
        return None
    return dx, dy


def refine_with_mosaic(frames_and_pos, crop_wh, max_corr=14.0):
    """2a passada (SLAM simples): alinha cada frame ao mosaico ja acumulado.

    Corrige a deriva do dead reckoning — sem isso a mesma area aparece repetida
    deslocada. Usa phase correlation (FFT), rapido e subpixel.

    frames_and_pos: [(png, x_tiles, y_tiles)] em ordem temporal
    devolve: [(png, x_corrigido, y_corrigido)]
    """
    import cv2

    cw, ch = crop_wh
    xs = [p[1] for p in frames_and_pos]
    ys = [p[2] for p in frames_and_pos]
    x0 = min(xs) * ZOOM - cw
    y0 = min(ys) * ZOOM - ch
    W = int((max(xs) - min(xs)) * ZOOM + 3 * cw)
    H = int((max(ys) - min(ys)) * ZOOM + 3 * ch)
    mos = np.zeros((H, W), dtype=float)
    filled = np.zeros((H, W), dtype=bool)
    win = cv2.createHanningWindow((cw, ch), cv2.CV_64F)

    out = []
    acc = np.zeros(2)  # correcao acumulada (tiles)
    for png, x, y in frames_and_pos:
        cur = crop_gray(png)
        gx, gy = (x + acc[0]) * ZOOM - x0, (y + acc[1]) * ZOOM - y0
        ox, oy = int(round(gx)), int(round(gy))
        if 0 <= ox < W - cw and 0 <= oy < H - ch:
            patch = mos[oy : oy + ch, ox : ox + cw]
            cov = filled[oy : oy + ch, ox : ox + cw].mean()
            if cov > 0.55:
                (dx, dy), resp = cv2.phaseCorrelate(patch.copy(), cur.copy(), win)
                if resp > 0.10 and abs(dx) < max_corr * ZOOM and abs(dy) < max_corr * ZOOM:
                    # dx>0: 'cur' esta deslocado p/ direita em relacao ao mosaico
                    acc -= np.array([dx, dy]) / ZOOM
                    gx, gy = (x + acc[0]) * ZOOM - x0, (y + acc[1]) * ZOOM - y0
                    ox, oy = int(round(gx)), int(round(gy))
            if 0 <= ox < W - cw and 0 <= oy < H - ch:
                blk = mos[oy : oy + ch, ox : ox + cw]
                msk = (cur > 0.12) & ~filled[oy : oy + ch, ox : ox + cw]
                blk[msk] = cur[msk]
                filled[oy : oy + ch, ox : ox + cw] |= msk
        out.append((png, x + acc[0], y + acc[1]))
    return out


class Tracker:
    """Acumula posicao relativa (em tiles) a partir de frames sequenciais."""

    def __init__(self):
        self.prev = None
        self.pos = np.zeros(2)  # tiles, relativo ao inicio
        self.ok = 0
        self.lost = 0

    def update(self, frame_png):
        try:
            cur = crop_gray(frame_png)
        except OSError:
            return None
        if self.prev is None:
            self.prev = cur
            return tuple(self.pos)
        s = shift_between(self.prev, cur)
        self.prev = cur
        if s is None:
            self.lost += 1
            return None
        # mapa desloca +dx quando o jogador anda -dx
        self.pos = self.pos - np.array(s, dtype=float) / ZOOM
        self.ok += 1
        return tuple(self.pos)
