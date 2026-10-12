"""Acrescenta a monstros_nomes.txt as especies vistas no laps.jsonl (loots/kills) — roda a cada volta."""
import json, pathlib, sys
s = pathlib.Path(sys.argv[1]); vp = pathlib.Path("monstros_nomes.txt")
atual = {l.strip().lower() for l in vp.read_text(encoding="utf-8").splitlines() if l.strip()}
novos = set()
for l in (s / "laps.jsonl").read_text(encoding="utf-8-sig").splitlines():
    if not l.strip(): continue
    L = json.loads(l)
    for k in list((L.get("loots") or {}).keys()) + list((L.get("kills") or {}).keys()):
        k = k.lower().rstrip("*").strip()
        if k and k not in ("outro", "compartilhado") and len(k) >= 4 and k not in atual:
            novos.add(k)
if novos:
    vp.write_text("\n".join(sorted(atual | novos)) + "\n", encoding="utf-8")
print("novos:", sorted(novos))
