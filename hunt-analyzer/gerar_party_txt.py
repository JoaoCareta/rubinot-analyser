"""Reconstroi o export do Party Hunt Analyser a partir dos frames (v2).

Membros: Hetero/Madruga decodificam; Mptres (lider, amarelo) vira linha toda-�;
Veloso (cinza, fora de range no fim) nao gera banda — bloco orfao de 3 valores.
Valida com soma dos balances individuais == balance da party.
"""
import pathlib
import re
import sys

import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw

CROP = (1578, 550, 1750, 1040)
SCROLL_X = 160
START = "2026-07-28, 07:05:30"
NUM = re.compile(r"-?[\d,]+")


def eh_valor(l):
    l = l.strip()
    m = NUM.search(l)
    if not m or ":" in l:
        return None
    resto = l.replace(m.group(), "").replace("�", "").strip()
    return m.group() if resto == "" else None


def parse_frame(f, glyphs, gap):
    img = Image.open(f).convert("RGB").crop(CROP)
    img.paste((0, 0, 0), (SCROLL_X, 0, img.width, img.height))
    linhas = [l.strip() for l in ab.decode_binary(ab.binarize_arr(np.asarray(img)), glyphs, gap)
              if l.strip()]
    out = {"session": None, "loot": None, "sup": None, "bal": None}
    blocos = []
    i = 0
    while i < len(linhas):
        l = linhas[i]
        m = re.search(r"(\d+:\d+h)", l)
        if m and out["session"] is None:
            out["session"] = m.group(1)
        elif "Supplies:" in l and out["sup"] is None and NUM.search(l.split(":", 1)[1]):
            out["sup"] = NUM.search(l.split(":", 1)[1]).group()
        elif "Balance:" in l and out["bal"] is None and NUM.search(l.split(":", 1)[1]):
            out["bal"] = NUM.search(l.split(":", 1)[1]).group()
        elif ":" in l and out["loot"] is None and out["sup"] is None and NUM.search(l.split(":", 1)[1] or ""):
            # linha "Loot: N" pode vir com label em banda-10 (todo �)
            if "Type" not in l and "Session" not in l:
                out["loot"] = NUM.search(l.split(":", 1)[1]).group()
        else:
            vals = []
            j = i
            while j < len(linhas) and len(vals) < 3:
                v = eh_valor(linhas[j])
                if v is None:
                    break
                vals.append(v)
                j += 1
            if len(vals) == 3:
                antes = linhas[i - 1] if i else ""
                if "Hetero" in antes:
                    nome = "Hetero afeminado"
                elif "Madruga" in antes:
                    nome = "Madruga solitario"
                elif "Veloso" in antes:
                    nome = "Veloso Hunter"
                elif antes and eh_valor(antes) is None and ":" not in antes \
                        and antes.replace("�", "").replace(" ", "") == "":
                    nome = "Mptres"
                else:
                    nome = None  # bloco orfao (nome cinza nao binariza) = Veloso
                blocos.append({"nome": nome, "vals": vals})
                i = j
                continue
        i += 1
    return out, blocos


def main():
    session = pathlib.Path(sys.argv[1])
    fim_max = lw.to_s(sys.argv[2]) if len(sys.argv) > 2 else 8 * 3600 + 59 * 60
    glyphs, gap = ab.load_atlas()
    fs = [f for f in sorted(session.glob("f_*.png")) if lw.fsec(f.name) <= fim_max]
    for f in reversed(fs):
        out, blocos = parse_frame(f, glyphs, gap)
        if not (out["bal"] and out["sup"] and len(blocos) == 4):
            continue
        usados = {b["nome"] for b in blocos if b["nome"]}
        resto = [n for n in ("Hetero afeminado", "Mptres", "Veloso Hunter", "Madruga solitario")
                 if n not in usados]
        orfaos = [b for b in blocos if b["nome"] is None]
        if len(orfaos) != len(resto):
            continue
        if len(orfaos) == 1:
            orfaos[0]["nome"] = resto[0]
        elif orfaos:
            continue
        soma = sum(int(b["vals"][0].replace(",", "")) for b in blocos)
        total = int(out["bal"].replace(",", ""))
        if abs(soma - total) > 2:
            continue
        ts = lw.fmt(lw.fsec(f.name))
        print(f"frame usado: {f.name} ({ts})  soma_balances={soma:,} == total ✓")
        linhas = [f"Session data: From {START} to 2026-07-28, {ts}"]
        if out["session"]:
            linhas.append(f"Session: {out['session']}")
        linhas.append("Loot Type: Leader")
        linhas.append(f"Loot: {out['loot'] or '0'}")
        linhas.append(f"Supplies: {out['sup']}")
        linhas.append(f"Balance: {out['bal']}")
        for b in blocos:
            nome = b["nome"] + (" (Leader)" if b["nome"] == "Mptres" else "")
            bal, dmg, heal = b["vals"]
            linhas += [nome, "\tLoot: 0", "\tSupplies: 0", f"\tBalance: {bal}",
                       f"\tDamage: {dmg}", f"\tHealing: {heal}"]
        outp = pathlib.Path(r"reports\Party hunt - energy 28-07.txt")
        outp.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        print(outp)
        print("\n".join(linhas))
        return
    print("nenhum frame completo — relaxar validacao ou fim_max")


if __name__ == "__main__":
    main()
