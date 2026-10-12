"""Aponta a area de trabalho (constantes de mapa_ingol) para outra hunt.

Os modulos de mapa/coach leem bbox e andar de `mapa_ingol` (X0..Z). Para rodar
em outra cave basta chamar aplicar(hunt) antes: sobrescreve as constantes com o
bbox/z do hunt_data/<hunt>/referencias.json. planos() e o stitch passam a
montar a cave certa sozinhos.
"""
import json
import pathlib

import mapa_ingol as mi


def aplicar(hunt):
    ref = json.loads((pathlib.Path(__file__).parent / "hunt_data" / hunt /
                      "referencias.json").read_text(encoding="utf-8"))
    mi.X0, mi.X1, mi.Y0, mi.Y1 = ref["bbox"]
    mi.Z = ref["z"]
    return ref
