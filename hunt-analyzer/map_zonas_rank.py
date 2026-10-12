"""Mapa da hunt com as ZONAS DE BOX coloridas pelo rank (verde/amarelo/vermelho).

- linha branca = por onde a party andou
- cada zona = aglomerado de kills, pintada pelo rendimento (kills por minuto
  parado nela): tercil de cima verde, meio amarelo, de baixo vermelho
- numero dentro da bolha = kills; abaixo, kills/min

Generico: recebe os arrays de cor/walk do andar (qualquer hunt) e a trajetoria.
"""
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
CORES = {"verde": (60, 225, 110), "amarelo": (250, 205, 55), "vermelho": (240, 80, 70)}


def _f(sz):
    return ImageFont.truetype(FONTE, sz)


def agrupar_zonas(kills_pos, raio=5.0):
    """kills_pos: [(x, y)] ou [(x, y, xp, profit)] -> zonas com kills/xp/profit."""
    zonas = []
    for k in kills_pos:
        x, y = k[0], k[1]
        xp = k[2] if len(k) > 2 else 0
        pf = k[3] if len(k) > 3 else 0
        for z in zonas:
            if ((x - z["x"]) ** 2 + (y - z["y"]) ** 2) ** 0.5 <= raio:
                n = z["kills"]
                z["x"] = (z["x"] * n + x) / (n + 1)
                z["y"] = (z["y"] * n + y) / (n + 1)
                z["kills"] += 1
                z["xp"] += xp
                z["profit"] += pf
                break
        else:
            zonas.append({"x": x, "y": y, "kills": 1, "xp": xp, "profit": pf})
    return [z for z in zonas if z["kills"] >= 3]


def permanencia(zonas, walked, raio=7.0, passo_max=10):
    """Segundos que a party passou dentro de cada zona (para o rendimento)."""
    for z in zonas:
        z["dwell_s"] = 0
    for i, (t, x, y) in enumerate(walked):
        passo = min(t - walked[i - 1][0], passo_max) if i else 2
        for z in zonas:
            if ((x - z["x"]) ** 2 + (y - z["y"]) ** 2) ** 0.5 <= raio:
                z["dwell_s"] += passo
                break
    # suavizacao: zona onde a pt so passou (2-5s) daria taxa absurda. O termo
    # PRIOR_S no denominador puxa amostra pequena para a media ate ela crescer.
    PRIOR_S = 30
    for z in zonas:
        dw = z.get("dwell_s", 0)
        z["kills_min"] = round(60 * z["kills"] / (dw + PRIOR_S), 2)
        z["passagem"] = dw < 15      # pouco tempo: nao e zona de box, e transito
    return zonas


