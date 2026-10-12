"""Vigia de voltas: acha o inicio da hunt, fecha cada volta e emite o resumo dela.

Ancora = posicao no inicio da volta (dead reckoning). Volta fecha quando o jogador se AFASTA
(> AWAY_TILES sustentado) e RETORNA (< NEAR_TILES), ou no teto de MAX_LAP_S. Ao fechar, processa
o chat da janela e grava o resumo; nao sai, emenda na proxima volta.

O que decide (inicio da hunt, refil, volta x deslocamento) esta em sinais.py e pede sempre duas
confirmacoes independentes (user, 22/09). O que esta sessao escreve:
  laps.jsonl      so volta de verdade, com "tipo": "volta"
  trechos.jsonl   o que fechou mas nao era volta (deslocamento), sem gastar numero de volta
  refills.jsonl   inicio, fim e duracao de cada refil, com os sinais que o confirmaram
  areas.jsonl     as mensagens de subarea do cliente (cidade do caminho, entrada da hunt)
  decisoes.jsonl  uma linha por decisao, com os numeros que a sustentam (auditoria)

Uso: python lap_watch.py capture\\session_YYYYMMDD_HHMMSS [nome do char]
Recomecar a analise do zero: apagar lap_state.json e esses arquivos e relancar.
"""
import collections
import datetime as dt
import functools
import json
import pathlib
import sys
import time

import numpy as np
from PIL import Image

import atlas_build as ab
import dead_reckon as dr
import events_build as ev
import layout
import fontes
import painel_stream
import rotations
import sinais as sg

MAP_CROP = (1692, 52, 1885, 228)
# fechamento da volta por DEAD RECKONING (tiles), nao mais por "cara" do minimapa
# 26/07: Falcon Bastion — loop compacto; 12:09+ guerra de spot deixou o circulo
# ainda menor (raio ~34), entao gatilhos apertados + teto de 8min garante card
AWAY_TILES = 25       # precisa se afastar tanto p/ valer como volta
# 27/07 Ingol: o loop e LARGO (pico 113 tiles) e o residuo do dead reckoning fica
# em ~5 tiles — o retorno bateu 15 tiles e o limiar de 12 PERDEU a volta (o user
# fechou a volta e o vigia so cortou no teto de 8min, ja no meio da volta 2).
NEAR_TILES = 20       # e voltar a menos que isso do ponto de partida
MIN_AWAY_S = 90       # tempo minimo longe
TH_AWAY = 0.11        # (legado, fingerprint)
TH_NEAR = 0.075
MAX_LAP_S = 480       # forca fechamento em 8min (analise em tempo real nao para)
STALL_S = 180         # frames pararam de chegar -> sessao acabou
MIN_PARCIAL_S = 60    # volta cortada pela parada so grava com pelo menos isto
BATTLE_Y_MIN = 24     # abaixo do titulo da Battle List (layout Traps 26/07 tarde); sessao usa o do layout.json
BATTLE_X_MAX = 175

# RubinOT usa XP PRE-nerf-2023 p/ boar (7720) e carnivostrich (7290)
# Ingol/Falcon: char Hetero (rate 7,5 x1,1 VIP = 8,25)
XP_SPECIES = {
    47190: "harpy", 41580: "crape man", 46200: "rhindeer",
    63690: "boar man", 60142: "carnivostrich", 60143: "carnivostrich",
    31185: "falcon knight", 34155: "falcon paladin",
    # 26/07: Traps com XP Gain Rate 675% (boost) — base x6.75
    42525: "falcon knight", 46575: "falcon paladin",
    # 26/07 tarde: rate 450% -> multiplicador REAL = 4.5 x 1.1 VIP = 4.95, ou
    # seja os MESMOS 31185/34155 da linha acima (confirmado 15:34 no chat).
    # 26/07 tarde: hunt Hell, rate 450% x1.1 VIP
    # demon/grimeleech = base Tibia (6000/5900), validar pelo loot
    17100: "hellfire fighter", 18000: "fury", 28116: "vexclaw",
    24480: "hellhound", 52740: "hellflayer",
    27000: "demon", 26550: "grimeleech",
}
# Hell (char Traps: rate 4,5 x1,1 VIP = 4,95) — valores confirmados pelo loot
XP_SPECIES.update({
    18810: "hellfire fighter",  # base 3800
    19800: "fury",              # base 4000
    30927: "vexclaw",           # base 6248
    26928: "hellhound",         # base 5440
    58014: "hellflayer",        # base 11720
})
# Zao/dragoes (custom RubinOT) — descobertos pelo loot em 25/07 22h
XP_SPECIES.update({
    26457: "wardragon",
    22997: "dragolisk",
    35565: "mega dragon",
})
# 27/07 noite, Ingol solo com Hetero: XP Gain Rate do painel = 1125% (= 750% do
# char + 50% de Store Boost, que expira ~09:42) -> multiplicador da MENSAGEM =
# 11,25 x 1,1 VIP = 12,375. Quando o boost cair, volta a valer o set x8,25 acima.
XP_SPECIES.update({
    70785: "harpy",          # base 5720
    62370: "crape man",      # base 5040
    69300: "rhindeer",       # base 5600
    95535: "boar man",       # base 7720
    90213: "carnivostrich",  # base 7290 (x12,375 = 90.213,75)
    90214: "carnivostrich",
})

