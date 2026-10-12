"""Mapa ao vivo da sessao: trajetoria registrada + clusters de kills + zonas.

Uso: python map_live.py capture\\session_X saida.png [X0 X1 Y0 Y1 z]
Cache incremental em <session>/walked_live.json (so registra frames novos).
"""
import collections
import json
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am
import atlas_build as ab
import events_build as ev

from pin_detect import PIN_TIP_PX as PIN_TIP  # lane m_ = MAP_CROP, ponta do pin (55,84)
ZOOM = 2


def to_s(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def fsec(name):
    return int(name[2:4]) * 3600 + int(name[4:6]) * 60 + int(name[6:8])


def walked_update(session, X0, X1, Y0, Y1, z):
    cache = session / "walked_live.json"
    walked = json.loads(cache.read_text()) if cache.exists() else []
    last_t = walked[-1][0] if walked else 0
    idx, _ = am.stitch_floor(z, X0, X1, Y0, Y1)
    bigs = cv2.resize(am.PAL[idx].astype(np.float32) / 255.0, None,
                      fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)
    for f in sorted(session.glob("m_*.png"))[::2]:
        t = fsec(f.name)
        if t <= last_t:
            continue
        try:
            crop = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32) / 255.0
        except OSError:
            continue
        res = cv2.matchTemplate(bigs, crop, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        if score < 0.90:
            continue
        walked.append((t, X0 + (loc[0] + PIN_TIP[0]) / ZOOM, Y0 + (loc[1] + PIN_TIP[1]) / ZOOM))
    cache.write_text(json.dumps(walked))
    return walked


def kill_times(session, t0=0, t1=10 ** 9):
    """Sinais unificados de kill direto das lanes (xp > loot > ouro), ±3s.

    t0/t1 limitam a varredura a uma janela: decodificar a sessao inteira a cada
    mapa ficou caro depois de 15 voltas (4400 frames de chat).
    """
    glyphs, gap = ab.load_atlas()
    prev, out = [], []
    for f in [f for f in sorted(session.glob("c_*.png")) if t0 <= fsec(f.name) <= t1]:
        cur = ev.frame_messages(f, glyphs, gap)
        if not cur:
            continue
        for ts, body in ev.new_tail(prev, cur):
            kind, d = ev.classify(body)
            if kind == "xp_gain" or kind == "loot" or (
                    kind == "looted" and "gold" in d.get("what", "")):
                t = to_s(ts)
                if all(abs(t - u) > 3 for u in out[-6:]):
                    out.append(t)
        prev = cur
    return out


def render(session, out_png, region):
    X0, X1, Y0, Y1, z = region
    walked = walked_update(session, X0, X1, Y0, Y1, z)
    kills = kill_times(session)
    wt = np.array([w[0] for w in walked])
    pos = []
    for t in kills:
        i = int(np.argmin(np.abs(wt - t)))
        if abs(wt[i] - t) <= 12:
            pos.append((walked[i][1], walked[i][2]))
    clusters = []
    for x, y in pos:
        for cl in clusters:
            cx = sum(p[0] for p in cl) / len(cl)
            cy = sum(p[1] for p in cl) / len(cl)
            if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= 4:
                cl.append((x, y))
                break
        else:
            clusters.append([(x, y)])
    clusters = [c for c in clusters if len(c) >= 3]

    color = np.load("falcon_z9_color.npy")
    walk = np.load("falcon_z9_walk.npy")
    AX0, AY0 = 33240, 31220
    ys, xs = np.nonzero(walk == 1)
    y0, y1 = max(0, ys.min() - 6), min(walk.shape[0], ys.max() + 7)
    x0, x1 = max(0, xs.min() - 6), min(walk.shape[1], xs.max() + 7)
    c = color[y0:y1, x0:x1]
    w = walk[y0:y1, x0:x1]
    rgb = am.PAL[c].astype(float) * 0.45
    rgb[w == 1] = rgb[w == 1] * 0.6 + np.array([120, 120, 130]) * 0.4
    S = 6
    img = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")
    F = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 28)
    Fs = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 16)

    def px(tx, ty):
        return (tx - AX0 - x0) * S, (ty - AY0 - y0) * S

    for i in range(1, len(walked)):
        if walked[i][0] - walked[i - 1][0] <= 6:
            d.line([px(walked[i - 1][1], walked[i - 1][2]), px(walked[i][1], walked[i][2])],
                   fill=(255, 255, 255, 55), width=2)
    for cl in sorted(clusters, key=len, reverse=True):
        n = len(cl)
        x = sum(p[0] for p in cl) / n
        y = sum(p[1] for p in cl) / n
        cx, cy = px(x, y)
        r = 8 + min(24, n)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 90, 30, 115),
                  outline=(255, 210, 70, 240), width=3)
        d.text((cx, cy), str(n), font=Fs, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=2, stroke_fill=(60, 20, 0, 255))
    zonas = {k: tuple(v) for k, v in json.load(open("zonas_falcon_z9_v3.json")).items()}
    for zl, (zx, zy) in zonas.items():
        cx, cy = px(zx, zy)
        d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], outline=(90, 220, 255, 160), width=3)
        d.text((cx, cy), zl, font=Fs, fill=(120, 230, 255, 190), anchor="mm")
    if walked:
        cx, cy = px(walked[-1][1], walked[-1][2])
        d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(60, 255, 90, 230),
                  outline=(0, 0, 0, 255), width=3)

    lx, ly, lw2, lh = 10, 10, 330, 168
    d.rectangle([lx, ly, lx + lw2, ly + lh], fill=(10, 10, 14, 220),
                outline=(200, 200, 210, 255), width=2)
    d.text((lx + 12, ly + 8), "FALCON z9 - MAPA AO VIVO", font=Fs, fill=(255, 255, 255, 255))
    yy = ly + 36
    d.line([lx + 16, yy + 8, lx + 46, yy + 8], fill=(255, 255, 255, 190), width=2)
    d.text((lx + 56, yy + 8), "sua rota na sessao", font=Fs, fill=(230, 230, 230, 255), anchor="lm")
    yy += 26
    d.ellipse([lx + 22, yy - 2, lx + 40, yy + 16], fill=(255, 90, 30, 150),
              outline=(255, 210, 70, 255), width=2)
    d.text((lx + 31, yy + 7), "9", font=Fs, fill=(255, 255, 255, 255), anchor="mm")
    d.text((lx + 56, yy + 8), "kills no aglomerado", font=Fs, fill=(230, 230, 230, 255), anchor="lm")
    yy += 26
    d.ellipse([lx + 22, yy - 2, lx + 40, yy + 16], outline=(90, 220, 255, 220), width=3)
    d.text((lx + 31, yy + 7), "A", font=Fs, fill=(120, 230, 255, 255), anchor="mm")
    d.text((lx + 56, yy + 8), "zonas na ordem da volta (A->H)", font=Fs, fill=(230, 230, 230, 255), anchor="lm")
    yy += 26
    d.ellipse([lx + 24, yy + 1, lx + 38, yy + 15], fill=(60, 255, 90, 230), outline=(0, 0, 0, 255), width=2)
    d.text((lx + 56, yy + 8), "voce agora", font=Fs, fill=(230, 230, 230, 255), anchor="lm")
    yy += 26
    d.rectangle([lx + 24, yy + 2, lx + 38, yy + 13], fill=(114, 114, 124, 255))
    d.text((lx + 56, yy + 8), "chao andavel; escuro = parede", font=Fs, fill=(230, 230, 230, 255), anchor="lm")
    img.save(out_png)
    print(f"mapa: {out_png} | {len(walked)} pts | {len(pos)}/{len(kills)} kills | {len(clusters)} clusters")


if __name__ == "__main__":
    session = pathlib.Path(sys.argv[1])
    out = sys.argv[2]
    region = tuple(map(int, sys.argv[3:8])) if len(sys.argv) > 3 else (33200, 33470, 31180, 31450, 9)
    render(session, out, region)
