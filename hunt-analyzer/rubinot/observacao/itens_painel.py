"""Itens visíveis de Supply/Loot: contagem estimada, identidade só por referência."""
import functools
import hashlib
from pathlib import Path
import re

import atlas_build as ab
import cv2
import nameplates
import numpy as np
from PIL import Image
import painel_stream as ps


@functools.lru_cache(maxsize=1)
def modelos():
    raiz = Path(__file__).resolve().parents[2]/'ui'
    out = {}
    for nome in ('avalanche','great_fireball','stone_shower','thunderstorm','sudden_death'):
        with Image.open(raiz/f'magia_{nome}_rune.png') as im:
            a = np.asarray(im.convert('RGBA'))
        # O contador se sobrepõe ao rodapé do sprite; identidade exige a parte superior.
        out[nome+'_rune'] = (a[:22,:,:3].copy(),(a[:22,:,3]>0).astype('uint8')*255)
    return out


def identificar(imagem):
    a = np.asarray(imagem.convert('RGB')); scores = []
    for nome,(ref,mask) in modelos().items():
        if a.shape[0]<ref.shape[0] or a.shape[1]<ref.shape[1]:
            continue
        score = cv2.matchTemplate(a,ref,cv2.TM_SQDIFF_NORMED,mask=mask)
        valor = float(np.nanmin(score))
        if valor<=.025:
            scores.append((valor,nome))
    return scores[0][1] if len(scores)==1 else None


def ler(imagem):
    linhas = ps.linhas_detalhadas(imagem)
    inicio = next((r['box'][3] for r in linhas if r['texto'].startswith('Per Hour:')),None)
    fim = next((r['box'][1] for r in linhas if r['texto'].startswith('Target:')),None)
    if inicio is None or fim is None or inicio>=fim:
        return {'itens':[],'estado':'lista_nao_delimitada','cobertura':'parcial'}
    arr = np.asarray(imagem.convert('RGB')).astype(int)
    branco = (arr.min(2)>=175)&(arr.max(2)-arr.min(2)<35)
    b = branco[inicio:fim]; idx = ps.referencias()['digitos_itens']; itens = []
    for y,z in ab.find_bands(b):
        if z-y!=8:
            continue
        banda = b[y:z]; xs = np.flatnonzero(banda.any(0))
        if not len(xs):
            continue
        cortes = np.flatnonzero(np.diff(xs)>=5)
        for a,c in zip([xs[0],*[xs[i+1] for i in cortes]],[*[xs[i]+1 for i in cortes],xs[-1]+1]):
            texto = nameplates.decode_shape(banda[:,a:c],idx)
            if not re.fullmatch(r'\d{1,6}',texto):
                continue
            # A quantidade fica à direita do sprite de 32 px, 22 px abaixo do topo.
            x0,y0 = max(0,int(c)-34),max(0,inicio+int(y)-22)
            box = [x0,y0,min(imagem.width,int(c)+2),min(imagem.height,y0+32)]
            icone = imagem.crop(box)
            itens.append({'item':identificar(icone),'quantidade':int(texto),'texto':texto,
                          'estimativa':True,'resolucao':1,'box':box,
                          'icone_sha256':hashlib.sha256(icone.tobytes()).hexdigest(),
                          'estado':'contador_lido'})
    return {'itens':itens,'estado':'lido' if itens else 'sem_contadores_legiveis',
            'cobertura':'somente_contadores_visiveis','identidades':'somente_referencias_confirmadas'}