# 26/07 party: as SUAS linhas de XP somem no flood da janela de 3 linhas; o kill
# vem da linha de LOOT (primario) pareada com o XP do membro da pt (secundario).
# Especie pelo XP do membro: fator = valor observado / base da especie.
PARTY_BASES = {6300: "falcon knight", 6900: "falcon paladin"}
PARTY_FACTOR = 21047 / 6300  # membro da pt, FK confirmado pelo loot 26/07


def party_species(value):
    base = value / PARTY_FACTOR
    for b, name in PARTY_BASES.items():
        if abs(base - b) <= b * 0.02:
            return name
    return "outro"


def fsec(name):
    return int(name[2:4]) * 3600 + int(name[4:6]) * 60 + int(name[6:8])


def to_s(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def fmt(s):
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fingerprint(path):
    g = Image.open(path).convert("L").crop(MAP_CROP).resize((22, 22))
    return np.asarray(g, dtype=float).ravel() / 255.0


@functools.lru_cache(maxsize=None)
def _y_min(pasta):
    return layout.da_sessao(pasta)["battle_y_min"]


def battle_count(path):
    # 21/09: titulo mascarado conforme o layout com que a sessao do frame foi gravada
    return battle_count_bin(ab.binarize(path), _y_min(str(pathlib.Path(path).parent)))


def battle_count_bin(binary, y_min=BATTLE_Y_MIN):
    binary = clean_binary(binary)  # scrollbar/borda emendam as bandas
    binary[:y_min, :] = False
    binary[:, BATTLE_X_MAX:] = False
    # entrada = icone+nome+barra, ate ~21px (pitch entre entradas = 22px)
    return sum(1 for y0, y1 in ab.find_bands(binary) if 6 <= y1 - y0 <= 21)


import re as _re

BATTLE_AMOSTRA_S = 5   # especies da Battle List: 1 quadro a cada 5 s basta (bicho fica > 5 s na lista)


def _sem_artigo(nome):
    return _re.sub(r"^(?:an?|the) ", "", nome.strip().lower())


def _casa_nome(lido, conhecidas):
    """Nome lido na Battle List -> nome conhecido. '?' = glifo que nao decodificou (curinga),
    '...' = nome cortado pelo cliente, palavra que sumiu no comeco = so o fim casa. Sem espacos
    dos dois lados: o espaco estreito da Battle List as vezes some ("Guardian ofTales")."""
    s = " ".join(t for t in lido.lower().split() if t.strip("?."))  # icone/borda viram '?' soltos
    if s in conhecidas:
        return s
    if sum(c.isalpha() for c in s) < 4:
        return None
    rx = _re.compile(".*" + ".*".join(_re.escape(p) for p in _re.split(r"\?+|\.\.\.", s.replace(" ", ""))))
    casou = next((n for n in conhecidas if rx.fullmatch(n.replace(" ", ""))), None)
    if casou:
        return casou
    # nome novo legivel (>= 2 palavras) entra como esta: o integrador filtra pelo catalogo
    return s if _re.fullmatch(r"[a-z'-]{2,}(?: [a-z'-]{2,})+", s) else None


def battle_especies(session, t0, t1, glyphs, conhecidas):
    """{especie: pico de quantas apareceram juntas na Battle List} entre t0 e t1.

    21/09 (user): o nome dos monstros sai tambem da Battle List. So o cinza do texto entra
    (o icone colorido emendava na 1a palavra: "Bramble Wyrmling" saia "? ?rmling").
    """
    import nameplates as npl
    sidx = npl.shape_index(glyphs)
    y_min = _y_min(str(session))
    pico, ult = collections.Counter(), None
    for f in sorted(session.glob("b_*.png")):
        s = fsec(f.name)
        if not (t0 <= s <= t1) or (ult is not None and s - ult < BATTLE_AMOSTRA_S):
            continue
        ult = s
        a = np.asarray(Image.open(f).convert("RGB"))
        mx = a.max(axis=2)
        b = (mx > ab.LUM_T) & (mx - a.min(axis=2) < 30)
        b[:y_min] = False
        b[:, b.sum(axis=0) >= 0.6 * b.shape[0]] = False  # scrollbar/borda
        quadro = collections.Counter()
        for y0, y1 in ab.find_bands(b):
            if ab.BAND_H[0] <= y1 - y0 <= ab.BAND_H[1]:
                # espaco da Battle List tem 4 px (o do chat, 5, colava "Guardian ofTales")
                n = _casa_nome(npl.decode_shape(b[y0:y1], sidx, space_gap=4), conhecidas)
                if n:
                    quadro[n] += 1
        for n, k in quadro.items():
            pico[n] = max(pico[n], k)
    return dict(pico)


def nomes_conhecidos(primeiro=()):
    """Nomes de monstro conhecidos, sem artigo; os de `primeiro` (chat da volta) casam antes."""
    import catalogo
    nomes = list(primeiro)
    nomes += [json.loads(p.read_text(encoding="utf-8")).get("nome", "") for p in catalogo.PASTA.glob("*/*.json")]
    txt = layout.PASTA / "monstros_nomes.txt"
    nomes += txt.read_text(encoding="utf-8").splitlines() if txt.exists() else []
    return list(dict.fromkeys(_sem_artigo(n) for n in nomes if n.strip()))


# largura 190: a scrollbar do painel (x~192+) emenda todas as linhas numa banda so
# top 788 (era 815): no layout Hetero a linha "Raw XP Gain" cai em 814-822 e o
# corte antigo comia 1px dela -> hash do glifo nao casava e o campo sumia.
PANEL_CROP = (0, 788, 190, 1048)  # legado (extract_session); panel_read usa o layout da sessao
SCROLLBAR_X = 168  # x relativo ao crop onde comeca a scrollbar do painel (28/07 pt: thumb na col 170)
# O painel do Hetero nao entrega "Raw XP Gain" nem "Loot" (os glifos dessas duas
# bandas nao estao no atlas), mas entrega "XP Gain" (total, com boost). O proprio
# painel diz que XP/h = Raw XP/h x 12,00 (conferido em 3 frames de 27/07), entao
# o XP RAW da volta = delta de XP Gain / 12. Loot = Balance + Supplies.
PANEL_MULT = 12.0
# (?![\S]) no fim: um glifo desconhecido (�) colado ao valor = valor TRUNCADO —
# rejeitar o campo no frame e deixar o merge pegar num frame integro
PANEL_RX = {
    "xp_gain": _re.compile(r"(?m)^XP Gain: ([\d,]+)(k?)(?!\S)"),
    "raw_xp_gain": _re.compile(r"(?m)^Raw XP Gain: ([\d,]+)(k?)(?!\S)"),
    "raw_xph": _re.compile(r"Raw XP/h: ([\d,]+)(k?)(?!\S)"),
    "loot": _re.compile(r"Loot: ([\d,]+)(k?)(?!\S)"),
    "supplies": _re.compile(r"Supplies: ([\d,]+)(k?)(?!\S)"),
    "balance": _re.compile(r"Balance: (-?[\d,]+)(k?)(?!\S)"),
}


def clean_binary(binary, max_run=40):
    """Apaga trechos verticais continuos > max_run px (bordas de painel,
    scrollbars, barras) que emendam as linhas numa banda so. Glifos tem <20px."""
    H = binary.shape[0]
    for x in range(binary.shape[1]):
        col = binary[:, x]
        y = 0
        while y < H:
            if col[y]:
                y2 = y
                while y2 < H and col[y2]:
                    y2 += 1
                if y2 - y > max_run:
                    col[y:y2] = False
                y = y2
            else:
                y += 1
    return binary


def decode_painel(binary, glyphs, gap):
    """ab.decode_binary para caixa de painel de qualquer altura.

    21/09: decode_binary ignora banda que comeca abaixo de ab.INPUT_TOP (campo de
    digitacao do console); o Party Hunt calibrado tem 517 px e o 4o membro cai em y~331.
    Caixa alta vai em pedacos, cortados numa linha em branco antes do INPUT_TOP.
    """
    out = []
    while len(binary) > ab.INPUT_TOP:
        vazias = np.flatnonzero(~binary[ab.INPUT_TOP - 40:ab.INPUT_TOP].any(axis=1))
        corte = ab.INPUT_TOP - 40 + (int(vazias[-1]) if len(vazias) else 40)
        out += ab.decode_binary(binary[:corte], glyphs, gap)
        binary = binary[corte:]
    return out + ab.decode_binary(binary, glyphs, gap)


def panel_read(session, target_s, glyphs, gap, window_s=90, max_frames=24):
    """Le o Hunting Analyser perto de target_s.

    O painel ROLA (nem toda linha visivel em todo frame), entao cada campo vem
    do frame mais proximo que o mostre, dentro de +-window_s.
    """
    live = fontes.da_sessao(session)['tipo'] == 'twitch'
    if live:
        window_s = min(window_s, 4)
    frames = sorted(session.glob("f_*.png"))
    cands = [f for f in frames if abs(fsec(f.name) - target_s) <= window_s]
    cands.sort(key=lambda f: abs(fsec(f.name) - target_s))
    hunt = layout.da_sessao(session)["hunt"]  # 21/09: caixa do Hunt Analyser da calibracao
    out = {}
    for f in cands[:max_frames]:
        img = Image.open(f).convert("RGB").crop(tuple(hunt["box"]))
        # thumb da scrollbar (claro) atravessa as linhas de cima e funde as
        # bandas do line-finder — apagar a coluna dele antes de decodificar
        img.paste((0, 0, 0), (hunt["scroll_x"], 0, img.width, img.height))
        if live:
            with Image.open(f) as inteiro:
                lidos, _ = painel_stream.ler_quadro(inteiro, session, tuple(hunt['box']), hunt['scroll_x'])
            nomes = {'xp_gain': 'XPGain', 'raw_xp_gain': 'RawXPGain', 'raw_xph': 'RawXP/h',
                     'loot': 'Loot', 'supplies': 'Supplies', 'balance': 'Balance'}
            return {k: lidos[v] for k, v in nomes.items() if v in lidos}
        binary = clean_binary(ab.binarize_arr(np.asarray(img)))
        text = "\n".join(decode_painel(binary, glyphs, gap))
        for key, rx in PANEL_RX.items():
            if key in out:
                continue
            m = rx.search(text)
            if m:
                v = int(m.group(1).replace(",", ""))
                if m.group(2) == "k":
                    v *= 1000
                out[key] = v
        if len(out) == len(PANEL_RX):
            break
    return out


SPELL_PREFIXES = ("exevo", "exori", "exura", "exana", "utani", "utamo", "utura", "utevo", "uteri", "exeta", "adori", "adevo")


def frame_messages_keep(path, glyphs, gap):
    """Como ev.frame_messages, mas mantem linhas com glifo desconhecido (icones)."""
    msgs, started = [], False
    for line in ab.decode_frame(path, glyphs, gap, input_top=None):
        m = ev.TS.match(line)
        if m:
            started = True
            msgs.append([m.group(1), m.group(2)])
        elif started and msgs:
            msgs[-1][1] += " " + line
    return [(t, b) for t, b in msgs]


def lane_events(session, prefix, t0, t1, glyphs, gap):
    out = []
    keep = prefix == "s"
    prev, last_ts = [], ""
    for f in sorted(session.glob(f"{prefix}_*.png")):
        s = fsec(f.name)
        if not (t0 <= s <= t1):
            continue
        cur = frame_messages_keep(f, glyphs, gap) if keep else ev.frame_messages(f, glyphs, gap)
        if not cur:
            continue
        if last_ts and all(t < last_ts for t, _ in cur):
            continue
        for ts, body in ev.new_tail(prev, cur):
            kind, data = ev.classify(body)
            out.append({"ts": ts, "kind": kind, "body": body, **data})
            last_ts = max(last_ts, ts)
        prev = cur
    return out


def lap_summary(session, t0, t1, glyphs, gap):
    msgs_events = lane_events(session, "c", t0, t1, glyphs, gap)

    spells = collections.Counter()
    me = getattr(sys.modules[__name__], "CHAR_NAME", None)
    for e in lane_events(session, "s", t0, t1, glyphs, gap):
        if e["kind"] == "speech":
            if me and e.get("actor") != me:
                continue  # canal Spells mostra casts de TODOS os jogadores proximos
            txt = e.get("text", "").replace("�", "").strip()
            if txt.startswith(SPELL_PREFIXES):
                spells[txt] += 1

    kills = collections.Counter()
    outros = collections.Counter()
    loot_species = collections.Counter()
    # 21/09: especies vistas na volta, para achar a cave pelos bichos (o "Loot of" vai para a
    # aba Loot e nao aparece no Server Log): alvo do seu dano, quem te bate e os loots
    especies = collections.Counter()
    campo = {"damage_dealt": "target", "damage_taken": "actor", "loot": "target"}
    xp_total = 0
    heal = 0
    hits = []          # (ts_s, valor) de cada golpe seu
    taken = []         # (ts_s, valor) de cada golpe recebido
    kill_list = []     # (ts_s, especie)
    for e in msgs_events:
        k = e["kind"]
        if e.get(campo.get(k)):
            especies[_re.sub(r"^(?:an?|the) ", "", e[campo[k]].lower())] += 1
        if k == "xp_gain":
            xp_total += e["value"]
            v = e["value"]
            sp = XP_SPECIES.get(v)
            if sp is None:
                # 26/07: kill dividido com outro player da a VOCE uma fracao
                # continua (nao 50%) — chutar especie por faixa erra feio.
                # Rotulo honesto; especies saem dos loots da volta no card.
                sp = "compartilhado"
            kills[sp] += 1
            kill_list.append((to_s(e["ts"]), sp))
            if sp == "outro":
                outros[v] += 1
        elif k == "damage_dealt":
            hits.append((to_s(e["ts"]), e["value"]))
        elif k == "damage_taken":
            taken.append((to_s(e["ts"]), e["value"]))
        elif k in ("heal_self", "healed"):
            heal += e["value"]
        elif k == "loot":
            loot_species[e.get("target", "?")] += 1
    dmg_out = sum(v for _, v in hits)
    dmg_in = sum(v for _, v in taken)
    # 21/09 (user): 2a fonte = Battle List; especies = uniao, contagem = max das fontes
    esp_battle = battle_especies(session, t0, t1, glyphs, nomes_conhecidos(n for n, _ in especies.most_common()))
    for n, k in esp_battle.items():
        especies[n] = max(especies[n], k)

    # sinais de kill UNIFICADOS (26/07 tarde): a janela de 3 linhas + auto-loot
    # + spot dividido derrubam qualquer sinal isolado. Ordem de confianca:
    # xp proprio > loot nomeado > xp de outro player > ouro saqueado; um kill
    # emite varios sinais -> dedupe por proximidade (±3s)
    used_t = [t for t, _ in kill_list]

    def livre(t):
        return all(abs(t - u) > 3 for u in used_t)

    fontes = (
        [(to_s(e["ts"]), e.get("target", "outro"))
         for e in msgs_events if e["kind"] == "loot"],
        [(to_s(e["ts"]), party_species(e["value"]))
         for e in msgs_events if e["kind"] == "xp_player"],
        [(to_s(e["ts"]), "saqueado") for e in msgs_events
         if e["kind"] == "looted" and "gold" in e.get("what", "")],
    )
    for fonte in fontes:
        for t, sp in fonte:
            if livre(t):
                kill_list.append((t, sp))
                used_t.append(t)
    kills = collections.Counter(sp for _, sp in kill_list)

    # catalogo de boxes: rajadas de kill (gap<=25s, min 3), com detalhe por box
    kill_list.sort()
    box_detail = []
    bframes_all = sorted(session.glob("b_*.png"))

    def close_box(burst):
        if len(burst) < 3:
            return
        b0, b1 = burst[0][0], burst[-1][0]
        # lure da box: battle na janela (inclui a juntada de 15s antes do 1o kill)
        bf = [f for f in bframes_all if b0 - 15 <= fsec(f.name) <= b1 + 5]
        lure = [battle_count(f) for f in bf[:: max(1, len(bf) // 30)]]
        box_detail.append({
            "box": len(box_detail) + 1,
            "inicio": fmt(b0), "fim": fmt(b1), "dur_s": b1 - b0,
            "kills": len(burst),
            "especies": dict(collections.Counter(s for _, s in burst)),
            "dmg_in": sum(v for t, v in taken if b0 - 10 <= t <= b1 + 10),
            "dmg_out": sum(v for t, v in hits if b0 - 10 <= t <= b1 + 10),
            "lure_pico": max(lure) if lure else None,
            "lure_medio": round(float(np.mean(lure)), 1) if lure else None,
        })

    cur = []
    for item in kill_list:
        if cur and item[0] - cur[-1][0] > 25:
            close_box(cur)
            cur = []
        cur.append(item)
    close_box(cur)
    n_bursts = len(box_detail)

    # magias inferidas: segundos com >=3 alvos atingidos = 1 cast de AoE
    per_sec = collections.Counter(t for t, _ in hits)
    aoe_casts = sum(1 for n in per_sec.values() if n >= 3)
    single_hits = sum(1 for n in per_sec.values() if n <= 2)

    peaks = []
    bfiles = [f for f in sorted(session.glob("b_*.png")) if t0 <= fsec(f.name) <= t1]
    for f in bfiles[:: max(1, len(bfiles) // 200)]:
        peaks.append(battle_count(f))

    # pulls/boxes por ciclos da battle: vale (<=2) -> pico (>=6) = 1 pull
    pulls, armed = 0, True
    for n in peaks:
        if n <= 2:
            armed = True
        elif n >= 6 and armed:
            pulls += 1
            armed = False
    n_boxes = pulls if peaks else n_bursts

    p0 = panel_read(session, t0, glyphs, gap)
    p1 = panel_read(session, t1, glyphs, gap)

    def delta(key):
        if key in p0 and key in p1:
            return p1[key] - p0[key]
        return None

    return {
        "eventos": len(msgs_events),
        "boxes": n_boxes,
        "boxes_detalhe": box_detail,
        "kills": dict(kills),
        "kills_total": sum(kills.values()),
        "loots": dict(loot_species),
        "especies": dict(especies),
        "especies_battle": esp_battle,
        "xp": xp_total,
        "xp_painel": delta("raw_xp_gain"),
        # XP RAW da volta pelo painel: campo direto quando legivel; senao
        # XP Gain / mult, com mult medido do proprio painel (o rate muda com
        # XP boost — 7,2 boosted vs 4,95 normal no Traps — nunca fixar)
        "xp_raw_painel": (delta("raw_xp_gain") if delta("raw_xp_gain") is not None
                          else (round(delta("xp_gain") / (p1["xp_gain"] / p1["raw_xp_gain"]))
                                if delta("xp_gain") is not None
                                and p1.get("raw_xp_gain") and p1.get("xp_gain")
                                else (round(delta("xp_gain") / PANEL_MULT)
                                      if delta("xp_gain") is not None else None))),
        "profit": delta("balance") if delta("balance") is not None else (
            delta("loot") - delta("supplies")
            if delta("loot") is not None and delta("supplies") is not None else None),
        "loot_delta": delta("loot"),
        "supplies_delta": delta("supplies"),
        "raw_xph_atual": p1.get("raw_xph"),
        "dmg_out": dmg_out,
        "golpes": len(hits),
        "dmg_medio_por_golpe": round(dmg_out / len(hits)) if hits else None,
        "golpe_max": max((v for _, v in hits), default=None),
        "magias": dict(spells.most_common(12)),
        "aoe_casts_inferidos": aoe_casts,
        "golpes_alvo_unico": single_hits,
        "dmg_in": dmg_in,
        "heal": heal,
        "battle_pico": max(peaks) if peaks else None,
        "battle_medio": round(float(np.mean(peaks)), 1) if peaks else None,
        "outro_valores": dict(outros.most_common(8)),
    }


CHAR_NAME = None

# --- deteccao automatica de inicio de hunt -------------------------------
# 22/09 (user): cada decisao pede DUAS confirmacoes independentes. Os sinais, os limiares e a
# medida nas sessoes reais estao em sinais.py; aqui fica so a leitura dos quadros e o log.
# O gatilho de antes ("battle list cheia + andou 25 tiles") abriu a hunt de 22/09 as 06:24:45,
# com o char ainda a caminho, passando pela Livraria de Gelo, e matando ZERO bicho na volta 1.
BATTLE_AMOSTRAS = 40      # quantos b_ da janela leem a Battle List quando nao ha trilha
PASSO_AVAL_S = 10         # de quantos em quantos segundos DE QUADRO a espera reavalia os sinais
RETRO_S = 600             # ate onde o inicio retroativo pode voltar


def pontos_janela(session, t0, t1, hist=()):
    """Amostras {t,z,x,y,battle} da janela: trilha do ao_vivo (absoluta, com andar) quando existe,
    senao o dead reckoning do proprio vigia (relativo, sem andar)."""
    tr = sg.amostras(session, t0, t1)
    if tr:
        return tr
    return [{"t": t, "z": None, "x": p[0], "y": p[1], "battle": None} for t, p in hist if t0 <= t <= t1]


def contagens_battle(session, pontos, t0, t1):
    """Battle List na janela: a da trilha, senao uma amostra dos b_."""
    b = [a["battle"] for a in pontos if a.get("battle") is not None]
    if b:
        return b
    bfs = [f for f in sorted(session.glob("b_*.png")) if t0 <= fsec(f.name) <= t1]
    return [battle_count(f) for f in bfs[:: max(1, len(bfs) // BATTLE_AMOSTRAS)]]


def decide(session, chat, hist, t_agora, t_min):
    """Os tres sinais da janela que termina em t_agora. (log, lugar, pilha, janela_inicio)."""
    t0 = max(t_agora - sg.JANELA_S, t_min)
    pontos = pontos_janela(session, t0, t_agora, hist)
    return (sg.sinal_log(chat.eventos, t0, t_agora),
            sg.sinal_lugar(pontos, t0, t_agora),
            sg.sinal_pilha(contagens_battle(session, pontos, t0, t_agora)),
            t0)


def anota_areas(session, novos):
    """Grava as mensagens "You have left/entered the subarea X" (user, 22/09 item 4).

    Sao a unica pista barata do caminho: em 22/09 elas marcam Edron Castle, Carlin e Isle of the
    Kings na ida e de novo no refil das 08:03. Ficam em areas.jsonl para a tela nao precisar
    reprocessar o chat inteiro da sessao.
    """
    vistas = [e for e in novos if e["kind"] == "area"]
    if vistas:
        with (session / "areas.jsonl").open("a", encoding="utf-8") as fh:
            fh.writelines(json.dumps({"t": e["t"], "quando": e["ts"], "acao": e["acao"],
                                      "area": e["area"], "kind": "area"}, ensure_ascii=False) + "\n"
                          for e in vistas)
    return novos


def anota(session, decisao, **campos):
    """Log interno de decisoes (user, 22/09 item 6): uma linha por decisao, com os numeros."""
    linha = {"quando": fmt(campos.pop("t", 0)), "decisao": decisao, **campos}
    with (session / "decisoes.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def dist_da_ancora(session, lap_start, t_agora, p_dr=None):
    """Tiles entre a posicao de agora e a ancora da volta. Trilha do ao_vivo quando existe (ela ve o
    teleporte do refil); senao o dead reckoning, que trava no teleporte e subestima."""
    tr = sg.amostras(session, lap_start, t_agora)
    if len(tr) >= 2:
        return float(np.hypot(tr[-1]["x"] - tr[0]["x"], tr[-1]["y"] - tr[0]["y"]))
    return float(np.hypot(p_dr[0], p_dr[1])) if p_dr is not None else None


def posicao_da_trilha(pontos, t_agora):
    """Posição relativa sem deriva; não usa ponto futuro, antigo ou outro andar para retorno."""
    atuais = [a for a in pontos if a['t'] <= t_agora]
    if not atuais or t_agora - atuais[-1]['t'] > 3:
        return None
    origem, atual = atuais[0], atuais[-1]
    return ((atual['x'] - origem['x'], atual['y'] - origem['y']),
            atual.get('z') == origem.get('z'))


def hunt_parou(session, chat, t_agora, t_min, dist_ancora=None):
    """Refil/pausa: parou de matar E uma segunda confirmacao (longe, lista vazia ou subarea)."""
    log, _, pilha, t0 = decide(session, chat, [], t_agora, t_min)
    if t_agora - t0 < sg.MIN_JANELA_PAROU_S:
        return False, {}, "janela incompleta"
    return sg.parou(log, pilha, dist_ancora)


def esperar_inicio(session, glyphs, gap, desde=0, chat=None):
    """Segura o vigia ate a hunt (re)comecar. Devolve (inicio, sinais, texto).

    O inicio e RETROATIVO: a confirmacao so fecha depois de ~90 s de evidencia, e a volta abre no
    comeco da sequencia de kills, nao no instante em que a evidencia fechou.
    """
    tracker = dr.Tracker()
    chat = chat or sg.Chat()
    hist, seen = [], set()
    print("aguardando inicio da hunt (nao precisa avisar)...", flush=True)
    ultimo_log, ok_desde, t_min, ultima = 0, None, None, None
    while True:
        frames = [f for f in (sorted(session.glob("m_*.png")) or sorted(session.glob("f_*.png")))
                  if fsec(f.name) >= desde and f.name not in seen]
        anota_areas(session, chat.atualiza(session, glyphs, gap, desde=desde))
        # 22/09: com a trilha do ao_vivo na pasta o dead reckoning nao e usado — e a busca de
        # deslocamento quadro a quadro e a coisa mais cara daqui, so para jogar fora
        usa_dr = not (session / "trilha.jsonl").exists()
        for f in frames:
            seen.add(f.name)
            t = fsec(f.name)
            t_min = t if t_min is None else t_min
            p = tracker.update(f) if usa_dr else None
            if p is not None:
                hist.append((t, p))
            # avalia a cada PASSO_AVAL_S de tempo DE QUADRO, nao de relogio: quem relanca o vigia
            # com uma pilha de quadros atrasados (ou um replay acelerado) decide nos mesmos instantes
            if ultima is not None and t - ultima < PASSO_AVAL_S:
                continue
            ultima = t
            log, lugar, pilha, t0 = decide(session, chat, hist, t, t_min)
            ok, quais, texto = sg.comecou(log, lugar, pilha)
            ok = ok and t - t0 >= sg.MIN_JANELA_S
            ok_desde = (ok_desde or t) if ok else None
            if ok_desde is not None and t - ok_desde >= sg.CONFIRMA_S:
                amplo = sg.sinal_log(chat.eventos, t - RETRO_S, t)
                piso = sg.piso_do_inicio(lugar, max(t - RETRO_S, t_min))
                inicio = sg.inicio_retroativo(amplo["kill_ts"], t, piso) or t
                print(f"HUNT COMECOU as {fmt(inicio)} — {texto}", flush=True)
                anota(session, "hunt comecou", t=t, inicio=fmt(inicio), sinais=quais, numeros=texto,
                      especies_antes=log["especies"])
                return inicio, quais, texto
            if t - ultimo_log >= 60:
                print(f"  {fmt(t)}: ainda esperando — {texto}", flush=True)
                anota(session, "esperando", t=t, sinais=quais, numeros=texto)
                ultimo_log = t
        time.sleep(5)


def main():
    global CHAR_NAME
    session = pathlib.Path(sys.argv[1])
    if len(sys.argv) > 2:
        CHAR_NAME = sys.argv[2]
    state_p = session / "lap_state.json"
    glyphs, gap = ab.load_atlas()

    rot = None  # rotulo sai da FORMA do trajeto (automatico)
    laps_p = session / "laps.jsonl"
    chat = sg.Chat()   # leitor incremental do Server Log: os sinais de kill saem dele

    if state_p.exists():
        st = json.loads(state_p.read_text())
        lap_n = st["lap"]
        # lap_start = null: refill/pausa ou sessao que parou — mantem o numero da volta
        # e espera a hunt voltar (senao a viagem de refill viraria uma "volta" de 8min).
        # 21/09: so com frames novos; os antigos dariam "hunt comecou" no ultimo frame
        # de antes da parada e a volta engoliria o buraco
        antigos = sorted(session.glob("m_*.png")) or sorted(session.glob("f_*.png"))
        lap_start = st["lap_start"] or esperar_inicio(
            session, glyphs, gap, desde=fsec(antigos[-1].name) + 1 if antigos else 0, chat=chat)[0]
    else:
        lap_n = 1
        lap_start = esperar_inicio(session, glyphs, gap, chat=chat)[0]   # segura ate a hunt comecar
    state_p.write_text(json.dumps({"lap": lap_n, "lap_start": lap_start}))

    print(f"vigia: volta {lap_n} desde {fmt(lap_start)} (rotacao = automatica)", flush=True)

    def voltas_boas():
        if not laps_p.exists():
            return []
        todas = [json.loads(l) for l in laps_p.read_text(encoding="utf-8").splitlines() if l.strip()]
        return [L for L in todas if L.get("tipo", "volta") == "volta"]

    def finish(now_s, motivo, path, parcial=False):
        """Fecha o pedaco aberto. Volta de verdade vai para laps.jsonl; deslocamento/refil, para
        trechos.jsonl — e sem gastar numero de volta (user, 22/09 item 2)."""
        prev = voltas_boas()
        label, dist, motivo_rot = rotations.classify(path, prev)
        summ = lap_summary(session, lap_start, now_s, glyphs, gap)
        out = {"volta": lap_n, "rotacao": label, "rotacao_motivo": motivo_rot,
               "inicio": fmt(lap_start), "fim": fmt(now_s),
               "dur_s": now_s - lap_start, "fechada_por": motivo,
               **({"parcial": True} if parcial else {}),
               **rotations.summarize_path(path), **summ,
               "path": [[round(x, 1), round(y, 1)] for x, y in path]}
        med = {"kills": float(np.median([L.get("kills_total") or 0 for L in prev])),
               "raio": float(np.median([L.get("raio_max_tiles") or 0 for L in prev]))} if prev else None
        tipo, porque = sg.classifica_volta(out, medianas=med)
        out["tipo"] = tipo
        anota(session, f"volta {lap_n} fechada como {tipo}", t=now_s, inicio=fmt(lap_start),
              fechada_por=motivo, tipo=tipo, porque=porque, kills=out.get("kills_total"),
              raio=out.get("raio_max_tiles"), percurso=out.get("percurso_tiles"))
        alvo = laps_p if tipo == "volta" else session / "trechos.jsonl"
        line = json.dumps(out if tipo == "volta" else
                          {k: v for k, v in out.items() if k not in ("path", "boxes_detalhe")},
                          ensure_ascii=False)
        with alvo.open("a", encoding="utf-8") as fh:  # nunca perde o resumo
            fh.write(line + "\n")
        if tipo == "volta":
            print("LAP_SUMMARY " + line, flush=True)
        else:
            print(f"TRECHO {tipo} {fmt(lap_start)}-{fmt(now_s)}: {porque}", flush=True)
        return tipo == "volta"

    def corta(t_end, motivo):
        # 21/09: pedaco curto ou sem trajeto nao e volta; o que grava sai "parcial"
        # (a tela tira da mais rapida e das comparacoes)
        grava = t_end - lap_start >= MIN_PARCIAL_S and len(path) >= 2
        return grava and finish(t_end, motivo, path, parcial=True)

    tracker = dr.Tracker()
    path = []
    away_since = None
    last_new = time.time()
    seen = set()
    ultimo_check = lap_start
    ultimo_q = None  # segundo do ultimo quadro visto
    trilha_ativa = False

    while True:
        # rastreio pela lane m_ (1s, recorte HD do Map View); f_ so como fallback
        frames = sorted(session.glob("m_*.png")) or sorted(session.glob("f_*.png"))
        # sinais de kill do Server Log, so os quadros novos; as subareas vao para areas.jsonl
        anota_areas(session, chat.atualiza(session, glyphs, gap, desde=lap_start))
        new = [f for f in frames if f.name not in seen and fsec(f.name) >= lap_start]
        # O motor já ancora o minimapa no mundo. Somar shifts em paralelo acumulava deriva
        # e perdeu o retorno real de 12/10 às 06:38:18 (virou deslocamento aos 8 min).
        pontos_trilha = sg.amostras(session, lap_start)
        mapa_local = (session / 'mapa_local.json').exists()
        for f in new:
            seen.add(f.name)
            last_new = time.time()
            now_s = fsec(f.name)
            if ultimo_q is not None and now_s - ultimo_q > STALL_S:
                # 21/09: buraco na gravacao (desligou e religou na mesma sessao): a volta aberta fecha
                # no ultimo quadro de antes (sem isso o teto de 8 min fechava uma volta de 30 min)
                if corta(ultimo_q, "gravacao parou"):
                    lap_n += 1
                state_p.write_text(json.dumps({"lap": lap_n, "lap_start": None}))
                lap_start = esperar_inicio(session, glyphs, gap, desde=now_s, chat=chat)[0]
                state_p.write_text(json.dumps({"lap": lap_n, "lap_start": lap_start}))
                tracker, path, away_since, seen, ultimo_q = dr.Tracker(), [], None, set(), None
                trilha_ativa = False
                last_new, ultimo_check = time.time(), lap_start
                print(f"--- volta {lap_n} comeca em {fmt(lap_start)}", flush=True)
                break
            ultimo_q = now_s
            p = tracker.update(f)
            mesmo_andar = True
            absoluto = posicao_da_trilha(pontos_trilha, now_s) if not mapa_local else None
            if absoluto is not None:
                if not trilha_ativa:
                    path, away_since = [], None  # nunca misturar as duas origens
                    trilha_ativa = True
                p, mesmo_andar = absoluto
            elif trilha_ativa:
                continue  # lacuna do mapa não devolve o detector para a origem com deriva
            if p is None:
                continue
            path.append(p)
            # refill/depot: sem combate na janela -> descarta a volta parcial e
            # espera a hunt voltar sozinha (o user nao avisa nem na ida nem na volta)
            if now_s - ultimo_check >= 30:
                ultimo_check = now_s
                parou, quais, motivo = hunt_parou(session, chat, now_s, lap_start,
                                                  dist_da_ancora(session, lap_start, now_s, p))
                if parou:
                    # 22/09 (user item 4): o refil comeca no ultimo kill, nao onde foi percebido
                    ultimo_kill = max((e["t"] for e in chat.eventos
                                       if e["t"] <= now_s and e["kind"] in sg.KILL_KINDS), default=now_s)
                    print(f"REFILL as {fmt(ultimo_kill)} — {motivo}; volta {lap_n} parcial descartada", flush=True)
                    anota(session, "refil comecou", t=now_s, inicio=fmt(ultimo_kill), sinais=quais,
                          numeros=motivo, volta_descartada=lap_n)
                    state_p.write_text(json.dumps({"lap": lap_n, "lap_start": None}))
                    lap_start = esperar_inicio(session, glyphs, gap, desde=now_s, chat=chat)[0]
                    with (session / "refills.jsonl").open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"volta_descartada": lap_n, "abriu": fmt(ultimo_kill),
                                             "detectado": fmt(now_s), "inicio": fmt(ultimo_kill),
                                             "fim": fmt(lap_start), "dur_s": lap_start - ultimo_kill,
                                             "sinais": quais, "numeros": motivo}) + "\n")
                    anota(session, "refil acabou", t=lap_start, dur_s=lap_start - ultimo_kill)
                    state_p.write_text(json.dumps({"lap": lap_n, "lap_start": lap_start}))
                    # 22/09: ultimo_q tambem zera — com o valor de antes do refil, o 1o quadro da
                    # volta nova ficava a 8 min do anterior e caia no ramo de "gravacao parou"
                    tracker, path, away_since, seen, ultimo_q = dr.Tracker(), [], None, set(), None
                    trilha_ativa = False
                    last_new = time.time()  # 18/09: sem isto o STALL_S disparava logo apos um refill longo
                    ultimo_check = lap_start
                    print(f"--- volta {lap_n} recomeca em {fmt(lap_start)}", flush=True)
                    break
            d = float(np.hypot(p[0], p[1]))
            if d > AWAY_TILES and away_since is None:
                away_since = now_s
                print(f"afastou as {fmt(now_s)} ({d:.0f} tiles)", flush=True)
            closed = None
            if mesmo_andar and away_since is not None and d < NEAR_TILES and now_s - away_since >= MIN_AWAY_S:
                closed = f"retorno ao ponto de partida ({d:.0f} tiles)"
            elif now_s - lap_start >= MAX_LAP_S:
                closed = f"tempo maximo ({MAX_LAP_S // 60}min)"
            if closed:
                # deslocamento nao gasta numero de volta: a proxima volta reancora aqui
                if finish(now_s, closed, path):
                    lap_n += 1
                lap_start = now_s
                state_p.write_text(json.dumps({"lap": lap_n, "lap_start": lap_start}))
                tracker = dr.Tracker()
                trilha_ativa = False
                path = []
                away_since = None
                seen = {f.name}
                print(f"--- volta {lap_n} comeca em {fmt(lap_start)}", flush=True)
                break
        if time.time() - last_new > STALL_S:
            t_end = max((fsec(f.name) for f in frames), default=lap_start)
            grava = corta(t_end, "sessao parou")
            # relancado, segue na volta seguinte (ou na mesma, se nada foi gravado) e espera a hunt voltar
            state_p.write_text(json.dumps({"lap": lap_n + 1 if grava else lap_n, "lap_start": None}))
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
