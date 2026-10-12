"""Caminho COMUM da hunt: mediana das voltas, linha grossa, seta de sentido e
cor pela velocidade (formato fechado com o user em 27/07).

Em vez de desenhar as 22 voltas (vira macarrao), reduz tudo a UMA curva: o anel
e aproximadamente anular, entao para cada fatia angular em volta do centroide
tira-se a mediana do raio e da velocidade. O sentido de cada trecho sai do sinal
da componente tangencial media — nao e chutado.

Saida: hunt_data/<hunt>/caminho_comum.json + reports/caminho_comum_<hunt>.png

Uso: python caminho_comum.py capture\\session_X [saida.png]
"""
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import anchor_map as am
import mapa_ingol as mi

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
BINS = 120          # fatias de 3 graus
SUAVIZA = 5         # janela circular de suavizacao do raio
LARGURA = 13        # px da linha grossa


def F(s):
    return ImageFont.truetype(FONTE, s)


def sec(h):
    a, b, c = h.split(":")
    return int(a) * 3600 + int(b) * 60 + int(c)


def cor_velocidade(v, vmin, vmax):
    """azul (parado/lento) -> verde -> amarelo -> vermelho (rapido)."""
    f = 0.0 if vmax <= vmin else max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
    paradas = [(0.0, (70, 130, 255)), (0.35, (60, 230, 140)),
               (0.70, (250, 215, 60)), (1.0, (255, 90, 60))]
    for (f0, c0), (f1, c1) in zip(paradas, paradas[1:]):
        if f <= f1:
            t = (f - f0) / (f1 - f0)
            return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return paradas[-1][1]


def curva(session, laps):
    """[(x, y, velocidade, sentido_tangencial)] por fatia angular."""
    W = json.loads((session / "walked_live.json").read_text())
    dentro = []
    for L in laps:
        t0, t1 = sec(L["inicio"]), sec(L["fim"])
        seg = [w for w in W if t0 <= w[0] <= t1]
        for i in range(1, len(seg)):
            dt = seg[i][0] - seg[i - 1][0]
            if dt <= 0 or dt > 6:
                continue
            d = math.hypot(seg[i][1] - seg[i - 1][1], seg[i][2] - seg[i - 1][2])
            dentro.append((seg[i][1], seg[i][2], d / dt,
                           seg[i][1] - seg[i - 1][1], seg[i][2] - seg[i - 1][2]))
    P = np.array(dentro)
    cx, cy = float(np.median(P[:, 0])), float(np.median(P[:, 1]))
    ang = np.arctan2(P[:, 1] - cy, P[:, 0] - cx)
    raio = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    idx = ((ang + math.pi) / (2 * math.pi) * BINS).astype(int) % BINS

    r_med, v_med, tang = np.zeros(BINS), np.zeros(BINS), np.zeros(BINS)
    mov = np.zeros((BINS, 2))
    for b in range(BINS):
        m = idx == b
        if m.sum() < 3:
            r_med[b] = np.nan
            continue
        r_med[b] = np.median(raio[m])
        v_med[b] = np.median(P[m, 2])
        a = (b + 0.5) / BINS * 2 * math.pi - math.pi
        # versor tangencial (anti-horario em coordenadas de tela)
        tx, ty = -math.sin(a), math.cos(a)
        tang[b] = float(np.mean(P[m, 3] * tx + P[m, 4] * ty))
        mov[b] = [float(np.mean(P[m, 3])), float(np.mean(P[m, 4]))]
    # preenche fatias vazias e suaviza circularmente
    bons = ~np.isnan(r_med)
    r_med = np.interp(np.arange(BINS), np.arange(BINS)[bons], r_med[bons], period=BINS)
    k = np.ones(SUAVIZA) / SUAVIZA
    r_s = np.convolve(np.r_[r_med, r_med, r_med], k, mode="same")[BINS:2 * BINS]
    v_s = np.convolve(np.r_[v_med, v_med, v_med], k, mode="same")[BINS:2 * BINS]

    pontos = []
    for b in range(BINS):
        a = (b + 0.5) / BINS * 2 * math.pi - math.pi
        pontos.append((cx + r_s[b] * math.cos(a), cy + r_s[b] * math.sin(a), v_s[b],
                       tang[b], float(mov[b][0]), float(mov[b][1])))
    return pontos, (cx, cy), float(np.median(P[:, 2]))


