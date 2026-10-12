"""Checks objetivos de calibracao (harness-calib-lanes): battle=0, painel campo a campo, pin."""
from PIL import Image

import atlas_build as ab
import lap_watch as lw
import pin_detect

FRAME = "z_calib_loe.png"

# 1. battle list vazia tem que dar 0
print("battle_count:", lw.battle_count("z_calib_loe_b.png"))

# 2. painel pessoal (Hunting Analyser) campo a campo
glyphs, gap = ab.load_atlas()
img = Image.open(FRAME).convert("RGB")
import numpy as np
PESSOAL = (0, 788, 190, 1048)
arr = np.asarray(img.crop(PESSOAL))
linhas = ab.decode_binary(lw.clean_binary(ab.binarize_arr(arr)), glyphs, gap)
print("--- painel pessoal ---")
for l in linhas:
    print(repr(l))

# 3. pin no Map View
print("pin:", pin_detect.find_pin(FRAME))

# 4. zoom da coluna direita p/ medir o crop novo do Party Hunt
img.crop((1570, 550, 1936, 1048)).resize((732, 996), Image.NEAREST).save("z_calib_loe_right.png")
print("zoom direita salvo")
