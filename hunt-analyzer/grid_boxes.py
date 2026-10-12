"""Junta as imagens de box num grid 2x2 (formato pedido pelo user em 27/07).

Cada painel entra recortado (a imagem de origem ja vem justa) com um cabecalho
de 2 linhas: identificacao + causa. As dicas completas vao no texto da resposta,
nao na imagem, para o grid ficar legivel.

Uso: python grid_boxes.py reports\\boxes_travadas [saida_prefixo]
"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
CEL_W, CEL_H = 760, 700          # celula do grid
CAB = 74                          # cabecalho por painel


def F(s):
    return ImageFont.truetype(FONTE, s)


def painel(caso, png):
    """Recorta SO a area desenhada (bbox do conteudo nao-fundo) e escala para a celula."""
    import numpy as np

    img = Image.open(png).convert("RGB")
    a = np.asarray(img).astype(int)
    fundo = np.array([16, 16, 20])
    mask = (np.abs(a - fundo).sum(axis=2) > 26)
    mask[:112, :] = False                      # ignora o cabecalho da imagem de origem
    ys, xs = np.nonzero(mask)
    y0, y1 = max(0, ys.min() - 4), min(img.size[1], ys.max() + 5)
    x0, x1 = max(0, xs.min() - 4), min(img.size[0], xs.max() + 5)
    mapa = img.crop((x0, y0, x1, y1))
    esc = min((CEL_W - 12) / mapa.size[0], (CEL_H - CAB - 12) / mapa.size[1])
    mapa = mapa.resize((max(1, int(mapa.size[0] * esc)), max(1, int(mapa.size[1] * esc))), Image.LANCZOS)

    cel = Image.new("RGB", (CEL_W, CEL_H), (20, 20, 26))
    cel.paste(mapa, ((CEL_W - mapa.size[0]) // 2, CAB + (CEL_H - CAB - mapa.size[1]) // 2))
    d = ImageDraw.Draw(cel)
    t0, t1, bx, by, dmg, pil = caso["trava"]
    d.rectangle([0, 0, CEL_W, CAB - 6], fill=(12, 12, 16))
    d.text((14, 20), f"BOX #{caso['n']}  ·  volta {caso['volta'] or 'refill'}  ·  {caso['hora']}"
                     f"  ·  {t1 - t0}s travado  ·  {dmg:,} de dano".replace(",", "."),
           font=F(21), fill=(255, 255, 255))
    causa = caso["erro"][3] if caso.get("erro") else "sem gatilho claro nos 60s anteriores"
    d.text((14, 48), causa[:96], font=F(17), fill=(255, 200, 110))
    d.rectangle([0, 0, CEL_W - 1, CEL_H - 1], outline=(60, 60, 72), width=2)
    return cel


def main():
    src = pathlib.Path(sys.argv[1])
    prefixo = sys.argv[2] if len(sys.argv) > 2 else str(src / "grid")
    casos = json.loads((src / "boxes_travadas.json").read_text(encoding="utf-8"))
    for c in casos:
        c["hora"] = pathlib.Path(c["png"]).stem.split("_")[-1]
        c["hora"] = f"{c['hora'][:2]}:{c['hora'][2:4]}:{c['hora'][4:]}"
    feitos = []
    for g in range(0, len(casos), 4):
        bloco = casos[g:g + 4]
        canvas = Image.new("RGB", (CEL_W * 2, CEL_H * 2 + 54), (14, 14, 18))
        d = ImageDraw.Draw(canvas)
        n0, n1 = bloco[0]["n"], bloco[-1]["n"]
        d.text((16, 27), f"BOXES {n0} a {n1} · INGOL z8 · 27/07 · 1 = onde o erro comeca · "
                         f"2 = onde travou · 3 = a saida que existia", font=F(23), fill=(255, 255, 255), anchor="lm")
        for i, c in enumerate(bloco):
            canvas.paste(painel(c, c["png"]), ((i % 2) * CEL_W, 54 + (i // 2) * CEL_H))
        out = f"{prefixo}_{n0}a{n1}.png"
        canvas.save(out)
        feitos.append(out)
        print(out, canvas.size)
    return feitos


if __name__ == "__main__":
    main()
