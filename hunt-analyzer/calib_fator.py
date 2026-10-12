"""Fator raw-XP/bicho da LoE a partir da sessao 24/07 do tracker (mesma pt x4)."""
import json
import sqlite3

db = sqlite3.connect(r"D:\Documentos\rubinot\loe-hunt-tracker\data.db")
(data,) = db.execute("SELECT data FROM sessions").fetchone()
s = json.loads(data)
print("chaves:", list(s.keys()))
party = s["party"]
print(f"party {party['start']} -> {party['end']}  dur={party['durationH']:.2f}h "
      f"balance={party['balance']:,}")
for m in s.get("mines", []):
    kills = m.get("kills", [])
    total = sum(k["count"] for k in kills)
    resto = {k: v for k, v in m.items() if k != "kills"}
    print("mine keys:", list(m.keys()))
    print("resto:", json.dumps(resto, ensure_ascii=False)[:600])
    print(f"kills total={total}")
    for k in sorted(kills, key=lambda k: -k["count"]):
        print(f"  {k['count']:6d}  {k['name']}")
