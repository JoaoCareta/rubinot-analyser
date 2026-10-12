"""Pin por cor + template 2px + decode do crop novo do Party Hunt."""
import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw
import pin_detect

FRAME = "z_calib_loe.png"

# pin por cor no crop m_ (bola vermelha r>150, g<90, b<90)
m = np.asarray(Image.open("z_calib_loe_m.png").convert("RGB")).astype(int)
mask = (m[:, :, 0] > 150) & (m[:, :, 1] < 90) & (m[:, :, 2] < 90)
ys, xs = np.nonzero(mask)
print(f"pin por cor: {len(xs)} px, bola=({xs.mean():.1f},{ys.mean():.1f})  esperado (46.1,74.8)")

# template antigo (2px classico)
tpl = np.asarray(Image.open("pin_template_2px.png").convert("RGB"))
import cv2
tpl_bgr = cv2.cvtColor(tpl, cv2.COLOR_RGB2BGR)
r = pin_detect.find_pin(FRAME, tpl_bgr, min_score=0.4)
print("find_pin tpl_2px:", r)

# decode do crop novo do Party Hunt
PARTY = (1753, 630, 1925, 1035)
SCROLL_X = 159  # 1912 - 1753
img = Image.open(FRAME).convert("RGB").crop(PARTY)
img.paste((0, 0, 0), (SCROLL_X, 0, img.width, img.height))
glyphs, gap = ab.load_atlas()
linhas = ab.decode_binary(ab.binarize_arr(np.asarray(img)), glyphs, gap)
print("--- party hunt ---")
for l in linhas:
    print(repr(l))
