"""Coach em DOIS paineis (formato fechado com o user em 27/07).

  ESQUERDA  so a area do player (recorte apertado do viewport, jogador circulado)
  DIREITA   o mapa da cave (caminho comum) com um pino em QUAL lugar e aquele

Uso (biblioteca):
    coach_2p.render(session, t, "titulo", ["dica 1", "dica 2"], destino_png,
                    seta_para=(dx_tiles, dy_tiles))   # opcional: para onde ir
"""
import json
import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am
import caminho_comum as cc
import lap_watch as lw
import mapa_ingol as mi

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
JOGADOR = (955, 435)      # posicao do personagem na janela (camera travada)
TILE_PX = 62              # px por tile no viewport
RAIO_TILES = (5.5, 4.2)   # quantos tiles mostrar em volta dele
CEL = (900, 720)


def F(s):
    return ImageFont.truetype(FONTE, s)


def _painel_player(session, t, seta_para=None, cor=(255, 70, 70)):
    fs = sorted(session.glob("f_*.png"))
    f = min(fs, key=lambda p: abs(lw.fsec(p.name) - t))
    im = Image.open(f).convert("RGB")
    dx, dy = int(RAIO_TILES[0] * TILE_PX), int(RAIO_TILES[1] * TILE_PX)
    box = (JOGADOR[0] - dx, JOGADOR[1] - dy, JOGADOR[0] + dx, JOGADOR[1] + dy)
    vp = im.crop(box)
    d = ImageDraw.Draw(vp, "RGBA")
    jx, jy = dx, dy
    for r, w, a in (int(TILE_PX * 0.95), 7, 255), (int(TILE_PX * 1.2), 4, 130):
        d.ellipse([jx - r, jy - r, jx + r, jy + r], outline=cor + (a,), width=w)
    d.rectangle([jx - 44, jy - int(TILE_PX * 1.2) - 40, jx + 44, jy - int(TILE_PX * 1.2) - 6],
                fill=(0, 0, 0, 225), outline=cor + (255,), width=3)
    d.text((jx, jy - int(TILE_PX * 1.2) - 23), "VOCE", font=F(26), fill=cor + (255,), anchor="mm")
    if seta_para:
        tx, ty = jx + seta_para[0] * TILE_PX, jy + seta_para[1] * TILE_PX
        d.line([jx, jy, tx, ty], fill=(60, 235, 110, 235), width=9)
        d.ellipse([tx - 26, ty - 26, tx + 26, ty + 26], outline=(60, 235, 110, 255), width=7)
        d.line([tx - 13, ty, tx + 13, ty], fill=(60, 235, 110, 255), width=6)
        d.line([tx, ty - 13, tx, ty + 13], fill=(60, 235, 110, 255), width=6)
    return vp, lw.fsec(f.name)


def _painel_mapa(xy, titulo):
    dados = json.loads(pathlib.Path("hunt_data/ingol/caminho_comum.json").read_text(encoding="utf-8"))
    pts = dados["pontos"]
    color, walk = mi.planos()
    xs = [p["x"] - mi.X0 for p in pts]
    ys = [p["y"] - mi.Y0 for p in pts]
    x0, x1 = int(min(xs)) - 10, int(max(xs)) + 10
    y0, y1 = int(min(ys)) - 10, int(max(ys)) + 10
    rgb = am.PAL[color[y0:y1, x0:x1]].astype(float) * 0.34
    w = walk[y0:y1, x0:x1]
    rgb[w == 1] = rgb[w == 1] * 0.55 + np.array([120, 120, 130]) * 0.45
    S = 7
    img = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    dr = ImageDraw.Draw(img, "RGBA")

    def px(tx, ty):
        return ((tx - mi.X0 - x0) * S + S // 2, (ty - mi.Y0 - y0) * S + S // 2)

    vs = [p["vel"] for p in pts]
    vmin, vmax = float(np.percentile(vs, 10)), float(np.percentile(vs, 90))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        cor = cc.cor_velocidade((a["vel"] + b["vel"]) / 2, vmin, vmax)
        dr.line([px(a["x"], a["y"]), px(b["x"], b["y"])], fill=cor + (255,), width=8)
    for i in range(0, len(pts), 15):
        a = pts[i]
        m = math.hypot(a["dx"], a["dy"])
        if m < 0.5:
            continue
        vx, vy = a["dx"] / m, a["dy"] / m
        cx, cy = px(a["x"], a["y"])
        L = 13
        dr.polygon([(cx + vx * L, cy + vy * L),
                    (cx - vx * L * 0.5 - vy * L * 0.6, cy - vy * L * 0.5 + vx * L * 0.6),
                    (cx - vx * L * 0.5 + vy * L * 0.6, cy - vy * L * 0.5 - vx * L * 0.6)],
                   fill=(255, 255, 255, 240), outline=(0, 0, 0, 255))
    cx, cy = px(*xy)
    for r, wid in ((30, 7), (46, 4)):
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 70, 70, 255), width=wid)
    dr.line([cx - 60, cy, cx - 34, cy], fill=(255, 70, 70, 255), width=6)
    tw = dr.textlength(titulo, font=F(20))
    bx = min(max(cx - tw / 2 - 10, 4), img.size[0] - tw - 24)
    dr.rectangle([bx, cy + 52, bx + tw + 20, cy + 88], fill=(0, 0, 0, 225), outline=(255, 70, 70, 255), width=3)
    dr.text((bx + 10, cy + 70), titulo, font=F(20), fill=(255, 140, 130, 255), anchor="lm")
    return img


def render(session, t, titulo, dicas, destino, seta_para=None, xy=None, rotulo_local="voce estava aqui"):
    session = pathlib.Path(session)
    esq, t_frame = _painel_player(session, t, seta_para)
    if xy is None:
        W = json.loads((session / "walked_live.json").read_text())
        i = int(np.argmin([abs(w[0] - t) for w in W]))
        xy = (W[i][1], W[i][2])
    dir_ = _painel_mapa(xy, rotulo_local)

    CAB, PE = 74, 40 + 34 * len(dicas)
    alt = max(esq.size[1] * CEL[0] // esq.size[0], dir_.size[1] * CEL[0] // dir_.size[0])
    canvas = Image.new("RGB", (CEL[0] * 2 + 12, alt + CAB + PE), (16, 16, 20))
    for i, im in enumerate((esq, dir_)):
        esc = min(CEL[0] / im.size[0], alt / im.size[1])
        im2 = im.convert("RGB").resize((int(im.size[0] * esc), int(im.size[1] * esc)), Image.LANCZOS)
        canvas.paste(im2, (i * (CEL[0] + 12) + (CEL[0] - im2.size[0]) // 2, CAB + (alt - im2.size[1]) // 2))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.size[0], CAB - 8], fill=(12, 12, 16))
    d.text((16, (CAB - 8) // 2), titulo, font=F(26), fill=(255, 255, 255), anchor="lm")
    yy = CAB + alt + 22
    for i, t_ in enumerate(dicas, 1):
        d.text((16, yy), f"{i}. {t_}", font=F(20),
               fill=(255, 190, 120) if i == 1 else (150, 255, 190))
        yy += 34
    canvas.save(destino)
    return destino


if __name__ == "__main__":
    import sys
    print(render(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4:6], sys.argv[6]))
