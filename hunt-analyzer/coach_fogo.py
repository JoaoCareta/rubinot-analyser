"""Coach de box do ED em pt (Livraria de Fogo, 18/09) — lente: mago em box = ERRO.

Trava = ED parado (<=1,2 tile por amostra) por >= 8s com pilha >= 6 na battle e
tomando dano. Ranqueia pelo dano tomado pelo ED e renderiza 2 paineis
(viewport do momento + mapa do andar com o ponto) com EXATAMENTE 2 ajustes.

Uso: python coach_fogo.py capture\\session_X <volta_ini> <volta_fim> <saida.png>
"""
import json
import os
import pathlib
import re
import sys
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import atlas_build as ab
import coach_2p
import lap_watch as lw
import loe_mapa
from lap_watch import to_s

FONTE = r"C:\Windows\Fonts\arialbd.ttf"
EK = os.environ.get("EK_NOME", "Infortunio")
PARADO_TILE, MIN_TRAVA_S, MIN_PILHA, MIN_DANO = 1.2, 8, 6, 2500
RX_ME = re.compile(r"^(\d\d:\d\d:\d\d) You lose (\d+) hitpoints due to an attack by (an? [\w' -]+)")
RX_EK = re.compile(r"^(\d\d:\d\d:\d\d) (\w+) loses (\d+) hitpoints")
RX_SIO = re.compile(r"^(\d\d:\d\d:\d\d) You heal (\w+) for (\d+)")


def F(s):
    return ImageFont.truetype(FONTE, s)


def linhas(session, t0, t1):
    glyphs, gap = ab.load_atlas()
    out, vistos = [], set()
    for c in sorted(session.glob("c_*.png")):
        t = lw.fsec(c.name)
        if not (t0 - 5 <= t <= t1 + 5):
            continue
        arr = np.asarray(Image.open(c).convert("RGB"))
        for l in ab.decode_binary(ab.binarize_arr(arr), glyphs, gap):
            if l not in vistos:
                vistos.add(l)
                out.append(l)
    return out


def eventos(session, t0, t1):
    me, ek, sio = [], [], []
    for l in linhas(session, t0, t1):
        m = RX_ME.match(l)
        if m:
            me.append((to_s(m.group(1)), int(m.group(2)), m.group(3)))
            continue
        m = RX_EK.match(l)
        if m and m.group(2) == EK:
            ek.append((to_s(m.group(1)), int(m.group(3))))
            continue
        m = RX_SIO.match(l)
        if m and m.group(2) != "yourself":
            sio.append((to_s(m.group(1)), m.group(2), int(m.group(3))))
    return me, ek, sio


def battle_por_t(session, t0, t1):
    out = {}
    for b in sorted(session.glob("b_*.png")):
        t = lw.fsec(b.name)
        if t0 <= t <= t1 and int(t) not in out:
            out[int(t)] = lw.battle_count(b)
    return out


def travas(session, pts, t0, t1, me, bat):
    """Janelas paradas com pilha e dano. pts = trajetoria [(t,z,x,y)] ordenada."""
    seq = [p for p in pts if t0 <= p["t"] <= t1]
    out, i = [], 0
    while i < len(seq):
        j = i
        while j + 1 < len(seq) and abs(seq[j + 1]["x"] - seq[i]["x"]) <= PARADO_TILE \
                and abs(seq[j + 1]["y"] - seq[i]["y"]) <= PARADO_TILE and seq[j + 1]["z"] == seq[i]["z"]:
            j += 1
        dur = seq[j]["t"] - seq[i]["t"]
        if dur >= MIN_TRAVA_S:
            ta, tb = seq[i]["t"], seq[j]["t"]
            pil = [v for t, v in bat.items() if ta <= t <= tb]
            dano = [(t, v, esp) for t, v, esp in me if ta <= t <= tb]
            d_tot = sum(v for _, v, _ in dano)
            pilha = float(np.mean(pil)) if pil else 0
            if pilha >= MIN_PILHA and d_tot >= MIN_DANO:
                # direcao de chegada -> "3-4 tiles atras" = contra a chegada
                # (primeiro ponto anterior a >=3 tiles; os 3 ultimos podem ser o mesmo tile)
                k = i - 1
                while k > 0 and abs(seq[i]["x"] - seq[k]["x"]) + abs(seq[i]["y"] - seq[k]["y"]) < 3:
                    k -= 1
                dx, dy = seq[i]["x"] - seq[k]["x"], seq[i]["y"] - seq[k]["y"]
                n = max(1e-6, (dx * dx + dy * dy) ** 0.5)
                out.append({"t": (ta + tb) / 2, "t_ini": ta, "t_fim": tb, "dur": dur, "z": seq[i]["z"],
                            "x": seq[i]["x"], "y": seq[i]["y"], "pilha": pilha, "pilha_max": max(pil),
                            "dano": d_tot, "por_bicho": _agrupa(dano),
                            "seta": (round(-dx / n * 3.5, 1), round(-dy / n * 3.5, 1))})
        i = j + 1
    return sorted(out, key=lambda o: -o["dano"])


