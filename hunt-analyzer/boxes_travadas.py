"""Acha TODA vez que o mago fechou a box e ficou TRAVADO, e explica cada uma.

Pedido do user (27/07): mago nao pode tomar box; sempre que acontecer, quero a
analise de onde comecou o erro e como evitar — uma imagem por caso.

Box travada != parada para soltar AoE. A diferenca esta no tempo e na saida:
  - parada normal: 2-6s, ele volta a andar quando quer
  - TRAVADA: >=8s sem sair do tile, pilha >=6 e tomando dano

Origem do erro (heuristica, olhando os 60s anteriores, o mais ANTIGO que valha):
  1. entrou em passagem estreita (poucos tiles andaveis em volta) com pilha grande
  2. deu meia-volta de frente para a pilha (inversao de rumo)
Saida: o tile andavel mais proximo que NAO estava no caminho da pilha.

Uso: python boxes_travadas.py capture\\session_X [dir_saida]
"""
import collections
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am
import lap_watch as lw
import mapa_ingol as mi

PARADO_TILE = 1.2      # deslocamento por amostra que ainda conta como parado
MIN_TRAVA_S = 8        # a partir daqui e trava, nao parada tatica
MIN_PILHA = 6
MIN_DANO = 2500
OLHAR_ATRAS_S = 60
ABERTURA_ESTREITA = 15  # tiles andaveis num 5x5 (25) -> <=15 e passagem estreita
FONTE = r"C:\Windows\Fonts\arialbd.ttf"


def F(s):
    return ImageFont.truetype(FONTE, s)


def sec(h):
    a, b, c = h.split(":")
    return int(a) * 3600 + int(b) * 60 + int(c)


def abertura(walk, x, y, r=2):
    x, y = int(round(x)) - mi.X0, int(round(y)) - mi.Y0
    sub = walk[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1]
    return int((sub == 1).sum())


def achar_travas(W, dano, batalha):
    """Devolve [(t_ini, t_fim, x, y, dano, pilha)] de cada trava."""
    travas, i = [], 0
    while i < len(W) - 1:
        j = i
        while j + 1 < len(W) and W[j + 1][0] - W[j][0] <= 6 and \
                float(np.hypot(W[j + 1][1] - W[i][1], W[j + 1][2] - W[i][2])) <= PARADO_TILE:
            j += 1
        dur = W[j][0] - W[i][0]
        if dur >= MIN_TRAVA_S:
            dmg = sum(v for t, v, _ in dano if W[i][0] - 2 <= t <= W[j][0] + 2)
            pilhas = [n for t, n in batalha.items() if W[i][0] <= t <= W[j][0]]
            pil = max(pilhas) if pilhas else 0
            if dmg >= MIN_DANO and pil >= MIN_PILHA:
                travas.append((int(W[i][0]), int(W[j][0]), float(W[i][1]), float(W[i][2]), dmg, pil))
            i = j
        i += 1
    return travas


def origem_do_erro(W, walk, batalha, t_box, dano):
    """Causa MAIS PROXIMA da trava (a mais antiga explicava mal: no box 8 ficava
    54s antes). Tres causas, todas com numero:
      a) parou com a pilha ainda fechando em chao aberto (corpos, nao parede)
      b) entrou em passagem estreita com pilha grande
      c) deu meia-volta de frente para a pilha
    """
    janela = [(t, x, y) for t, x, y in W if t_box - OLHAR_ATRAS_S <= t < t_box]
    if len(janela) < 4:
        return None
    def pilha(t):
        return max([n for tt, n in batalha.items() if t - 3 <= tt <= t + 3] or [0])
    cand = []
    for k in range(2, len(janela)):
        t, x, y = janela[k]
        pil = pilha(t)
        if pil < 6:
            continue
        ab = abertura(walk, x, y)
        v1 = np.array(janela[k - 1][1:]) - np.array(janela[k - 2][1:])
        v2 = np.array([x, y]) - np.array(janela[k - 1][1:])
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        dmg6 = sum(v for tt, v, _ in dano if t - 6 <= tt <= t)
        if n2 <= 1.0 and pil >= 10 and ab >= 20 and dmg6 >= 2000:
            cand.append((t, x, y, f"parou no meio da pilha ({pil} bichos) em chao aberto, "
                                  f"tomando {dmg6} nos 6s anteriores"))
        elif ab <= ABERTURA_ESTREITA and pil >= 8:
            cand.append((t, x, y, f"entrou em passagem estreita ({ab} de 25 andaveis) com {pil} bichos"))
        elif n1 > 2 and n2 > 2 and float(v1 @ v2) < 0 and pil >= 8:
            cand.append((t, x, y, f"deu meia-volta de frente para a pilha ({pil} bichos)"))
    if not cand:
        return None
    perto = [c for c in cand if t_box - c[0] >= 4]
    return (perto[-1] if perto else cand[-1])


