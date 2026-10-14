"""Geometria observada no quadro; não depende do servidor nem altera calibração."""
import functools
import hashlib
import json
from pathlib import Path
import re

import cv2
import numpy as np
from PIL import Image
import atlas_build as ab
import nameplates

TITULOS = {'hunt': 'Hunt Analyser', 'xp': 'XP Analyser', 'party': 'Party Hunt',
           'input': 'Input Analyser', 'supply': 'Supply Analyser', 'loot': 'Loot Analyser',
           'battle': 'Battle List', 'skills': 'Skills'}
VERSAO = 1


@functools.lru_cache(maxsize=1)
def modelos():
    raiz = Path(__file__).resolve().parents[2]
    glyphs, gap = ab.load_atlas()
    with Image.open(raiz/'botao_x.png') as im:
        botao = np.asarray(im, dtype=np.float32)
    return botao, nameplates.shape_index(glyphs), gap


def _identidade(texto):
    # Não aceitar Loot como Supply pelo sufixo comum Analyser.
    s = re.sub(r'[^a-z ]', '', texto.lower())
    for chave, titulo in TITULOS.items():
        palavras = titulo.lower().split()
        if all(p in s for p in palavras):
            return chave
    if 'supply analyse' in s:
        return 'supply'
    return None


def _detectar(imagem, escala):
    w, h = imagem.size
    normal = imagem if escala == 1 else imagem.resize((round(w/escala), round(h/escala)), Image.Resampling.NEAREST)
    arr = np.asarray(normal.convert('RGB'))
    cinza = arr.max(2).astype(np.float32)
    botao, idx, gap = modelos()
    if min(cinza.shape) < max(botao.shape):
        return {}, []
    res = cv2.matchTemplate(cinza, botao, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(res >= .86)
    picos = []
    for i in np.argsort(res[ys, xs])[::-1][:300]:
        y, x = int(ys[i]), int(xs[i])
        if all(abs(y-a)>6 or abs(x-b)>6 for a,b in picos):
            picos.append((y,x))
    achados = {}; ambiguos = set()
    for y,x in sorted(picos):
        if y+13 >= cinza.shape[0]:
            continue
        # Moldura vertical inteira, não a largura presumida de 158 px.
        faixa = (cinza[y:y+13] >= 95).mean(0)
        candidatos = [i for i in range(max(0,x-700),max(0,x-60))
                      if faixa[i]>.9 and faixa[i+1]>.9]
        if not candidatos:
            continue
        esquerda = max(candidatos)+3
        b = cinza[y+1:y+13,esquerda:x]>115
        titulo = ' '.join(nameplates.decode_shape(b[a:z],idx,gap)
                          for a,z in ab.text_bands(b,input_top=None))
        chave = _identidade(titulo)
        if not chave:
            continue
        abaixo = [a for a,c in picos if abs(c-x)<=6 and a>y]
        fundo = min(abaixo)-2 if abaixo else cinza.shape[0]-4
        # O limite esquerdo da scrollbar acompanha o botão da moldura.
        box = [round(v*escala) for v in (esquerda,y+13,x-1,fundo)]
        if box[2]-box[0]<50 or box[3]-box[1]<5:
            continue
        if chave in achados:
            ambiguos.add(chave)
        achados[chave] = {'box':box,'escala':escala,'titulo':titulo,
                           'estado':'identificado','origem':'moldura_e_titulo'}
    for chave in ambiguos:
        achados.pop(chave,None)
    return achados, sorted(ambiguos)


def detectar(imagem):
    """Cache no próprio quadro; nenhuma coordenada é reaproveitada em outra imagem."""
    if imagem.info.get('_geometria_paineis', {}).get('dimensoes') == list(imagem.size):
        return imagem.info['_geometria_paineis']
    regioes, ambiguos = _detectar(imagem,1)
    # Escalas suportadas: só entram quando a moldura normal não é reconhecida.
    if not regioes and min(imagem.size)>=300:
        for escala in (.75,1.25,1.5,2):
            candidatos, amb = _detectar(imagem,escala)
            if candidatos:
                regioes, ambiguos = candidatos,amb
                break
    assinatura = {'dimensoes':list(imagem.size),'regioes':regioes,'ambiguos':ambiguos}
    r = {**assinatura,'versao':VERSAO,
         'revisao':hashlib.sha256(json.dumps(assinatura,sort_keys=True).encode()).hexdigest()[:20]}
    imagem.info['_geometria_paineis'] = r
    return r


def recorte(imagem, regiao):
    b = regiao['box']; escala = regiao.get('escala',1)
    if not (0<=b[0]<b[2]<=imagem.width and 0<=b[1]<b[3]<=imagem.height):
        return None
    im = imagem.crop(b)
    if escala != 1:
        im = im.resize((round(im.width/escala),round(im.height/escala)),Image.Resampling.NEAREST)
    return im
