"""Um grid 2x2 POR BOX (formato fechado com o user em 27/07).

  [1] print do jogo em que o erro comeca      [2] print do meio do caminho
  [3] print dentro da box (travado)           [4] mapa com a correcao

Os prints saem dos frames f_ (a cada 4s), recortados no viewport e com o
jogador circulado — a camera do cliente centraliza o personagem, entao a posicao
dele na tela e fixa.

Uso: python grid_box_frames.py capture\\session_X reports\\boxes_travadas
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import lap_watch as lw

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
VIEWPORT = (503, 103, 1430, 793)     # area do jogo na janela (layout Hetero)
JOGADOR = (955, 435)                 # o personagem na janela (camera travada nele)
CEL = (900, 700)                     # celula do grid
CAB = 62
VERMELHO, AMARELO, VERDE = (255, 70, 70), (255, 205, 60), (60, 235, 110)


def F(s):
    return ImageFont.truetype(FONTE, s)


def frame_mais_perto(session, t):
    fs = sorted(session.glob("f_*.png"))
    if not fs:
        return None
    f = min(fs, key=lambda p: abs(lw.fsec(p.name) - t))
    return f if abs(lw.fsec(f.name) - t) <= 6 else None


def painel_print(session, t, n, titulo, cor, historia=None):
    f = frame_mais_perto(session, t)
    cel = Image.new("RGB", CEL, (20, 20, 26))
    d = ImageDraw.Draw(cel)
    d.rectangle([0, 0, CEL[0], CAB - 6], fill=(12, 12, 16))
    d.text((14, 20), f"{n}  ·  {lw.fmt(t)}  ·  {titulo}", font=F(22), fill=cor)
    if f is None:
        d.text((CEL[0] // 2, CEL[1] // 2), "sem frame nesse instante", font=F(22),
               fill=(200, 200, 200), anchor="mm")
        return cel
    vp = Image.open(f).convert("RGB").crop(VIEWPORT)
    jx, jy = JOGADOR[0] - VIEWPORT[0], JOGADOR[1] - VIEWPORT[1]
    dv = ImageDraw.Draw(vp, "RGBA")
    for r, wid, a in ((62, 7, 255), (78, 4, 140)):
        dv.ellipse([jx - r, jy - r, jx + r, jy + r], outline=cor + (a,), width=wid)
    dv.rectangle([jx - 30, jy - 104, jx + 30, jy - 70], fill=(0, 0, 0, 220), outline=cor + (255,), width=3)
    dv.text((jx, jy - 87), str(n), font=F(30), fill=cor + (255,), anchor="mm")
    linhas = quebra(historia or "", 88) if historia else []
    alt_hist = 26 * len(linhas) + (12 if linhas else 0)
    esc = min((CEL[0] - 12) / vp.size[0], (CEL[1] - CAB - alt_hist - 12) / vp.size[1])
    vp = vp.resize((int(vp.size[0] * esc), int(vp.size[1] * esc)), Image.LANCZOS)
    cel.paste(vp, ((CEL[0] - vp.size[0]) // 2, CAB + 4))
    yy = CAB + 12 + vp.size[1]
    for ln in linhas:
        d.text((14, yy), ln, font=F(19), fill=(240, 240, 240))
        yy += 26
    ImageDraw.Draw(cel).rectangle([0, 0, CEL[0] - 1, CEL[1] - 1], outline=(60, 60, 72), width=2)
    return cel


def quebra(txt, n):
    fora, linha = [], ""
    for p in txt.split():
        if len(linha) + len(p) + 1 > n:
            fora.append(linha)
            linha = p
        else:
            linha = (linha + " " + p).strip()
    if linha:
        fora.append(linha)
    return fora[:2]


def painel_mapa(png, titulo, notas=()):
    puro = pathlib.Path(str(png).replace(".png", "_mapa.png"))
    img = Image.open(puro if puro.exists() else png).convert("RGB")
    a = np.asarray(img).astype(int)
    mask = (np.abs(a - np.array([16, 16, 20])).sum(axis=2) > 26)
    if not puro.exists():
        mask[:112, :] = False
    ys, xs = np.nonzero(mask)
    mapa = img.crop((max(0, xs.min() - 4), max(0, ys.min() - 4),
                     min(img.size[0], xs.max() + 5), min(img.size[1], ys.max() + 5)))
    cel = Image.new("RGB", CEL, (20, 20, 26))
    d = ImageDraw.Draw(cel)
    d.rectangle([0, 0, CEL[0], CAB - 6], fill=(12, 12, 16))
    d.text((14, 20), titulo, font=F(22), fill=(150, 255, 190))
    alt_notas = 26 * len(notas) + 14
    esc = min((CEL[0] - 12) / mapa.size[0], (CEL[1] - CAB - alt_notas - 12) / mapa.size[1])
    mapa = mapa.resize((int(mapa.size[0] * esc), int(mapa.size[1] * esc)), Image.LANCZOS)
    cel.paste(mapa, ((CEL[0] - mapa.size[0]) // 2, CAB + 4))
    yy = CAB + 12 + mapa.size[1]
    for cor, txt in notas:
        d.text((14, yy), txt, font=F(17), fill=cor)
        yy += 26
    d.rectangle([0, 0, CEL[0] - 1, CEL[1] - 1], outline=(60, 60, 72), width=2)
    return cel


def main():
    session = pathlib.Path(sys.argv[1])
    src = pathlib.Path(sys.argv[2])
    casos = json.loads((src / "boxes_travadas.json").read_text(encoding="utf-8"))
    feitos = []
    for c in casos:
        t0, t1 = c["trava"][0], c["trava"][1]
        t_erro = c["erro"][0] if c.get("erro") else t0 - 30
        t_meio = (t_erro + t0) // 2
        titulo_erro = (c["erro"][3][:44] if c.get("erro") else "30s antes (sem gatilho detectado)")
        hist = c.get("historia") or ["", "", ""]
        paineis = [
            painel_print(session, t_erro, 1, "onde comecou", AMARELO, hist[0]),
            painel_print(session, t_meio, 2, "o que mudou no caminho", (255, 150, 60), hist[1]),
            painel_print(session, t0 + 4, 3, f"a box — {t1 - t0}s sem sair do tile", VERMELHO, hist[2]),
            painel_mapa(c["png"], "4  ·  o caminho, a trava e a saida que existia", (
                (AMARELO, f"1  {lw.fmt(t_erro)}  {titulo_erro}"),
                (VERMELHO, f"2  {lw.fmt(t0)}  travou {t1 - t0}s · {c['trava'][4]} de dano"),
                (VERDE, f"3  {c['fixes'][1][:104]}"),
            )),
        ]
        canvas = Image.new("RGB", (CEL[0] * 2, CEL[1] * 2 + 56), (14, 14, 18))
        d = ImageDraw.Draw(canvas)
        dmg = f"{c['trava'][4]:,}".replace(",", ".")
        d.text((16, 28), f"BOX #{c['n']}  ·  volta {c['volta'] or 'refill'}  ·  {lw.fmt(t0)}  ·  "
                         f"{t1 - t0}s travado  ·  {dmg} de dano  ·  pilha {c['trava'][5]}",
               font=F(25), fill=(255, 255, 255), anchor="lm")
        for i, p in enumerate(paineis):
            canvas.paste(p, ((i % 2) * CEL[0], 56 + (i // 2) * CEL[1]))
        out = src / f"boxgrid_{c['n']:02d}.png"
        canvas.save(out)
        feitos.append(str(out))
        print(out, canvas.size)
    return feitos


if __name__ == "__main__":
    main()
