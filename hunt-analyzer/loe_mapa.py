"""Mapa de zonas da Livraria (formato fechado): paineis por andar empilhados +
tabela lateral. Bolha por zona (cluster das boxes dos laps), cor = tercil do
rendimento bayesiano 60*kills/(dwell+30), numero = ordem da 1a visita.

Uso: python loe_mapa.py capture\\session_20260728_072106 reports\\mapa_loe.png
"""
import json
import os
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from anchor_map import PAL
from lap_watch import to_s

# 18/09: generalizado por hunt (HUNT_PREFIX=fogo, FATOR_BICHOS=8280, HUNT_TITULO=...)
PREFIX = os.environ.get("HUNT_PREFIX", "loe")
FATOR = float(os.environ.get("FATOR_BICHOS", 6386))
TITULO = os.environ.get("HUNT_TITULO", "Library of Energy · pt x4 · zonas por rendimento")

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
CORES = {"verde": (60, 225, 110), "amarelo": (250, 205, 55), "vermelho": (240, 80, 70)}
ESC = 4
TW = 430
PISO = 1
CLUSTER_TILES = 8
MIN_DWELL = 15


def _f(s):
    return ImageFont.truetype(FONTE, s)


def carrega(session):
    orig = json.load(open(f"{PREFIX}_origem.json"))
    pts = [json.loads(l) for l in (session / f"{PREFIX}_track.jsonl").read_text(encoding="utf-8").splitlines()]
    pts.sort(key=lambda p: p["t"])
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8-sig").splitlines()
            if l.strip()]
    boxes = []
    for L in laps:
        for b in L.get("boxes_detalhe", []):
            tm = (to_s(b["inicio"]) + to_s(b["fim"])) / 2
            perto = min(pts, key=lambda p: abs(p["t"] - tm))
            if abs(perto["t"] - tm) > 45:
                continue
            boxes.append({"t": tm, "z": perto["z"], "x": perto["x"], "y": perto["y"],
                          "kills": b["kills"], "dur": b["dur_s"]})
    # totais reais da hunt: raw somado das voltas; bichos = raw/fator;
    # profit medido do painel Party Hunt (delta 07:21->08:57 da sessao 28/07)
    raw = sum(L["xp_raw_painel"] for L in laps if L.get("xp_raw_painel"))
    # profit = delta do Balance do painel Party Hunt entre a 1a e a ultima volta
    import atlas_build as ab
    import pt_card
    glyphs, gap = ab.load_atlas()
    # soma por volta (volta com base de preco trocada = None, fica de fora)
    profit = sum(v for v in (pt_card.volta(session, glyphs, gap, L)["balance_atual"] for L in laps) if v)
    tot = {"raw": raw, "profit": profit, "bichos": round(raw / FATOR)}
    # corta o transito de saida (volta fechada por tempo maximo = reset/fim)
    t_max = max((to_s(L["fim"]) for L in laps
                 if "tempo maximo" not in L.get("fechada_por", "")), default=None)
    if t_max:
        pts = [p for p in pts if p["t"] <= t_max]
        boxes = [b for b in boxes if b["t"] <= t_max]
    return orig, pts, boxes, tot


