"""Card padrao de fim de volta para hunt em party (formato pedido pelo user).

Mostra SO tres metricas + variacao vs volta anterior. Todo o resto continua
sendo coletado e gravado, apenas nao aparece no card.

Uso: python party_card.py capture\\session_X          (ultima volta)
     python party_card.py capture\\session_X 3        (volta 3)
"""
import json
import pathlib
import sys


def kk(v, casas=2):
    """1_750_000 -> '1,75 kk'. Sempre virgula decimal, sufixo kk."""
    if v is None:
        return "-"
    return f"{v / 1_000_000:.{casas}f}".replace(".", ",") + " kk"


def balance(v):
    """Estilo do painel do jogo em MILHARES: 316000 -> '316k', 1272000 -> '1,272k'."""
    if v is None:
        return "-"
    return f"{v / 1000:,.0f}k"


def pct(atual, anterior):
    """Variacao vs volta anterior. '-' na primeira volta ou sem base."""
    if anterior in (None, 0) or atual is None:
        return "-"
    d = 100.0 * (atual - anterior) / abs(anterior)
    return f"{d:+.0f}%"


def dur(s):
    return f"{s // 60}m{s % 60:02d}"


def selo(p, inverso=False):
    """Emoji do sinal da variacao. inverso: subir e ruim (supplies = gasto)."""
    if p == "-":
        return "–"
    v = int(p.rstrip("%"))
    sobe, desce = ("🔴", "🟢") if inverso else ("🟢", "🔴")
    if v >= 5:
        return f"{sobe} **{p}**"
    if v <= -5:
        return f"{desce} **{p}**"
    return f"⚪ {p}"


def humor(deltas):
    """Emoji do titulo: le o conjunto das variacoes da volta."""
    vs = [int(d.rstrip("%")) for d in deltas if d != "-"]
    if not vs:
        return "📖"
    m = sum(vs) / len(vs)
    return "🔥" if m >= 8 else ("👍" if m > 0 else ("🐌" if m <= -8 else "😐"))


def xph_volta(lap):
    """XP raw/h da volta.

    21/09 (user): a raw so estabiliza 15 min depois de comecar a cacar. Volta com a
    janela de 15 min limpa usa a raw dos ultimos 15 min (o mesmo numero do XP Analyser
    do jogo); sem janela (inicio da hunt, pos-pausa, caminho antigo) usa o delta da volta.
    `raw_xph_atual` e a media da SESSAO inteira — nunca usar.
    """
    if not lap:
        return None
    if lap.get("xp_raw_15min"):
        return lap["xp_raw_15min"] * 4
    v, d = lap.get("xp_raw_painel"), lap.get("dur_s")
    if v and d:
        return round(v * 3600 / d)
    return None  # sem painel legivel na volta: mostrar "-", nunca a media da sessao


def card(lap, prev=None, hunt="Livraria de Fogo", emoji="🔥📚"):
    """Card markdown de uma volta. lap/prev = dicts do laps.jsonl."""
    estab = lap.get("estabilizando")  # raw ainda estabilizando: XP sem comparacao, titulo ⏳
    xph = xph_volta(lap)
    profit = lap.get("balance_atual")
    if profit is None:                      # fallback: acumula os deltas
        profit = lap.get("profit")
    kills = lap.get("kills_total")

    # raw so compara com raw da mesma natureza (janela 15 min x janela 15 min)
    mesma_base = prev is not None and bool(lap.get("xp_raw_15min")) == bool(prev.get("xp_raw_15min"))
    p_xph = xph_volta(prev) if mesma_base and not estab else None
    p_profit = (prev.get("balance_atual") if prev else None)
    if prev and p_profit is None:
        p_profit = prev.get("profit")
    p_kills = prev.get("kills_total") if prev else None

    d = [pct(xph, p_xph), pct(profit, p_profit), pct(kills, p_kills)]
    linhas = [
        ("📈 **XP raw/h**", f"**{kk(xph)}/h**" if xph else "–", selo(d[0])),
        ("💰 **Profit**", f"**{balance(profit)}**", selo(d[1])),
    ]
    # 21/09 (user): supplies da pt inteira e do jogador; em solo so a linha do jogador
    ant = prev or {}
    if "supplies_pt" in lap:
        s = lap["supplies_pt"]
        linhas.append(("🧪 **Supplies da pt**", f"**{balance(s)}**", selo(pct(s, ant.get("supplies_pt")), inverso=True)))
    s = lap.get("supplies_eu", lap.get("supplies"))
    linhas.append(("🧪 **Seus supplies**", f"**{balance(s)}**",
                   selo(pct(s, ant.get("supplies_eu", ant.get("supplies"))), inverso=True)))
    linhas.append(("💀 **Bichos mortos**", f"**{kills}**" if kills is not None else "–", selo(d[2])))
    # da volta 6 em diante: veredicto da correcao pedida no coach da volta anterior
    st = lap.get("coach_status")
    if st:
        icone = {"corrigida": "✅ **corrigida**", "parcial": "🟡 **parcial**",
                 "repetiu": "❌ **repetiu**"}.get(st, st)
        cor = {"corrigida": "🟢", "parcial": "⚪", "repetiu": "🔴"}.get(st, "")
        imp = lap.get("coach_impacto") or "–"
        linhas.append(("🎯 **Box problemática**", icone,
                       f"{cor} **{imp}**" if imp != "–" else "–"))
    head = (f"### {emoji} VOLTA {lap.get('volta')} · {hunt} · "
            f"{dur(lap.get('dur_s', 0))} {'⏳' if estab else humor(d)}")
    tbl = ["| Métrica | Atual | vs volta anterior |", "|---|---|---|"]
    tbl += [f"| {a} | {b} | {c} |" for a, b, c in linhas]
    return head + "\n\n" + "\n".join(tbl)


def main():
    session = pathlib.Path(sys.argv[1])
    laps = [json.loads(l) for l in open(session / "laps.jsonl", encoding="utf-8-sig") if l.strip()]
    alvo = int(sys.argv[2]) if len(sys.argv) > 2 else laps[-1]["volta"]
    i = next(i for i, L in enumerate(laps) if L["volta"] == alvo)
    print(card(laps[i], laps[i - 1] if i else None))


if __name__ == "__main__":
    main()
