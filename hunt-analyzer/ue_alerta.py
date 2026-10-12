"""Alerta sonoro para soltar a UE (mas frigo) NA MAO no melhor momento.

Le a tela sozinho (mss, ~3x/s, nada em disco): conta as BARRAS de HP dentro do RAIO
da UE (21/09: na pilha densa os nomes se fundem e nao decodificam; a barra 31x4 nao)
e escala pela Battle List (exata, sem oclusao, exclui o proprio char; os membros da
pt entram nela). Jogador = barra de mana azul colada embaixo -> fica fora. Apita quando
  (1) tem >= MIN bichos dentro do raio,
  (2) a pilha FECHOU (nao cresceu nos ultimos ESTAVEL_S segundos) e
  (3) a UE esta fora do cooldown (CD_S depois do ultimo apito).
Apito duplo agudo = solta agora. Apito grave (opcional --aviso-cd) = cooldown acabou.

Uso: python ue_alerta.py [--raio 4.5] [--min 6] [--cd 44] [--tile 65] [--player 967,468]
     (sem --tile/--player: tela do jogo e tile do layout da calibracao)
     python ue_alerta.py --calib            # salva z_ue_calib.png com o que ele ve
     python ue_alerta.py --frame f.png      # roda a deteccao num frame salvo (teste)

ponytail: cooldown por timer a partir do apito (nao ve a hotkey); se sobrar tempo,
trocar por hook de teclado (pynput) na tecla da UE.
"""
import argparse
import collections
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

import atlas_build as ab
import capture
import layout
from nameplates import _mask
import lap_watch as lw

# 19/09: a COR do nameplate e o HP da criatura (verde 100%, verde-claro, amarelo, laranja,
# vermelho) — vale p/ bicho E jogador; texto de cast (237,237,0) e sistema (90,214,90) ficam fora.
NAMEPLATE = ((0, 192, 0), (96, 192, 96), (192, 192, 0), (192, 96, 0), (192, 0, 0), (255, 0, 0), (96, 0, 0))

# 21/09: Battle List, tela do jogo e px por tile vem da calibracao (layout.LEGADO = o de antes)
LAYOUT = layout.atual()
MARGEM_TILES = 7.5         # com --player: quanto olhar em volta (bem mais que o raio da UE)


PT_OUTROS = 2              # membros da pt alem de mim (entram na Battle List; eu nao)
BAR_W = (25, 35)           # moldura preta da barra de HP: 31x4 neste cliente


def barras(arr):
    """Barras de HP no recorte: [(x, y, w, fill_px, mana)], x,y = canto sup. esq. da moldura.
    Moldura preta 31x4; fill = 2 linhas na cor do HP ancorado a esquerda; jogador = barra de
    mana azul (0,0,255) colada embaixo (o cliente desenha a mana dos membros da pt)."""
    black = arr.max(axis=2) <= 10
    hp = _mask(arr, NAMEPLATE)
    blue = (arr[:, :, 2] >= 240) & (arr[:, :, 0] <= 15) & (arr[:, :, 1] <= 15)
    H, W = black.shape
    # candidato = canto: borda esquerda preta nas 4 linhas + fill nas linhas 1-2 + topo/base pretos
    c = (black[:-3, :-1] & black[1:-2, :-1] & black[2:-1, :-1] & black[3:, :-1]
         & hp[1:-2, 1:] & hp[2:-1, 1:] & black[:-3, 1:] & black[3:, 1:])
    out = []
    for y, x in np.argwhere(c):
        seg = black[y, x:x + BAR_W[1] + 1]
        w = int(np.argmin(seg)) if not seg.all() else len(seg)
        if not (BAR_W[0] <= w <= BAR_W[1]):
            continue
        x2 = x + w
        if not (black[y + 3, x:x2].all() and black[y + 1, x2 - 1] and black[y + 2, x2 - 1]):
            continue
        inner = slice(x + 1, x2 - 1)
        if not ((black[y + 1, inner] | hp[y + 1, inner]).all() and (black[y + 2, inner] | hp[y + 2, inner]).all()):
            continue
        fill = int(hp[y + 1, inner].sum())
        mana = bool(y + 7 < H and black[y + 4, x:x2].all() and black[y + 7, x:x2].all()
                    and blue[y + 5, x + 1] and blue[y + 6, x + 1])
        out.append((int(x), int(y), w, fill, mana))
    return out


def contar(arr, raio, tile):
    """Bichos (barra sem mana) e distancia em tiles a MINHA barra (a com mana mais perto do centro)."""
    bs = barras(arr)
    h, w = arr.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    eu = [b for b in bs if b[4]]
    if eu:
        b = min(eu, key=lambda b: (b[0] + b[2] / 2 - cx) ** 2 + (b[1] - cy) ** 2)
        cx, cy = b[0] + b[2] / 2.0, b[1] + 1.5
    pts = []
    for x, y, bw, fill, mana in bs:
        px, py = x + bw / 2.0, y + 1.5
        dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 / tile
        nome = "eu" if (mana and dist < 0.01) else ("pt" if mana else "bicho")
        pts.append((px, py, dist, nome))
    bichos = [p for p in pts if p[3] == "bicho"]
    return sum(1 for p in bichos if p[2] <= raio), len(bichos), pts


def estimar(dentro, tela, battle, pt_outros=PT_OUTROS):
    """Bichos no raio = (Battle List - membros da pt) x fracao das barras visiveis que esta no raio.
    ponytail: numeros de dano/texto escondem 30-50% das barras na pilha; a Battle List nao."""
    bichos_tela = max(0, battle - pt_outros)
    return min(bichos_tela, round(bichos_tela * dentro / tela)) if tela else 0


