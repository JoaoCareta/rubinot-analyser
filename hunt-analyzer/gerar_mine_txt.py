"""Reconstroi o Hunt Analyser pessoal do Hetero (resetado sem querer no fim).

Campos do frame 08:57:00 (crop largo, sem mascara — o painel alargou no fim).
Killed Monsters: usa contagens reais se a lista aparecer scrollada em algum
frame final; senao estima pelo mix de loots da propria sessao escalado ao
total de bichos (raw / 6386).
"""
import collections
import json
import pathlib
import re

import numpy as np
from PIL import Image

import atlas_build as ab
import lap_watch as lw

SESSION = pathlib.Path(r"capture\session_20260728_072106")
F_CAMPOS = SESSION / "f_085700_539.png"
CROP = (0, 780, 188, 1048)
FATOR = 6386
ESPECIES = ("Energetic Book", "Brain Squid", "Knowledge Elemental",
            "Energuardian of Tales", "Biting Book", "Flying Book")

glyphs, gap = ab.load_atlas()


def decode(f, crop=CROP):
    img = Image.open(f).convert("RGB").crop(crop)
    img.paste((0, 0, 0), (0, 0, 5, img.height))      # borda esquerda da janela
    img.paste((0, 0, 0), (169, 0, img.width, img.height))  # scrollbar do painel
    return [re.sub(r"[�\s]+$", "", l) for l in
            ab.decode_binary(ab.binarize_arr(np.asarray(img)), glyphs, gap) if l.strip()]


def valor(l):
    m = re.search(r"(-?[\d,]+)(k?)$", l)
    if not m:
        return None
    return int(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)


linhas = decode(F_CAMPOS)
print("linhas do painel:", linhas)
campos = {}
ordem = ["session", "raw", "xp", "rawh", "xph", "loot", "sup", "bal",
         "dmg", "dmgh", "heal", "healh"]
idx = 0
for l in linhas:
    if re.search(r"\d+:\d+h", l):
        campos["session"] = re.search(r"(\d+:\d+h)", l).group(1)
        idx = 1
        continue
    if idx and idx < len(ordem):
        v = valor(l)
        if v is not None:
            campos[ordem[idx]] = v
            idx += 1
print("campos:", campos)

# lista Killed Monsters scrollada em algum frame final?
reais = {}
fs = [f for f in sorted(SESSION.glob("f_*.png")) if lw.fsec(f.name) >= 8 * 3600 + 57 * 60]
for f in fs:
    for l in decode(f):
        m = re.match(r"^(\d+)\s*x\s+(.+)$", l.replace("�", "").strip())
        if m:
            nome = m.group(2).strip().title()
            cand = next((e for e in ESPECIES if e.lower().startswith(nome.lower()[:6])), None)
            if cand:
                reais[cand] = max(reais.get(cand, 0), int(m.group(1)))
print(f"kills reais na tela ({len(fs)} frames):", reais)

total = round(campos["raw"] / FATOR)
if len(reais) >= 4:
    kills = reais
    fonte = "lista real do painel"
else:
    # loots do chat (janela de 3 linhas) tem vies brutal de especie (Energuardian
    # 18% do spawn real aparece 0x). Mix confiavel = analyser real de 24/07,
    # mesma pt x4 e mesma rota: 3.519 kills contados.
    MIX_2407 = {"Energetic Book": 1017, "Brain Squid": 926, "Knowledge Elemental": 692,
                "Energuardian of Tales": 633, "Biting Book": 185, "Flying Book": 66}
    soma = sum(MIX_2407.values())
    kills = {e: round(total * n / soma) for e, n in MIX_2407.items()}
    kills[max(kills, key=kills.get)] += total - sum(kills.values())
    fonte = "estimado pelo mix real de 24/07 (mesma pt/rota)"
print(f"kills ({fonte}), total {sum(kills.values())}")

out = ["Session data: From 2026-07-28, 07:05:30 to 2026-07-28, 08:57:00",
       f"Session: {campos.get('session', '01:41h')}",
       f"Raw XP Gain: {campos['raw']:,}",
       f"XP Gain: {campos['xp']:,}",
       f"Raw XP/h: {campos['rawh']:,}",
       f"XP/h: {campos['xph']:,}",
       f"Loot: {campos['loot']:,}",
       f"Supplies: {campos['sup']:,}",
       f"Balance: {campos['bal']:,}",
       f"Damage: {campos['dmg']:,}",
       f"Damage/h: {campos['dmgh']:,}",
       f"Healing: {campos['heal']:,}",
       f"Healing/h: {campos['healh']:,}",
       "Killed Monsters:"]
for e, n in sorted(kills.items(), key=lambda kv: -kv[1]):
    out.append(f"\t{n}x {e}")
out.append("Looted Items:")
outp = pathlib.Path(r"reports\Hunting Analysing - energy 28-07.txt")
outp.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"\n{outp}\n")
print("\n".join(out))
