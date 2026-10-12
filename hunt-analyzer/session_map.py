"""Mapa da sessao: spots globais, ordem de visita e efeito do intervalo (respawn).

Dead reckoning CONTINUO na sessao inteira + loop closure (a cada volta fechada,
distribui a deriva acumulada) => posicoes comparaveis entre voltas. Com isso:
  - pulls (ciclos da battle list) viram SPOTS globais
  - cada volta vira uma SEQUENCIA de spots (a ordem que o user faz)
  - mede kills por visita vs INTERVALO desde a visita anterior aquele spot

Uso: python session_map.py capture\\session_X [HH:MM:SS inicio]
"""
import collections
import json
import pathlib
import sys

import numpy as np

import atlas_build as ab
import dead_reckon as dr
import lap_watch as lw

SPOT_RADIUS = 22       # tiles
PULL_LO, PULL_HI = 2, 6
MIN_PULL_S = 8


def build_path(session, t0, refine=True):
    """Trajetoria: dead reckoning + 2a passada contra o mosaico (tira a deriva)."""
    frames = [f for f in sorted(session.glob("f_*.png")) if lw.fsec(f.name) >= t0]
    tr = dr.Tracker()
    raw = []
    for f in frames:
        p = tr.update(f)
        if p is not None:
            raw.append((f, p[0], p[1]))
    if refine and len(raw) > 20:
        from pin_detect import MAP_CROP
        wh = (MAP_CROP[2] - MAP_CROP[0], MAP_CROP[3] - MAP_CROP[1])
        raw = dr.refine_with_mosaic(raw, wh)
    return np.array([[lw.fsec(f.name), x, y] for f, x, y in raw], dtype=float)


def find_laps(pts):
    """Indices (i0, i1) de cada volta fechada, pelo criterio do vigia."""
    laps, start, away = [], 0, None
    for i in range(1, len(pts)):
        rel = pts[i, 1:] - pts[start, 1:]
        d = float(np.hypot(*rel))
        t = pts[i, 0]
        if d > lw.AWAY_TILES and away is None:
            away = t
        if away is not None and d < lw.NEAR_TILES and t - away >= lw.MIN_AWAY_S:
            laps.append((start, i))
            start, away = i, None
    return laps


def close_loops(pts, laps):
    """Distribui a deriva de cada volta (deveria voltar ao mesmo ponto)."""
    out = pts.copy()
    shift = np.zeros(2)
    for i0, i1 in laps:
        out[i0 : i1 + 1, 1:] += shift
        drift = out[i1, 1:] - out[i0, 1:]
        n = i1 - i0
        if n > 0:
            corr = np.linspace(0, 1, n + 1)[:, None] * drift
            out[i0 : i1 + 1, 1:] -= corr
        shift = out[i1, 1:] - pts[i1, 1:]
    if laps:
        out[laps[-1][1] :, 1:] += shift
    return out


def battle_series(session, t0, t1):
    counts = {}
    for f in sorted(session.glob("b_*.png")):
        s = lw.fsec(f.name)
        if t0 <= s <= t1 and s % 2 == 0:
            counts[s] = lw.battle_count(f)
    return counts


STOP_RADIUS = 11      # tiles: raio em que o jogador "fica parado" fazendo a box
STOP_MIN_S = 14       # duracao minima da parada
STOP_GAP_S = 8        # paradas separadas por menos que isso viram uma so


def find_stops(pts):
    """Boxes por PARADA: janelas em que o jogador fica num raio pequeno.

    Funciona mesmo em trem continuo (battle list nunca esvazia), que e o caso
    das caves de dragao.
    """
    stops = []
    i = 0
    n = len(pts)
    while i < n:
        j = i
        while j + 1 < n:
            seg = pts[i : j + 2, 1:]
            c = seg.mean(axis=0)
            if np.hypot(*(seg - c).T).max() > STOP_RADIUS:
                break
            j += 1
        dur = pts[j, 0] - pts[i, 0]
        if dur >= STOP_MIN_S:
            c = pts[i : j + 1, 1:].mean(axis=0)
            stops.append({"t0": int(pts[i, 0]), "t1": int(pts[j, 0]), "pos": c,
                          "peak": 0})
            i = j + 1
        else:
            i += 1
    # funde paradas quase coladas no mesmo lugar
    merged = []
    for s in stops:
        if merged and s["t0"] - merged[-1]["t1"] <= STOP_GAP_S and \
                float(np.hypot(*(s["pos"] - merged[-1]["pos"]))) <= STOP_RADIUS:
            m = merged[-1]
            m["t1"] = s["t1"]
            m["pos"] = (m["pos"] + s["pos"]) / 2
        else:
            merged.append(s)
    return merged