def render(pontos, saida, titulo, vmed):
    color, walk = mi.planos()
    xs = [p[0] - mi.X0 for p in pontos]
    ys = [p[1] - mi.Y0 for p in pontos]
    x0, x1 = int(min(xs)) - 12, int(max(xs)) + 12
    y0, y1 = int(min(ys)) - 12, int(max(ys)) + 12
    rgb = am.PAL[color[y0:y1, x0:x1]].astype(float) * 0.36
    w = walk[y0:y1, x0:x1]
    rgb[w == 1] = rgb[w == 1] * 0.55 + np.array([120, 120, 130]) * 0.45
    S = 11
    img = Image.fromarray(rgb.astype(np.uint8)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
    dr = ImageDraw.Draw(img, "RGBA")

    def px(tx, ty):
        return ((tx - mi.X0 - x0) * S + S // 2, (ty - mi.Y0 - y0) * S + S // 2)

    vs = [p[2] for p in pontos]
    vmin, vmax = float(np.percentile(vs, 10)), float(np.percentile(vs, 90))
    n = len(pontos)
    for i in range(n):
        a, b = pontos[i], pontos[(i + 1) % n]
        cor = cor_velocidade((a[2] + b[2]) / 2, vmin, vmax)
        dr.line([px(a[0], a[1]), px(b[0], b[1])], fill=cor + (255,), width=LARGURA)
    # setas de sentido a cada 10 fatias, na direcao medida
    for i in range(0, n, 10):
        a = pontos[i]
        vx, vy = a[4], a[5]          # vetor medido de movimento naquela fatia
        m = math.hypot(vx, vy)
        if m < 0.5:
            continue
        vx, vy = vx / m, vy / m
        cx, cy = px(a[0], a[1])
        L = 20
        p1 = (cx + vx * L, cy + vy * L)
        p2 = (cx - vx * L * 0.5 - vy * L * 0.55, cy - vy * L * 0.5 + vx * L * 0.55)
        p3 = (cx - vx * L * 0.5 + vy * L * 0.55, cy - vy * L * 0.5 - vx * L * 0.55)
        dr.polygon([p1, p2, p3], fill=(255, 255, 255, 245), outline=(0, 0, 0, 255))

    TOP, BOT = 120, 96
    cap = Image.new("RGB", (img.size[0], img.size[1] + TOP + BOT), (16, 16, 20))
    cap.paste(img.convert("RGB"), (0, TOP))
    dc = ImageDraw.Draw(cap)
    dc.text((18, 32), titulo, font=F(27), fill=(255, 255, 255))
    dc.text((18, 74), f"linha = caminho mais comum das voltas · setas = seu sentido · "
                      f"passo mediano {vmed:.1f} tiles/s", font=F(19), fill=(200, 200, 200))
    # legenda de velocidade
    yb = TOP + img.size[1] + 26
    dc.text((18, yb - 2), "devagar", font=F(18), fill=(200, 200, 200))
    lx = 110
    for i in range(240):
        cor = cor_velocidade(vmin + (vmax - vmin) * i / 239, vmin, vmax)
        dc.line([(lx + i, yb - 6), (lx + i, yb + 16)], fill=cor)
    dc.text((lx + 250, yb - 2), "rapido", font=F(18), fill=(200, 200, 200))
    dc.text((lx, yb + 26), f"{vmin:.1f} tiles/s", font=F(16), fill=(170, 170, 170))
    dc.text((lx + 190, yb + 26), f"{vmax:.1f} tiles/s", font=F(16), fill=(170, 170, 170))
    cap.save(saida)
    return saida


def main():
    import area_hunt
    session = pathlib.Path(sys.argv[1])
    hunt = sys.argv[2] if len(sys.argv) > 2 else "ingol"
    saida = sys.argv[3] if len(sys.argv) > 3 else f"reports/caminho_comum_{hunt}.png"
    area_hunt.aplicar(hunt)
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # delta de painel negativo = analyser resetado no meio da volta — descartar
    laps = [L for L in laps if (L.get("xp_raw_painel") or 0) >= 0]
    pontos, centro, vmed = curva(session, laps)
    dados = {"centro": centro, "passo_mediano": vmed,
             "pontos": [{"x": round(p[0], 1), "y": round(p[1], 1), "vel": round(p[2], 2),
                         "dx": round(p[4], 2), "dy": round(p[5], 2)} for p in pontos]}
    dest = pathlib.Path("hunt_data") / hunt / "caminho_comum.json"
    dest.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print("centro", centro, "| passo mediano", round(vmed, 2), "tiles/s | salvo em", dest)
    print(render(pontos, saida, f"CAMINHO COMUM · {hunt.upper()} z{mi.Z} · {len(laps)} voltas", vmed))


if __name__ == "__main__":
    main()
