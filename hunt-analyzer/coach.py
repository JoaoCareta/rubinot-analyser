"""Coach: transforma o resumo de uma volta em sugestoes acionaveis.

Uso:  python coach.py capture\\session_X\\laps.jsonl
      (ou pipe: o lap_watch grava cada LAP_SUMMARY nesse arquivo)

As sugestoes saem ordenadas por ganho estimado. Cada uma cita o numero que a
justifica — nada de conselho generico.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
MONSTERS = json.loads((HERE / "monsters.json").read_text(encoding="utf-8"))
ELEMENT_OF_SPELL = {"san": "holy", "flam": "fire", "vis": "energy", "frigo": "ice",
                    "tera": "earth", "mort": "death", "moe": "physical"}


def spell_element(name):
    for tok in name.split():
        if tok in ELEMENT_OF_SPELL:
            return ELEMENT_OF_SPELL[tok]
    return None


def main_element(spells):
    """Elemento dominante do kit ofensivo (ignora curas exura/utevo/utani)."""
    votes = {}
    for name, n in spells.items():
        if name.startswith(("exura", "utani", "utamo", "utevo")):
            continue
        el = spell_element(name)
        if el:
            votes[el] = votes.get(el, 0) + n
    return max(votes, key=votes.get) if votes else None


def efficiency_table(element):
    """XP por ponto de dano efetivo, por especie (so as do codex)."""
    rows = []
    for sp, m in MONSTERS.items():
        if sp.startswith("_") or "xp_msg_traps" not in m:
            continue
        mult = m.get("damage_taken", {}).get(element, 1.0)
        if mult <= 0:
            continue
        eff_hp = m["hp"] / mult
        rows.append({"sp": sp, "xp": m["xp_msg_traps"], "eff_hp": eff_hp,
                     "xp_per_dmg": m["xp_msg_traps"] / eff_hp, "mult": mult})
    return sorted(rows, key=lambda r: -r["xp_per_dmg"])


def suggest(lap, prev=None):
    out = []
    kills = {k: v for k, v in lap["kills"].items() if not k.endswith("*")}
    total_kills = sum(kills.values()) or 1
    dur = lap["dur_s"] or 1
    el = main_element(lap.get("magias", {}))

    # 1) mix de alvos vs eficiencia do seu elemento
    if el:
        tab = {r["sp"]: r for r in efficiency_table(el)}
        present = [(sp, n) for sp, n in kills.items() if sp in tab]
        if len(present) >= 2:
            best = max(present, key=lambda kv: tab[kv[0]]["xp_per_dmg"])
            worst = min(present, key=lambda kv: tab[kv[0]]["xp_per_dmg"])
            ratio = tab[best[0]]["xp_per_dmg"] / tab[worst[0]]["xp_per_dmg"]
            if ratio >= 1.25:
                share = worst[1] / total_kills
                out.append((
                    3 * share * (ratio - 1),
                    f"ALVOS: seu dano e {el.upper()}. **{worst[0]}** absorve "
                    f"({int(tab[worst[0]]['mult'] * 100)}% de {el}) e rende "
                    f"{tab[worst[0]]['xp_per_dmg']:.1f} XP por ponto de dano, contra "
                    f"{tab[best[0]]['xp_per_dmg']:.1f} do **{best[0]}** ({ratio:.0%} melhor). "
                    f"Você matou {worst[1]} deles ({share:.0%} da volta) — priorize "
                    f"{best[0]} e deixe {worst[0]} por último."))
        # alvo de maior valor absoluto
        if kills:
            top_xp = max(kills, key=lambda s: MONSTERS.get(s, {}).get("xp_msg_traps", 0))
            xp_top = MONSTERS.get(top_xp, {}).get("xp_msg_traps", 0)
            if xp_top:
                med = sum(MONSTERS.get(s, {}).get("xp_msg_traps", 0) * n for s, n in kills.items()) / total_kills
                if xp_top > med * 1.7:
                    out.append((1.5, f"FOCO: **{top_xp}** vale {xp_top:,} XP — "
                                     f"{xp_top / med:.1f}x a média da volta ({med:,.0f}). "
                                     f"Matou {kills.get(top_xp, 0)}. Sempre foque ele primeiro no pull."))

    # 2) tamanho do pull (AoE rende proporcional aos alvos)
    peak, avg = lap.get("battle_pico"), lap.get("battle_medio")
    if peak and avg and peak >= avg * 1.8 and avg < 6:
        ganho = (min(peak, 8) - avg) / avg
        out.append((2.2, f"PULL: sua battle list ficou em média **{avg}** bichos, mas o pico foi "
                         f"**{peak}** — o spot aguenta bem mais. Puxar até 7-8 antes de soltar o "
                         f"AoE renderia ~{ganho:.0%} mais dano por magia gasta."))

    # 3) proporcao de dano em AoE
    aoe, single = lap.get("aoe_casts_inferidos", 0), lap.get("golpes_alvo_unico", 0)
    if aoe + single > 20:
        frac = aoe / (aoe + single)
        if frac < 0.6:
            out.append((1.8, f"AoE: só **{frac:.0%}** dos seus momentos de dano atingiram 3+ alvos "
                             f"({aoe} de {aoe + single}). Agrupar mais antes do burst sobe esse número."))
        else:
            out.append((0.4, f"AoE ok: {frac:.0%} dos momentos de dano com 3+ alvos."))

    # 4) dano recebido por kill (tendencia)
    dpk = lap["dmg_in"] / total_kills
    if prev:
        pk = sum(v for k, v in prev["kills"].items() if not k.endswith("*")) or 1
        dpk_prev = prev["dmg_in"] / pk
        delta = (dpk - dpk_prev) / dpk_prev
        if delta > 0.15:
            out.append((2.0, f"DEFESA: tomou **{dpk:,.0f}** de dano por kill, {delta:+.0%} vs a volta "
                             f"anterior ({dpk_prev:,.0f}). Sinal de pull maior que o seu sustain ou "
                             f"posicionamento pior — cheque se está no meio do pack."))
        elif delta < -0.12:
            out.append((0.3, f"DEFESA melhorou: {dpk:,.0f} de dano por kill ({delta:+.0%} vs volta anterior)."))

    # 5) ritmo
    kpm = total_kills / (dur / 60)
    if prev:
        kpm_prev = (sum(v for k, v in prev["kills"].items() if not k.endswith("*")) or 1) / (prev["dur_s"] / 60)
        d = (kpm - kpm_prev) / kpm_prev
        tag = "acelerou" if d > 0 else "caiu"
        out.append((0.5 + abs(d) * 2, f"RITMO: **{kpm:.1f} kills/min** ({tag} {abs(d):.0%} vs volta anterior "
                                      f"— {kpm_prev:.1f}). Volta de {dur // 60}m{dur % 60:02d}s."))

    # 6) custo de supply por XP
    sup = lap.get("supplies_delta")
    if sup and lap.get("xp"):
        per_m = sup / (lap["xp"] / 1e6)
        msg = f"SUPPLY: {sup:,} gasto = {per_m:,.0f} por milhão de XP."
        if prev and prev.get("supplies_delta") and prev.get("xp"):
            pm = prev["supplies_delta"] / (prev["xp"] / 1e6)
            msg += f" Volta anterior: {pm:,.0f} ({(per_m - pm) / pm:+.0%})."
        out.append((0.6, msg))

    # 7) kills divididos com outros players
    shared = sum(v for k, v in lap["kills"].items() if k.endswith("*"))
    if shared >= 3:
        out.append((1.0 + shared * 0.1, f"CONCORRÊNCIA: **{shared} kills divididos** com outros players "
                                        f"nesta volta — XP pela metade neles. Se repetir, vale inverter "
                                        f"o sentido da volta ou trocar de andar."))

    out.sort(key=lambda t: -t[0])
    return [m for _, m in out]


def main():
    path = pathlib.Path(sys.argv[1])
    laps = [json.loads(l) for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    lap = laps[-1]
    prev = laps[-2] if len(laps) > 1 else None
    print(f"=== SUGESTÕES — volta {lap['volta']} ({lap['inicio']}–{lap['fim']}) ===")
    for i, s in enumerate(suggest(lap, prev), 1):
        print(f"{i}. {s}")


if __name__ == "__main__":
    main()
