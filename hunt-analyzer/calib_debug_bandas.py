"""Debug: bandas da binarizacao do painel pessoal no frame da volta 1."""
import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw

F = r"capture\session_20260728_072106\f_072414_626.png"
img = Image.open(F).convert("RGB").crop(lw.PANEL_CROP)
img.paste((0, 0, 0), (lw.SCROLLBAR_X, 0, img.width, img.height))
b = ab.binarize_arr(np.asarray(img))
rows = b.any(axis=1)
y = 0
bandas = []
while y < len(rows):
    if rows[y]:
        y0 = y
        while y < len(rows) and rows[y]:
            y += 1
        bandas.append((y0, y))
    y += 1
print("bandas (y0,y1,altura):")
for y0, y1 in bandas:
    print(f"  {y0:4d}-{y1:4d}  h={y1 - y0}")
glyphs, gap = ab.load_atlas()
linhas = ab.decode_binary(b, glyphs, gap)
print(f"decode deu {len(linhas)} linhas:")
for l in linhas:
    print(repr(l))
