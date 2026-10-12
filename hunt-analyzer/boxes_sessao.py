"""Analise de TODAS as box da sessao (pedido do user em 27/07).

LICAO: nesta hunt o kill e CONTINUO (trem), entao separar box por "gap sem kill"
nao funciona (deu 1 box de 1315s). Box aqui = PARADA onde ele limpa a pilha, ou
seja aglomerado ESPACIAL de kills. Como ele repassa os mesmos pontos a cada
volta, o mesmo ponto reaparece: o relatorio agrega por PONTO e conta em quantas
voltas ele foi usado.

Para cada box: bichos, tempo parado, dano tomado por perto, dano por bicho,
bichos/min e o trecho do anel. O decode do chat inteiro e caro (~4min), entao os
eventos ficam em cache em <session>/eventos_sessao.json.

Uso: python boxes_sessao.py capture\\session_X [saida.json]
"""
import collections
import json
import pathlib
import sys

import numpy as np

import atlas_build as ab
import lap_watch as lw
import map_live
import mapa_ingol as mi

RAIO = 6.0        # tiles: mesmo ponto do anel
MIN_KILLS = 6     # menos que isso na sessao inteira = passagem
JANELA = 12       # s: casa evento com ponto da rota


def sec(h):
    a, b, c = h.split(":")
    return int(a) * 3600 + int(b) * 60 + int(c)


def trecho(x, y):
    if y <= 32578:
        return "quina nordeste" if x >= 33745 else ("quina noroeste" if x <= 33690 else "faixa norte")
    if y >= 32610:
        return "quina sudoeste" if x <= 33697 else "reta sul"
    return "reta leste" if x >= 33745 else ("reta oeste" if x <= 33697 else "meio")


def eventos(session, t0, t1):
    """kills e dano com timestamp, em cache (decode do chat e caro)."""
    cache = session / "eventos_sessao.json"
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        return d["kills"], d["dano"]
    glyphs, gap = ab.load_atlas()
    kills, dano = [], []
    for e in lw.lane_events(session, "c", t0, t1, glyphs, gap):
        t = sec(e["ts"])
        if e["kind"] == "loot":
            kills.append([t, e.get("target") or "?"])
        elif e["kind"] == "looted" and "gold" in e.get("what", ""):
            # auto-loot esconde a especie; o ouro saqueado marca o kill
            kills.append([t, "?"])
        elif e["kind"] == "damage_taken":
            dano.append([t, e["value"], e.get("actor") or "?"])
    cache.write_text(json.dumps({"kills": kills, "dano": dano}), encoding="utf-8")
    return kills, dano


