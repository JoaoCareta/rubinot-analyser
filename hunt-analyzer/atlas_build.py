"""Atlas de glifos da fonte do console do RubinOT + decodificador de chat crops.

A fonte e bitmap sem antialiasing: cada glifo binarizado e identico pixel a pixel
sempre que aparece, entao o reconhecimento e um dicionario hash(bitmap) -> char.

Modos:
  python atlas_build.py teach <png> "linha 1" ["linha 2" ...]
      Alinha as N ultimas linhas de texto do frame com o gabarito digitado e
      aprende os glifos. Falha alto se a contagem nao bater.
      Pares que encostam na fonte (ex.: "tt") marcam-se como um glifo so com
      colchetes no gabarito: "an a[tt]ack".
  python atlas_build.py decode <png> [<png> ...]
      Decodifica frames usando o atlas; glifo desconhecido vira �.
  python atlas_build.py teach-line <png> "gabarito da linha"
      Acha sozinho a banda do frame que casa com o gabarito (pelos glifos ja
      conhecidos) e aprende so os desconhecidos.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).parent
ATLAS_PATH = HERE / "atlas.json"

LUM_T = 140        # glifo mais escuro visto: cinza 168 (itens comuns); sombra <=120
X_MAX = 1180       # corta setas de scroll a direita do console
INPUT_TOP = 315    # bandas comecando daqui para baixo sao o campo de digitacao
BAND_H = (6, 15)   # altura de uma linha de texto
SPACE_GAP_DEFAULT = 4


def load_atlas_full():
    if ATLAS_PATH.exists():
        return json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    return {"glyphs": {}, "min_space": None, "max_join": 0}


def load_atlas():
    d = load_atlas_full()
    return d["glyphs"], space_gap_of(d)


def space_gap_of(d):
    gap = max(SPACE_GAP_DEFAULT, d.get("max_join", 0) + 1)
    if d.get("min_space") is not None and gap > d["min_space"]:
        print(f"AVISO: max_join {d['max_join']} >= min_space {d['min_space']}")
    return gap


def save_atlas(d):
    ATLAS_PATH.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def binarize_arr(img):
    """Binariza um array HxWx3 (ordem de canais irrelevante — usa o max)."""
    binary = img.max(axis=2) > LUM_T
    binary[:, X_MAX:] = False
    return binary


def binarize(png_path):
    return binarize_arr(np.asarray(Image.open(png_path).convert("RGB")))


def find_bands(binary):
    rows = binary.any(axis=1)
    bands, y = [], 0
    while y < len(rows):
        if rows[y]:
            y0 = y
            while y < len(rows) and rows[y]:
                y += 1
            bands.append((y0, y))
        else:
            y += 1
    return bands


def text_bands(binary, input_top=INPUT_TOP):
    lo, hi = BAND_H
    return [
        (a, b)
        for a, b in find_bands(binary)
        if lo <= b - a <= hi and (input_top is None or a < input_top)
    ]


def glyphs_of(binary, y0, y1):
    """Glifos da banda: lista de (key, gap_antes). Key e string estavel."""
    seg = binary[y0:y1]
    cols = seg.any(axis=0)
    out, prev_end, x = [], None, 0
    while x < len(cols):
        if cols[x]:
            x0 = x
            while x < len(cols) and cols[x]:
                x += 1
            g = seg[:, x0:x]
            rws = g.any(axis=1)
            top = int(np.argmax(rws))
            bot = len(rws) - int(np.argmax(rws[::-1]))
            tight = g[top:bot]
            rows_bits = [int("".join("1" if v else "0" for v in row), 2) for row in tight]
            key = json.dumps([top, x - x0, rows_bits])
            gap = 0 if prev_end is None else x0 - prev_end
            out.append((key, gap))
            prev_end = x
        else:
            x += 1
    return out


def parse_truth(text):
    """Gabarito -> (tokens nao-espaco, indices de token precedidos por espaco)."""
    tokens, space_before = [], set()
    pending_space = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == " ":
            pending_space = True
            i += 1
            continue
        if c == "\\" and i + 1 < len(text) and text[i + 1] in "[]":
            tok = text[i + 1]  # \[ e \] = colchete literal (glifo real)
            i += 2
        elif c == "[":
            j = text.index("]", i)
            tok = text[i + 1 : j]
            i = j + 1
        else:
            tok = c
            i += 1
        if pending_space:
            space_before.add(len(tokens))
            pending_space = False
        tokens.append(tok)
    return tokens, space_before


def learn_band(atlas, gs, chars, space_before):
    """Aprende glifo->char de uma banda alinhada. Devolve (aprendidos, conflitos)."""
    glyphs = atlas["glyphs"]
    learned, conflicts = 0, 0
    min_space, max_join = atlas.get("min_space"), atlas.get("max_join", 0)
    for i, (key, gap) in enumerate(gs):
        if i in space_before:
            min_space = gap if min_space is None else min(min_space, gap)
        elif i > 0:
            max_join = max(max_join, gap)
        ch = chars[i]
        if key in glyphs and glyphs[key] != ch:
            print(f"CONFLITO: glifo ja mapeado como {glyphs[key]!r}, gabarito diz {ch!r}")
            conflicts += 1
        elif key not in glyphs:
            glyphs[key] = ch
            learned += 1
    atlas.update(min_space=min_space, max_join=max_join)
    return learned, conflicts


def finish_teach(atlas, learned, conflicts):
    save_atlas(atlas)
    print(
        f"aprendidos {learned} glifos ({conflicts} conflitos); atlas={len(atlas['glyphs'])}; "
        f"space_gap={space_gap_of(atlas)} (min espaco={atlas['min_space']}, "
        f"max juncao={atlas['max_join']})"
    )


def teach(png_path, lines):
    atlas = load_atlas_full()
    binary = binarize(png_path)
    bands = text_bands(binary)
    if len(bands) < len(lines):
        sys.exit(f"so {len(bands)} bandas de texto no frame, gabarito tem {len(lines)} linhas")
    bands = bands[-len(lines):]  # console = ultimas bandas antes do input

    learned, conflicts = 0, 0
    for (y0, y1), text in zip(bands, lines):
        gs = glyphs_of(binary, y0, y1)
        chars, space_before = parse_truth(text)
        if len(gs) != len(chars):
            sys.exit(
                f"banda y={y0}-{y1}: {len(gs)} glifos vs {len(chars)} tokens no gabarito\n"
                f"gabarito: {text!r}\n"
                f"gaps: {[g for _, g in gs]}"
            )
        n, c = learn_band(atlas, gs, chars, space_before)
        learned += n
        conflicts += c
    finish_teach(atlas, learned, conflicts)


def teach_line(png_path, text):
    atlas = load_atlas_full()
    glyphs = atlas["glyphs"]
    gap_t = space_gap_of(atlas)
    binary = binarize(png_path)
    chars, space_before = parse_truth(text)

    cands = []
    for y0, y1 in text_bands(binary):
        gs = glyphs_of(binary, y0, y1)
        if len(gs) < len(chars):
            continue
        tail = gs[-len(chars):]  # gabarito pode ser sufixo (sem o timestamp)
        if len(gs) > len(chars) and tail[0][1] < gap_t:
            continue  # sufixo tem de comecar depois de um espaco
        known_match = all(
            glyphs.get(key) in (None, chars[i]) for i, (key, _) in enumerate(tail)
        )
        spaces = {i for i, (_, gap) in enumerate(tail) if i and gap >= gap_t}
        if known_match and spaces == space_before:
            cands.append(tail)
    if len(cands) != 1:
        sys.exit(f"{len(cands)} bandas candidatas para o gabarito (esperava exatamente 1)")
    learned, conflicts = learn_band(atlas, cands[0], chars, space_before)
    finish_teach(atlas, learned, conflicts)


def decode_binary(binary, glyphs, space_gap, input_top=INPUT_TOP):
    out = []
    for y0, y1 in text_bands(binary, input_top):
        gs = glyphs_of(binary, y0, y1)
        parts = []
        for i, (key, gap) in enumerate(gs):
            if i and gap >= space_gap:
                parts.append(" ")
            parts.append(glyphs.get(key, "�"))
        out.append("".join(parts))
    return out


def decode_frame(png_path, glyphs, space_gap, input_top=INPUT_TOP):
    return decode_binary(binarize(png_path), glyphs, space_gap, input_top)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    mode, paths = sys.argv[1], sys.argv[2:]
    if mode == "teach":
        teach(paths[0], paths[1:])
    elif mode == "teach-line":
        teach_line(paths[0], paths[1])
    elif mode == "decode":
        glyphs, space_gap = load_atlas()
        for p in paths:
            print(f"--- {pathlib.Path(p).name}")
            for line in decode_frame(p, glyphs, space_gap):
                print(line)
    else:
        sys.exit(f"modo desconhecido: {mode}")


if __name__ == "__main__":
    main()
