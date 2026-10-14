"""Leitura conservadora de painéis comprimidos, sem truncar dígitos desconhecidos."""
import functools
import re

import cv2
import numpy as np
import atlas_build as ab
import nameplates
from rubinot.observacao import geometria_paineis

NUMERO = re.compile(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(k?)')


def numero(texto):
    texto = texto.strip()
    m = NUMERO.fullmatch(texto)
    if not m:
        return None
    return int(texto.rstrip('k').replace(',', '')) * (1000 if m[1] else 1)


@functools.lru_cache(maxsize=1)
def _atlas():
    import json
    from pathlib import Path
    glyphs, gap = ab.load_atlas()
    idx = nameplates.shape_index(glyphs)
    refs = json.loads((Path(__file__).resolve().parent/'ui'/'paineis_referencias.json').read_text(encoding='utf8'))
    idx.update(refs.get('glifos', {}))
    return idx, gap


def linhas_detalhadas(img):
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
            antes = nameplates.decode_shape(banda[:, :inicio], idx, gap).strip()
            if (5 <= fim - inicio <= 12 and 7 <= y1 - y0 <= 15 and ouro.mean() > 0.6
                    and re.search(r'\d(?:[\d,]*k)?$', antes)):
                banda[:, inicio:fim] = False
        out.append({'texto': nameplates.decode_shape(banda, idx, gap).strip(),
                    'box': [0, int(y0), img.width, int(y1)]})
    return out


def linhas(img):
    return [r['texto'] for r in linhas_detalhadas(img)]


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
    recorte = recortar_painel(img, sessao, 'hunt', box, scroll_x)
    valores, textos = ler(recorte) if recorte is not None else ({}, [])
    for chave in ('RawXPGain','XPGain','RawXP/h','XP/h'):
        valores.pop(chave,None)
    valores.update(ler_xp(img,sessao))
    # Supply/Loot são estimativas de outra janela: nunca invalidam a economia.
    valores.pop('Session', None)
    return valores, textos


def recortar_painel(img, sessao, nome, box=None, scroll_x=None):
    """Reconhece o painel no próprio quadro; nunca usa posição antiga em tela inteira."""
    geometria = geometria_paineis.detectar(img)
    if nome in geometria['regioes']:
        return geometria_paineis.recorte(img, geometria['regioes'][nome])
    if min(img.size) >= 300 or nome in geometria['ambiguos']:
        return None
    # Compatibilidade com imagens legadas já recortadas e ferramentas de diagnóstico.
    box = box or regiao(sessao, nome)
    if not box:
        return None
    im = img.crop(box)
    if scroll_x is not None and 0 <= scroll_x < im.width:
        im.paste((0, 0, 0), (scroll_x, 0, im.width, im.height))
    return im


def ler_painel(img, sessao, nome):
    im = recortar_painel(img, sessao, nome)
    return ler(im) if im is not None else ({}, [])


def tempo_sessao(textos):
    """Session HH:MMh do Party Hunt, com resolução de um minuto (sem extrapolar)."""
    for texto in textos:
        m = re.fullmatch(r'Session:\s*(\d{1,4}):([0-5]\d)h', texto.strip())
        if m:
            return (int(m[1])*60 + int(m[2]))*60
    return None


def ler_tempo_sessao(img, sessao):
    _, textos = ler_painel(img, sessao, 'party')
    return tempo_sessao(textos)


def regiao(sessao, nome):
    import json
    from pathlib import Path
    sessao = Path(sessao)
    p = sessao/'calibracao.json'
    c = json.loads(p.read_text(encoding='utf8')) if p.exists() else {}
    r = c.get('regioes', {}).get(nome)
    if r:
        return (r['left'],r['top'],r['left']+r['width'],r['top']+r['height'])
    p = sessao/'layout.json'
    lay = json.loads(p.read_text(encoding='utf8')) if p.exists() else {}
    return tuple(lay[nome]['box']) if lay.get(nome,{}).get('box') else None


def ler_xp(img, sessao):
    """XP exclusivamente do XP Analyser identificado no quadro. Sem fallback."""
    valores, _ = ler_painel(img, sessao, 'xp')
    return {k:v for k,v in valores.items() if k in ('RawXPGain','XPGain','RawXP/h','XP/h')}


def ler_input(img, sessao):
    """Total/DPS e distribuição visível; ícone sem identidade fica desconhecido."""
    recorte = recortar_painel(img, sessao, 'input')
    if recorte is None:
        return {'origem':'Input Analyser','total':None,'max_dps':None,'tipos':[], 'estado':'sem_regiao'}
    textos = linhas(recorte); total = maximo = None; dano = False; tipos = []; tipos_on = False
    from pathlib import Path
    from PIL import Image
    with Image.open(Path(__file__).resolve().parent/'ui'/'input_received_damage.png') as molde:
        ref=np.asarray(molde.convert('RGB')); arr=np.asarray(recorte.convert('RGB'))
    if arr.shape[0]>=ref.shape[0] and arr.shape[1]>=ref.shape[1]:
        dano = bool(cv2.matchTemplate(arr,ref,cv2.TM_SQDIFF_NORMED).min()<=.002)
    for texto in textos:
        if 'Received Damage' in texto:
            dano = True; tipos_on = False
        elif 'Received Healing' in texto or 'Damage Sources' in texto:
            dano = False; tipos_on = False
        elif 'DamageTypes' in texto.replace(' ',''):
            tipos_on = True; dano = False
        elif dano:
            campos_linha = campos([texto])
            total = campos_linha.get('Total',total); maximo = campos_linha.get('Max-DPS',maximo)
        elif tipos_on:
            m = re.search(r'(?<![0-9?])([0-9,]+)\s+\(',texto)
            if m:
                pct = re.search(r'\(([0-9]+(?:\.[0-9]+)?)%[)?]*$',texto)
                tipos.append({'tipo':None,'valor':numero(m[1]),'percentual':float(pct[1]) if pct else None,'texto':texto})
    distribuicao = distribuicao_input(recorte)
    return {'origem':'Input Analyser','total':total,'max_dps':maximo,'tipos':distribuicao['tipos'] or tipos,
            'fontes':distribuicao['fontes'], 'modo':distribuicao['modo'],
            'textos':textos,'estado':'observado' if total is not None else 'sem_leitura',
            'limite':'Tipos sem ícone identificado permanecem sem nome; total não separa absorção pelo escudo.'}


@functools.lru_cache(maxsize=1)
def referencias():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parent/'ui'/'paineis_referencias.json').read_text(encoding='utf8'))


