"""Recortes da janela do jogo, relativos a ela (como no capture.py).

21/09 (user): a calibracao marca as regioes e a captura e os leitores seguem o que ela
marcou. Cada sessao guarda o layout com que foi gravada em layout.json; sessao sem ele
(gravada antes de 21/09 a tarde) usa LEGADO.

Chaves: chat/spell/battle/map/tela = retangulos {left, top, width, height};
hunt/party = caixa (x0, y0, x1, y1) nos f_ + scroll_x (onde a scrollbar comeca dentro
da caixa; = largura quando a caixa ja deixa a scrollbar de fora); battle_y_min = linhas
do topo do recorte da Battle List que sao titulo; tile = px por tile na tela do jogo.
"""
import json
import pathlib
import fontes

PASTA = pathlib.Path(__file__).parent
CALIBRACAO = PASTA / "calibracao.json"
REGIOES_OBRIGATORIAS = ('tela', 'server_log', 'mapa', 'battle', 'hunt', 'xp', 'party', 'input', 'supply')


def calibrada(c):
    return bool(c and all((c.get('regioes') or {}).get(k) for k in REGIOES_OBRIGATORIAS))

LEGADO = {
    # 18/09: Server Log no console da DIREITA (lane c_); esquerda = Spells (lane s_)
    "chat": {"left": 963, "top": 972, "width": 590, "height": 48},
    "spell": {"left": 368, "top": 972, "width": 588, "height": 48},
    # 18/09: 2a coluna da esquerda, titulo em y=232-246 (mascarado por battle_y_min),
    # conteudo 250-780, scrollbar em x>=342 fora. Lista vazia -> 0.
    "battle": {"left": 192, "top": 226, "width": 150, "height": 554},
    "battle_y_min": 24,
    # 18/09: bola do pin medida em (1740.9,123.4) abs -> mesmo pixel do MAP_CROP do pin_detect
    "map": {"left": 1694, "top": 48, "width": 193, "height": 176},
    # 18/09 08:24: borda esquerda do painel entrava no recorte (x 0-3 brancas) -> caixa em x=4
    "hunt": {"box": [4, 788, 190, 1048], "scroll_x": 164},
    # 18/09: titulo y=445; 3 membros acabam em ~760 (Fur Backpack abaixo NAO pode entrar);
    # 07:19 o painel encolheu 2px e a scrollbar caiu em x=158
    "party": {"box": [1578, 440, 1750, 770], "scroll_x": 155},
    # ue_alerta: jogador em (955,435) +- 7,5 tiles de 62 px (coach_2p)
    "tela": {"left": 490, "top": 87, "width": 930, "height": 696},
    "tile": 62,
}

# ponta do pin (pin_detect.PIN_TIP_PX) dentro do recorte m_ de 193x176
PIN_TIP = (55, 84)
MAP_WH = (193, 176)


def recorte_mapa(m):
    """Recorte m_ (MAP_WH) do Map View marcado: ponta do pin = centro do Map View + (2,5; -2,5)."""
    px = round(m["left"] + m["width"] / 2 + 2.5)
    py = round(m["top"] + m["height"] / 2 - 2.5)
    return {"left": px - PIN_TIP[0], "top": py - PIN_TIP[1], "width": MAP_WH[0], "height": MAP_WH[1]}


def da_calibracao(c):
    """Layout a partir do calibracao.json. Spells é uma região opcional (08/10).
    Ajustes medidos no calibracao_print.png (21/09)."""
    r = c["regioes"]

    def caixa(k):
        g = r[k]  # scroll_x = largura: a regiao calibrada ja deixa a scrollbar de fora
        return {"box": [g["left"], g["top"], g["left"] + g["width"], g["top"] + g["height"]],
                "scroll_x": g["width"]}

    b = r["battle"]
    return {
        "chat": dict(r["server_log"]),
        **({"spell": dict(r["spells"])} if r.get("spells") else {}),
        # sobe 19 px: sem isso o 1o bicho emenda na borda do titulo; corta 16 px embaixo:
        # o rodape do painel vira uma banda e conta um bicho a mais
        "battle": {"left": b["left"], "top": b["top"] - 19, "width": b["width"], "height": b["height"] + 19 - 16},
        "battle_y_min": 24,
        "map": recorte_mapa(r["mapa"]),  # recorte m_ igual ao do LEGADO
        "hunt": caixa("hunt"),
        "party": caixa("party"),
        "tela": dict(r["tela"]),
        "tile": c.get("tile_px") or LEGADO["tile"],
    }


def atual():
    """Layout para gravar agora: o da calibracao, senao LEGADO."""
    calibracao, _ = fontes.caminhos()
    if calibracao.exists():
        return da_calibracao(json.loads(calibracao.read_text(encoding="utf-8")))
    return LEGADO


def da_sessao(sessao):
    """Layout com que a sessao foi gravada."""
    p = pathlib.Path(sessao) / "layout.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else LEGADO
