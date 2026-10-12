"""Tira um frame de calibracao da janela do RubinOT e recorta as lanes atuais."""
import sys

import mss
import mss.tools

import capture

OUT = sys.argv[1] if len(sys.argv) > 1 else "z_calib_loe.png"

g = capture.find_game_rect()
if not g:
    print("JANELA NAO ENCONTRADA - abrir o RubinOT")
    sys.exit(1)
print("title:", g["title"])
print("rect:", g["rect"])
with mss.MSS() as sct:
    img = sct.grab(g["rect"])
    mss.tools.to_png(img.rgb, img.size, output=OUT)
    for name, rel in (("c", capture.CHAT_REL), ("s", capture.SPELL_REL),
                      ("b", capture.BATTLE_REL), ("m", capture.MAP_REL)):
        lane = sct.grab(capture.rel_rect(g["rect"], rel))
        mss.tools.to_png(lane.rgb, lane.size, output=OUT.replace(".png", f"_{name}.png"))
print("frame salvo:", OUT, img.size)
