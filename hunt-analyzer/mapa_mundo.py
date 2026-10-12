"""Mapa de qualquer hunt pelo minimapa do cliente (.otmm), sem arrays prontos por cave (user, 21/09).

Antes só as Livrarias tinham mapa (arrays_hunt.py gerado na mão). Aqui tudo sai direto dos blocos
minimap1520_<X>_<Y>_<Z>.otmm, 64x64 tiles, cor no byte [4120:8216] (índice da paleta PAL):

  localizar(pngs, zs=None)        onde o m_ está no mundo, em qualquer andar (busca global, ~s)
  regiao(x0, x1, y0, y1, zs)      {"cor": {z: índices}, "big": {z: BGR 0-1}, "X0", "Y0"}: o que o
                                  rastrear() e o ao_vivo usam
  rastrear(png, reg, ultimo=None) posição do m_ dentro da região (< 50 ms), troca de andar sozinho
  fundo(z, bbox)                  PNG das cores do minimapa como data URL, bbox = (x0, x1, y0, y1)

Posição = {"x", "y", "z", "score"}, x/y do tile da ponta do pin. Uso típico:
  p = localizar(ultimos_3_m)
  reg = regiao(p["x"] - 160, p["x"] + 160, p["y"] - 160, p["y"] + 160, range(p["z"] - 2, p["z"] + 3))
  p = rastrear(m_novo, reg, p) ...   None = fora da região (refill, templo): localizar de novo
"""
import base64
import io
import os
import pathlib
import re
import threading
import time

import cv2
import numpy as np
from PIL import Image

from anchor_map import MMDIR, PAL
from pin_detect import PIN_TIP_PX

ZOOM = 2           # Map View: 2 px por tile
MIN_SCORE = 0.88   # loe_track: abaixo disso o m_ não é daquele lugar
GROSSO = 4         # busca global com 4 tiles por px: o mundo explorado cabe em poucos MB e casa em ~1 s
CANDIDATOS = 12    # picos da busca grossa que são conferidos no tile
RAIO = 30          # rastrear: tiles em volta da última posição antes de olhar a região inteira
RECARGA_S = 600    # o cliente grava o que o jogador explora: índice global com mais de 10 min é refeito
NOME = re.compile(r"minimap1520_(\d+)_(\d+)_(\d+)\.otmm")
PONTA = (PIN_TIP_PX[0] / ZOOM, PIN_TIP_PX[1] / ZOOM)   # ponta do pin em tiles dentro do m_

_trava = threading.Lock()
_indice_cache = {"t": 0.0, "pedacos": [], "assin": None}
CACHE = pathlib.Path(__file__).parent / "cache_mundo.npz"   # índice do mundo pronto (24/09)


def _bloco(bx, by, z):
    """Cores 64x64 do bloco ou None. Os 'OTMM HD' (zlib, de maio/junho) têm < 8216 bytes e ficam de fora:
    quase todos vazios. ponytail: decodificar o HD se aparecer amigo com o mapa só nesse formato."""
    try:
        with open(MMDIR / f"minimap1520_{bx}_{by}_{z}.otmm", "rb") as h:
            h.seek(4120)
            d = h.read(4096)
    except OSError:
        return None
    return np.frombuffer(d, np.uint8).reshape(64, 64) if len(d) == 4096 else None