def distribuicao_input(imagem):
    """Tipos por ícone confirmado; fontes por texto integral; modo desconhecido conservado."""
    arr = np.asarray(imagem.convert('RGB')); icones = []
    for tipo, pixels in referencias()['tipos'].items():
        ref = np.asarray(pixels, dtype=np.uint8)
        if arr.shape[0] < ref.shape[0] or arr.shape[1] < ref.shape[1]:
            continue
        score = cv2.matchTemplate(arr[:, :min(32,arr.shape[1])], ref, cv2.TM_SQDIFF_NORMED)
        ys, xs = np.where(score <= .008)
        icones.extend((tipo,int(x),int(y),ref.shape[0]) for y,x in zip(ys,xs))
    secao = None; tipos = []; fontes = []
    for linha in linhas_detalhadas(imagem):
        texto = linha['texto']; junto = texto.replace(' ','')
        if 'DamageTypes' in junto:
            secao = 'tipos'; continue
        if 'DamageSources' in junto:
            secao = 'fontes'; continue
        if 'Received' in texto or 'Healing' in texto:
            secao = None
        if secao is None:
            continue
        m = re.fullmatch(r'(.*?)\s*([\d,]+k?)\s+\(([\d]+(?:\.\d+)?)%[)?]*',texto)
        if not m:
            continue
        if re.search(r'\d',m[1]):
            continue
        ident = {k for k,x,y,h in icones if abs(y-linha['box'][1])<=3}
        nome = m[1].strip()
        r = {'tipo': next(iter(ident)) if len(ident)==1 else None,
             'nome': nome if secao=='fontes' and re.fullmatch(r"[A-Za-z][A-Za-z '\-]+",nome) else None,
             'valor': numero(m[2]), 'percentual': float(m[3]), 'texto': texto,
             'box': linha['box'], 'resolucao':1000 if m[2].endswith('k') else 1}
        if r['percentual'] > 100:
            continue
        (tipos if secao=='tipos' else fontes).append(r)
    return {'tipos':tipos,'fontes':fontes,'cobertura':'somente_linhas_visiveis','modo':'desconhecido'}

