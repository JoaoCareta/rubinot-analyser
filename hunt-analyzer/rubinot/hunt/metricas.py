"""Contrato canônico de métricas; não depende de captura nem persistência."""
import collections
import math

PAUSA_S = 360   # volta de 6 min ou mais = refill/pausa: fora da média (a mesma constante da tela)


def especies(voltas):
    """Espécies da hunt: {nome: mortes}, a mais morta primeiro — a MESMA lista na tela de hunt, no
    resumo guardado e nos bichos da capa do histórico (user, 24/09).

    O motor já tirou de `especies` o que não é bicho e o que é de outra hunt (`_volta`). Sessão em
    que nenhuma volta trouxe espécie cai para o `loots`: antes de 21/09 o loot ainda vinha pelo
    Server Log e era ele que dizia o que morreu.
    """
    vs = [v for v in voltas if (v.get("tipo") or "volta") == "volta"]
    campo = "especies" if any(v.get("especies") for v in vs) else "loots"
    conta = collections.Counter()
    for v in vs:
        conta.update(v.get(campo) or {})
    return dict(conta.most_common())


def taxas(voltas):
    """Os números de um conjunto de voltas — a MESMA conta em toda a tela (user, 24/09: "as fórmulas
    e dados devem ser os mesmos tanto no histórico quanto nas análises").

    Esta é a fonte da verdade; `ui/taxas.js` é a cópia que a tela usa para poder recalcular ao vivo
    e na prévia, e o `_demo` compara as duas com o node para elas nunca desandarem.

    Regras:
      · volta limpa = fechada, não parcial e com menos de PAUSA_S (a volta do refill fica de fora,
        como já ficava na volta média, na mais rápida e na mais lenta)
      · XP raw/h = MEDIANA das voltas limpas com a raw consolidada (15 min × 4 = o número do XP
        Analyser, CLAUDE.md); sem nenhuma consolidada, soma da raw lida ÷ o tempo dessas voltas
      · profit, supplies e bichos = só as voltas em que a medida FOI LIDA, por volta (media) e por
        hora (taxa), numerador e denominador das mesmas voltas — volta sem leitura é lacuna, nunca
        zero (foi o que fez o gráfico dizer 12,10 kk/h numa hunt de 13,90)
    """
    # Math.round da tela arredonda empates para cima; round do Python usa pares.
    arredonda = lambda x: math.floor(x + 0.5)
    vs = [v for v in voltas if (v.get("dur") or 0) > 0 and (v.get("tipo") or "volta") == "volta"]
    limpas = [v for v in vs if not v.get("parcial") and v["dur"] < PAUSA_S]
    est = sorted(v["xp_raw_15min"] * 4 for v in limpas if v.get("xp_raw_15min"))
    com_raw = [v for v in limpas if v.get("xp_raw") is not None]
    seg_raw = sum(v["dur"] for v in com_raw)

    def lidas(k):
        ok = [v for v in limpas if v.get(k) is not None]
        return ok, sum(v["dur"] for v in ok)

    def media(k):
        ok, _ = lidas(k)
        return arredonda(sum(v[k] for v in ok) / len(ok)) if ok else None

    def taxa(k):
        ok, seg = lidas(k)
        return arredonda(sum(v[k] for v in ok) * 3600 / seg) if seg else None

    raw_h = est[len(est) // 2] if est else (arredonda(sum(v["xp_raw"] for v in com_raw) * 3600 / seg_raw) if seg_raw else None)
    return {"voltas": len(limpas), "total": len(vs),
            "parciais": sum(1 for v in vs if v.get("parcial")),
            "refil": len(vs) - len(limpas) - sum(1 for v in vs if v.get("parcial")),
            "dur_s": sum(v["dur"] for v in limpas),
            "dur_media": arredonda(sum(v["dur"] for v in limpas) / len(limpas)) if limpas else None,
            "raw_h": raw_h, "raw_de": "15min" if est else ("soma" if seg_raw else None),
            "voltas_raw": len(com_raw), "voltas_15min": len(est),
            "media": {k: media(j) for k, j in (("profit", "profit"), ("sup_pt", "sup_pt"),
                                               ("sup_eu", "sup_eu"), ("bichos", "bichos"))},
            "taxa": {"profit_h": taxa("profit"), "sup_pt_h": taxa("sup_pt"),
                     "sup_eu_h": taxa("sup_eu"), "bichos_h": taxa("bichos")}}

