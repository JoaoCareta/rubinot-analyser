"""Mapa da hunt de Ingol no padrao map_hunt (andares + painel de box).

Ingol = z8 (confirmado 27/07 por matchTemplate: 0,96-0,98 contra 0,11 no z7 e
0,50 no z9). Trajetoria por posicao ABSOLUTA (casa o recorte m_ no stitch dos
.otmm), sem dead reckoning — nao acumula deriva.

Uso: python mapa_ingol.py capture\\session_X reports\\saida.png [volta_ini volta_fim]
"""
import json
import pathlib
import sys

import numpy as np

import anchor_map as am
import map_hunt
import map_live

X0, X1, Y0, Y1, Z = 33600, 33900, 32460, 32700, 8


def planos():
    """color (indices da paleta) + walk (byte por tile) do z8 no bbox de Ingol."""
    color, n = am.stitch_floor(Z, X0, X1, Y0, Y1)
    walk = np.zeros((Y1 - Y0, X1 - X0), dtype=np.uint8)
    import re
    for f in am.MMDIR.glob(f"minimap1520_*_{Z}.otmm"):
        m = re.match(r"minimap1520_(\d+)_(\d+)_", f.stem)
        bx, by = int(m.group(1)), int(m.group(2))
        if bx + 64 <= X0 or bx >= X1 or by + 64 <= Y0 or by >= Y1:
            continue
        data = f.read_bytes()
        if len(data) < 8216:
            continue
        blk = np.frombuffer(data[24:4120], dtype=np.uint8).reshape(64, 64)
        xl, xh = max(bx, X0), min(bx + 64, X1)
        yl, yh = max(by, Y0), min(by + 64, Y1)
        walk[yl - Y0:yh - Y0, xl - X0:xh - X0] = blk[yl - by:yh - by, xl - bx:xh - bx]
    print(f"stitch z{Z}: {n} blocos")
    return color, walk


def kills_posicionados(session, walked, laps):
    """Kill = sinal unificado das lanes, posicionado no ponto de rota +-12s.

    XP e profit de cada kill = rateio do valor do PAINEL da volta (fonte
    lossless) pelos kills daquela volta.
    """
    t0 = map_live.to_s(laps[0]["inicio"]); t1 = map_live.to_s(laps[-1]["fim"])
    ts = map_live.kill_times(session, t0, t1)
    wt = np.array([w[0] for w in walked])
    faixas = []
    for L in laps:
        t0, t1 = map_live.to_s(L["inicio"]), map_live.to_s(L["fim"])
        dentro = [t for t in ts if t0 <= t <= t1]
        n = max(1, len(dentro))
        faixas.append((t0, t1, (L.get("xp_raw_painel") or 0) / n, (L.get("profit") or 0) / n))
    out = []
    for t in ts:
        i = int(np.argmin(np.abs(wt - t)))
        if abs(wt[i] - t) > 12:
            continue
        xp = pf = 0
        for t0, t1, xpk, pfk in faixas:
            if t0 <= t <= t1:
                xp, pf = xpk, pfk
                break
        out.append((t, walked[i][1], walked[i][2], xp, pf))
    print(f"kills: {len(out)}/{len(ts)} posicionados")
    return out


def main():
    session = pathlib.Path(sys.argv[1])
    saida = sys.argv[2]
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(sys.argv) > 4:
        ini, fim = int(sys.argv[3]), int(sys.argv[4])
        laps = [L for L in laps if ini <= L["volta"] <= fim]
    color, walk = planos()
    walked = map_live.walked_update(session, X0, X1, Y0, Y1, Z)
    t0, t1 = map_live.to_s(laps[0]["inicio"]), map_live.to_s(laps[-1]["fim"])
    walked = [w for w in walked if t0 <= w[0] <= t1]
    print(f"rota: {len(walked)} pontos entre {laps[0]['inicio']} e {laps[-1]['fim']}")

    # calibra o byte de PISO pelos tiles realmente pisados (regra generica 26/07)
    hist = {}
    for _, x, y in walked:
        b = int(walk[int(round(y)) - Y0, int(round(x)) - X0])
        hist[b] = hist.get(b, 0) + 1
    print("bytes de walk sob a rota:", dict(sorted(hist.items(), key=lambda kv: -kv[1])))

    andar = {"z": Z, "color": color, "walk": walk, "origem": (X0, Y0), "walked": walked,
             "kills": kills_posicionados(session, walked, laps), "escadas": []}
    titulo = (f"INGOL z{Z}  ·  voltas {laps[0]['volta']}-{laps[-1]['volta']}  ·  "
              f"{laps[0]['inicio']}-{laps[-1]['fim']}")
    print(map_hunt.render(saida, [andar], titulo)[0])


if __name__ == "__main__":
    main()