def _cor(x0, x1, y0, y1, z, existe=None):
    """Índices de cor de um andar no retângulo [x0, x1) x [y0, y1); None se nenhum bloco existe.
    existe = {(bx, by)} já listados: poupa abrir arquivo que não existe ou é HD (busca global)."""
    a = np.zeros((y1 - y0, x1 - x0), np.uint8)
    achou = False
    for by in range(y0 // 64 * 64, y1, 64):
        for bx in range(x0 // 64 * 64, x1, 64):
            b = None if existe is not None and (bx, by) not in existe else _bloco(bx, by, z)
            if b is None:
                continue
            xl, xh, yl, yh = max(bx, x0), min(bx + 64, x1), max(by, y0), min(by + 64, y1)
            a[yl - y0:yh - y0, xl - x0:xh - x0] = b[yl - by:yh - by, xl - bx:xh - bx]
            achou = True
    return a if achou else None


def _bgr(cor):
    return PAL[cor][:, :, ::-1].astype(np.float32) / 255.0


def _molde(png, fator=ZOOM):
    """m_ reduzido INTER_AREA (upscale do mapa falha com a fase sub-tile), BGR uint8. PIL: caminho com acento."""
    a = np.ascontiguousarray(np.asarray(Image.open(png).convert("RGB"))[:, :, ::-1])
    return cv2.resize(a, (a.shape[1] // fator, a.shape[0] // fator), interpolation=cv2.INTER_AREA)


def regiao(x0, x1, y0, y1, zs):
    """Região do mundo direto dos .otmm, no formato que o rastrear() usa. Andar sem bloco nenhum fica de fora."""
    x0, x1, y0, y1 = int(x0), int(x1), int(y0), int(y1)
    cor = {z: c for z in zs if 0 <= z <= 15 for c in [_cor(x0, x1, y0, y1, z)] if c is not None}
    return {"cor": cor, "big": {z: _bgr(c) for z, c in cor.items()}, "X0": x0, "Y0": y0}


def fundo(z, bbox):
    """Fundo de um andar: PNG 1 px por tile nas cores do minimapa, como data URL (os fundos do mock)."""
    x0, x1, y0, y1 = (int(v) for v in bbox)
    c = _cor(x0, x1, y0, y1, z)
    buf = io.BytesIO()
    Image.fromarray(PAL[c if c is not None else np.zeros((y1 - y0, x1 - x0), np.uint8)]).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def rastrear(png, reg, ultimo=None, raio=RAIO):
    """Posição do m_ na região: primeiro em volta da última (andar dela primeiro, depois os outros: escada),
    depois na região inteira. None = nenhum andar casou (o m_ não é dessa região)."""
    tpl = _molde(png).astype(np.float32) / 255.0
    th, tw = tpl.shape[:2]
    best = (-1.0, None, 0, 0)
    for janela in ((True, False) if ultimo else (False,)):
        zs = sorted(reg["big"], key=lambda z: abs(z - ultimo["z"])) if ultimo else list(reg["big"])
        for z in zs:
            big = reg["big"][z]
            x0 = y0 = 0
            if janela:
                x0 = max(int(ultimo["x"] - PONTA[0]) - reg["X0"] - raio, 0)
                y0 = max(int(ultimo["y"] - PONTA[1]) - reg["Y0"] - raio, 0)
                big = big[y0:y0 + th + 2 * raio, x0:x0 + tw + 2 * raio]
            if big.shape[0] < th or big.shape[1] < tw:
                continue
            _, sc, _, loc = cv2.minMaxLoc(cv2.matchTemplate(big, tpl, cv2.TM_CCOEFF_NORMED))
            if sc > best[0]:
                best = (float(sc), z, x0 + loc[0], y0 + loc[1])
            if janela and z == ultimo["z"] and sc >= MIN_SCORE:
                break   # mesmo andar casou: não gasta tempo com os outros
        if best[0] >= MIN_SCORE:
            sc, z, lx, ly = best
            return {"x": reg["X0"] + lx + PONTA[0], "y": reg["Y0"] + ly + PONTA[1], "z": z, "score": round(sc, 3)}
    return None


def _varre():
    """Blocos com cor por andar e a assinatura da pasta (quantos blocos e o mtime mais novo).
    Varrer os 69 mil .otmm custa 0,25 s; remontar o índice custa 4,5 s (14 s com o disco frio)."""
    por_z, n, novo = {}, 0, 0.0
    # sem a pasta do minimapa (jogo em outro lugar): sem mapa, mas o resto da análise segue
    for e in (os.scandir(MMDIR) if MMDIR.is_dir() else ()):
        m = NOME.fullmatch(e.name)
        if m:
            st = e.stat()
            if st.st_size >= 8216:
                x, y, z = map(int, m.groups())
                por_z.setdefault(z, set()).add((x, y))
                n, novo = n + 1, max(novo, st.st_mtime)
    return por_z, (float(n), round(novo, 3))


def _monta(por_z):
    pedacos = []
    for z, bs in por_z.items():
        b = np.array(sorted(bs)) // 64
        g0 = b.min(axis=0) - 1
        grade = np.zeros(tuple((b.max(axis=0) - g0 + 2)[::-1]), np.uint8)
        grade[b[:, 1] - g0[1], b[:, 0] - g0[0]] = 1
        # 1 bloco de folga em volta: o m_ passa da borda do que foi explorado
        grade = cv2.dilate(grade, np.ones((3, 3), np.uint8))
        _, _, st, _ = cv2.connectedComponentsWithStats(grade, connectivity=8)
        for gx, gy, w, h, _a in st[1:]:
            X0, Y0 = int(g0[0] + gx) * 64, int(g0[1] + gy) * 64
            c = _cor(X0, X0 + w * 64, Y0, Y0 + h * 64, z, bs)
            if c is not None:
                pedacos.append((z, X0, Y0, cv2.resize(np.ascontiguousarray(PAL[c][:, :, ::-1]),
                                                      (w * 64 // GROSSO, h * 64 // GROSSO),
                                                      interpolation=cv2.INTER_AREA)))
    return pedacos


def _le_cache(assin):
    """Índice do arquivo, se ele foi gravado com esta mesma pasta de minimapa. 11 ms em 26 MB."""
    try:
        with np.load(CACHE) as arq:
            if not np.array_equal(arq["assin"], np.array(assin, np.float64)):
                return None
            return [(*(int(v) for v in k[2:].split("_")[:3]), arq[k]) for k in arq.files if k[:2] == "p_"]
    except (OSError, ValueError, KeyError, EOFError):   # sem cache, ou gravado pela metade
        return None


def _grava_cache(pedacos, assin):
    try:   # sem compressão: 26 MB e ~0,2 s para gravar (comprimir custa mais do que remontar)
        np.savez(CACHE, assin=np.array(assin, np.float64),
                 **{f"p_{z}_{x}_{y}_{i}": img for i, (z, x, y, img) in enumerate(pedacos)})
    except OSError:   # disco cheio ou pasta só de leitura: segue sem cache
        pass


def _indice():
    """Mundo explorado em 1/GROSSO, por pedaço contíguo de cada andar: [(z, X0, Y0, BGR uint8)].

    24/09 (user): o índice é caro (4,5 s com os arquivos em cache do SO, 14 s com o disco frio) e
    era refeito a cada 10 min e a cada abertura do programa. Agora ele vai para o disco e só é
    remontado quando a pasta do minimapa muda — o cliente gravou 39 blocos em 24 h, então no meio
    da hunt a conferência é a varredura de 0,25 s e mais nada.
    """
    with _trava:
        if time.time() - _indice_cache["t"] <= RECARGA_S:
            return _indice_cache["pedacos"]
        por_z, assin = _varre()
        if assin != _indice_cache["assin"]:
            pedacos = _le_cache(assin)
            if pedacos is None:
                # 28/09: remontar segura o processo por segundos e o painel chegou a achar que o
                # programa tinha caído. Fica registrado no app.log com o tempo que levou.
                t0 = time.time()
                pedacos = _monta(por_z)
                _grava_cache(pedacos, assin)
                print(f"[{time.strftime('%d/%m %H:%M:%S')}] índice do minimapa remontado em "
                      f"{time.time() - t0:.1f}s ({len(pedacos)} pedaços, {int(assin[0])} blocos)", flush=True)
            _indice_cache.update(pedacos=pedacos, assin=assin)
        _indice_cache["t"] = time.time()
        return _indice_cache["pedacos"]


def _candidatos(png, zs):
    """Picos da busca grossa, conferidos no tile: posições com score >= MIN_SCORE, melhor primeiro."""
    tg = _molde(png, ZOOM * GROSSO)
    th, tw = tg.shape[:2]
    picos = []
    for z, X0, Y0, img in _indice():
        if (zs is not None and z not in zs) or img.shape[0] < th or img.shape[1] < tw:
            continue
        res = cv2.matchTemplate(img, tg, cv2.TM_CCOEFF_NORMED)
        for _ in range(3):   # 3 picos por pedaço, apagando a vizinhança de cada um
            _, sc, _, (lx, ly) = cv2.minMaxLoc(res)
            picos.append((sc, z, X0 + lx * GROSSO, Y0 + ly * GROSSO))
            res[max(ly - 4, 0):ly + 5, max(lx - 4, 0):lx + 5] = -1
    achados = []
    m = 2 * GROSSO   # erro da busca grossa, em tiles
    for sc, z, x, y in sorted(picos, reverse=True)[:CANDIDATOS]:
        reg = regiao(x - m, x + tw * GROSSO + m, y - m, y + th * GROSSO + m, [z])
        p = rastrear(png, reg)
        if p:
            achados.append(p)
    return sorted(achados, key=lambda p: -p["score"])


def localizar(pngs, zs=None):
    """Posição do último m_ de pngs (um caminho ou lista de 2-3 m_ seguidos) no mundo, ou None.
    O 1º quadro acha os candidatos no mundo inteiro; os seguintes confirmam em volta do candidato."""
    pngs = list(pngs) if isinstance(pngs, (list, tuple)) else [pngs]
    for p in _candidatos(pngs[0], zs):
        for png in pngs[1:]:
            reg = regiao(p["x"] - 100, p["x"] + 100, p["y"] - 100, p["y"] + 100, range(p["z"] - 1, p["z"] + 2))
            p = rastrear(png, reg, p)
            if not p:
                break
        else:
            return p
    return None


if __name__ == "__main__":
    import tempfile

    # m_ sintético (2 px por tile, pin na ponta) tirado do próprio minimapa: roda sem o jogo
    def m_falso(x, y, z, pasta):
        c = _cor(int(x - PONTA[0]), int(x - PONTA[0]) + 97, int(y - PONTA[1]), int(y - PONTA[1]) + 88, z)
        png = os.path.join(pasta, f"m_{x}_{y}_{z}.png")
        Image.fromarray(PAL[np.kron(c, np.ones((2, 2), np.uint8))][:176, :193]).save(png)
        return png

    X, Y, Z = 32636, 32690, 12   # Livraria de Fogo (sessão de 21/09)
    assert _bloco(X // 64 * 64, Y // 64 * 64, Z) is not None, "minimapa do cliente sem a Livraria de Fogo"
    with tempfile.TemporaryDirectory() as d:
        t = time.time()
        p = localizar([m_falso(X, Y, Z, d), m_falso(X + 2, Y, Z, d), m_falso(X + 4, Y + 1, Z, d)])
        print(f"localizar {time.time() - t:.1f} s ->", p)
        assert p and p["z"] == Z and abs(p["x"] - (X + 4)) <= 1 and abs(p["y"] - (Y + 1)) <= 1, p
        reg = regiao(X - 160, X + 160, Y - 160, Y + 160, range(Z - 2, Z + 3))
        passos = [(X + 6, Y + 3, Z), (X + 6, Y + 3, Z + 1)]   # anda e desce a escada
        for x, y, z in passos:
            png = m_falso(x, y, z, d)
            t = time.time()
            p = rastrear(png, reg, p)
            print(f"rastrear {1000 * (time.time() - t):.0f} ms ->", p)
            assert p and p["z"] == z and abs(p["x"] - x) <= 1 and abs(p["y"] - y) <= 1, (p, x, y, z)
        assert fundo(Z, (X - 50, X + 50, Y - 50, Y + 50)).startswith("data:image/png;base64,")
    print("mapa_mundo ok")
