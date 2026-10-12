"""Histograma do battle_count da hunt de hoje (amostra 2s) + dano por membro agora.

Responde: quantas vezes a pilha atinge cada gate "Creatures N+" do RTC.
"""
import collections
import pathlib
import re
import sys

import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw
import pt_card

session = pathlib.Path(sys.argv[1])
INICIO = 7 * 3600 + 21 * 60 + 24

bs = [f for f in sorted(session.glob("b_*.png")) if lw.fsec(f.name) >= INICIO]
amostra = bs[::4]  # 2s
hist = collections.Counter()
for f in amostra:
    try:
        hist[lw.battle_count(str(f))] += 1
    except Exception:
        pass
tot = sum(hist.values())
print(f"{tot} amostras de battle (2s) desde 07:21:24")
acum = 0
for n in sorted(hist, reverse=True):
    acum += hist[n]
    print(f"  battle >= {n:2d}: {100.0 * acum / tot:5.1f}%   (= {n}: {hist[n]})")

# dano por membro do f_ mais recente (painel Party Hunt)
f = sorted(session.glob("f_*.png"))[-1]
print(f"\nparty hunt em {f.name}:")
img = Image.open(f).convert("RGB").crop(pt_card.PARTY)
img.paste((0, 0, 0), (pt_card.PARTY_SCROLL_X, 0, img.width, img.height))
glyphs, gap = ab.load_atlas()
for l in ab.decode_binary(ab.binarize_arr(np.asarray(img)), glyphs, gap):
    print(repr(l))
