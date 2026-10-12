"""Card da volta em PT x4 na Livraria de Energy (28/07, char Hetero afeminado).

Profit = delta Balance do painel PARTY HUNT. XP raw = delta Raw XP Gain do
Hunting Analyser pessoal (fallback: delta XP Gain / mult). Bichos = raw / fator
medido na sessao de 24/07 da MESMA pt x4 (22.477.907 raw / 3.520 kills).

Uso: python pt_card.py capture\\session_X [volta]
"""
import json
import os
import pathlib
import re
import sys
import functools

import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw
import layout
import fontes
import painel_stream
import locais
import party_card

# caixas legadas (scripts antigos importam); volta() usa as do layout da sessao (21/09)
PARTY = tuple(layout.LEGADO["party"]["box"])
PARTY_SCROLL_X = layout.LEGADO["party"]["scroll_x"]
PESSOAL = tuple(layout.LEGADO["hunt"]["box"])
PESSOAL_SCROLL_X = layout.LEGADO["hunt"]["scroll_x"]
# raw XP por bicho: a MESMA tabela do programa (locais.py, user 24/09). HUNT_NOME diz qual hunt e
# o painel diz quantos membros; FATOR_BICHOS no ambiente ainda manda, para medir pt nova.
FATOR_ENV = float(os.environ["FATOR_BICHOS"]) if os.environ.get("FATOR_BICHOS") else None
RESET_PAINEL = 1_000_000          # queda maior que isto no Balance = painel resetado, nao prejuizo
JANELA_S = 900                    # o Raw XP/h do XP Analyser olha os ultimos 15 min
PAUSA_S = 360                     # volta >= 6 min dentro da janela = refill/pausa (normal: 2-4 min)
BURACO_S = 60                     # tempo sem volta entre duas voltas acima disto = refill/pausa
# 21/09: sobe quando o leitor muda; card em cache (cards.jsonl) de outra versao e recalculado
VERSAO = 5  # Party Hunt pela mesma leitura de nomes/valores do motor de dano.

# o painel abrevia valores grandes com sufixo k ("XP Gain: 11,529k" = 11.529.000)
RX = {
    "sup": re.compile(r"Supplies:\s*(-?[\d,]+)(k?)$"),
    "bal": re.compile(r"Balance:\s*(-?[\d,]+)(k?)$"),
    "raw": re.compile(r"Raw XP Gain:\s*([\d,]+)(k?)$"),
    "xpg": re.compile(r"(?<!Raw )XP Gain:\s*([\d,]+)(k?)$"),
    # base de preco do loot (Market/Leader): se mudar dentro da volta, o delta de Balance nao vale
    "tipo": re.compile(r"Loot\s?Type:\s*(\w+)$"),
}
# 21/09: no Party Hunt cada membro e uma linha com o nome e 3 linhas de icone + numero
# (balance, dano, cura), sem rotulo "Damage:"; nome = linha sem digito nem ":"
NOME_MEMBRO = re.compile(r"^[^\d:]*[A-Za-z]{3}[^\d:]*$")


@functools.lru_cache(maxsize=1)
def _leitor_party():
    import ks
    return ks.Leitor()


def sec(h):
    a, b, c = h.split(":")
    return int(a) * 3600 + int(b) * 60 + int(c)