def rajadas_ek(ek, sio, limiar=2500, janela=6):
    """Pancadas no EK (>= limiar em `janela` s) e quanto o sio do ED demorou (None = nao veio)."""
    sio_ek = sorted(t for t, alvo, _ in sio if alvo == EK)
    ek = sorted(ek)
    out, i = [], 0
    while i < len(ek):
        j, acc = i, 0
        while j < len(ek) and ek[j][0] - ek[i][0] <= janela:
            acc += ek[j][1]
            j += 1
        if acc >= limiar:
            prox = next((t for t in sio_ek if t >= ek[i][0]), None)
            out.append((ek[i][0], acc, None if prox is None else prox - ek[i][0]))
            i = j
        else:
            i += 1
    return out


def _agrupa(dano):
    acc = {}
    for _, v, esp in dano:
        acc[esp] = acc.get(esp, 0) + v
    return dict(sorted(acc.items(), key=lambda kv: -kv[1]))


def painel_mapa(session, ev, orig, pts_all, colors, walks, laps):
    boxes = []
    for L in laps:
        for b in L.get("boxes_detalhe", []):
            tm = (to_s(b["inicio"]) + to_s(b["fim"])) / 2
            perto = min(pts_all, key=lambda p: abs(p["t"] - tm))
            if abs(perto["t"] - tm) <= 45:
                boxes.append({"t": tm, "z": perto["z"], "x": perto["x"], "y": perto["y"],
                              "kills": b["kills"], "dur": b["dur_s"]})
    zonas = loe_mapa.zonas_de(boxes, walks, orig)
    z = ev["z"]
    meus = [p for p in pts_all if p["z"] == z]
    xs, ys = [p["x"] for p in meus], [p["y"] for p in meus]
    bbox = (int(min(xs)) - 10, int(max(xs)) + 11, int(min(ys)) - 10, int(max(ys)) + 11)
    img = loe_mapa.painel(z, colors[z], orig, pts_all, zonas, bbox, None)
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = (ev["x"] - bbox[0]) * loe_mapa.ESC, (ev["y"] - bbox[2]) * loe_mapa.ESC
    for r, w in ((18, 5), (28, 3)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 70, 70, 255), width=w)
    d.text((cx, cy + 40), f"andar z{z} · {ev.get('rotulo', 'box travada')}", font=F(15), fill=(255, 140, 130),
           anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    return img


def _dica_sio(ek, sio, v0, v1):
    r = rajadas_ek(ek, sio)
    if not r:
        return f"Sem rajada >= 2.500 no EK nas voltas {v0}-{v1} (linhas do Server Log): nada a ajustar no sio."
    lentas = [x for x in r if x[2] is None or x[2] > 6]
    atrasos = sorted(x[2] for x in r if x[2] is not None)
    med = atrasos[len(atrasos) // 2] if atrasos else None
    pior = max(r, key=lambda x: x[1])
    return (f"Sio no EK: {len(lentas)} de {len(r)} pancadas >= 2.500 nas voltas {v0}-{v1} ficaram > 6 s sem sio "
            f"(mediana {med} s; pior {nm(pior[1])} as {lw.fmt(int(pior[0]))}, sio {pior[2] if pior[2] is not None else '—'} s depois). "
            f"Limiar 70% nao dispara na pancada — para AMANHA: EK 70 -> 80% (config validada 27/07). Hoje: RTC nao muda.")


def render(session, ev, dicas, titulo, destino, orig, pts, colors, walks, laps):
    esq, _ = coach_2p._painel_player(session, ev["t"], ev["seta"])
    dir_ = painel_mapa(session, ev, orig, pts, colors, walks, laps)
    CEL = 860
    CAB, PE = 74, 40 + 70 * len(dicas)
    alt = max(esq.size[1] * CEL // esq.size[0], dir_.size[1] * CEL // dir_.size[0])
    alt = min(alt, 700)
    canvas = Image.new("RGB", (CEL * 2 + 12, alt + CAB + PE), (16, 16, 20))
    for i, im in enumerate((esq, dir_)):
        esc = min(CEL / im.size[0], alt / im.size[1])
        im2 = im.convert("RGB").resize((int(im.size[0] * esc), int(im.size[1] * esc)), Image.LANCZOS)
        canvas.paste(im2, (i * (CEL + 12) + (CEL - im2.size[0]) // 2, CAB + (alt - im2.size[1]) // 2))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.size[0], CAB - 8], fill=(12, 12, 16))
    d.text((16, (CAB - 8) // 2), titulo, font=F(26), fill=(255, 255, 255), anchor="lm")
    yy = CAB + alt + 20
    for i, t_ in enumerate(dicas, 1):
        for j, ln in enumerate(textwrap.wrap(f"{i}. {t_}", 150)):
            d.text((16 + (28 if j else 0), yy), ln, font=F(19), fill=(255, 190, 120) if i == 1 else (150, 255, 190))
            yy += 26
        yy += 12
    canvas.save(destino)
    return destino


def nm(v):
    """3618 -> '3.618' (milhar com ponto, padrao do user)."""
    return f"{int(round(v)):,}".replace(",", ".")


def main():
    session = pathlib.Path(sys.argv[1])
    v0, v1 = int(sys.argv[2]), int(sys.argv[3])
    destino = sys.argv[4]
    laps = [json.loads(l) for l in (session / "laps.jsonl").read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    laps_sel = [L for L in laps if v0 <= L["volta"] <= v1]
    t0, t1 = to_s(laps_sel[0]["inicio"]), to_s(laps_sel[-1]["fim"])
    orig, pts, _, _ = loe_mapa.carrega(session)
    zs = tuple(orig.get("zs", (12, 13)))
    colors = {z: np.load(f"{loe_mapa.PREFIX}_z{z}_color.npy") for z in zs}
    walks = {z: np.load(f"{loe_mapa.PREFIX}_z{z}_walk.npy") for z in zs}
    me, ek, sio = eventos(session, t0, t1)
    bat = battle_por_t(session, t0, t1)
    tv = travas(session, pts, t0, t1, me, bat)
    dano_me = sum(v for _, v, _ in me) or 1
    print(json.dumps({"voltas": [v0, v1], "travas": len(tv), "dano_ed_total_linhas": dano_me,
                      "dano_ek_linhas": sum(v for _, v in ek), "sios": len(sio),
                      "sio_alvos": sorted({s[1] for s in sio})}, ensure_ascii=False))
    for o in tv[:5]:
        print(json.dumps({k: v for k, v in o.items()}, ensure_ascii=False))
    if not tv:
        # pt em trem continuo: sem trava classica -> ponto quente = celula 4x4 onde o ED mais apanhou
        print("SEM TRAVA: nenhuma parada >=8s com pilha>=6 e dano>=2500 -> usando ponto quente de dano")
        cel = {}
        for t, v, esp in me:
            p = min(pts, key=lambda q: abs(q["t"] - t))
            if abs(p["t"] - t) <= 3:
                k = (p["z"], int(p["x"] // 4 * 4), int(p["y"] // 4 * 4))
                cel.setdefault(k, []).append((t, v, esp, p))
        if not cel:
            print("sem linhas de dano posicionadas")
            return
        k, hits = max(cel.items(), key=lambda kv: sum(h[1] for h in kv[1]))
        t_pior, v_pior, _, p_pior = max(hits, key=lambda h: h[1])
        ts_hits = sorted(h[0] for h in hits)
        pil = [v for t, v in bat.items() if any(abs(t - th) <= 3 for th in ts_hits)]
        seq = sorted(pts, key=lambda q: q["t"])
        i = next(n for n, q in enumerate(seq) if q is p_pior)
        kk_ = i - 1
        while kk_ > 0 and abs(p_pior["x"] - seq[kk_]["x"]) + abs(p_pior["y"] - seq[kk_]["y"]) < 3:
            kk_ -= 1
        dx, dy = p_pior["x"] - seq[kk_]["x"], p_pior["y"] - seq[kk_]["y"]
        n = max(1e-6, (dx * dx + dy * dy) ** 0.5)
        tv = [{"t": t_pior, "t_ini": ts_hits[0], "t_fim": ts_hits[-1], "dur": ts_hits[-1] - ts_hits[0],
               "z": k[0], "x": p_pior["x"], "y": p_pior["y"], "pilha": float(np.mean(pil)) if pil else 0,
               "pilha_max": max(pil) if pil else 0, "dano": sum(h[1] for h in hits),
               "por_bicho": _agrupa([(h[0], h[1], h[2]) for h in hits]),
               "seta": (round(-dx / n * 3.5, 1), round(-dy / n * 3.5, 1)), "passagens": len(hits), "hit_max": v_pior}]
        print(json.dumps(tv[0], ensure_ascii=False))
    ev = tv[0]
    # padrao que se repete > acidente: travas a <=3 tiles da pior
    repeticoes = [o for o in tv[1:] if o["z"] == ev["z"] and abs(o["x"] - ev["x"]) <= 3 and abs(o["y"] - ev["y"]) <= 3]
    ev["repete"] = len(repeticoes)
    # sio durante a pior trava: quantas curas no EK e maior buraco entre pancada grande e sio
    sio_ek = [s for s in sio if s[1] == EK and ev["t_ini"] - 2 <= s[0] <= ev["t_fim"] + 2]
    ek_dano = [(t, v) for t, v in ek if ev["t_ini"] <= t <= ev["t_fim"]]
    pior = max((v for _, v in ek_dano), default=0)
    bicho, dano_bicho = next(iter(ev["por_bicho"].items()), ("?", 0))
    esp = re.sub(r"^an? ", "", bicho)
    blob = sum(v for _, v, e in me if "ink blob" in e)
    if "passagens" in ev:
        ev["rotulo"] = "ponto onde mais apanha"
        titulo = f"COACH · voltas {v0}-{v1} · sem box travada; ponto onde você mais apanha ({lw.fmt(int(ev['t']))})"
        dicas = [
            f"Ponto onde você mais apanha: ({ev['x']:.0f},{ev['y']:.0f}) z{ev['z']} — {nm(ev['dano'])} em {ev['passagens']} hits "
            f"({ev['dano'] / dano_me:.0%} do teu dano nas voltas {v0}-{v1}), maior {nm(ev['hit_max'])} de {esp}, pilha {ev['pilha']:.0f}. "
            f"Aqui, chegar e ficar 3-4 tiles atrás do EK (X verde), não colado.",
            _dica_sio(ek, sio, v0, v1),
        ]
    else:
        titulo = f"COACH · voltas {v0}-{v1} · box travada as {lw.fmt(int(ev['t']))}"
        dicas = [
            f"Parou {ev['dur']:.0f}s no tile ({ev['x']:.0f},{ev['y']:.0f}) z{ev['z']} com pilha {ev['pilha']:.0f} "
            f"(pico {ev['pilha_max']}) e tomou {nm(ev['dano'])} — {ev['dano'] / dano_me:.0%} de tudo que tomou nas voltas {v0}-{v1}; "
            f"{esp} = {nm(dano_bicho)}. "
            + (f"MESMO tile travou mais {ev['repete']}x (total {nm(sum(o['dano'] for o in tv if abs(o['x'] - ev['x']) <= 3 and abs(o['y'] - ev['y']) <= 3))}). " if ev["repete"] else "")
            + "Recuar 3-4 tiles pelo caminho que chegou (X verde).",
            f"Nessa box o EK tomou {nm(sum(v for _, v in ek_dano))} (maior hit {nm(pior)}) e recebeu {len(sio_ek)} sio seu em {ev['dur']:.0f}s "
            f"— de longe, recuado, o sio continua saindo (alcance do sio > alcance da pilha).",
        ]
    render(session, ev, dicas, titulo, destino, orig, pts, colors, walks, laps)
    print("coach salvo:", destino)


if __name__ == "__main__":
    main()
