"""Desenha o mapa da hunt: mosaico das vistas do Map View + spots ranqueados.

O fundo e construido colando cada recorte do Map View na posicao rastreada
(dead reckoning), entao fica no MESMO referencial dos spots — nao depende de
casar com o .otmm (que falha em cave escura).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import atlas_build as ab
import lap_watch as lw
import session_map as sm
from pin_detect import MAP_CROP, PIN_TIP_PX

ZOOM = 2.0
S = 2  # px de saida por px de minimapa
PIN_BOX = (38, 66, 62, 92)  # regiao do pin no crop — nao colar (senao mancha o mapa)


def main():
    session = pathlib.Path(sys.argv[1])
    t0 = lw.to_s(sys.argv[2]) if len(sys.argv) > 2 else 0
    out_png = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else \
        pathlib.Path(r"D:\Documentos\rubinot\hunt-analyzer\reports\mapa_boxes.png")

    t_fim = lw.to_s(sys.argv[4]) if len(sys.argv) > 4 else None
    pts = sm.build_path(session, t0)
    if t_fim:  # recorta a janela (1 volta = pouca deriva, mapa nitido)
        pts = pts[pts[:, 0] <= t_fim]
    laps = sm.find_laps(pts)
    pts = sm.close_loops(pts, laps)
    stops = sm.find_stops(pts)
    evs = [json.loads(l) for l in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    for s in stops:
        s["kills"] = sum(1 for e in evs if e["kind"] == "xp_gain" and s["t0"] <= lw.to_s(e["ts"]) <= s["t1"] + 6)
        s["xp"] = sum(e["value"] for e in evs if e["kind"] == "xp_gain" and s["t0"] <= lw.to_s(e["ts"]) <= s["t1"] + 6)
        s["dur"] = s["t1"] - s["t0"]

    spots = []
    for p in stops:
        for s in spots:
            if float(np.hypot(*(s["pos"] - p["pos"]))) <= sm.SPOT_RADIUS:
                s["stops"].append(p)
                s["pos"] = np.mean([q["pos"] for q in s["stops"]], axis=0)
                break
        else:
            spots.append({"id": len(spots) + 1, "pos": p["pos"], "stops": [p]})

    # lure medio ate cada spot
    order = sorted(stops, key=lambda q: q["t0"])
    for a, b in zip(order, order[1:]):
        gap = b["t0"] - a["t1"]
        if 0 < gap <= 240:
            b["lure"] = gap
    for s in spots:
        lures = [q.get("lure") for q in s["stops"] if q.get("lure")]
        s["lure"] = float(np.mean(lures)) if lures else 0.0
        s["kills"] = sum(q["kills"] for q in s["stops"])
        s["xp"] = sum(q["xp"] for q in s["stops"])
        ciclo = sum(q["dur"] + (q.get("lure") or 0) for q in s["stops"])
        s["xpm"] = s["xp"] / (ciclo / 60) if ciclo else 0.0
        s["visitas"] = len(s["stops"])

    # --- fundo: mosaico das vistas ---
    px = pts[:, 1:] * ZOOM  # tiles -> px do minimapa
    cw, ch = MAP_CROP[2] - MAP_CROP[0], MAP_CROP[3] - MAP_CROP[1]
    x0, x1 = px[:, 0].min() - cw, px[:, 0].max() + cw
    y0, y1 = px[:, 1].min() - ch, px[:, 1].max() + ch
    W, H = int(x1 - x0), int(y1 - y0)
    acc = np.zeros((H, W, 3), dtype=np.uint8)

    frames = [f for f in sorted(session.glob("f_*.png"))
              if lw.fsec(f.name) >= t0 and (t_fim is None or lw.fsec(f.name) <= t_fim)]
    tmap = {int(t): (X, Y) for t, X, Y in pts}
    used = 0
    for f in frames:
        t = lw.fsec(f.name)
        if t not in tmap:
            continue
        X, Y = tmap[t]
        ox = int(round(X * ZOOM - x0))
        oy = int(round(Y * ZOOM - y0))
        if not (0 <= ox < W - cw and 0 <= oy < H - ch):
            continue
        img = np.asarray(Image.open(f).convert("RGB").crop(MAP_CROP))
        block = acc[oy : oy + ch, ox : ox + cw]
        mask = (img.sum(axis=2) > 30) & (block.sum(axis=2) == 0)
        mask[PIN_BOX[1] : PIN_BOX[3], PIN_BOX[0] : PIN_BOX[2]] = False
        block[mask] = img[mask]
        used += 1
    print(f"mosaico de {used} vistas: {W}x{H}px")

    img = Image.fromarray(acc).resize((W * S, H * S), Image.NEAREST).convert("RGB")
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr_ = ImageDraw.Draw(ov)
    try:
        font = ImageFont.truetype("arialbd.ttf", 26)
        fs = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = fs = ImageFont.load_default()

    def cv(p):
        return ((p[0] * ZOOM - x0) * S + PIN_TIP_PX[0] * S, (p[1] * ZOOM - y0) * S + PIN_TIP_PX[1] * S)

    # trajeto
    path = [cv(p) for p in pts[:, 1:]]
    dr_.line(path, fill=(90, 200, 255, 150), width=3, joint="curve")

    xpms = [s["xpm"] for s in spots if s["xpm"] > 0]
    hi = np.percentile(xpms, 70) if xpms else 1
    lo = np.percentile(xpms, 30) if xpms else 0
    for s in spots:
        x, y = cv(s["pos"])
        r = (9 + 2.6 * s["kills"] ** 0.62) * S
        if s["kills"] == 0:
            col = (150, 150, 150)
        elif s["xpm"] >= hi:
            col = (46, 204, 113)
        elif s["xpm"] <= lo:
            col = (231, 76, 60)
        else:
            col = (241, 196, 15)
        dr_.ellipse([x - r, y - r, x + r, y + r], fill=col + (90,), outline=col + (240,), width=3)

    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d2 = ImageDraw.Draw(img)
    for s in spots:
        x, y = cv(s["pos"])
        d2.text((x - 13, y - 15), f"S{s['id']}", fill=(255, 255, 255), font=font,
                stroke_width=3, stroke_fill=(0, 0, 0))
        lbl = f"{s['kills']}k · {s['xpm']/1000:.0f}k/min · lure {s['lure']:.0f}s"
        d2.text((x - 58, y + 16), lbl, fill=(255, 255, 255), font=fs, stroke_width=3, stroke_fill=(0, 0, 0))

    LEG = 190
    fin = Image.new("RGB", (max(img.width, 900), img.height + LEG), (18, 18, 18))
    fin.paste(img, ((fin.width - img.width) // 2, 0))
    d3 = ImageDraw.Draw(fin)
    yb = img.height + 12
    for i, (c, t) in enumerate([
        ((46, 204, 113), "VERDE = compensa puxar (XP/min de ciclo no topo)"),
        ((241, 196, 15), "AMARELO = mediano"),
        ((231, 76, 60), "VERMELHO = nao compensa (lure caro pro que rende)"),
        ((150, 150, 150), "CINZA = zero kills (reposicao/travessia)"),
    ]):
        d3.ellipse([14, yb + i * 30 + 4, 34, yb + i * 30 + 24], fill=c)
        d3.text((46, yb + i * 30 + 5), t, fill=(230, 230, 230), font=fs)
    d3.text((14, yb + 4 * 30 + 6),
            "tamanho do circulo = kills acumulados | linha azul = trajeto | rotulo: kills - XP/min de ciclo - lure medio",
            fill=(150, 210, 255), font=fs)
    out_png.parent.mkdir(exist_ok=True)
    fin.save(out_png)
    print(out_png)


if __name__ == "__main__":
    main()
