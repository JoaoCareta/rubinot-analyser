"""Vigia leve da criatura RARA (Plunder Patriarch) — paralelo, nao toca capture/lap_watch.

A cada ~3s decodifica o b_*.png (battle list) e o c_*.png (chat) mais novos da
sessao com o atlas de glifos (a battle list usa a MESMA fonte do console — nomes
como Rhindeer/Boar Man decodificam direto). Ao ver "plunder"/"patriarch":

    PLUNDER_AVISTADO <hora> <nome>        (stdout, flush)
    <sessao>/plunder_events.jsonl         {ts, nome, fonte, arquivo}

Dedupe: mesma (fonte, nome) nao repete por 120s — a battle list mostra o bicho
em todo frame enquanto ele vive.

Uso: python plunder_watch.py capture\\session_YYYYMMDD_HHMMSS [--replay]
     --replay processa TODOS os frames da sessao e sai (validacao/pos-hunt).
"""
import json
import pathlib
import sys
import time

import atlas_build as ab
from lap_watch import clean_binary, fsec, fmt

# qualquer um casa (glifo desconhecido pode quebrar uma das palavras)
KEYWORDS = ("plunder", "patriarch")
DEDUPE_S = 120
POLL_S = 3


def scan_lines(lines):
    """Linhas decodificadas que contem alguma keyword, ja limpas de icones."""
    hits = []
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in KEYWORDS):
            hits.append(line.replace("�", "").strip())
    return hits


def scan_file(f, glyphs, gap):
    binary = clean_binary(ab.binarize(str(f)))
    return scan_lines(ab.decode_binary(binary, glyphs, gap))


def main():
    args = [a for a in sys.argv[1:] if a != "--replay"]
    replay = "--replay" in sys.argv
    session = pathlib.Path(args[0])
    glyphs, gap = ab.load_atlas()
    events_p = session / "plunder_events.jsonl"
    last_seen = {}   # (fonte, nome) -> fsec do ultimo aviso
    done = {"b": "", "c": ""}  # ultimo arquivo processado por lane

    def report(fonte, f, nomes):
        t = fsec(f.name)
        for nome in nomes:
            key = (fonte, nome.lower())
            if t - last_seen.get(key, -DEDUPE_S) < DEDUPE_S:
                continue
            last_seen[key] = t
            print(f"PLUNDER_AVISTADO {fmt(t)} {nome}", flush=True)
            with events_p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": fmt(t), "nome": nome, "fonte": fonte,
                                     "arquivo": f.name}, ensure_ascii=False) + "\n")

    fontes = (("battle", "b"), ("chat", "c"))
    if replay:
        for fonte, prefix in fontes:
            frames = sorted(session.glob(f"{prefix}_*.png"))
            print(f"replay {fonte}: {len(frames)} frames", flush=True)
            for i, f in enumerate(frames):
                if i and i % 2000 == 0:
                    print(f"  {fonte} {i}/{len(frames)}", flush=True)
                report(fonte, f, scan_file(f, glyphs, gap))
        print("replay concluido: "
              f"{sum(1 for _ in events_p.open()) if events_p.exists() else 0} eventos",
              flush=True)
        return

    print(f"vigia plunder: {session.name} (ao vivo, poll {POLL_S}s)", flush=True)
    while True:
        for fonte, prefix in fontes:
            frames = sorted(session.glob(f"{prefix}_*.png"))
            if frames and frames[-1].name != done[prefix]:
                done[prefix] = frames[-1].name
                report(fonte, frames[-1], scan_file(frames[-1], glyphs, gap))
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