def main():
    import area_hunt
    session = pathlib.Path(sys.argv[1])
    hunt = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].endswith(".json") else "ingol"
    area_hunt.aplicar(hunt)
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # delta de painel negativo = analyser resetado no meio da volta — descartar
    lim = [L for L in laps if (L.get("xp_raw_painel") or 0) >= 0]
    walked = map_live.walked_update(session, mi.X0, mi.X1, mi.Y0, mi.Y1, mi.Z)
    wt = np.array([w[0] for w in walked])
    t0s, t1s = sec(lim[0]["inicio"]), sec(lim[-1]["fim"])
    kills, dano = eventos(session, t0s, t1s)
    print(f"{len(kills)} kills, {len(dano)} linhas de dano")

    janelas = [(sec(L["inicio"]), sec(L["fim"]), L["volta"]) for L in lim]

    def volta_de(t):
        for a, z, v in janelas:
            if a <= t <= z:
                return v
        return None

    def pos(t):
        i = int(np.argmin(np.abs(wt - t)))
        return (walked[i][1], walked[i][2]) if abs(wt[i] - t) <= JANELA else None

    # 1) aglomera kills por posicao
    pontos = []
    for t, sp in kills:
        v = volta_de(t)
        if v is None:
            continue
        p = pos(t)
        if p is None:
            continue
        for c in pontos:
            if ((p[0] - c["x"]) ** 2 + (p[1] - c["y"]) ** 2) ** 0.5 <= RAIO:
                n = c["kills"]
                c["x"] = (c["x"] * n + p[0]) / (n + 1)
                c["y"] = (c["y"] * n + p[1]) / (n + 1)
                c["kills"] += 1
                c["especies"][sp] += 1
                c["voltas"].add(v)
                c["t_primeiro"] = min(c["t_primeiro"], t)
                break
        else:
            pontos.append({"x": p[0], "y": p[1], "kills": 1, "t_primeiro": t,
                           "especies": collections.Counter({sp: 1}), "voltas": {v},
                           "dano": 0, "dwell": 0, "quem": collections.Counter()})
    pontos = [c for c in pontos if c["kills"] >= MIN_KILLS]

    def perto(x, y):
        melhor, dm = None, RAIO + 2
        for c in pontos:
            dd = ((x - c["x"]) ** 2 + (y - c["y"]) ** 2) ** 0.5
            if dd <= dm:
                melhor, dm = c, dd
        return melhor

    # 2) dano tomado e tempo parado em cada ponto
    for t, v, quem in dano:
        if volta_de(t) is None:
            continue
        p = pos(t)
        if p and (c := perto(*p)):
            c["dano"] += v
            c["quem"][quem] += v
    for i, (t, x, y) in enumerate(walked):
        if volta_de(t) is None:
            continue
        passo = min(t - walked[i - 1][0], 10) if i else 2
        if c := perto(x, y):
            c["dwell"] += passo

    saida = []
    for c in sorted(pontos, key=lambda c: c["t_primeiro"]):
        saida.append({
            "box": len(saida) + 1, "x": round(c["x"]), "y": round(c["y"]),
            "trecho": trecho(c["x"], c["y"]), "kills": c["kills"],
            "voltas": len(c["voltas"]), "dwell_s": c["dwell"], "dano": c["dano"],
            "dano_por_bicho": round(c["dano"] / c["kills"]),
            "kills_min": round(60 * c["kills"] / max(1, c["dwell"]), 1),
            "especies": dict(c["especies"].most_common(4)),
            "quem_bateu": {k: round(100 * v / max(1, c["dano"])) for k, v in c["quem"].most_common(3)},
        })

    print(f"\n{len(saida)} box (pontos usados em 6+ kills na sessao)\n")
    print("  #  onde              bichos  voltas  parado  dano/bicho  b/min  trecho")
    for b in saida:
        print(f" {b['box']:>3}  ({b['x']},{b['y']})  {b['kills']:>7} {b['voltas']:>7} "
              f"{b['dwell_s']:>6}s {b['dano_por_bicho']:>10} {b['kills_min']:>6}  {b['trecho']}")

    print("\n=== ranking por dano por bicho (barato -> caro) ===")
    for b in sorted(saida, key=lambda b: b["dano_por_bicho"])[:5]:
        print(f"  MELHOR  box {b['box']:>2} ({b['x']},{b['y']}) {b['trecho']:<16} "
              f"{b['dano_por_bicho']:>5}/bicho · {b['kills']} bichos · {b['kills_min']}/min")
    for b in sorted(saida, key=lambda b: -b["dano_por_bicho"])[:5]:
        print(f"  PIOR    box {b['box']:>2} ({b['x']},{b['y']}) {b['trecho']:<16} "
              f"{b['dano_por_bicho']:>5}/bicho · {b['kills']} bichos · {b['kills_min']}/min")

    print("\n=== por trecho ===")
    agg = collections.defaultdict(lambda: [0, 0, 0, 0])
    for b in saida:
        a = agg[b["trecho"]]
        a[0] += 1; a[1] += b["kills"]; a[2] += b["dano"]; a[3] += b["dwell_s"]
    print("  trecho            box  bichos  parado  dano/bicho  bichos/min")
    for tr, (n, k, dm, dw) in sorted(agg.items(), key=lambda kv: kv[1][2] / max(1, kv[1][1])):
        print(f"  {tr:<16} {n:>4} {k:>7} {dw:>6}s {dm / max(1, k):>11.0f} {60 * k / max(1, dw):>11.1f}")
    tot_k = sum(b["kills"] for b in saida); tot_d = sum(b["dano"] for b in saida)
    print(f"\n  TOTAL {len(saida)} box · {tot_k} bichos · {tot_d / max(1, tot_k):.0f} de dano por bicho")

    jsons = [a for a in sys.argv[2:] if a.endswith(".json")]
    data = session.name.split("_")[1] if "_" in session.name else "hoje"
    p = (pathlib.Path(jsons[0]) if jsons
         else pathlib.Path("hunt_data") / hunt / f"boxes_{data}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print("salvo em", p)


if __name__ == "__main__":
    main()