def saida_livre(walk, bx, by, rumo_pilha):
    """Tile andavel mais proximo (raio 6) na direcao OPOSTA a de onde vem a pilha."""
    melhor = None
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            x, y = int(bx) + dx, int(by) + dy
            if walk[y - mi.Y0, x - mi.X0] != 1:
                continue
            d = (dx * dx + dy * dy) ** 0.5
            if d < 2.5 or d > 6:
                continue
            v = np.array([dx, dy]) / d
            score = abertura(walk, x, y) - 12 * float(v @ rumo_pilha)
            if melhor is None or score > melhor[0]:
                melhor = (score, x, y)
    return (melhor[1], melhor[2]) if melhor else None


def rumo_nome(dx, dy):
    ns = "norte" if dy < -1 else ("sul" if dy > 1 else "")
    lo = "leste" if dx > 1 else ("oeste" if dx < -1 else "")
    return (ns + ("-" if ns and lo else "") + lo) or "ao lado"


def _rumo(W, ta, tb):
    """(nome do rumo, vetor, velocidade em tiles/s pelo CAMINHO andado).

    Velocidade pelo comprimento do caminho, nao pelo deslocamento liquido: com
    zigue-zague o liquido subestima o passo e inventava 'diminuiu a velocidade'.
    """
    pts = [(t, x, y) for t, x, y in W if ta <= t <= tb]
    if len(pts) < 2:
        return None, np.zeros(2), 0.0
    dx = pts[-1][1] - pts[0][1]
    dy = pts[-1][2] - pts[0][2]
    caminho = sum(float(np.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]))
                  for i in range(1, len(pts)))
    dt = max(1, pts[-1][0] - pts[0][0])
    return rumo_nome(dx, dy), np.array([dx, dy], dtype=float), caminho / dt


def _dano(dano, ta, tb):
    """dano por 2s na janela."""
    tot = sum(v for t, v, _ in dano if ta <= t <= tb)
    return round(tot / max(1, (tb - ta) / 2))


def narrativa(W, dano, walk, batalha, t_erro, t0, t1, bx, by):
    """As 3 frases da historia: o que ele fez em cada momento (pedido do user)."""
    # 1) a decisao que abriu o problema
    r_antes, vec_a, _ = _rumo(W, t_erro - 10, t_erro)
    r_depois, vec_b, _ = _rumo(W, t_erro, t_erro + 10)
    pil = max([n for t, n in batalha.items() if t_erro - 4 <= t <= t_erro + 4] or [0])
    cos = 0.0
    if np.linalg.norm(vec_a) > 1 and np.linalg.norm(vec_b) > 1:
        cos = float(vec_a @ vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
    if cos < -0.3:
        f1 = f"Deu meia-volta: vinha para {r_antes} e voltou para {r_depois} com {pil} bichos colados"
    elif cos < 0.5:
        f1 = f"Cortou o rumo de {r_antes} para {r_depois} com {pil} bichos colados"
    else:
        f1 = f"Seguiu para {r_depois or r_antes} com {pil} bichos colados, sem abrir distancia"

    # 2) o que mudou entre a decisao e a trava
    meio = (t_erro + t0) // 2
    _, _, v1 = _rumo(W, t_erro, meio)
    _, _, v2 = _rumo(W, meio, t0)
    d1, d2 = _dano(dano, t_erro, meio), _dano(dano, meio, t0)
    if v2 < v1 * 0.75:
        f2 = (f"Diminuiu o passo de {v1:.1f} para {v2:.1f} tiles/s e deixou o lure reencostar "
              f"(dano por 2s subiu de {d1} para {d2})")
    elif d2 > d1 * 1.2:
        f2 = (f"Manteve o passo em {v2:.1f} tiles/s, mas a pilha acompanhou: dano por 2s "
              f"de {d1} para {d2}")
    else:
        f2 = (f"Andou a {v2:.1f} tiles/s com a pilha na cola o tempo todo (dano por 2s ~{d2})"
              )

    # 3) o passo que fechou a box
    r_final, _, _ = _rumo(W, t0 - 6, t0)
    ab = abertura(walk, bx, by)
    livres = sum(1 for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))
                 if walk[int(round(by)) + dy - mi.Y0, int(round(bx)) + dx - mi.X0] == 1)
    pilb = max([n for t, n in batalha.items() if t0 <= t <= t1] or [0])
    if ab <= 16:
        f3 = (f"Entrou para {r_final} num canto de {ab} de 25 tiles andaveis ({livres} vizinhos livres) "
              f"e parou: {pilb} bichos fecharam os vizinhos e consolidaram a box")
    else:
        f3 = (f"Parou indo para {r_final} em chao aberto ({ab} de 25 andaveis): os {pilb} bichos "
              f"ocuparam os 8 tiles em volta — box por corpos, nao por parede")
    return [f1, f2, f3]


