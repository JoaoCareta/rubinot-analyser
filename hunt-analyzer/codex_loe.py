"""Extrai resist/fraqueza dos bichos da LoE do codex embutido no tracker."""
import re

txt = open(r"D:\Documentos\rubinot\loe-hunt-tracker\public\index.html", encoding="utf-8").read()
nomes = ("Energetic Book", "Brain Squid", "Knowledge Elemental",
         "Energuardian of Tales", "Biting Book", "Flying Book")
for n in nomes:
    m = re.search(re.escape(n) + r"['\"]?\s*:\s*\{(.{0,900}?)sprite", txt, re.S)
    if not m:
        m = re.search(re.escape(n) + r"['\"]?\s*:\s*\{(.{0,900}?)\}", txt, re.S)
    corpo = re.sub(r"\s+", " ", m.group(1))[:500] if m else "NAO ACHADO"
    print(n, "->", corpo, "\n")
