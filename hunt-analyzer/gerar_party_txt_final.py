"""Export final do Party Hunt: tudo do frame 08:57:00 + Madruga lido da imagem."""
import pathlib

import atlas_build as ab
import gerar_party_txt as g

F = pathlib.Path(r"capture\session_20260728_072106\f_085700_539.png")
MADRUGA = ("394,850", "11,825,857", "762,259")  # lido do zoom do proprio frame
START = "2026-07-28, 07:05:30"
FIM = "2026-07-28, 08:57:00"
SESSION = "01:41h"  # painel (01:42h as 08:58) — 1 min antes

glyphs, gap = ab.load_atlas()
out, blocos = g.parse_frame(F, glyphs, gap)
assert len(blocos) == 3, blocos
orfao = next(b for b in blocos if b["nome"] is None)
orfao["nome"] = "Veloso Hunter"
blocos.append({"nome": "Madruga solitario", "vals": list(MADRUGA)})

soma = sum(int(b["vals"][0].replace(",", "")) for b in blocos)
total = int(out["bal"].replace(",", ""))
print(f"totais: loot={out['loot']} sup={out['sup']} bal={out['bal']}")
print(f"soma balances membros = {soma:,} vs total {total:,} (delta {soma - total:+,})")
# split real do fim da hunt (user 28/07): loot dividido, ~3,8kk por cabeca
por_membro = total // 4
sobra = total - por_membro * 4
for i, b in enumerate(blocos):
    b["vals"][0] = f"{por_membro + (sobra if i == 0 else 0):,}"

linhas = [f"Session data: From {START} to {FIM}", f"Session: {SESSION}",
          "Loot Type: Leader", f"Loot: {out['loot']}", f"Supplies: {out['sup']}",
          f"Balance: {out['bal']}"]
for b in blocos:
    nome = b["nome"] + (" (Leader)" if b["nome"] == "Mptres" else "")
    bal, dmg, heal = b["vals"]
    linhas += [nome, "\tLoot: 0", "\tSupplies: 0", f"\tBalance: {bal}",
               f"\tDamage: {dmg}", f"\tHealing: {heal}"]
outp = pathlib.Path(r"reports\Party hunt - energy 28-07.txt")
outp.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print(f"\n{outp}\n")
print("\n".join(linhas))
