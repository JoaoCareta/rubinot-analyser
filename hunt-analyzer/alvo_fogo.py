"""Linha 🎯 do card (voltas 6+): o tile do coach repetiu? Compara com a referencia.

Uso: python alvo_fogo.py capture\\session_X <volta> [z x y dano_ref]
"""
import json
import pathlib
import sys

import coach_fogo as cf
import loe_mapa
from lap_watch import to_s

REF = (12, 32639.5, 32705.5)
REF_DANO = 7090


def main():
    s = pathlib.Path(sys.argv[1])
    volta = int(sys.argv[2])
    ref = tuple(float(v) for v in sys.argv[3:6]) if len(sys.argv) >= 6 else REF
    ref_dano = float(sys.argv[6]) if len(sys.argv) >= 7 else REF_DANO
    laps = [json.loads(l) for l in (s / "laps.jsonl").read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    L = next(L for L in laps if L["volta"] == volta)
    t0, t1 = to_s(L["inicio"]), to_s(L["fim"])
    _, pts, _, _ = loe_mapa.carrega(s)
    me, ek, sio = cf.eventos(s, t0, t1)
    bat = cf.battle_por_t(s, t0, t1)
    tv = cf.travas(s, pts, t0, t1, me, bat)
    perto = [o for o in tv if o["z"] == ref[0] and abs(o["x"] - ref[1]) <= 3 and abs(o["y"] - ref[2]) <= 3]
    seq = [p for p in pts if t0 <= p["t"] <= t1 and p["z"] == ref[0]
           and abs(p["x"] - ref[1]) <= 3 and abs(p["y"] - ref[2]) <= 3]
    dano_tile = sum(v for t, v, _ in me if any(abs(p["t"] - t) <= 2 for p in seq))
    if not perto:
        status = "✅ corrigida"
    elif max(o["dano"] for o in perto) < 0.5 * ref_dano:
        status = "🟡 parcial"
    else:
        status = "❌ repetiu"
    print(json.dumps({"volta": volta, "status": status, "travas_no_tile": [(o["dur"], o["dano"]) for o in perto],
                      "dwell_tile_s": len(seq) * 2, "dano_no_tile": dano_tile,
                      "var_vs_ref": f"{(dano_tile - ref_dano) / ref_dano:+.0%}",
                      "dano_ED_volta": sum(v for _, v, _ in me), "travas_total": len(tv), "sios": len(sio),
                      "outras_travas": [(o["z"], round(o["x"]), round(o["y"]), o["dur"], o["dano"]) for o in tv if o not in perto][:3]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
