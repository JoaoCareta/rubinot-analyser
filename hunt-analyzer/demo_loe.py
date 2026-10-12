"""Exemplo do mapa padrao aplicado a Livraria de Energy.

Base = minimapa REAL da Livraria, extraido dos clipes do user (dois andares,
capturados no momento em que a party trocou de nivel). As box e os numeros sao
ILUSTRATIVOS — servem para mostrar o formato; os reais saem da hunt ao vivo.
"""
from PIL import Image, ImageDraw, ImageFont

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
CORES = {"verde": (60, 225, 110), "amarelo": (250, 205, 55), "vermelho": (240, 80, 70)}
TW = 520


def _f(s):
    return ImageFont.truetype(FONTE, s)


def painel(mini_png, z, boxes, escadas, rota, escala=3):
    base = Image.open(mini_png).convert("RGB")
    img = base.resize((base.size[0] * escala, base.size[1] * escala), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")
    if len(rota) > 1:
        d.line([(x * escala, y * escala) for x, y in rota], fill=(255, 255, 255, 105), width=3)
    for e in escadas:
        cx, cy = e["px"][0] * escala, e["px"][1] * escala
        d.rectangle([cx - 13, cy - 13, cx + 13, cy + 13], outline=(120, 210, 255, 255), width=4)
        d.text((cx, cy), e["dir"], font=_f(16), fill=(170, 228, 255, 255), anchor="mm")
    for b in sorted(boxes, key=lambda b: b["kills"]):
        cor = CORES[b["cor"]]
        cx, cy = b["px"][0] * escala, b["px"][1] * escala
        r = 15 + min(20, b["kills"] // 2)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor + (105,), outline=(0, 0, 0, 255), width=5)
        d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=cor + (255,), width=3)
        d.text((cx, cy), str(b["box"]), font=_f(20), fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=3, stroke_fill=(0, 0, 0, 255))
    faixa = 34
    out = Image.new("RGB", (img.size[0], img.size[1] + faixa), (16, 16, 20))
    out.paste(img.convert("RGB"), (0, faixa))
    dd = ImageDraw.Draw(out)
    n = len(boxes)
    dd.text((12, faixa // 2), f"ANDAR {z}   ·   {n} box" + ("" if n == 1 else "es"),
            font=_f(19), fill=(235, 235, 235), anchor="lm")
    return out


def render(saida, andares, titulo, nota):
    paineis = [painel(a["mini"], a["z"], a["boxes"], a["escadas"], a["rota"]) for a in andares]
    LW = max(p.size[0] for p in paineis)
    LH = sum(p.size[1] for p in paineis) + 8 * (len(paineis) - 1)
    H = max(LH + 46 + 30, 480)
    canvas = Image.new("RGB", (LW + TW, H), (16, 16, 20))
    yy = 46
    for p in paineis:
        canvas.paste(p, (0, yy))
        yy += p.size[1] + 8
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.size[0], 40], fill=(10, 10, 14))
    d.text((14, 20), titulo, font=_f(21), fill=(255, 255, 255), anchor="lm")
    d.text((14, H - 16), nota, font=_f(14), fill=(150, 150, 150), anchor="lm")

    todas = sorted((b for a in andares for b in a["boxes"]), key=lambda b: b["box"])
    andar_de = {b["box"]: a["z"] for a in andares for b in a["boxes"]}
    x0t = LW + 18
    d.text((x0t, 66), "BOX DA VOLTA  ·  na ordem do percurso", font=_f(19), fill=(255, 255, 255))
    for dx, t in ((0, "box"), (58, "andar"), (140, "kills"), (222, "k/min"), (310, "XP"), (410, "profit")):
        d.text((x0t + dx, 104), t, font=_f(14), fill=(170, 170, 170), anchor="lm")
    d.line([x0t, 88, x0t + TW - 36, 88], fill=(110, 110, 110), width=1)
    topo, rod = 124, 86
    lh = min(60, max(26, (H - topo - rod) // max(1, len(todas))))
    fs = min(22, max(14, int(lh * 0.5)))
    yy = topo
    for b in todas:
        cy = yy + lh // 2
        if b["box"] % 2 == 0:
            d.rectangle([x0t - 2, yy, x0t + TW - 36, yy + lh - 2], fill=(24, 24, 30))
        d.rectangle([x0t - 10, yy + 2, x0t - 4, yy + lh - 4], fill=CORES[b["cor"]])
        for dx, t in ((0, str(b["box"])), (58, str(andar_de[b["box"]])), (140, str(b["kills"])),
                      (222, f"{b['kmin']:.1f}"), (310, f"{b['xp']:.2f} kk".replace(".", ",")),
                      (410, f"{b['profit']} k")):
            d.text((x0t + dx, cy), t, font=_f(fs), fill=(234, 234, 234), anchor="lm")
        yy += lh
    tk = sum(b["kills"] for b in todas)
    tx = sum(b["xp"] for b in todas)
    tp = sum(b["profit"] for b in todas)
    d.line([x0t, H - rod + 10, x0t + TW - 36, H - rod + 10], fill=(150, 150, 150), width=2)
    d.text((x0t, H - rod + 30), "TOTAL", font=_f(14), fill=(255, 220, 90), anchor="lm")
    for dx, t in ((140, str(tk)), (310, f"{tx:.2f} kk".replace(".", ",")), (410, f"{tp} k")):
        d.text((x0t + dx, H - rod + 56), t, font=_f(max(17, fs)), fill=(255, 220, 90), anchor="lm")
    canvas.save(saida)
    return saida