def beep(tipo):
    try:
        import winsound
        if tipo == "solta":
            for _ in range(2):
                winsound.Beep(1500, 160)
                time.sleep(0.05)
        else:
            winsound.Beep(600, 250)
    except Exception:
        print("\a", end="", flush=True)


def area(args):
    """(x0, y0, x1, y1) da area do jogo na janela: a tela do layout, ou --player +- MARGEM_TILES."""
    if args.player is None:
        t = LAYOUT["tela"]
        return t["left"], t["top"], t["left"] + t["width"], t["top"] + t["height"]
    px, py = args.player
    mx, my = int(MARGEM_TILES * args.tile), int(MARGEM_TILES * args.tile * 0.75)
    return px - mx, py - my, px + mx, py + my


def regiao(args):
    g = capture.find_game_rect()
    if not g:
        sys.exit("janela do RubinOT nao encontrada")
    r = g["rect"]
    x0, y0, x1, y1 = area(args)
    return {"left": r["left"] + x0, "top": r["top"] + y0, "width": x1 - x0, "height": y1 - y0}


def desenha(arr, pts, raio, tile, destino):
    im = Image.fromarray(arr)
    d = ImageDraw.Draw(im)
    h, w = arr.shape[:2]
    eu = next((p for p in pts if p[3] == "eu"), None)
    cx, cy = (eu[0], eu[1]) if eu else (w / 2, h / 2)
    r = raio * tile
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(60, 235, 110), width=3)
    d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 70, 70))
    for px, py, dist, nome in pts:
        cor = (60, 235, 110) if dist <= raio else (255, 200, 60)
        d.ellipse([px - 7, py - 7, px + 7, py + 7], outline=cor, width=3)
        d.text((px + 9, py - 6), f"{dist:.1f} {nome[:14]}", fill=cor)
    im.save(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raio", type=float, default=4.5, help="raio da UE em tiles (mas frigo 61 sqm ~ 4,4)")
    ap.add_argument("--min", type=int, default=6, help="bichos dentro do raio para apitar")
    ap.add_argument("--cd", type=float, default=44.0, help="cooldown da UE em s (40 + folga)")
    ap.add_argument("--estavel", type=float, default=1.5, help="s sem a pilha crescer = pilha fechou")
    ap.add_argument("--tile", type=float, default=LAYOUT["tile"])
    ap.add_argument("--player", type=lambda s: tuple(int(v) for v in s.split(",")), default=None,
                    help="centro do personagem na janela (padrao: centro da tela calibrada)")
    ap.add_argument("--pt", type=int, default=PT_OUTROS, help="membros da pt alem de mim (saem da Battle List)")
    ap.add_argument("--aviso-cd", action="store_true", help="apito grave quando o cooldown acabar")
    ap.add_argument("--calib", action="store_true")
    ap.add_argument("--frame")
    args = ap.parse_args()

    if args.frame:
        arr = np.asarray(Image.open(args.frame).convert("RGB").crop(area(args)))
        dentro, tela, pts = contar(arr, args.raio, args.tile)
        desenha(arr, pts, args.raio, args.tile, "z_ue_calib.png")
        print(f"frame: {dentro} dentro do raio / {tela} na tela -> z_ue_calib.png")
        return

    import mss
    reg = regiao(args)
    reg_b = capture.rel_rect(capture.find_game_rect()["rect"], LAYOUT["battle"])
    y_min = LAYOUT["battle_y_min"]
    hist = collections.deque(maxlen=int(args.estavel / 0.33) + 1)
    ultimo_apito, avisou_cd = -1e9, True
    print(f"UE alerta: raio {args.raio} tiles, min {args.min}, cd {args.cd}s, pt {args.pt}, regiao {reg}", flush=True)
    with mss.MSS() as sct:
        grab = lambda r: np.asarray(sct.grab(r))[:, :, :3][:, :, ::-1]
        if args.calib:
            arr = grab(reg)
            dentro, tela, pts = contar(arr, args.raio, args.tile)
            battle = lw.battle_count_bin(ab.binarize_arr(grab(reg_b)), y_min)
            desenha(np.ascontiguousarray(arr), pts, args.raio, args.tile, "z_ue_calib.png")
            print(f"calib: barras {dentro} no raio / {tela} na tela, battle {battle} -> est {estimar(dentro, tela, battle, args.pt)}"
                  " -> z_ue_calib.png (circulo verde = raio; ponto vermelho = minha barra)")
            return
        while True:
            t0 = time.time()
            arr = grab(reg)
            barras_raio, tela, _ = contar(arr, args.raio, args.tile)
            battle = lw.battle_count_bin(ab.binarize_arr(grab(reg_b)), y_min)
            dentro = estimar(barras_raio, tela, battle, args.pt)
            hist.append(dentro)
            em_cd = (t0 - ultimo_apito) < args.cd
            if not em_cd and not avisou_cd:
                avisou_cd = True
                if args.aviso_cd:
                    beep("cd")
            fechou = len(hist) == hist.maxlen and dentro >= max(hist)
            if dentro >= args.min and fechou and not em_cd:
                beep("solta")
                ultimo_apito, avisou_cd = t0, False
                print(f"{time.strftime('%H:%M:%S')} SOLTA! {dentro} no raio (barras {barras_raio}/{tela}, battle {battle})", flush=True)
            else:
                resta = max(0.0, args.cd - (t0 - ultimo_apito))
                print(f"\r{time.strftime('%H:%M:%S')} raio={dentro:2d} barras={barras_raio:2d}/{tela:2d} battle={battle:2d} cd={resta:4.0f}s   ", end="", flush=True)
            time.sleep(max(0.0, 0.33 - (time.time() - t0)))


if __name__ == "__main__":
    main()