def leia(d, glyphs, gap, t, box, scroll_x, chaves, jan=35):
    """Campos do painel nos f_ mais proximos de t. So aceita linha com fim limpo
    (glifo desconhecido no meio dos digitos derruba a amostra, nunca trunca)."""
    out = {}
    live = fontes.da_sessao(d)['tipo'] == 'twitch'
    if live:
        jan = min(jan, 4)
    fs = [f for f in sorted(d.glob("f_*.png")) if abs(lw.fsec(f.name) - t) <= jan]
    fs.sort(key=lambda p: abs(lw.fsec(p.name) - t))
    lay = layout.da_sessao(d)
    eh_party = tuple(box) == tuple(lay['party']['box'])
    char = None
    for nome in ('calibracao.json', 'ks.json'):
        p = d / nome
        if p.exists():
            char = json.loads(p.read_text(encoding='utf-8')).get('char') or char
    for f in fs[:10]:
        img = Image.open(f).convert("RGB").crop(box)
        img.paste((0, 0, 0), (scroll_x, 0, img.width, img.height))
        if eh_party:
            valores, _ = painel_stream.ler(img)
            for k, campo in (('sup','Supplies'), ('bal','Balance'), ('tipo','LootType')):
                if k in chaves and campo in valores and k not in out:
                    out[k] = valores[campo]
            if 'membros' in chaves:
                leitura = _leitor_party().party(f, lay, char)
                if leitura:
                    out['membros'] = 0 if leitura.get('solo') else len(leitura['nomes'])
            if all(k in out for k in chaves):
                break
            continue
        if live:
            with Image.open(f) as inteiro:
                valores, textos = painel_stream.ler_quadro(inteiro, d, box, scroll_x)
            nomes = {'sup': 'Supplies', 'bal': 'Balance', 'raw': 'RawXPGain', 'xpg': 'XPGain', 'tipo': 'LootType'}
            out = {k: valores[nomes[k]] for k in chaves if k in nomes and nomes[k] in valores}
            if 'membros' in chaves:
                out['membros'] = sum(1 for x in textos if NOME_MEMBRO.fullmatch(x) and '?' not in x)
            return out
        # 21/09: a borda da scrollbar acesa so em ~50% da altura ficava abaixo do corte de 60%
        # e emendava Session..Loot numa banda so; trecho vertical > 40 px sai antes
        b = lw.clean_binary(ab.binarize_arr(np.asarray(img)))
        # 18/09: borda/scrollbar que entra no recorte funde todas as bandas -> apagar
        # qualquer coluna branca em >=60% da altura (texto nunca chega perto disso)
        b[:, b.sum(axis=0) >= 0.6 * b.shape[0]] = False
        linhas = [re.sub(r"[�\s]+$", "", x) for x in lw.decode_painel(b, glyphs, gap)]
        if "membros" in chaves:  # maior contagem entre os frames lidos (nome que nao decodificou num frame)
            out["membros"] = max(out.get("membros", 0), sum(1 for x in linhas if NOME_MEMBRO.match(x)))
        for line in linhas:
            for k in chaves:
                if k not in out:
                    m = RX[k].search(line)
                    if m:
                        if k == "tipo":
                            out[k] = m.group(1)
                        else:
                            out[k] = int(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        if all(k in out for k in chaves):
            break
    return out


def raw_15min(d, glyphs, gap, laps, L):
    """(estabilizando, raw dos ultimos 15 min) no fim da volta L.

    21/09 (user): nos 15 primeiros min a pt esta estabilizando a raw; aos 15 min ela
    chega ao limite. Janela que pega o inicio da hunt ou uma pausa = ainda estabilizando.
    ponytail: pausa = volta >= PAUSA_S na janela; trocar pelo refill do lap_watch se errar.
    """
    t1 = sec(L["fim"])
    ini = t1 - JANELA_S
    laps = sorted(laps, key=lambda x: sec(x["inicio"]))
    # 21/09: refill/pausa ENTRE voltas (o lap_watch descarta a parcial) = buraco entre o fim
    # de uma e o inicio da seguinte, dentro da janela
    buraco = any(sec(b["inicio"]) - sec(a["fim"]) > BURACO_S and sec(b["inicio"]) > ini and sec(a["fim"]) < t1
                 for a, b in zip(laps, laps[1:]))
    suja = buraco or sec(laps[0]["inicio"]) > ini or any(
        sec(x["fim"]) > ini and sec(x["inicio"]) < t1 and x.get("dur_s", 0) >= PAUSA_S for x in laps)
    if suja:
        return True, None
    hunt = layout.da_sessao(d)["hunt"]
    a = leia(d, glyphs, gap, ini, tuple(hunt["box"]), hunt["scroll_x"], ["raw"])
    b = leia(d, glyphs, gap, t1, tuple(hunt["box"]), hunt["scroll_x"], ["raw"])
    ok = "raw" in a and "raw" in b and b["raw"] > a["raw"]
    return False, (b["raw"] - a["raw"] if ok else None)


def volta(d, glyphs, gap, L, laps=None):
    t0, t1 = sec(L["inicio"]), sec(L["fim"])
    dur = max(1, t1 - t0)
    lay = layout.da_sessao(d)  # 21/09: caixas da calibracao com que a sessao foi gravada
    party, hunt = (tuple(lay["party"]["box"]), lay["party"]["scroll_x"]), (tuple(lay["hunt"]["box"]), lay["hunt"]["scroll_x"])
    p0 = leia(d, glyphs, gap, t0, *party, ["bal", "sup", "tipo"])
    p1 = leia(d, glyphs, gap, t1, *party, ["bal", "sup", "tipo", "membros"])
    m0 = leia(d, glyphs, gap, t0, *hunt, ["raw", "xpg", "bal", "sup"])
    m1 = leia(d, glyphs, gap, t1, *hunt, ["raw", "xpg", "bal", "sup"])

    # base do loot e tamanho da pt no fim da volta (antes do solo trocar p1 pelo painel pessoal)
    base, membros = p1.get("tipo"), p1.get("membros", 0)
    mesma_base = p0.get("tipo") == p1.get("tipo")
    # 21/09 (user): solo com o Party Hunt na tela mostra o painel zerado e sem membros ->
    # profit/supplies saiam 0; sem membro e sem gasto da pt = solo (pt de verdade gasta supplies)
    # Só painel realmente vazio prova solo; título/campo ilegível é lacuna.
    solo = 'membros' in p1 and membros == 0 and p1.get('sup') == 0 and p1.get('bal') == 0
    # 21/09 (user): supplies da pt inteira E os do jogador — o pessoal vem do Hunt Analyser
    sup_eu = m1["sup"] - m0["sup"] if "sup" in m0 and "sup" in m1 and m1["sup"] >= m0["sup"] else None
    if solo:  # Party Hunt vazio: Balance do painel pessoal
        p0, p1, mesma_base = m0, m1, True
    profit = p1["bal"] - p0["bal"] if "bal" in p0 and "bal" in p1 and mesma_base else None
    supplies = p1["sup"] - p0["sup"] if "sup" in p0 and "sup" in p1 and mesma_base else None
    # 21/09: supplies do painel so crescem; se cairam, ele foi resetado (entrou membro: Balance
    # 5,5 kk -> -329, que o "Balance >= 0" deixava passar como prejuizo de 5,5 kk)
    reset = profit is not None and ((supplies is not None and supplies < 0) or (profit < -RESET_PAINEL and p1["bal"] >= 0))
    if reset:
        # 21/09: painel Party Hunt resetado no meio da volta (Balance 6,08 kk -> 0) ->
        # o delta vira -5 kk. Piso honesto = o que acumulou desde o reset.
        # 22/09: marcado: nao compara com as voltas vizinhas (dava -100% e +322350%)
        profit, supplies = p1["bal"], p1.get("sup")

    dxp_raw = None
    if "raw" in m0 and "raw" in m1 and m1["raw"] > m0["raw"]:
        dxp_raw = m1["raw"] - m0["raw"]
    elif "xpg" in m0 and "xpg" in m1 and m1["xpg"] > m0["xpg"]:
        # painel raw parado na pt: mult medido dos acumulados. 21/09: sem Raw XP Gain legivel, sem
        # raw (o 8,25 fixo era a rate do dono; boost e rate de outro char mudam o mult, nunca fixar)
        mult = next((m["xpg"] / m["raw"] for m in (m1, m0) if m.get("raw") and m.get("xpg")), None)
        dxp_raw = round((m1["xpg"] - m0["xpg"]) / mult) if mult else None

    fator = FATOR_ENV if FATOR_ENV is not None else locais.raw_por_bicho(os.environ.get("HUNT_NOME"), membros)
    kills = round(dxp_raw / fator) if dxp_raw and fator else None  # sem fator conhecido: a contagem fica com o chat
    out = {
        "volta": L["volta"], "inicio": L["inicio"], "fim": L["fim"], "dur_s": dur,
        "xp_raw_painel": dxp_raw, "balance_atual": profit, "supplies": supplies,
        "supplies_eu": sup_eu, "kills_total": kills, "kills_piso_chat": L.get("kills_total"),
        "base": base, "membros": membros, "solo": solo, "reset": reset,
    }
    if not solo:
        out["supplies_pt"] = supplies
    if laps:
        out["estabilizando"], out["xp_raw_15min"] = raw_15min(d, glyphs, gap, laps, L)
    return out


def main():
    d = pathlib.Path(sys.argv[1])
    glyphs, gap = ab.load_atlas()
    laps = [json.loads(l) for l in (d / "laps.jsonl").read_text(encoding="utf-8-sig").splitlines()
            if l.strip()]
    alvo = int(sys.argv[2]) if len(sys.argv) > 2 else laps[-1]["volta"]
    # 3o arg opcional: volta de referencia (rota passa 2x perto da ancora ->
    # comparar metade A com A, B com B)
    ref = int(sys.argv[3]) if len(sys.argv) > 3 else alvo - 1
    atual = volta(d, glyphs, gap, next(L for L in laps if L["volta"] == alvo), laps)
    prev = None
    if ref >= 1:
        prev = volta(d, glyphs, gap, next(L for L in laps if L["volta"] == ref), laps)
    print(party_card.card(atual, prev, hunt=os.environ.get("HUNT_NOME", "Livraria de Fogo"),
                          emoji=os.environ.get("HUNT_EMOJI", "🔥📚")))
    print(json.dumps({"atual": atual, "anterior": prev}, ensure_ascii=False))


if __name__ == "__main__":
    main()
