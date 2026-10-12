"""Mapa da hunt sobre o MAPA REAL do cliente (.otmm), com boxes e trajeto."""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am
import lap_watch as lw
import session_map as sm

S = 5


def main():
    session = pathlib.Path(sys.argv[1])
    t0 = lw.to_s(sys.argv[2])
    out = pathlib.Path(sys.argv[3])
    t1 = lw.to_s(sys.argv[4]) if len(sys.argv) > 4 else None

    pts = sm.build_path(session, t0)
    if t1:
        pts = pts[pts[:, 0] <= t1]
    frames = [f for f in sorted(session.glob("f_*.png"))
              if lw.fsec(f.name) >= t0 and (t1 is None or lw.fsec(f.name) <= t1)]
    region, floors = None, (6, 7, 8, 5, 9, 4)
    if len(sys.argv) > 5:  # "X0,X1,Y0,Y1[,z]"
        parts = [int(v) for v in sys.argv[5].split(",")]
        region = tuple(parts[:4])
        if len(parts) > 4:
            floors = (parts[4],)
    print("ancorando no mapa real...")
    z, to_abs, idx, X0, Y0, err = am.anchor(frames, pts, floors=floors, region=region)
    print(f"andar z{z}, erro {err:.4f}")

    stops = sm.find_stops(pts)
    evs = [json.loads(l) for l in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    for s_ in stops:
        s_["kills"] = sum(1 for e in evs if e["kind"] == "xp_gain" and s_["t0"] <= lw.to_s(e["ts"]) <= s_["t1"] + 6)
        s_["xp"] = sum(e["value"] for e in evs if e["kind"] == "xp_gain" and s_["t0"] <= lw.to_s(e["ts"]) <= s_["t1"] + 6)
        s_["dur"] = s_["t1"] - s_["t0"]
    order = sorted(stops, key=lambda q: q["t0"])
    for a, b in zip(order, order[1:]):
        g = b["t0"] - a["t1"]
        if 0 < g <= 240:
            b["lure"] = g

    spots = []
    for p in stops:
        for s_ in spots:
            if float(np.hypot(*(s_["pos"] - p["pos"]))) <= sm.SPOT_RADIUS:
                s_["stops"].append(p)
                s_["pos"] = np.mean([q["pos"] for q in s_["stops"]], axis=0)
                break
        else:
            spots.append({"id": len(spots) + 1, "pos": p["pos"], "stops": [p]})
    for s_ in spots:
        s_["kills"] = sum(q["kills"] for q in s_["stops"])
        s_["xp"] = sum(q["xp"] for q in s_["stops"])
        ciclo = sum(q["dur"] + (q.get("lure") or 0) for q in s_["stops"])
        s_["xpm"] = s_["xp"] / (ciclo / 60) if ciclo else 0.0
        s_["lure"] = float(np.mean([q.get("lure") or 0 for q in s_["stops"]]))

    abs_path = [to_abs(p) for p in pts[:, 1:]]
    ax = [p[0] for p in abs_path]
    ay = [p[1] for p in abs_path]
    bx0, bx1 = int(min(ax)) - 22, int(max(ax)) + 22
    by0, by1 = int(min(ay)) - 22, int(max(ay)) + 22
    sub = idx[by0 - Y0 : by1 - Y0, bx0 - X0 : bx1 - X0]
    W, H = sub.shape[1], sub.shape[0]
    img = Image.fromarray(am.PAL[sub]).resize((W * S, H * S), Image.NEAREST).convert("RGB")
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_ = ImageDraw.Draw(ov)

    def cv(p):
        return ((p[0] - bx0) * S, (p[1] - by0) * S)

    d_.line([cv(p) for p in abs_path], fill=(90, 200, 255, 210), width=3, joint="curve")
    xpms = [s_["xpm"] for s_ in spots if s_["xpm"] > 0]
    hi = np.percentile(xpms, 70) if xpms else 1
    lo = np.percentile(xpms, 30) if xpms else 0
    for s_ in spots:
        x, y = cv(to_abs(s_["pos"]))
        r = (4 + 1.5 * s_["kills"] ** 0.62) * S
        col = (150, 150, 150) if s_["kills"] == 0 else \
            (46, 204, 113) if s_["xpm"] >= hi else (231, 76, 60) if s_["xpm"] <= lo else (241, 196, 15)
        d_.ellipse([x - r, y - r, x + r, y + r], fill=col + (95,), outline=col + (240,), width=3)

    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d2 = ImageDraw.Draw(img)
    try:
        fb = ImageFont.truetype("arialbd.ttf", 22)
        fs = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        fb = fs = ImageFont.load_default()
    for s_ in spots:
        x, y = cv(to_abs(s_["pos"]))
        d2.text((x - 11, y - 13), f"S{s_['id']}", fill=(255, 255, 255), font=fb, stroke_width=3, stroke_fill=(0, 0, 0))
        d2.text((x - 46, y + 13), f"{s_['kills']}k · {s_['xpm']/1000:.0f}k/min · lure {s_['lure']:.0f}s",
                fill=(255, 255, 255), font=fs, stroke_width=3, stroke_fill=(0, 0, 0))
    d2.text((8, 6), f"mapa real do cliente (z{z})  x {bx0}-{bx1}  y {by0}-{by1}",
            fill=(255, 255, 255), font=fs, stroke_width=2, stroke_fill=(0, 0, 0))
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