def find_pulls(counts):
    pulls, cur = [], None
    for s in sorted(counts):
        n = counts[s]
        if cur is None:
            if n >= PULL_HI:
                cur = {"t0": s, "peak": n}
        else:
            cur["peak"] = max(cur["peak"], n)
            if n <= PULL_LO:
                cur["t1"] = s
                if cur["t1"] - cur["t0"] >= MIN_PULL_S:
                    pulls.append(cur)
                cur = None
    return pulls


def main():
    session = pathlib.Path(sys.argv[1])
    t0 = lw.to_s(sys.argv[2]) if len(sys.argv) > 2 else 0
    glyphs, gap = ab.load_atlas()

    pts = build_path(session, t0)
    laps = find_laps(pts)
    pts = close_loops(pts, laps)
    print(f"{len(pts)} posicoes, {len(laps)} voltas fechadas (loop closure aplicado)")

    pulls = find_stops(pts)
    print(f"{len(pulls)} boxes (paradas) detectadas")

    evs = [json.loads(l) for l in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()] \
        if (session / "events.jsonl").exists() else []
    if not evs:
        print("AVISO: sem events.jsonl — rode events_build.py antes p/ ter kills por box")

    def pos_at(t):
        i = int(np.argmin(np.abs(pts[:, 0] - t)))
        return pts[i, 1:] if abs(pts[i, 0] - t) <= 12 else None

    # spots globais
    spots = []
    for p in pulls:
        xy = p["pos"]
        for s in spots:
            if float(np.hypot(*(s["pos"] - xy))) <= SPOT_RADIUS:
                s["pulls"].append(p)
                s["pos"] = np.mean([q["pos"] for q in s["pulls"]], axis=0)
                p["spot"] = s
                break
        else:
            s = {"id": len(spots) + 1, "pos": xy, "pulls": [p]}
            spots.append(s)
            p["spot"] = s

    for p in pulls:
        p["kills"] = sum(1 for e in evs if e["kind"] == "xp_gain"
                         and p["t0"] <= lw.to_s(e["ts"]) <= p["t1"] + 6)
        p["xp"] = sum(e["value"] for e in evs if e["kind"] == "xp_gain"
                      and p["t0"] <= lw.to_s(e["ts"]) <= p["t1"] + 6)

    # ordem por volta
    print("\n=== ORDEM DAS BOXES POR VOLTA ===")
    lap_seq = []
    for k, (i0, i1) in enumerate(laps, 1):
        a, b = int(pts[i0, 0]), int(pts[i1, 0])
        seq = [p for p in pulls if a <= p["t0"] <= b and "spot" in p]
        s = "".join(f" S{p['spot']['id']}({p['kills']})" for p in seq)
        lap_seq.append((k, a, b, [p["spot"]["id"] for p in seq]))
        print(f"  volta {k} {lw.fmt(a)}-{lw.fmt(b)}:{s}")

    # intervalo entre visitas x rendimento
    print("\n=== SPOT: RENDIMENTO x INTERVALO DESDE A ULTIMA VISITA ===")
    print(f"{'spot':>5} {'visitas':>8} {'kills/visita':>13} {'intervalo medio':>16}  detalhe (intervalo->kills)")
    tips = []
    for s in spots:
        ps = sorted(s["pulls"], key=lambda q: q["t0"])
        det, ints, kk = [], [], []
        for i, p in enumerate(ps):
            gap_s = int(p["t0"] - ps[i - 1]["t1"]) if i else None
            det.append(f"{gap_s if gap_s is not None else '-'}s->{p['kills']}")
            if gap_s:
                ints.append(gap_s)
                kk.append(p["kills"])
        med_int = f"{np.mean(ints):.0f}s" if ints else "-"
        print(f"S{s['id']:>4} {len(ps):>8} {np.mean([p['kills'] for p in ps]):>13.1f} {med_int:>16}  {'  '.join(det)}")
        if len(ints) >= 2:
            corr = float(np.corrcoef(ints, kk)[0, 1]) if np.std(ints) > 1 and np.std(kk) > 0 else 0.0
            if corr > 0.5 and np.mean(ints) < 300:
                tips.append((2 + corr, f"S{s['id']}: quanto MAIS tempo você demora pra voltar, mais rende "
                                       f"(correlação {corr:+.2f}). Intervalo médio atual {np.mean(ints):.0f}s — "
                                       f"passe nele mais tarde na volta."))
            if corr < -0.4:
                tips.append((1.5, f"S{s['id']}: rende MENOS quando você demora (correlação {corr:+.2f}) — "
                                  f"provável concorrência de outro player levando o respawn."))
    if tips:
        print("\n=== SUGESTOES DE ORDEM ===")
        for i, (_, t) in enumerate(sorted(tips, key=lambda x: -x[0]), 1):
            print(f"{i}. {t}")


if __name__ == "__main__":
    main()
