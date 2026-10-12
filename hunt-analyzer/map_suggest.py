"""Mapa da rota SUGERIDA: mesmo circuito, tempo realocado pelo rendimento medido.

Regras derivadas dos dados do dia (zonas_rendimento.json):
- sentido INVERTIDO (anti-horario rendeu +33% XP/h na manha)
- tempo por zona proporcional ao rendimento (kills/min parado)
- zonas fracas viram passagem, nao parada
Caminho desenhado por BFS no chao andavel (walk == 1).
"""
import collections
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am

AX0, AY0 = 33240, 31220
S = 6


def bfs_path(walk, a, b, limit=400):
    """Menor caminho em tiles andaveis entre a e b (coords absolutas)."""
    start = (a[0] - AX0, a[1] - AY0)
    goal = (b[0] - AX0, b[1] - AY0)
    H, W = walk.shape
    prev = {start: None}
    q = collections.deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cur[0] + dx, cur[1] + dy
            if not (0 <= nx < W and 0 <= ny < H) or (nx, ny) in prev:
                continue
            if walk[ny, nx] != 1:
                continue
            prev[(nx, ny)] = cur
            q.append((nx, ny))
    if goal not in prev:
        return None
    out, cur = [], goal
    while cur:
        out.append((cur[0] + AX0, cur[1] + AY0))
        cur = prev[cur]
    return out[::-1] if len(out) <= limit else None


def main(out_png):
    zonas = {k: tuple(v) for k, v in json.load(open("zonas_falcon_z9_v3.json")).items()}
    rend = json.load(open("zonas_rendimento.json"))  # zona -> [kills/min, kills, dwell]
    color = np.load("falcon_z9_color.npy")
    walk = np.load("falcon_z9_walk.npy")

    ys, xs = np.nonzero(walk == 1)
    y0, y1 = max(0, ys.min() - 6), min(walk.shape[0], ys.max() + 7)
    x0, x1 = max(0, xs.min() - 6), min(walk.shape[1], xs.max() + 7)
    c = color[y0:y1, x0:x1]
    w = walk[y0:y1, x0:x1]
    rgb = am.PAL[c].astype(float) * 0.45
    rgb[w == 1] = rgb[w == 1] * 0.6 + np.array([120, 120, 130]) * 0.4
    img = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")
    F = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 26)
    Fs = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 16)
    Ft = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 13)

    def px(tx, ty):
        return (tx - AX0 - x0) * S, (ty - AY0 - y0) * S

    # sentido invertido do atual (A->H->G->F->E->D->C->B->A)
    ordem = ["A", "H", "G", "F", "E", "D", "C", "B"]
    # tempo sugerido: 8s base + peso pelo rendimento (kills/min), teto 16s
    kpm = {z: rend[z][0] for z in zonas}
    lo, hi = min(kpm.values()), max(kpm.values())
    seg = [int(round(5 + 12 * (kpm[z] - lo) / (hi - lo))) for z in ordem]

    for i, zl in enumerate(ordem):
        nxt = ordem[(i + 1) % len(ordem)]
        path = bfs_path(walk, zonas[zl], zonas[nxt])
        if not path:
            d.line([px(*zonas[zl]), px(*zonas[nxt])], fill=(255, 220, 60, 110), width=3)
            continue
        pts = [px(x, y) for x, y in path]
        d.line(pts, fill=(255, 210, 40, 210), width=6)
        # seta no meio do trecho
        mid = pts[len(pts) // 2]
        nxtp = pts[min(len(pts) - 1, len(pts) // 2 + 4)]
        vx, vy = nxtp[0] - mid[0], nxtp[1] - mid[1]
        n = (vx * vx + vy * vy) ** 0.5 or 1
        vx, vy = vx / n * 13, vy / n * 13
        d.polygon([(mid[0] + vx, mid[1] + vy),
                   (mid[0] - vy * 0.5 - vx * 0.3, mid[1] + vx * 0.5 - vy * 0.3),
                   (mid[0] + vy * 0.5 - vx * 0.3, mid[1] - vx * 0.5 - vy * 0.3)],
                  fill=(255, 255, 255, 235))

    for i, zl in enumerate(ordem):
        zx, zy = zonas[zl]
        cx, cy = px(zx, zy)
        r = 12 + seg[i]
        forte = kpm[zl] >= 4.5
        fill = (60, 230, 110, 130) if forte else (150, 150, 160, 110)
        outline = (90, 255, 130, 255) if forte else (200, 200, 210, 220)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=(0, 0, 0, 255), width=5)
        d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=outline, width=3)
        d.text((cx, cy - 6), zl, font=F, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=3, stroke_fill=(0, 0, 0, 255))
        d.text((cx, cy + 13), f"{seg[i]}s", font=Ft, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0, 255))
        d.text((cx, cy + r + 12), f"{kpm[zl]:.1f}/min", font=Ft, fill=outline, anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0, 255))

    lx, ly, lw2, lh = 10, 10, 350, 196
    d.rectangle([lx, ly, lx + lw2, ly + lh], fill=(10, 10, 14, 225),
                outline=(255, 220, 60, 255), width=2)
    d.text((lx + 12, ly + 8), "ROTA SUGERIDA (dados de hoje)", font=Fs, fill=(255, 220, 60, 255))
    yy = ly + 36
    for txt, col in (
        ("sentido INVERTIDO do atual (+33% XP/h)", (255, 235, 140, 255)),
        ("verde = zona forte, fique mais", (120, 255, 150, 255)),
        ("cinza = zona fraca, so passe", (210, 210, 215, 255)),
        ("Ns = segundos sugeridos na zona", (230, 230, 230, 255)),
        ("x.x/min = kills por minuto medido", (230, 230, 230, 255)),
        ("lure alvo: 6 (nao 9-14)", (255, 160, 90, 255)),
    ):
        d.text((lx + 16, yy), txt, font=Ft, fill=col)
        yy += 22
    total = sum(seg)
    d.text((lx + 16, yy + 2), f"volta sugerida: ~{total}s de parada + transito",
           font=Ft, fill=(255, 220, 60, 255))
    img.save(out_png)
    print(f"mapa sugerido: {out_png} | ordem {'->'.join(ordem)} | tempos {seg}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reports/mapa_sugerido.png")
