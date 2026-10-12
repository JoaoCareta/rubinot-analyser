"""Anota um frame da hunt no estilo 'coach de esporte'.

Circulo no jogador no momento do erro, seta curva para onde ele deveria ter ido,
marcacoes nos grupos de bicho e um painel com os pontos a corrigir.

Uso como modulo:
    coach(frame_png, saida_png, titulo, jogador=(x,y), destino=(x,y),
          marcas=[{'px':(x,y),'r':90,'cor':'perigo','label':'...'}],
          pontos=['...','...'])
"""
import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CORES = {
    "voce": (255, 60, 60),
    "destino": (60, 230, 110),
    "perigo": (255, 140, 0),
    "box": (90, 200, 255),
}
FONTE = r"C:\Windows\Fonts\arialbd.ttf"


def _f(sz):
    return ImageFont.truetype(FONTE, sz)


def _seta_curva(d, p0, p1, cor, largura=9, curva=0.35):
    """Seta em arco (bezier quadratica) de p0 a p1."""
    (x0, y0), (x1, y1) = p0, p1
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    cx, cy = mx - dy * curva, my + dx * curva          # ponto de controle
    pts = []
    for i in range(41):
        t = i / 40
        u = 1 - t
        pts.append((u * u * x0 + 2 * u * t * cx + t * t * x1,
                    u * u * y0 + 2 * u * t * cy + t * t * y1))
    d.line(pts, fill=cor + (235,), width=largura, joint="curve")
    # ponta
    ax, ay = pts[-1]
    bx, by = pts[-6]
    ang = math.atan2(ay - by, ax - bx)
    L, W = 34, 0.42
    d.polygon([(ax, ay),
               (ax - L * math.cos(ang - W), ay - L * math.sin(ang - W)),
               (ax - L * math.cos(ang + W), ay - L * math.sin(ang + W))],
              fill=cor + (255,))


def coach(frame_png, saida, titulo, jogador, destino=None, marcas=(), pontos=(),
          viewport=None, legenda_destino="posicao correta"):
    base = Image.open(frame_png).convert("RGB")
    W, H = base.size

    # foco: escurece tudo fora do viewport
    if viewport:
        escuro = Image.new("RGB", (W, H), (0, 0, 0))
        mask = Image.new("L", (W, H), 130)
        ImageDraw.Draw(mask).rectangle(viewport, fill=0)
        base = Image.composite(escuro, base, mask)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    for m in marcas:
        cor = CORES.get(m.get("cor", "perigo"), CORES["perigo"])
        x, y = m["px"]
        r = m.get("r", 90)
        d.ellipse([x - r, y - r, x + r, y + r], outline=cor + (210,), width=6)
        if m.get("label"):
            tw = d.textlength(m["label"], font=_f(22))
            d.rectangle([x - tw / 2 - 10, y - r - 40, x + tw / 2 + 10, y - r - 8],
                        fill=(0, 0, 0, 200), outline=cor + (255,), width=2)
            d.text((x, y - r - 24), m["label"], font=_f(22), fill=cor + (255,), anchor="mm")

    if destino:
        _seta_curva(d, jogador, destino, CORES["destino"])
        x, y = destino
        d.ellipse([x - 30, y - 30, x + 30, y + 30], outline=CORES["destino"] + (255,), width=6)
        d.line([x - 14, y, x + 14, y], fill=CORES["destino"] + (255,), width=5)
        d.line([x, y - 14, x, y + 14], fill=CORES["destino"] + (255,), width=5)
        tw = d.textlength(legenda_destino, font=_f(24))
        d.rectangle([x - tw / 2 - 12, y + 36, x + tw / 2 + 12, y + 72],
                    fill=(0, 0, 0, 205), outline=CORES["destino"] + (255,), width=2)
        d.text((x, y + 54), legenda_destino, font=_f(24),
               fill=CORES["destino"] + (255,), anchor="mm")

    # circulo no jogador (por ultimo, fica por cima)
    jx, jy = jogador
    for r, w, a in ((78, 8, 255), (94, 4, 150)):
        d.ellipse([jx - r, jy - r, jx + r, jy + r], outline=CORES["voce"] + (a,), width=w)
    d.rectangle([jx - 40, jy - 116, jx + 40, jy - 84], fill=(0, 0, 0, 215),
                outline=CORES["voce"] + (255,), width=2)
    d.text((jx, jy - 100), "VOCÊ", font=_f(24), fill=CORES["voce"] + (255,), anchor="mm")

    ov = ov.filter(ImageFilter.SMOOTH)
    img = Image.alpha_composite(base.convert("RGBA"), ov)
    d = ImageDraw.Draw(img, "RGBA")

    # faixa do titulo
    d.rectangle([0, 0, W, 46], fill=(12, 12, 16, 235))
    d.text((16, 23), titulo, font=_f(26), fill=(255, 255, 255, 255), anchor="lm")

    # painel dos pontos
    if pontos:
        fp = _f(21)
        lh = 34
        ph = 52 + lh * len(pontos)
        pw = int(max(d.textlength(f"{i}. {t}", font=fp) for i, t in enumerate(pontos, 1))) + 44
        px0, py0 = 16, H - ph - 16
        d.rectangle([px0, py0, px0 + pw, py0 + ph], fill=(12, 12, 16, 228),
                    outline=(255, 210, 60, 255), width=3)
        d.text((px0 + 18, py0 + 24), "COMO CORRIGIR", font=_f(22), fill=(255, 210, 60, 255), anchor="lm")
        for i, t in enumerate(pontos, 1):
            d.text((px0 + 18, py0 + 48 + lh * i - lh // 2), f"{i}. {t}", font=fp,
                   fill=(240, 240, 240, 255), anchor="lm")

    img.convert("RGB").save(saida)
    return saida
