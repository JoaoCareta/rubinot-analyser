"""Debug: decode cru dos dois paineis num f_ da volta 1."""
import pathlib
import sys

import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw
import pt_card

d = pathlib.Path(r"capture\session_20260728_072106")
alvo = sys.argv[1] if len(sys.argv) > 1 else "072415"
fs = sorted(d.glob("f_*.png"))
f = min(fs, key=lambda p: abs(lw.fsec(p.name) - (int(alvo[:2]) * 3600 + int(alvo[2:4]) * 60 + int(alvo[4:6]))))
print("frame:", f.name)
glyphs, gap = ab.load_atlas()
for nome, box, sx in (("PESSOAL", pt_card.PESSOAL, pt_card.PESSOAL_SCROLL_X),
                      ("PARTY", pt_card.PARTY, pt_card.PARTY_SCROLL_X)):
    img = Image.open(f).convert("RGB").crop(box)
    img.paste((0, 0, 0), (sx, 0, img.width, img.height))
    print(f"--- {nome} ---")
    for l in ab.decode_binary(ab.binarize_arr(np.asarray(img)), glyphs, gap):
        print(repr(l))
img = Image.open(f).convert("RGB")
img.crop((1570, 550, 1936, 1048)).save("z_debug_right.png")
img.crop((0, 780, 366, 1048)).save("z_debug_left.png")
print("crops salvos")
