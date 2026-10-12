"""PADRAO DE MAPA DA HUNT (fechado com o user em 26/07).

Layout:
  ESQUERDA  andares empilhados na VERTICAL, um painel por andar
  DIREITA   painel unico com a tabela de TODAS as box, ocupando a altura inteira

Regras:
  - a numeracao da box segue a ORDEM DA VOLTA e NAO reseta por andar
    (box 1-4 no andar 1, box 5 no -1, box 6 de volta no 1 em outro ponto)
  - a cor da bolha e o rank de rendimento (verde/amarelo/vermelho)
  - cada linha da tabela mostra andar, kills, kills/min, XP e profit
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
CORES = {"verde": (60, 225, 110), "amarelo": (250, 205, 55), "vermelho": (240, 80, 70)}
PRIOR_S = 30          # suavizacao do rendimento
DWELL_MIN = 15        # abaixo disso e passagem, nao box
TW = 520              # largura do painel de informacoes


def _f(sz):
    return ImageFont.truetype(FONTE, sz)


def agrupar(kills, raio=5.0):
    """kills: [(t, x, y, xp, profit)] -> boxes daquele andar."""
    zs = []
    for t, x, y, xp, pf in kills:
        for z in zs:
            if ((x - z["x"]) ** 2 + (y - z["y"]) ** 2) ** 0.5 <= raio:
                n = z["kills"]
                z["x"] = (z["x"] * n + x) / (n + 1)
                z["y"] = (z["y"] * n + y) / (n + 1)
                z["kills"] += 1
                z["xp"] += xp
                z["profit"] += pf
                z["t0"] = min(z["t0"], t)
                break
        else:
            zs.append({"x": x, "y": y, "kills": 1, "xp": xp, "profit": pf, "t0": t})
    return [z for z in zs if z["kills"] >= 3]


def encaixar_no_chao(zs, walk, origem, piso=(1, 3, 5), raio_busca=8):
    """Puxa o centro da box para o CHAO ANDAVEL mais proximo.

    O centroide de um aglomerado pode cair em parede (kills em volta dela) e a
    bolha aparece fora de onde a party anda. Marca `fora_do_chao` quando nem
    perto existe chao: sinal de ancoragem ruim, nao de box ruim.
    """
    import numpy as _np

    AX0, AY0 = origem
    H, W = walk.shape
    for z in zs:
        cx, cy = int(round(z["x"])) - AX0, int(round(z["y"])) - AY0
        if 0 <= cx < W and 0 <= cy < H and walk[cy, cx] in piso:
            z["fora_do_chao"] = False
            continue
        melhor = None
        for dy in range(-raio_busca, raio_busca + 1):
            for dx in range(-raio_busca, raio_busca + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < W and 0 <= ny < H and walk[ny, nx] in piso:
                    d2 = dx * dx + dy * dy
                    if melhor is None or d2 < melhor[0]:
                        melhor = (d2, nx, ny)
        if melhor:
            z["x"], z["y"] = melhor[1] + AX0, melhor[2] + AY0
            z["fora_do_chao"] = False
        else:
            z["fora_do_chao"] = True
    return zs


def permanencia(zs, walked, raio=7.0):
    for z in zs:
        z["dwell_s"] = 0
    for i, (t, x, y) in enumerate(walked):
        passo = min(t - walked[i - 1][0], 10) if i else 2
        for z in zs:
            if ((x - z["x"]) ** 2 + (y - z["y"]) ** 2) ** 0.5 <= raio:
                z["dwell_s"] += passo
                break
    for z in zs:
        z["kills_min"] = round(60 * z["kills"] / (z["dwell_s"] + PRIOR_S), 2)
    return [z for z in zs if z["dwell_s"] >= DWELL_MIN]


def numerar_e_rankear(andares):
    """Numera as box pela ORDEM DA VOLTA (global) e pinta pelo rank de rendimento."""
    todas = [(z, a["z"]) for a in andares for z in a["boxes"]]
    for i, (z, _) in enumerate(sorted(todas, key=lambda p: p[0]["t0"]), 1):
        z["box"] = i
    vals = sorted(z["kills_min"] for z, _ in todas)
    if len(vals) >= 3:
        c1, c2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    else:
        c1 = c2 = None
    for z, _ in todas:
        if c1 is None:
            z["cor"] = "amarelo"
        elif z["kills_min"] >= c2:
            z["cor"] = "verde"
        elif z["kills_min"] >= c1:
            z["cor"] = "amarelo"
        else:
            z["cor"] = "vermelho"
    return todas


def painel_andar(a, escala=5):
    """Renderiza um andar: mapa + rota + bolhas numeradas."""
    from anchor_map import PAL

    color, walk = a["color"], a["walk"]
    AX0, AY0 = a["origem"]
    ys, xs = np.nonzero(walk == 1)
    if not len(ys):
        ys, xs = np.nonzero(color != 0)
    y0, y1 = max(0, ys.min() - 5), min(color.shape[0], ys.max() + 6)
    x0, x1 = max(0, xs.min() - 5), min(color.shape[1], xs.max() + 6)
    rgb = PAL[color[y0:y1, x0:x1]].astype(float) * 0.42
    w = walk[y0:y1, x0:x1]
    rgb[w == 1] = rgb[w == 1] * 0.6 + np.array([120, 120, 130]) * 0.4
    S = escala
    img = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S),
                                                       Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")

    def px(tx, ty):
        return (tx - AX0 - x0) * S, (ty - AY0 - y0) * S

    wk = a["walked"]
    for i in range(1, len(wk)):
        if wk[i][0] - wk[i - 1][0] <= 6:
            d.line([px(wk[i - 1][1], wk[i - 1][2]), px(wk[i][1], wk[i][2])],
                   fill=(255, 255, 255, 80), width=2)
    for z in sorted(a["boxes"], key=lambda z: z["kills"]):
        cor = CORES[z["cor"]]
        cx, cy = px(z["x"], z["y"])
        r = 15 + min(20, z["kills"] // 2)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor + (105,),
                  outline=(0, 0, 0, 255), width=5)
        d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], outline=cor + (255,), width=3)
        d.text((cx, cy), str(z["box"]), font=_f(20), fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=3, stroke_fill=(0, 0, 0, 255))
    for esc in a.get("escadas", []):
        cx, cy = px(*esc["px"])
        d.rectangle([cx - 13, cy - 13, cx + 13, cy + 13], outline=(120, 210, 255, 255), width=4)
        d.text((cx, cy), esc.get("dir", "↕"), font=_f(17), fill=(160, 225, 255, 255), anchor="mm")
    faixa = 34
    out = Image.new("RGB", (img.size[0], img.size[1] + faixa), (16, 16, 20))
    out.paste(img.convert("RGB"), (0, faixa))
    dd = ImageDraw.Draw(out)
    nb = len(a["boxes"])
    rot = f"ANDAR {a['z']}   ·   {nb} box" + ("" if nb == 1 else "es")
    dd.text((12, faixa // 2), rot, font=_f(19), fill=(235, 235, 235), anchor="lm")
    return out


def render(saida, andares, titulo, escala=5):
    """andares: [{'z', 'color', 'walk', 'origem', 'walked', 'kills', 'escadas'}]"""
    for a in andares:
        bx = permanencia(agrupar(a["kills"]), a["walked"])
        a["boxes"] = encaixar_no_chao(bx, a["walk"], a["origem"])
        fora = [b for b in a["boxes"] if b.get("fora_do_chao")]
        if fora:
            print(f"  AVISO andar {a['z']}: {len(fora)} box longe de chao andavel "
                  f"(suspeita de ancoragem errada)")
    todas = numerar_e_rankear(andares)

    paineis = [painel_andar(a, escala) for a in andares]
    LW = max(p.size[0] for p in paineis)
    LH = sum(p.size[1] for p in paineis) + 8 * (len(paineis) - 1)
    H = max(LH + 46, 420)
    canvas = Image.new("RGB", (LW + TW, H), (16, 16, 20))
    yy = 46
    for p in paineis:
        canvas.paste(p, (0, yy))
        yy += p.size[1] + 8
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.size[0], 40], fill=(10, 10, 14))
    d.text((14, 20), titulo, font=_f(21), fill=(255, 255, 255), anchor="lm")

    # ---- painel de informacoes: 1 ou 2 colunas, sem invadir o rodape ----
    x0t = LW + 18
    linhas = sorted((z for z, _ in todas), key=lambda z: z["box"])
    andar_de = {id(z): zz for z, zz in todas}
    topo, rod, LH_MIN = 124, 92, 20
    disp = max(60, H - topo - rod)
    n = max(1, len(linhas))
    ncols = 1 if disp // n >= LH_MIN else 2
    por_col = (n + ncols - 1) // ncols
    lh = min(60, max(14, disp // max(1, por_col)))
    fs = min(22, max(12, int(lh * 0.52)))
    colw = 500
    if ncols == 2 and canvas.size[0] < LW + 18 + colw * 2:
        nova = Image.new("RGB", (LW + 36 + colw * 2, H), (16, 16, 20))
        nova.paste(canvas, (0, 0))
        canvas = nova
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, canvas.size[0], 40], fill=(10, 10, 14))
        d.text((14, 20), titulo, font=_f(21), fill=(255, 255, 255), anchor="lm")

    d.text((x0t, 66), "BOX DA VOLTA  ·  na ordem do percurso", font=_f(19), fill=(255, 255, 255))
    cols = ((0, "box"), (52, "andar"), (130, "kills"), (208, "k/min"), (290, "XP"), (390, "profit"))
    for ci in range(ncols):
        bx = x0t + ci * colw
        for dx, t in cols:
            d.text((bx + dx, 104), t, font=_f(14), fill=(170, 170, 170), anchor="lm")
        d.line([bx, 88, bx + colw - 40, 88], fill=(110, 110, 110), width=1)

    for i, z in enumerate(linhas):
        ci, ri = i // por_col, i % por_col
        bx = x0t + ci * colw
        yy = topo + ri * lh
        cy = yy + lh // 2
        if z["box"] % 2 == 0:
            d.rectangle([bx - 2, yy, bx + colw - 40, yy + lh - 2], fill=(24, 24, 30))
        d.rectangle([bx - 10, yy + 2, bx - 4, yy + lh - 4], fill=CORES[z["cor"]])
        vals = ((0, str(z["box"])), (52, str(andar_de[id(z)])), (130, str(z["kills"])),
                (208, f"{z['kills_min']:.1f}"),
                (290, f"{z['xp'] / 1e6:.2f} kk".replace(".", ",")),
                (390, f"{z['profit'] / 1000:.0f} k"))
        for dx, t in vals:
            d.text((bx + dx, cy), t, font=_f(fs), fill=(234, 234, 234), anchor="lm")

    tk = sum(z["kills"] for z in linhas)
    tx = sum(z["xp"] for z in linhas)
    tp = sum(z["profit"] for z in linhas)
    ytot = topo + por_col * lh + 14
    largura_tab = colw * ncols - 40
    d.line([x0t, ytot, x0t + largura_tab, ytot], fill=(150, 150, 150), width=2)
    d.text((x0t, ytot + 20), "TOTAL", font=_f(14), fill=(255, 220, 90), anchor="lm")
    for dx, t in ((130, str(tk)), (290, f"{tx / 1e6:.2f} kk".replace(".", ",")),
                  (390, f"{tp / 1000:.0f} k")):
        d.text((x0t + dx, ytot + 46), t, font=_f(max(17, fs)), fill=(255, 220, 90), anchor="lm")
    canvas.save(saida)
    return saida, linhas
