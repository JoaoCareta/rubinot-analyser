"""Desenha o cartao de AJUSTE DO RTC: a grade do RTCaster com o que mudar.

Nao e print do jogo — e um esquema com a mesma cara da tela do RTCaster, para
o ajuste ser aplicado batendo o olho. Celula alterada vem destacada com
"valor atual -> valor novo".
"""
from PIL import Image, ImageDraw, ImageFont

F = r"C:\Windows\Fonts\arialbd.ttf"
FR = r"C:\Windows\Fonts\arial.ttf"
BG = (46, 46, 46)
PANEL = (62, 62, 62)
LINHA = (90, 90, 90)
TXT = (226, 226, 226)
MUDA = (255, 205, 45)
OK = (90, 235, 130)


def _f(sz, bold=True):
    return ImageFont.truetype(F if bold else FR, sz)


def card_rtc(saida, preset, linhas, titulo, motivo, ganho, rodape=None):
    """linhas: [{spell, mana, creatures, priority, muda: {campo: novo}}]"""
    W = 1010
    top = 150
    lh = 46
    H = top + lh * len(linhas) + 245
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 56], fill=(24, 24, 28))
    d.text((22, 28), titulo, font=_f(24), fill=(255, 255, 255), anchor="lm")
    d.text((22, 82), f"Preset:  {preset}", font=_f(19), fill=TXT, anchor="lm")
    d.text((300, 82), "aplique só o que está em amarelo", font=_f(16, False), fill=MUDA, anchor="lm")

    cols = [(30, "Spell", 300), (330, "Mana %", 140), (490, "Creatures", 180),
            (690, "Priority", 150)]
    d.rectangle([20, top - 34, W - 20, top - 4], fill=PANEL)
    for x, nome, _ in cols:
        d.text((x + 8, top - 19), nome, font=_f(17), fill=(180, 180, 180), anchor="lm")

    for i, ln in enumerate(linhas):
        y = top + i * lh
        muda = ln.get("muda") or {}
        if muda:
            d.rectangle([20, y, W - 20, y + lh - 6], fill=(70, 62, 26),
                        outline=MUDA, width=2)
        else:
            d.rectangle([20, y, W - 20, y + lh - 6], fill=(54, 54, 54),
                        outline=LINHA, width=1)
        d.text((38, y + lh // 2 - 3), ln["spell"], font=_f(19),
               fill=TXT if not muda else (255, 255, 255), anchor="lm")
        for campo, x in (("mana", 338), ("creatures", 498), ("priority", 698)):
            v = str(ln[campo])
            if campo in muda:
                d.text((x, y + lh // 2 - 3), v, font=_f(19), fill=(150, 150, 150),
                       anchor="lm")
                w = d.textlength(v, font=_f(19))
                d.line([x, y + lh // 2 - 2, x + w, y + lh // 2 - 2],
                       fill=(170, 90, 90), width=2)
                d.line([x + w + 12, y + lh // 2 - 2, x + w + 30, y + lh // 2 - 2], fill=MUDA, width=3)
                d.polygon([(x + w + 34, y + lh // 2 - 2), (x + w + 25, y + lh // 2 - 8), (x + w + 25, y + lh // 2 + 4)], fill=MUDA)
                d.text((x + w + 44, y + lh // 2 - 3), str(muda[campo]), font=_f(22),
                       fill=MUDA, anchor="lm")
            else:
                d.text((x, y + lh // 2 - 3), v, font=_f(19), fill=TXT, anchor="lm")

    y0 = top + lh * len(linhas) + 22
    d.rectangle([20, y0, W - 20, y0 + 180], fill=(30, 34, 30), outline=OK, width=2)
    d.text((40, y0 + 28), "POR QUE", font=_f(18), fill=OK, anchor="lm")
    d.text((40, y0 + 60), motivo, font=_f(18, False), fill=TXT, anchor="lm")
    d.text((40, y0 + 100), "GANHO ESPERADO", font=_f(18), fill=OK, anchor="lm")
    d.text((40, y0 + 128), ganho, font=_f(19), fill=(255, 255, 255), anchor="lm")
    if rodape:
        d.text((40, y0 + 158), rodape, font=_f(16, False), fill=(170, 170, 170), anchor="lm")
    img.save(saida)
    return saida
