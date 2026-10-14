"""Hotkeys identificadas por referência visual; estoque não é contador de uso."""
import base64
import hashlib
import io
import re


def ler_numero(imagem, digitos):
    import numpy as np
    a = np.asarray(imagem.convert('RGB')).astype(int)
    mask = (a.min(2)>=175)&(a.max(2)-a.min(2)<35)
    cols = np.flatnonzero(mask.any(0))
    if not len(cols):
        return None
    cortes = np.flatnonzero(np.diff(cols)>1)
    texto = ''
    for x0,x1 in zip([cols[0],*[cols[i+1] for i in cortes]], [*[cols[i]+1 for i in cortes],cols[-1]+1]):
        g = mask[:,x0:x1]; ys = np.flatnonzero(g.any(1)); g = g[ys[0]:ys[-1]+1]
        matches = [n for n,formas in digitos.items() if any(g.shape==np.asarray(f).shape and np.array_equal(g,f) for f in formas)]
        if len(matches)!=1:
            return None
        texto += matches[0]
    return int(texto) if texto.isdigit() and len(texto)<=6 else None


def hotkeys(imagem, referencias, char, t, prova, serie):
    import cv2
    import numpy as np
    from PIL import Image
    arr = np.asarray(imagem.convert('RGB')); saida = []
    for ref in referencias.get('itens', []):
        if not (ref.get('identidade_confirmada') or ref.get('referencia_visual_confirmada')):
            continue
        molde = np.asarray(Image.open(io.BytesIO(base64.b64decode(ref['icone']))).convert('RGB'))
        h,w = molde.shape[:2]
        if h>arr.shape[0] or w>arr.shape[1]:
            continue
        scores = cv2.matchTemplate(arr, molde, cv2.TM_SQDIFF_NORMED)
        ys,xs = np.nonzero(scores<=.002)
        # Duplicações em inventário/janela de compra ficam inconclusivas.
        if len(xs)!=1:
            continue
        x,y = int(xs[0]),int(ys[0]); dx,dy,cw,ch = ref['contador_relativo']
        if min(x+dx,y+dy)<0 or x+dx+cw>imagem.width or y+dy+ch>imagem.height:
            continue
        guarda = ref.get('guarda_contador')
        if guarda:
            gx,gy,gw,gh = guarda['relativo']
            if not np.array_equal(np.asarray(imagem.crop((x+gx,y+gy,x+gx+gw,y+gy+gh)).convert('RGB')),np.asarray(guarda['pixels'])):
                continue
        quantidade = ler_numero(imagem.crop((x+dx,y+dy,x+dx+cw,y+dy+ch)), referencias.get('digitos',{}))
        if quantidade is None:
            continue
        ident = ref['item']
        preco = ref.get('preco_observado')
        if preco and preco.get('desde'):
            data = re.search(r'20\d{6}',serie)
            if not data or data[0] < preco['desde'].replace('-',''):
                preco = None
        saida.append({'id':hashlib.sha256(f'{prova}:{ident}:estoque'.encode()).hexdigest(),
            'char':char,'item':ident,'t':t,'serie':serie, 'valor':quantidade,
            'origem':'estoque_hotkey','unidade':'unidades','prova':prova,
            'qualidade':'icone_e_numero_integrais','local':[x,y],
            'preco_observado':preco, 'referencia':ref.get('referencia'), 'identidade_confirmada':bool(ref.get('identidade_confirmada'))})
    return saida
