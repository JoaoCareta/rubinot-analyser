"""Pin por cor restrito ao redor do pixel esperado + inspecao do data.db do tracker."""
import sqlite3

import numpy as np
from PIL import Image

m = np.asarray(Image.open("z_calib_loe_m.png").convert("RGB")).astype(int)
mask = (m[:, :, 0] > 150) & (m[:, :, 1] < 90) & (m[:, :, 2] < 90)
ys, xs = np.nonzero(mask)
near = (abs(xs - 46) <= 12) & (abs(ys - 75) <= 12)
print(f"pin perto do esperado: {near.sum()} px, bola=({xs[near].mean():.1f},{ys[near].mean():.1f})"
      f"  esperado (46.1,74.8)")

db = sqlite3.connect(r"D:\Documentos\rubinot\loe-hunt-tracker\data.db")
print("tabelas:", [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")])
for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    cols = [c[1] for c in db.execute(f"PRAGMA table_info({name})")]
    n = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"{name}: {n} rows, cols={cols}")
row = db.execute("SELECT * FROM sessions LIMIT 1").fetchone()
if row:
    for v in row:
        s = str(v)
        print(s[:800])
