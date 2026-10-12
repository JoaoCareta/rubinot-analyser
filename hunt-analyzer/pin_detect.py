"""Detector do pin do jogador no Map View (template matching do sprite).

O pin e um balao vermelho com cauda prata; a PONTA (nao a bola) marca o tile do
jogador. O sprite e identico em todo frame/zoom, entao template matching e exato.
Telhados vermelhos de cidade quebram deteccao por cor — por isso template.
"""
import pathlib

import cv2
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).parent
TPL_PATH = HERE / "pin_template.png"
MAP_CROP = (1694, 48, 1887, 224)  # 18/09: painel subiu 4px / foi 2px p/ direita

# O Map View TRAVA a camera no jogador: o pin fica sempre no MESMO pixel do
# painel. Medido por variancia (std<6 em 100+ frames) e identico em Ingol e
# Falcon: bola em (46.1, 74.8), PONTA DA AGULHA em (55, 84).
# A ponta e o tile do jogador (o usuario confirmou: "a ponta inferior do pin
# e onde estou, NAO a bolinha vermelha").
PIN_TIP_PX = (55.0, 84.0)
PIN_BALL_PX = (46.1, 74.8)
TIP_OFFSET = (PIN_TIP_PX[0] - PIN_BALL_PX[0], PIN_TIP_PX[1] - PIN_BALL_PX[1])


def build_template(frame_png, ball_xy, out=TPL_PATH):
    """Extrai o sprite do pin de um frame onde a bola esta em ball_xy (coord do crop)."""
    img = Image.open(frame_png).convert("RGB").crop(MAP_CROP)
    bx, by = int(round(ball_xy[0])), int(round(ball_xy[1]))
    tpl = img.crop((bx - 7, by - 7, bx + 13, by + 17))  # 20x24 cobre bola + cauda
    tpl.save(out)
    return out


def load_template():
    return cv2.cvtColor(np.asarray(Image.open(TPL_PATH).convert("RGB")), cv2.COLOR_RGB2BGR)


def find_pin(frame_png, tpl=None, min_score=0.62):
    """Devolve (tip_x, tip_y, score) em px do crop do Map View, ou None."""
    if tpl is None:
        tpl = load_template()
    img = cv2.cvtColor(
        np.asarray(Image.open(frame_png).convert("RGB").crop(MAP_CROP)), cv2.COLOR_RGB2BGR)
    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < min_score:
        return None
    ball_x, ball_y = loc[0] + 7, loc[1] + 7  # volta do canto p/ centro da bola
    return ball_x + TIP_OFFSET[0], ball_y + TIP_OFFSET[1], float(score)


if __name__ == "__main__":
    import sys

    if sys.argv[1] == "build":
        # build <frame.png> <ball_x> <ball_y>
        p = build_template(sys.argv[2], (float(sys.argv[3]), float(sys.argv[4])))
        print(f"template salvo em {p}")
    else:
        tpl = load_template()
        for f in sys.argv[1:]:
            r = find_pin(f, tpl)
            print(f"{pathlib.Path(f).name}: {r}")
