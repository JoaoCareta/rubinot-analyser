"""Ícone real + glifos + nome; número flutuante isolado não é Hazard."""
import base64
import io
import re


def ler(imagem, char, viewport, referencia, indice, gap=5, integrantes=None, nomes_observados=None):
    import cv2
    import numpy as np
    from PIL import Image
    import nameplates
    desconhecido = {'nivel': None, 'char': char, 'estado': 'sem_leitura', 'visiveis': []}
    permitidos = {n.casefold() for n in (integrantes or []) if isinstance(n,str)} | {char.casefold()}
    if not referencia.get('icone_png'):
        return desconhecido
    arr = np.asarray(imagem.convert('RGB')); x0,y0,x1,y1 = viewport
    if not (0 <= x0 < x1 <= imagem.width and 0 <= y0 < y1 <= imagem.height):
        return desconhecido
    modelo = np.asarray(Image.open(io.BytesIO(base64.b64decode(referencia['icone_png']))).convert('RGB'))
    h,w = modelo.shape[:2]; recorte = arr[y0:y1,x0:x1]
    if recorte.shape[0] < h or recorte.shape[1] < w:
        return desconhecido
    mask = np.zeros((h,w),np.uint8); a,b,c,d = referencia['mascara']; mask[b:d,a:c]=255
    matches = cv2.matchTemplate(recorte, modelo, cv2.TM_SQDIFF_NORMED, mask=mask)
    ys,xs = np.where(np.isfinite(matches) & (matches <= .002))
    nomes = nomes_observados if nomes_observados is not None else nameplates.nameplates(imagem, sidx=indice, viewport=viewport)
    vistos = []; usados = []
    for x,y in sorted(zip(xs.tolist(),ys.tolist()),key=lambda p:float(matches[p[1],p[0]])):
        if any(abs(x-a)<w and abs(y-b)<h for a,b in usados): continue
        usados.append((x,y)); nx,ny,nf,nb = referencia['numero']
        if x+nf > recorte.shape[1] or y+nb > recorte.shape[0]: continue
        patch = recorte[y+ny:y+nb,x+nx:x+nf]
        branco = patch.min(2)>=170
        # Recortar somente o primeiro bloco: outro texto próximo não vira dígito.
        cols = branco.any(0); ativos = np.flatnonzero(cols)
        if not len(ativos) or ativos[0]>2: continue
        fim=int(ativos[0]); vazio=0
        while fim<len(cols):
            vazio=0 if cols[fim] else vazio+1
            if vazio>3: break
            fim+=1
        texto=nameplates.decode_shape(branco[:,:fim],indice,gap)
        if not re.fullmatch(r'\d{1,3}',texto): continue
        candidatos=[n for n in nomes if (n['tipo']=='jogador' or n['nome'].casefold() in permitidos)
                    and abs(x-n['px'][0])<=35 and 8<=y-n['px'][1]<=60]
        nome=candidatos[0]['nome'] if len(candidatos)==1 else None
        if nome is None or nome.casefold() not in permitidos:
            continue
        vistos.append({'nivel':int(texto),'char':nome,'regiao':[x+x0,y+y0,w,h],
                       'origem':'icone_e_glifos', 'associacao':'unica' if nome else 'inconclusiva'})
    niveis={r['nivel'] for r in vistos}
    repetidos=len({r['char'].casefold() for r in vistos})!=len(vistos)
    return {**desconhecido,'visiveis':vistos,
            'integrantes_observados':[r['char'] for r in vistos],
            **({'nivel':next(iter(niveis)),'estado':'observado','origem':'icone_glifos_integrantes_pt'}
               if len(niveis)==1 and not repetidos else
               {'estado':'inconclusivo_integrantes'} if vistos else {})}
