"""MAPA DA VOLTA — PADRAO FECHADO (user, 27/07). Sai nas voltas multiplas de 5.

ESQUERDA: mapa da cave + caminho comum (linha grossa colorida pela velocidade,
setas de sentido) + ZONAS de box em bolhas; legenda em faixa PROPRIA embaixo
(dentro do mapa ela tapava o mapa e o texto vazava da caixa).
DIREITA: rank por profit, com bichos por VOLTA (media, nao total), XP raw e
profit por regiao. XP abaixo de 1 kk vai em k: 741 k, nunca 0,74 kk.

As 37 box individuais viram ~12 zonas (juntando o que esta a <=10 tiles), senao
o mapa fica ilegivel.

Uso: python mapa_volta.py capture\\session_X ingol [saida.png]
"""
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am
import caminho_comum as cc
import mapa_ingol as mi

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
RAIO_ZONA = 10          # tiles: junta box vizinhas na mesma zona
MIN_KILLS = 15          # zona com menos que isso nao entra
TW = 620                # largura do painel da direita
CORES = {"verde": (60, 225, 110), "amarelo": (250, 205, 55), "vermelho": (240, 80, 70)}


def F(s):
    return ImageFont.truetype(FONTE, s)


def xp_fmt(v):
    """Abaixo de 1 kk mostra em k (740 k, nao 0,74 kk) — pedido do user 27/07."""
    if v < 1_000_000:
        return f"{v / 1000:.0f} k"
    return f"{v / 1e6:.2f} kk".replace(".", ",")


def zonas(boxes, xp_total=0, profit_total=0):
    zs = []
    for b in sorted(boxes, key=lambda b: -b["kills"]):
        for z in zs:
            if math.hypot(b["x"] - z["x"], b["y"] - z["y"]) <= RAIO_ZONA:
                k = z["kills"] + b["kills"]
                z["x"] = (z["x"] * z["kills"] + b["x"] * b["kills"]) / k
                z["y"] = (z["y"] * z["kills"] + b["y"] * b["kills"]) / k
                z["kills"] = k
                z["dwell"] += b["dwell_s"]
                z["dano"] += b["dano"]
                z["voltas"] = max(z["voltas"], b["voltas"])
                break
        else:
            zs.append({"x": b["x"], "y": b["y"], "kills": b["kills"], "voltas": b["voltas"],
                       "dwell": b["dwell_s"], "dano": b["dano"], "trecho": b["trecho"]})
    zs = [z for z in zs if z["kills"] >= MIN_KILLS]
    tk = sum(z["kills"] for z in zs) or 1
    for z in zs:
        z["kills_min"] = 60 * z["kills"] / max(1, z["dwell"])
        z["hp_bicho"] = z["dano"] / max(1, z["kills"])
        z["bichos_volta"] = z["kills"] / max(1, z["voltas"])
        # XP e profit da regiao: rateio por bichos (o painel so da o valor da VOLTA)
        z["xp"] = xp_total * z["kills"] / tk
        z["profit"] = profit_total * z["kills"] / tk
    zs.sort(key=lambda z: -z["profit"])
    vals = sorted(z["profit"] for z in zs)
    c1, c2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    for i, z in enumerate(zs, 1):
        z["rank"] = i
        z["cor"] = "verde" if z["profit"] >= c2 else ("amarelo" if z["profit"] >= c1 else "vermelho")
    return zs


