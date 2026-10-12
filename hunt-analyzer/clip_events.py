"""Extrai eventos de chat de um clip mp4 do RubinOT (mesmo pipeline dos frames).

Uso:  python clip_events.py <clip.mp4> [step]
step = processa 1 a cada N frames do video (default 3 ~ 9.5fps).

O clip e um buffer "para tras": o horario no nome e o FIM da gravacao.
Saida: capture\\clip_<inicio>\\events.jsonl (mesmo formato das sessoes).
"""
import datetime as dt
import json
import pathlib
import re
import sys

import cv2

import atlas_build as ab
import events_build as ev

# janela maximizada 1936x1048 -> area cliente do clip 1920x1008: offset (-8,-32)
CHAT = (357, 668, 1210, 340)  # x, y, w, h


def main():
    clip = pathlib.Path(sys.argv[1])
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    m = re.match(r"clip_(\d{4})-(\d\d)-(\d\d)_(\d\d)-(\d\d)-(\d\d)", clip.stem)
    end = dt.datetime(*map(int, m.groups()))

    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start = end - dt.timedelta(seconds=n / fps)
    out_dir = pathlib.Path(__file__).parent / "capture" / start.strftime("clip_%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{clip.name}: {n} frames @ {fps:.1f}fps, {start:%H:%M:%S} -> {end:%H:%M:%S}, step={step}")

    glyphs, gap = ab.load_atlas()
    x, y, w, h = CHAT
    events, prev, last_ts = [], [], ""
    idx = 0
    while True:
        if not cap.grab():
            break
        if idx % step == 0:
            ok, fr = cap.retrieve()
            if ok:
                binary = ab.binarize_arr(fr[y : y + h, x : x + w])
                msgs, started = [], False
                for line in ab.decode_binary(binary, glyphs, gap):
                    tm = ev.TS.match(line)
                    if tm:
                        started = True
                        msgs.append([tm.group(1), tm.group(2)])
                    elif started and msgs:
                        msgs[-1][1] += " " + line
                cur = [(t, b) for t, b in msgs if "�" not in b]
                if cur and not (last_ts and all(t < last_ts for t, _ in cur)):
                    stamp = (start + dt.timedelta(seconds=idx / fps)).strftime("%H%M%S")
                    for ts, body in ev.new_tail(prev, cur):
                        kind, data = ev.classify(body)
                        events.append({"ts": ts, "kind": kind, "body": body,
                                       "frame": f"{clip.stem}@{stamp}", **data})
                        last_ts = max(last_ts, ts)
                    prev = cur
        idx += 1
    cap.release()

    out = out_dir / "events.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"gravado {out}\n")
    ev.summarize(events)


if __name__ == "__main__":
    main()