def zonas_de(boxes, walks, orig):
    zonas = []
    for b in sorted(boxes, key=lambda b: b["t"]):
        for zn in zonas:
            if zn["z"] == b["z"] and abs(zn["x"] - b["x"]) <= CLUSTER_TILES \
                    and abs(zn["y"] - b["y"]) <= CLUSTER_TILES:
                n = zn["n"] + 1
                zn["x"] = (zn["x"] * zn["n"] + b["x"]) / n
                zn["y"] = (zn["y"] * zn["n"] + b["y"]) / n
                zn["n"] = n
                zn["kills"] += b["kills"]
                zn["dwell"] += b["dur"]
                break
        else:
            zonas.append({"z": b["z"], "x": b["x"], "y": b["y"], "n": 1,
                          "kills": b["kills"], "dwell": b["dur"]})
    zonas = [z for z in zonas if z["dwell"] >= MIN_DWELL]
    for i, z in enumerate(zonas):
        z["num"] = i + 1
        z["rend"] = 60.0 * z["kills"] / (z["dwell"] + 30)
        # encaixar no chao andavel
        w = walks[z["z"]]
        cx, cy = int(z["x"] - orig["X0"]), int(z["y"] - orig["Y0"])
        if w[cy, cx] != PISO:
            cands = [(abs(dx) + abs(dy), dx, dy) for dx in range(-8, 9) for dy in range(-8, 9)
                     if 0 <= cy + dy < w.shape[0] and 0 <= cx + dx < w.shape[1]
                     and w[cy + dy, cx + dx] == PISO]
            if cands:
                _, dx, dy = min(cands)
                z["x"] += dx
                z["y"] += dy
    rends = sorted(z["rend"] for z in zonas)
    if rends:
        t1 = rends[len(rends) // 3]
        t2 = rends[2 * len(rends) // 3]
        for z in zonas:
            z["cor"] = "vermelho" if z["rend"] <= t1 else ("amarelo" if z["rend"] <= t2 else "verde")
    return zonas


def painel(z, color, orig, pts, zonas, bbox, atual):
    x0, x1, y0, y1 = bbox
    idx = color[y0 - orig["Y0"]:y1 - orig["Y0"], x0 - orig["X0"]:x1 - orig["X0"]]
    img = Image.fromarray(PAL[idx]).resize(((x1 - x0) * ESC, (y1 - y0) * ESC), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")

    def px(p):
        return ((p["x"] - x0) * ESC, (p["y"] - y0) * ESC)

    meus = [p for p in pts if p["z"] == z]
    for a, b in zip(meus, meus[1:]):
        if b["t"] - a["t"] <= 6:
            d.line([px(a), px(b)], fill=(255, 255, 255, 130), width=2)
    # escadas: transicoes de andar
    for a, b in zip(pts, pts[1:]):
        if a["z"] != b["z"] and b["t"] - a["t"] <= 8:
            p = a if a["z"] == z else b
            cx, cy = px(p)
            d.rectangle([cx - 9, cy - 9, cx + 9, cy + 9], outline=(120, 210, 255, 255), width=3)
    for zn in [zn for zn in zonas if zn["z"] == z]:
        cor = CORES[zn["cor"]]
        cx, cy = px(zn)
        r = 14 + min(22, zn["kills"])
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor + (100,), outline=(0, 0, 0, 255), width=4)
        d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=cor + (255,), width=2)
        d.text((cx, cy - 6), str(zn["num"]), font=_f(20), fill=(255, 255, 255),
               anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
        d.text((cx, cy + 11), f"{zn.get('bichos_est', zn['kills'])}", font=_f(12),
               fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
    if atual and atual["z"] == z:
        cx, cy = px(atual)
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(70, 140, 255, 255),
                  outline=(255, 255, 255, 255), width=2)
    faixa = 34
    out = Image.new("RGB", (img.size[0], img.size[1] + faixa), (16, 16, 20))
    out.paste(img, (0, faixa))
    dd = ImageDraw.Draw(out)
    n = sum(1 for zn in zonas if zn["z"] == z)
    dd.text((12, faixa // 2), f"ANDAR z{z}   ·   {n} zona" + ("" if n == 1 else "s"),
            font=_f(19), fill=(235, 235, 235), anchor="lm")
    return out


def main():
    session = pathlib.Path(sys.argv[1])
    saida = sys.argv[2] if len(sys.argv) > 2 else r"reports\mapa_loe.png"
    orig, pts, boxes, tot = carrega(session)
    zs = tuple(orig.get("zs", (12, 13)))
    walks = {z: np.load(f"{PREFIX}_z{z}_walk.npy") for z in zs}
    colors = {z: np.load(f"{PREFIX}_z{z}_color.npy") for z in zs}
    zonas = zonas_de(boxes, walks, orig)
    atual = pts[-1] if pts else None
    # escala real dos cards: rateia bichos/XP/profit da hunt pelo share de kills
    kchat = sum(z["kills"] for z in zonas) or 1
    for z in zonas:
        share = z["kills"] / kchat
        z["bichos_est"] = round(tot["bichos"] * share)
        z["xp"] = tot["raw"] * share
        z["profit"] = tot["profit"] * share

    paineis = []
    for z in zs:
        meus = [p for p in pts if p["z"] == z]
        if not meus:
            continue
        xs = [p["x"] for p in meus]
        ys = [p["y"] for p in meus]
        bbox = (int(min(xs)) - 10, int(max(xs)) + 11, int(min(ys)) - 10, int(max(ys)) + 11)
        paineis.append(painel(z, colors[z], orig, pts, zonas, bbox, atual))

    LW = max(p.size[0] for p in paineis)
    LH = sum(p.size[1] for p in paineis) + 8 * (len(paineis) - 1)
    H = max(LH + 56, 480)
    canvas = Image.new("RGB", (LW + TW, H), (16, 16, 20))
    yy = 46
    for p in paineis:
        canvas.paste(p, (0, yy))
        yy += p.size[1] + 8
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.size[0], 40], fill=(10, 10, 14))
    d.text((14, 20), TITULO, font=_f(21),
           fill=(255, 255, 255), anchor="lm")

    def kk(v):
        return f"{v / 1_000_000:.2f}".replace(".", ",") + " kk"

    x0t = LW + 16
    d.text((x0t, 60), "ZONAS · ordem do percurso", font=_f(18), fill=(255, 255, 255))
    for dx, t in ((0, "zona"), (74, "bichos"), (168, "XP raw"), (290, "profit")):
        d.text((x0t + dx, 96), t, font=_f(14), fill=(170, 170, 170), anchor="lm")
    d.line([x0t, 84, x0t + TW - 30, 84], fill=(110, 110, 110), width=1)
    topo, rod = 112, 82
    lh = min(46, max(22, (H - topo - rod) // max(1, len(zonas))))
    fs = min(20, max(13, int(lh * 0.55)))
    yy = topo
    for zn in zonas:
        cy = yy + lh // 2
        if zn["num"] % 2 == 0:
            d.rectangle([x0t - 2, yy, x0t + TW - 30, yy + lh - 2], fill=(24, 24, 30))
        d.rectangle([x0t - 10, yy + 2, x0t - 4, yy + lh - 4], fill=CORES[zn["cor"]])
        for dx, t in ((0, str(zn["num"])), (74, str(zn["bichos_est"])),
                      (168, kk(zn["xp"])), (290, f"{zn['profit'] / 1000:,.0f}k")):
            d.text((x0t + dx, cy), t, font=_f(fs), fill=(234, 234, 234), anchor="lm")
        yy += lh
    d.line([x0t, H - rod + 8, x0t + TW - 30, H - rod + 8], fill=(150, 150, 150), width=2)
    d.text((x0t, H - rod + 26), "TOTAL", font=_f(14), fill=(255, 220, 90), anchor="lm")
    for dx, t in ((74, str(sum(z["bichos_est"] for z in zonas))),
                  (168, kk(sum(z["xp"] for z in zonas))),
                  (290, f"{sum(z['profit'] for z in zonas) / 1000:,.0f}k")):
        d.text((x0t + dx, H - rod + 50), t, font=_f(max(16, fs)), fill=(255, 220, 90), anchor="lm")
    canvas.save(saida)
    print("mapa salvo:", saida, canvas.size)


if __name__ == "__main__":
    main()