def render(pontos, zs, saida, titulo, vmed, profit_total):
    color, walk = mi.planos()
    xs = [p["x"] - mi.X0 for p in pontos] + [z["x"] - mi.X0 for z in zs]
    ys = [p["y"] - mi.Y0 for p in pontos] + [z["y"] - mi.Y0 for z in zs]
    x0, x1 = int(min(xs)) - 12, int(max(xs)) + 12
    y0, y1 = int(min(ys)) - 12, int(max(ys)) + 12
    rgb = am.PAL[color[y0:y1, x0:x1]].astype(float) * 0.34
    w = walk[y0:y1, x0:x1]
    rgb[w == 1] = rgb[w == 1] * 0.55 + np.array([120, 120, 130]) * 0.45
    S = 10
    mapa = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    dr = ImageDraw.Draw(mapa, "RGBA")

    def px(tx, ty):
        return ((tx - mi.X0 - x0) * S + S // 2, (ty - mi.Y0 - y0) * S + S // 2)

    vs = [p["vel"] for p in pontos]
    vmin, vmax = float(np.percentile(vs, 10)), float(np.percentile(vs, 90))
    n = len(pontos)
    for i in range(n):
        a, b = pontos[i], pontos[(i + 1) % n]
        cor = cc.cor_velocidade((a["vel"] + b["vel"]) / 2, vmin, vmax)
        dr.line([px(a["x"], a["y"]), px(b["x"], b["y"])], fill=cor + (255,), width=12)
    for i in range(0, n, 10):
        a = pontos[i]
        m = math.hypot(a["dx"], a["dy"])
        if m < 0.5:
            continue
        vx, vy = a["dx"] / m, a["dy"] / m
        cx, cy = px(a["x"], a["y"])
        L = 18
        dr.polygon([(cx + vx * L, cy + vy * L),
                    (cx - vx * L * 0.5 - vy * L * 0.6, cy - vy * L * 0.5 + vx * L * 0.6),
                    (cx - vx * L * 0.5 + vy * L * 0.6, cy - vy * L * 0.5 - vx * L * 0.6)],
                   fill=(255, 255, 255, 245), outline=(0, 0, 0, 255))
    for z in sorted(zs, key=lambda z: z["kills"]):
        cor = CORES[z["cor"]]
        cx, cy = px(z["x"], z["y"])
        r = 17 + min(22, int(z["bichos_volta"]) * 3)
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor + (110,), outline=(0, 0, 0, 255), width=5)
        dr.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=cor + (255,), width=3)
        dr.text((cx, cy), f"{z['bichos_volta']:.1f}", font=F(20), fill=(255, 255, 255, 255), anchor="mm",
                stroke_width=3, stroke_fill=(0, 0, 0, 255))
        dr.text((cx, cy + r + 11), f"#{z['rank']}", font=F(16), fill=cor + (255,), anchor="mm",
                stroke_width=3, stroke_fill=(0, 0, 0, 255))
    TOP, LEG = 92, 152
    canvas = Image.new("RGB", (mapa.size[0] + TW, max(mapa.size[1] + TOP + LEG, 700)), (16, 16, 20))
    canvas.paste(mapa.convert("RGB"), (0, TOP))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.size[0], TOP - 10], fill=(10, 10, 14))
    d.text((16, 30), titulo, font=F(25), fill=(255, 255, 255))
    d.text((16, 62), f"passo mediano {vmed:.1f} tiles/s · zonas juntam box a menos de "
                     f"{RAIO_ZONA} tiles · numero na bolha = bichos por volta (media)",
           font=F(17), fill=(195, 195, 195))

    xt = mapa.size[0] + 18
    d.text((xt, 108), "ZONAS  ·  rank por profit", font=F(20), fill=(255, 255, 255))
    cols = ((0, "#"), (46, "bichos/volta"), (186, "XP raw"), (296, "profit"), (398, "trecho"))
    for dx, t in cols:
        d.text((xt + dx, 142), t, font=F(15), fill=(170, 170, 170), anchor="lm")
    d.line([xt, 156, xt + TW - 40, 156], fill=(110, 110, 110), width=1)
    lh2 = min(40, max(22, (canvas.size[1] - 300) // max(1, len(zs))))
    for i, z in enumerate(zs):
        yy = 168 + i * lh2
        if i % 2 == 0:
            d.rectangle([xt - 4, yy, xt + TW - 40, yy + lh2 - 3], fill=(24, 24, 30))
        d.rectangle([xt - 10, yy + 3, xt - 5, yy + lh2 - 6], fill=CORES[z["cor"]])
        cy = yy + lh2 // 2
        for dx, t in ((0, f"#{z['rank']}"), (46, f"{z['bichos_volta']:.1f}"),
                      (186, xp_fmt(z["xp"])),
                      (296, f"{z['profit'] / 1000:.0f} k"), (398, z["trecho"])):
            d.text((xt + dx, cy), t, font=F(17), fill=(234, 234, 234), anchor="lm")
    tk = sum(z["kills"] for z in zs)
    tbv = sum(z["bichos_volta"] for z in zs)
    txp = sum(z["xp"] for z in zs)
    tpf = sum(z["profit"] for z in zs)
    yt = 168 + len(zs) * lh2 + 10
    d.line([xt, yt, xt + TW - 40, yt], fill=(150, 150, 150), width=2)
    cy = yt + 26
    for dx, t in ((0, "TOT"), (46, f"{tbv:.1f}"), (186, xp_fmt(txp)),
                  (296, f"{tpf / 1000:.0f} k"), (398, f"{len(zs)} zonas")):
        d.text((xt + dx, cy), t, font=F(17), fill=(255, 220, 90), anchor="lm")
    d.text((xt, cy + 30), f"{tk} bichos na sessao · XP e profit rateados por bichos",
           font=F(15), fill=(165, 165, 165), anchor="lm")
    # legenda numa faixa propria embaixo do mapa
    ly = TOP + mapa.size[1] + 12
    itens = [((150, 190, 255), "linha grossa = caminho comum (cor = seu passo)"),
             ((255, 255, 255), "seta = sentido que voce anda"),
             ((255, 255, 255), "numero na bolha = bichos por VOLTA (media)"),
             (CORES["verde"], "zona verde = mais profit"),
             (CORES["amarelo"], "zona amarela = profit medio"),
             (CORES["vermelho"], "zona vermelha = menos profit")]
    fl = F(17)
    # largura da coluna pelo TEXTO mais longo (com 3 colunas fixas o item 1 invadia o 2)
    larg = max(d.textlength(t, font=fl) for _, t in itens) + 52
    ncols = max(1, min(3, int((mapa.size[0] - 60) // larg)))
    colw = int(larg)
    nlin = -(-len(itens) // ncols)
    d.rectangle([12, ly, min(mapa.size[0] - 12, 30 + ncols * colw + 12), ly + 28 * nlin + 16],
                fill=(10, 10, 14), outline=(90, 90, 100), width=2)
    for i, (cor, txt) in enumerate(itens):
        cxx = 30 + (i % ncols) * colw
        cyy = ly + 22 + (i // ncols) * 28
        d.ellipse([cxx, cyy - 8, cxx + 16, cyy + 8], fill=cor, outline=(0, 0, 0), width=2)
        d.text((cxx + 26, cyy), txt, font=fl, fill=(230, 230, 230), anchor="lm")
    canvas.save(saida)
    return saida


def main():
    import area_hunt
    session = pathlib.Path(sys.argv[1])
    hunt = sys.argv[2] if len(sys.argv) > 2 else "ingol"
    area_hunt.aplicar(hunt)
    saida = sys.argv[3] if len(sys.argv) > 3 else f"reports/mapa_volta_{hunt}.png"
    base = pathlib.Path("hunt_data") / hunt
    pontos = json.loads((base / "caminho_comum.json").read_text(encoding="utf-8"))
    boxes = json.loads(next(base.glob("boxes_*.json")).read_text(encoding="utf-8"))
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # delta de painel negativo = analyser resetado no meio da volta — descartar
    laps = [L for L in laps if (L.get("xp_raw_painel") or 0) >= 0]
    profit = sum((L.get("profit") or 0) for L in laps)
    xp = sum((L.get("xp_raw_painel") or 0) for L in laps)
    zs = zonas(boxes, xp, profit)
    print(f"{len(boxes)} box -> {len(zs)} zonas")
    print(render(pontos["pontos"], zs, saida,
                 f"MAPA DA VOLTA · {hunt.upper()} z{mi.Z} · caminho comum e zonas de box",
                 pontos["passo_mediano"], profit))


if __name__ == "__main__":
    main()
