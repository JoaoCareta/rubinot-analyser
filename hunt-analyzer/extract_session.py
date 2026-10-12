"""Extrai o que importa de uma sessao ANTES de apagar os frames.

Gera <session>/summary.json com: janela de tempo, painel final (Hunting
Analyser lido do ultimo frame legivel), totais de eventos por tipo, atores
terceiros (KS) e o resumo das voltas. Depois disso os PNGs sao descartaveis.

Uso: python extract_session.py capture\\session_YYYYMMDD_HHMMSS
"""
import collections
import json
import pathlib
import sys

import atlas_build as ab
import lap_watch as lw


def fsec(name):
    return int(name[2:4]) * 3600 + int(name[4:6]) * 60 + int(name[6:8])


def painel_final(session, glyphs, gap, tentativas=25):
    """Le o painel nos ultimos frames (o painel rola: junta campo a campo).
    21/09: pelo lw.panel_read, que usa a caixa do Hunt Analyser do layout da sessao
    (sessao gravada com a calibracao nao tem o painel no PANEL_CROP fixo)."""
    frames = sorted(session.glob("f_*.png"))
    if not frames:
        return {}
    return lw.panel_read(session, fsec(frames[-1].name), glyphs, gap, window_s=10 ** 6, max_frames=tentativas)


def main(path):
    session = pathlib.Path(path)
    glyphs, gap = ab.load_atlas()
    out = {"sessao": session.name}

    frames = sorted(session.glob("f_*.png"))
    if frames:
        out["inicio"] = frames[0].name[2:8]
        out["fim"] = frames[-1].name[2:8]
        out["dur_s"] = fsec(frames[-1].name) - fsec(frames[0].name)
        out["painel_final"] = painel_final(session, glyphs, gap)

    ev_p = session / "events.jsonl"
    if ev_p.exists():
        kinds = collections.Counter()
        outros = collections.Counter()
        xp_outros = collections.Counter()
        min_tot, min_ks = set(), set()
        dmg_me = xp_me = dmg_in = heal = 0
        especies = collections.Counter()
        for line in open(ev_p, encoding="utf-8"):
            e = json.loads(line)
            h, m, s = map(int, e["ts"].split(":"))
            min_tot.add(h * 60 + m)
            k = e["kind"]
            kinds[k] += 1
            v = e.get("value") or 0
            if k == "damage_dealt":
                dmg_me += v
            elif k == "damage_taken":
                dmg_in += v
            elif k in ("heal_self", "healed"):
                heal += v
            elif k == "xp_gain":
                xp_me += v
                sp = lw.XP_SPECIES.get(v)
                especies[sp or "?"] += 1
            elif k == "damage_dealt_player":
                a = e.get("actor") or "?"
                outros[a] += v
                min_ks.add(h * 60 + m)
            elif k == "xp_player":
                xp_outros[e.get("actor") or "?"] += v
        tot_o = sum(outros.values())
        out["eventos"] = dict(kinds.most_common())
        out["voce"] = {"dano_dado": dmg_me, "dano_tomado": dmg_in, "heal": heal, "xp_chat": xp_me}
        out["especies_por_xp"] = dict(especies.most_common())
        out["ks"] = {
            "pct_dano_terceiros": round(100 * tot_o / (dmg_me + tot_o), 1) if dmg_me + tot_o else 0,
            "minutos_disputados": len(min_ks),
            "minutos_totais": len(min_tot),
            "atores": [{"nome": a, "dano": v, "xp": xp_outros.get(a, 0)}
                       for a, v in outros.most_common(8)],
        }

    laps_p = session / "laps.jsonl"
    if laps_p.exists():
        laps = [json.loads(l) for l in open(laps_p, encoding="utf-8-sig") if l.strip()]
        out["voltas"] = [{
            "volta": L.get("volta"), "rotacao": L.get("rotacao"),
            "inicio": L.get("inicio"), "fim": L.get("fim"), "dur_s": L.get("dur_s"),
            "kills": L.get("kills_total"), "especies": L.get("kills"),
            "xp": L.get("xp"), "profit": L.get("profit"),
            "supplies": L.get("supplies_delta"),
            "dmg_out": L.get("dmg_out"), "dmg_in": L.get("dmg_in"), "heal": L.get("heal"),
            "battle_medio": L.get("battle_medio"),
            "boxes": [{k: b.get(k) for k in
                       ("box", "inicio", "fim", "dur_s", "kills", "especies",
                        "dmg_in", "dmg_out", "lure_pico", "lure_medio")}
                      for b in L.get("boxes_detalhe", [])],
        } for L in laps]

    w = session / "walked_live.json"
    if w.exists():
        out["trajetoria_pts"] = len(json.loads(w.read_text()))

    (session / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{session.name}: summary.json gravado "
          f"({len(out.get('voltas', []))} voltas, KS {out.get('ks', {}).get('pct_dano_terceiros', '-')}%)")


if __name__ == "__main__":
    main(sys.argv[1])
