"""Identificacao AUTOMATICA de rotacoes pela forma do trajeto da volta.

Cada volta e um caminho (dead reckoning, relativo ao ponto de partida). Duas
voltas sao a mesma rotacao quando os caminhos, reamostrados por comprimento de
arco, ficam proximos ponto a ponto. Sentido invertido vira rotulo "X-inv".
"""
import string

import numpy as np

N_POINTS = 32
SAME_ROT_TILES = 30.0   # distancia media maxima p/ considerar a mesma rotacao


def resample(path, n=N_POINTS):
    """Caminho -> n pontos equidistantes em comprimento de arco."""
    P = np.asarray(path, dtype=float)
    if len(P) < 4:
        return None
    seg = np.hypot(*np.diff(P, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if cum[-1] < 20:  # volta curta demais p/ ter forma
        return None
    t = np.linspace(0, cum[-1], n)
    return np.stack([np.interp(t, cum, P[:, 0]), np.interp(t, cum, P[:, 1])], axis=1)


def shape_dist(a, b):
    return float(np.hypot(*(a - b).T).mean())


def signed_area(P):
    x, y = P[:, 0], P[:, 1]
    return float(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def classify(path, previous):
    """Rotula uma volta comparando com as anteriores.

    previous: lista de dicts {"rotacao": str, "path": [[x,y],...]}
    Devolve (rotulo, distancia, motivo).
    """
    cur = resample(path)
    if cur is None:
        return "?", None, "trajeto curto demais"

    previous = [p for p in previous if p.get("rotacao") and p.get("path")]
    best = None
    for p in previous:
        prev = resample(p.get("path") or [])
        if prev is None:
            continue
        d = shape_dist(cur, prev)
        d_inv = shape_dist(cur, prev[::-1])
        if best is None or min(d, d_inv) < best[0]:
            best = (min(d, d_inv), p["rotacao"], d_inv < d)

    if best and best[0] <= SAME_ROT_TILES:
        base = best[1].replace("-inv", "")
        if best[2]:
            lbl = base if best[1].endswith("-inv") else base + "-inv"
            return lbl, best[0], f"mesmo trajeto de {best[1]} em sentido inverso ({best[0]:.0f} tiles)"
        return best[1], best[0], f"igual a {best[1]} ({best[0]:.0f} tiles de diferenca)"

    usadas = {p["rotacao"].replace("-inv", "") for p in previous}
    for letra in string.ascii_uppercase:
        if letra not in usadas:
            motivo = "primeira volta medida" if best is None else \
                f"diferente de tudo (mais proxima: {best[1]} a {best[0]:.0f} tiles)"
            return letra, (best[0] if best else None), motivo
    return "Z", None, "sem letras livres"


def summarize_path(path):
    """Metricas descritivas do trajeto (p/ o card da volta)."""
    P = np.asarray(path, dtype=float)
    if len(P) < 3:
        return {}
    seg = np.hypot(*np.diff(P, axis=0).T)
    R = resample(path)
    return {
        "percurso_tiles": round(float(seg.sum())),
        "raio_max_tiles": round(float(np.hypot(P[:, 0], P[:, 1]).max())),
        "sentido": "horario" if R is not None and signed_area(R) < 0 else "anti-horario",
    }
