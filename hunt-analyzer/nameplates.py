"""Localiza criaturas e membros da party na TELA pelo nameplate.

O cliente desenha o nome de cada criatura numa cor fixa:
  (0,192,0) / (96,192,96) = jogador (voce e party)   (192,192,0) = monstro
  (192,0,0) / (255,0,0)   = alvo atacado
Como a fonte e a mesma do chat, o atlas de glifos decodifica o nome; a posicao
do texto da a posicao da criatura em TILES relativos a voce (voce fica no centro
do viewport).

Uso: python nameplates.py frame.png
"""
import numpy as np
from PIL import Image

import atlas_build as ab

VIEWPORT = (455, 88, 1478, 840)   # janela do mundo (layout 1936x1048)
TILE_PX = 64                       # zoom padrao do cliente: 64px por tile

CORES = {
    "jogador": ((0, 192, 0), (96, 192, 96)),
    "monstro": ((192, 192, 0),),
    "alvo": ((192, 0, 0), (255, 0, 0), (192, 48, 48)),
}


def shape_index(glyphs):
    """Atlas indexado so pela FORMA (o hash normal inclui o topo dentro da banda,
    que muda fora do chat). Colisao resolvida pelo char mais frequente."""
    import collections
    import json as _json

    idx = collections.defaultdict(collections.Counter)
    for key, ch in glyphs.items():
        top, w, rows = _json.loads(key)
        idx[_json.dumps([w, rows])][ch] += 1
    return {k: c.most_common(1)[0][0] for k, c in idx.items()}


def decode_shape(binary, sidx, space_gap=5):
    """Decodifica uma banda de texto usando o indice por forma."""
    import json as _json

    cols = binary.any(axis=0)
    parts, prev_end, x = [], None, 0
    while x < len(cols):
        if not cols[x]:
            x += 1
            continue
        x0 = x
        while x < len(cols) and cols[x]:
            x += 1
        g = binary[:, x0:x]
        rws = g.any(axis=1)
        if not rws.any():
            continue
        top = int(np.argmax(rws))
        bot = len(rws) - int(np.argmax(rws[::-1]))
        tight = g[top:bot]
        rows_bits = [int("".join("1" if v else "0" for v in row), 2) for row in tight]
        if prev_end is not None and x0 - prev_end >= space_gap:
            parts.append(" ")
        parts.append(sidx.get(_json.dumps([x - x0, rows_bits]), "?"))
        prev_end = x
    return "".join(parts)


def _mask(arr, cores, tol=12):
    m = np.zeros(arr.shape[:2], dtype=bool)
    for c in cores:
        d = np.abs(arr.astype(int) - np.array(c)).sum(axis=2)
        m |= d <= tol
    return m


def nameplates(frame_png, sidx=None, viewport=VIEWPORT):
    """Devolve [{'nome','tipo','dx_tiles','dy_tiles','px'}] das criaturas visiveis."""
    if sidx is None:
        sidx = shape_index(ab.load_atlas()[0])
    if isinstance(frame_png,Image.Image):
        arr=np.asarray(frame_png.convert('RGB').crop(viewport))
    else:
        with Image.open(frame_png) as im:arr=np.asarray(im.convert('RGB').crop(viewport))
    h, w = arr.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    out = []
    for tipo, cores in CORES.items():
        m = _mask(arr, cores)
        if not m.any():
            continue
        for y0, y1 in ab.find_bands(m):
            if not (5 <= y1 - y0 <= 14):
                continue
            faixa = m[y0 : y1 + 1]
            cols = faixa.any(axis=0)
            # agrupa colunas em blocos de texto (gap > 12px separa nomes)
            x = 0
            while x < len(cols):
                if not cols[x]:
                    x += 1
                    continue
                x2 = x
                vazio = 0
                while x2 < len(cols) and vazio <= 12:
                    vazio = 0 if cols[x2] else vazio + 1
                    x2 += 1
                bloco = faixa[:, x : x2]
                txt = decode_shape(bloco, sidx).strip()
                if len(txt) >= 3 and txt.count("?") <= 1:
                    px = x + (x2 - x) / 2.0
                    py = y1 + 8   # o nome fica ~8px acima do corpo
                    out.append({
                        "nome": txt, "tipo": tipo,
                        "dx_tiles": round((px - cx) / TILE_PX, 1),
                        "dy_tiles": round((py - cy) / TILE_PX, 1),
                        "dist_tiles": round(((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 / TILE_PX, 1),
                        "px": (int(px), int(py)),
                    })
                x = x2
    return out


if __name__ == "__main__":
    import sys

    for f in sys.argv[1:]:
        print(f)
        for n in sorted(nameplates(f), key=lambda d: d["dist_tiles"]):
            print(f"  {n['tipo']:>8} {n['nome'][:28]:<28} "
                  f"dx={n['dx_tiles']:>5} dy={n['dy_tiles']:>5} dist={n['dist_tiles']}")