def rankear(zonas):
    """Tercis de rendimento -> cor. Empate/sem dwell cai no amarelo."""
    vals = sorted(z["kills_min"] for z in zonas if z["kills_min"] > 0)
    if len(vals) >= 3:
        c1 = vals[len(vals) // 3]
        c2 = vals[2 * len(vals) // 3]
    else:
        c1 = c2 = None
    for i, z in enumerate(sorted(zonas, key=lambda z: -z["kills_min"]), 1):
        z["rank"] = i
        if c1 is None or z["kills_min"] == 0:
            z["cor"] = "amarelo"
        elif z["kills_min"] >= c2:
            z["cor"] = "verde"
        elif z["kills_min"] >= c1:
            z["cor"] = "amarelo"
        else:
            z["cor"] = "vermelho"
    return zonas


def render(saida, color_arr, walk_arr, origem, walked, kills_pos, titulo, escala=6):
    """origem: (X0, Y0) do canto dos arrays. walked: [(t,x,y)]. kills_pos: [(x,y)]."""
    from anchor_map import PAL

    AX0, AY0 = origem
    zonas = permanencia(agrupar_zonas(kills_pos), walked)
    zonas = rankear([z for z in zonas if not z.get("passagem")])

    ys, xs = np.nonzero(walk_arr == 1)
    if not len(ys):
        ys, xs = np.nonzero(color_arr != 0)
    y0, y1 = max(0, ys.min() - 6), min(color_arr.shape[0], ys.max() + 7)
    x0, x1 = max(0, xs.min() - 6), min(color_arr.shape[1], xs.max() + 7)
    c = color_arr[y0:y1, x0:x1]
    w = walk_arr[y0:y1, x0:x1]
    rgb = PAL[c].astype(float) * 0.42
    rgb[w == 1] = rgb[w == 1] * 0.6 + np.array([120, 120, 130]) * 0.4
    S = escala
    img = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S),
                                                       Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")

    def px(tx, ty):
        return (tx - AX0 - x0) * S, (ty - AY0 - y0) * S

    for i in range(1, len(walked)):
        if walked[i][0] - walked[i - 1][0] <= 6:
            d.line([px(walked[i - 1][1], walked[i - 1][2]), px(walked[i][1], walked[i][2])],
                   fill=(255, 255, 255, 75), width=2)

    for z in sorted(zonas, key=lambda z: z["kills"]):
        cor = CORES[z["cor"]]
        cx, cy = px(z["x"], z["y"])
        r = 12 + min(26, z["kills"])
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor + (95,),
                  outline=(0, 0, 0, 255), width=5)
        d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=cor + (255,), width=3)
        d.text((cx, cy - 4), str(z["kills"]), font=_f(20), fill=(255, 255, 255, 255),
               anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, 255))
        d.text((cx, cy + r - 2), f"#{z['rank']}", font=_f(13), fill=(255, 255, 255, 210),
               anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, 255))

    if walked:
        cx, cy = px(walked[-1][1], walked[-1][2])
        d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(80, 200, 255, 235),
                  outline=(0, 0, 0, 255), width=3)

    W = img.size[0]
    d.rectangle([0, 0, W, 44], fill=(12, 12, 16, 235))
    d.text((16, 22), titulo, font=_f(21), fill=(255, 255, 255, 255), anchor="lm")
    lx, ly = 12, 56
    d.rectangle([lx, ly, lx + 292, ly + 152], fill=(12, 12, 16, 225),
                outline=(200, 200, 210, 255), width=2)
    itens = [
        ((255, 255, 255), "linha", "por onde a pt andou"),
        (CORES["verde"], "zona", "melhor rendimento"),
        (CORES["amarelo"], "zona", "rendimento médio"),
        (CORES["vermelho"], "zona", "pior rendimento"),
        ((80, 200, 255), "ponto", "posição atual"),
    ]
    yy = ly + 24
    for cor, _tipo, txt in itens:
        d.ellipse([lx + 18, yy - 8, lx + 34, yy + 8], fill=cor + (140,), outline=cor + (255,), width=2)
        d.text((lx + 46, yy), txt, font=_f(15), fill=(232, 232, 232, 255), anchor="lm")
        yy += 28
    # ---- painel lateral: ocupa a ALTURA INTEIRA da imagem ----
    TW = 500
    linhas_tab = sorted(zonas, key=lambda z: z["rank"])
    H = img.size[1]
    canvas = Image.new("RGB", (img.size[0] + TW, H), (16, 16, 20))
    canvas.paste(img.convert("RGB"), (0, 0))
    dt = ImageDraw.Draw(canvas)
    x0t = img.size[0] + 16

    topo_rows = 96          # abaixo do titulo + cabecalho de coluna
    rodape = 78             # espaco do total
    disp = max(60, H - topo_rows - rodape)
    n = max(1, len(linhas_tab))
    lh = min(64, max(22, disp // n))
    fs = min(23, max(14, int(lh * 0.52)))

    dt.text((x0t, 30), "ZONAS  ·  rank por kills/min", font=_f(20), fill=(255, 255, 255))
    for x, t in ((x0t, "#"), (x0t + 56, "kills"), (x0t + 148, "kills/min"),
                 (x0t + 268, "XP"), (x0t + 380, "profit")):
        dt.text((x, 74), t, font=_f(15), fill=(170, 170, 170), anchor="lm")
    dt.line([x0t, 58, x0t + TW - 32, 58], fill=(110, 110, 110), width=1)

    yy = topo_rows
    for z in linhas_tab:
        cor = CORES[z["cor"]]
        cy = yy + lh // 2
        dt.rectangle([x0t - 9, yy + 2, x0t - 3, yy + lh - 4], fill=cor)
        if (z["rank"] % 2) == 0:
            dt.rectangle([x0t - 1, yy, x0t + TW - 32, yy + lh - 2], fill=(24, 24, 30))
        for x, t in ((x0t, f"#{z['rank']}"), (x0t + 56, str(z["kills"])),
                     (x0t + 148, f"{z['kills_min']:.1f}"),
                     (x0t + 268, f"{z.get('xp', 0) / 1e6:.2f} kk".replace(".", ",")),
                     (x0t + 380, f"{z.get('profit', 0) / 1000:.0f} k")):
            dt.text((x, cy), t, font=_f(fs), fill=(234, 234, 234), anchor="lm")
        yy += lh

    tot_k = sum(z["kills"] for z in zonas)
    tot_x = sum(z.get("xp", 0) for z in zonas)
    tot_p = sum(z.get("profit", 0) for z in zonas)
    dt.line([x0t, H - rodape + 8, x0t + TW - 32, H - rodape + 8],
            fill=(150, 150, 150), width=2)
    dt.text((x0t, H - rodape + 24), "TOTAL", font=_f(14), fill=(255, 220, 90), anchor="lm")
    for x, t in ((x0t + 56, str(tot_k)),
                 (x0t + 268, f"{tot_x / 1e6:.2f} kk".replace(".", ",")),
                 (x0t + 380, f"{tot_p / 1000:.0f} k")):
        dt.text((x, H - rodape + 48), t, font=_f(max(16, fs)), fill=(255, 220, 90), anchor="lm")
    canvas.save(saida)
    return saida, zonas
