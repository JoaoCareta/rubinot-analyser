"""Leitura conservadora de painéis comprimidos, sem truncar dígitos desconhecidos."""
import functools
import re

import cv2
import numpy as np
import atlas_build as ab
import nameplates

NUMERO = re.compile(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(k?)')


def numero(texto):
    texto = texto.strip()
    m = NUMERO.fullmatch(texto)
    if not m:
        return None
    return int(texto.rstrip('k').replace(',', '')) * (1000 if m[1] else 1)


@functools.lru_cache(maxsize=1)
def _atlas():
    glyphs, gap = ab.load_atlas()
    return nameplates.shape_index(glyphs), gap


def linhas(img):
    arr = np.asarray(img.convert('RGB'))
    b = arr.max(axis=2) > 140
    vert = cv2.morphologyEx(b.astype('uint8'), cv2.MORPH_OPEN, np.ones((20, 1), 'uint8'))
    horiz = cv2.morphologyEx(b.astype('uint8'), cv2.MORPH_OPEN, np.ones((1, 100), 'uint8'))
    b &= ~(vert.astype(bool) | horiz.astype(bool))
    idx, gap = _atlas()
    out = []
    for y0, y1 in ab.text_bands(b, input_top=None):
        banda = b[y0:y1].copy()
        cols = banda.any(axis=0)
        xs = np.flatnonzero(cols)
        if len(xs):
            fim = int(xs[-1]) + 1
            inicio = fim - 1
            while inicio > 0 and cols[inicio - 1]:
                inicio -= 1
            pixels = arr[y0:y1, inicio:fim][banda[:, inicio:fim]]
            # Moeda dourada medida nos frames: 7 px de largura, ~10 px de altura.
            # Nunca aparar '?' textual: um dígito ruim continua invalidando o valor.
            ouro = (pixels[:, 0] > 140) & (pixels[:, 1] > 110) & (pixels[:, 2] < 120)
            if 5 <= fim - inicio <= 12 and 7 <= y1 - y0 <= 15 and ouro.mean() > 0.6:
                banda[:, inicio:fim] = False
        out.append(nameplates.decode_shape(banda, idx, gap).strip())
    return out


def campos(textos):
    out = {}
    for texto in textos:
        rotulo, sep, valor = texto.partition(':')
        if not sep:
            continue
        chave = rotulo.strip().replace(' ', '')
        v = numero(valor)
        if v is not None:
            out[chave] = v
        elif chave == 'LootType' and valor.strip() in ('Market', 'Leader'):
            out[chave] = valor.strip()
    loot, sup, bal = (out.get(k) for k in ('Loot', 'Supplies', 'Balance'))
    # Balance só é confiável quando os três valores do MESMO painel/quadro conferem.
    if bal is not None and (loot is None or sup is None or bal != loot - sup):
        out.pop('Balance', None)
    return out


def ler(img):
    textos = linhas(img)
    return campos(textos), textos


def ler_quadro(img, sessao, box, scroll_x):
    import json
    p = sessao / 'calibracao.json'
    c = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    recorte = img.crop(box)
    recorte.paste((0, 0, 0), (scroll_x, 0, recorte.width, recorte.height))
    valores, textos = ler(recorte)
    r = c.get('regioes', {})
    h = r.get('hunt', {})
    if not h or tuple(box) != (h['left'], h['top'], h['left'] + h['width'], h['top'] + h['height']):
        return valores, textos
    for painel, campo, outro in [('xp', 'RawXPGain', 'RawXPGain'), ('supply', 'Supplies', 'GoldValue'), ('loot', 'Loot', 'GoldValue')]:
        reg = r.get(painel)
        if not reg:
            continue
        x, y, w, h = (reg[k] for k in ('left', 'top', 'width', 'height'))
        comparacao, _ = ler(img.crop((x, y, x+w, y+h)))
        if campo in valores and outro in comparacao and valores[campo] != comparacao[outro]:
            valores.pop(campo, None)
            if campo in ('Loot', 'Supplies'):
                valores.pop('Balance', None)
    return valores, textos