def render(caso, W, walk, color, saida_png):
    """Mapa com 3 badges numerados + legenda embaixo (rotulo em cima se sobrepoe)."""
    t0, t1, bx, by, dmg, pil = caso["trava"]
    pts = [(bx, by)]
    if caso.get("erro"):
        pts.append((caso["erro"][1], caso["erro"][2]))
    if caso.get("saida"):
        pts.append(tuple(caso["saida"]))
    trecho_rota = [(x, y) for t, x, y in W if caso["t_ini_rota"] <= t <= t1 + 14]
    pts += trecho_rota
    M = 7  # margem em tiles
    xs = [p[0] - mi.X0 for p in pts]; ys = [p[1] - mi.Y0 for p in pts]
    x0, x1 = int(min(xs)) - M, int(max(xs)) + M
    y0, y1 = int(min(ys)) - M, int(max(ys)) + M
    S = max(7, min(15, int(560 / max(x1 - x0, y1 - y0))))
    rgb = am.PAL[color[y0:y1, x0:x1]].astype(float) * 0.30
    w = walk[y0:y1, x0:x1]
    rgb[w == 1] = np.array([150, 150, 162]) * 0.55 + rgb[w == 1] * 0.45
    mapa = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    dr = ImageDraw.Draw(mapa, "RGBA")

    def px(tx, ty):
        return ((tx - mi.X0 - x0) * S + S // 2, (ty - mi.Y0 - y0) * S + S // 2)

    seg = [(t, x, y) for t, x, y in W if caso["t_ini_rota"] <= t <= t1 + 14]
    for i in range(1, len(seg)):
        f = i / len(seg)
        dr.line([px(seg[i - 1][1], seg[i - 1][2]), px(seg[i][1], seg[i][2])],
                fill=(int(90 + 165 * f), int(230 - 170 * f), int(255 - 215 * f), 245), width=7)

    def badge(x, y, n, cor, r=25):
        cx, cy = px(x, y)
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 170), outline=cor + (255,), width=6)
        dr.text((cx, cy), n, font=F(24), fill=cor + (255,), anchor="mm")

    linhas = []
    AMARELO, VERMELHO, VERDE = (255, 205, 60), (255, 70, 70), (60, 235, 110)
    if caso.get("erro"):
        et, ex, ey, motivo = caso["erro"]
        badge(ex, ey, "1", AMARELO)
        d_tile = int(round(((ex - bx) ** 2 + (ey - by) ** 2) ** 0.5))
        linhas.append((AMARELO, f"1  {lw.fmt(et)}  o erro comeca aqui ({t0 - et}s e {d_tile} tiles antes) — {motivo}"))
    badge(bx, by, "2", VERMELHO, 29)
    linhas.append((VERMELHO, f"2  {lw.fmt(t0)}  travou {t1 - t0}s · {dmg:,} de dano · pilha {pil}".replace(",", ".")))
    if caso.get("saida"):
        sx, sy = caso["saida"]
        badge(sx, sy, "3", VERDE)
        d = int(round(((sx - bx) ** 2 + (sy - by) ** 2) ** 0.5))
        linhas.append((VERDE, f"3  a saida livre estava {d} tiles a {rumo_nome(sx - bx, sy - by)}"))

    fs = F(19)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    largura_txt = max([tmp.textlength(t, font=fs) for _, t in linhas] +
                      [tmp.textlength(f"{i + 1}. {t}", font=fs) for i, t in enumerate(caso["fixes"])]) + 60
    Wc = int(max(mapa.size[0], largura_txt))
    TOP = 112
    BOT = 40 + 30 * len(linhas) + 20 + 34 * len(caso["fixes"])
    cap = Image.new("RGB", (Wc, mapa.size[1] + TOP + BOT), (16, 16, 20))
    cap.paste(mapa.convert("RGB"), ((Wc - mapa.size[0]) // 2, TOP))
    dc = ImageDraw.Draw(cap)
    dc.text((18, 30), f"BOX #{caso['n']} · volta {caso['volta'] or 'refill'} · {lw.fmt(t0)}", font=F(27), fill=(255, 255, 255))
    dc.text((18, 70), "linha azul = antes · laranja = o momento da trava · cinza claro = chao andavel",
            font=F(17), fill=(195, 195, 195))
    yy = TOP + mapa.size[1] + 26
    for cor, t in linhas:
        dc.text((18, yy), t, font=fs, fill=cor)
        yy += 30
    yy += 14
    for i, t in enumerate(caso["fixes"]):
        dc.text((18, yy), f"{i + 1}. {t}", font=fs, fill=(255, 190, 120) if i == 0 else (150, 255, 190))
        yy += 34
    cap.save(saida_png)
    mapa.convert('RGB').save(str(saida_png).replace('.png', '_mapa.png'))
    return saida_png


def t_erro_ou(erro, t0):
    return erro[0] if erro else t0 - 30


def main():
    session = pathlib.Path(sys.argv[1])
    out_dir = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    W = [tuple(w) for w in json.loads((session / "walked_live.json").read_text())]
    dano = [tuple(x) for x in json.loads((session / "eventos_sessao.json").read_text())["dano"]]
    color, walk = mi.planos()

    a, z = sec(laps[0]["inicio"]), sec(laps[-1]["fim"])
    batalha = {lw.fsec(f.name): lw.battle_count(f) for f in sorted(session.glob("b_*.png"))
               if a <= lw.fsec(f.name) <= z and lw.fsec(f.name) % 2 == 0}
    print(f"battle list amostrada em {len(batalha)} pontos")

    travas = achar_travas(W, dano, batalha)
    print(f"{len(travas)} travas de {MIN_TRAVA_S}s+ com pilha {MIN_PILHA}+ e {MIN_DANO}+ de dano\n")
    volta_de = {}
    for L in laps:
        for t in range(sec(L["inicio"]), sec(L["fim"]) + 1):
            volta_de[t] = L["volta"]

    casos, feitos = [], []
    for n, tr in enumerate(travas, 1):
        t0, t1, bx, by, dmg, pil = tr
        erro = origem_do_erro(W, walk, batalha, t0, dano)
        t_ini_rota = (erro[0] - 6) if erro else (t0 - 30)
        viz = [(t, x, y) for t, x, y in W if t0 - 12 <= t <= t0]
        rumo = np.array([0.0, 0.0])
        if len(viz) >= 2:
            v = np.array(viz[-1][1:]) - np.array(viz[0][1:])
            if np.linalg.norm(v) > 0:
                rumo = v / np.linalg.norm(v)
        sai = saida_livre(walk, bx, by, -rumo)
        ab = abertura(walk, bx, by)
        if ab <= 16:
            f2 = (f"O tile tinha so {ab} de 25 andaveis em volta: {pil} bichos fecham isso. "
                  f"Nunca pare em passagem estreita com a pilha atras")
        else:
            f2 = (f"O chao era ABERTO ({ab} de 25): quem fechou foram os CORPOS, nao a parede. "
                  f"Pare na borda da pilha, nunca no meio dela")
        if sai:
            d = int(round(((sai[0] - bx) ** 2 + (sai[1] - by) ** 2) ** 0.5))
            f2 += f" — o chao livre estava a {d} tiles a {rumo_nome(sai[0] - bx, sai[1] - by)}"
        fixes = [(f"O erro: {erro[3]}" if erro else
                  "O erro: nao achei gatilho claro nos 60s antes — parou com a pilha ja em cima"), f2]
        hist = narrativa(W, dano, walk, batalha, t_erro_ou(erro, t0), t0, t1, bx, by)
        caso = {"n": n, "volta": volta_de.get(t0), "trava": tr, "erro": erro, "saida": sai,
                "abertura": ab, "fixes": fixes, "t_ini_rota": t_ini_rota, "historia": hist}
        png = out_dir / f"box_{n:02d}_{lw.fmt(t0).replace(':','')}.png"
        render(caso, W, walk, color, png)
        for i, h in enumerate(hist, 1):
            print(f"    {i}. {h}")
        casos.append({**caso, "png": str(png), "erro": list(erro) if erro else None,
                      "trava": list(tr), "saida": list(sai) if sai else None})
        feitos.append(str(png))
        print(f"BOX #{n} volta {caso['volta']} {lw.fmt(t0)}-{lw.fmt(t1)} ({t1-t0}s) "
              f"{dmg} de dano, pilha {pil}, abertura {ab}/25 -> {png.name}")
        if erro:
            print(f"    erro em {lw.fmt(erro[0])}: {erro[3]}")

    (out_dir / "boxes_travadas.json").write_text(json.dumps(casos, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + "\n".join(feitos))


if __name__ == "__main__":
    main()
