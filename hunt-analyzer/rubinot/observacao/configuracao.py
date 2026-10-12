"""Leitores visuais de configuração; não iniciam monitores nem gravam snapshots."""
import hashlib
import base64
import io
import pathlib
import re
import cv2
import numpy as np
from PIL import Image
import atlas_build as ab
import nameplates
from rubinot.adapters.arquivos import ler_json as _json
AQUI = pathlib.Path(__file__).resolve().parents[2]
_atlas = None
_refs_rtc = None
_refs_roda = None
def linhas(imagem):
    global _atlas
    if _atlas is None:
        glyphs, gap = ab.load_atlas()
        indice = nameplates.shape_index(glyphs)
        indice.update(_json(AQUI / 'ui' / 'configuracoes_glifos.json').get('formas', {}))
        _atlas = (indice, gap)
    arr = np.asarray(imagem.convert('RGB'))
    # Cinza da fonte do cliente. Ícones coloridos não entram como glifos.
    hi, lo = arr.max(axis=2), arr.min(axis=2)
    # Fonte bitmap usa níveis exatos; brilho genérico também capturaria a textura da roda.
    b = np.isin(hi, (144, 160, 164, 168, 176, 192)) & (hi == lo)
    vert = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_OPEN, np.ones((20, 1), np.uint8))
    hor = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, 80), np.uint8))
    b &= ~(vert.astype(bool) | hor.astype(bool))
    out = []
    for ini, fim in ab.find_bands(b):
        if not 6 <= fim - ini <= 16:
            continue
        # Campos em colunas têm espaços grandes: decodificar por blocos separados.
        banda = b[ini:fim]
        cols = np.flatnonzero(banda.any(axis=0))
        if not len(cols):
            continue
        cortes = np.flatnonzero(np.diff(cols) > 14)
        inicios = [int(cols[0]), *[int(cols[i+1]) for i in cortes]]
        finais = [*[int(cols[i]+1) for i in cortes], int(cols[-1]+1)]
        for x0, x1 in zip(inicios, finais):
            texto = nameplates.decode_shape(banda[:, x0:x1], *_atlas)
            out.append({'x': x0, 'y': ini, 'texto': texto})
    return out


def rtc_da_imagem(imagem, textos):
    """Layout ancorado no título real. Lista de opções/oclusão nunca vira slot."""
    global _refs_rtc
    campos, slots = {}, []
    titulo = next((l for l in textos if l['texto'] == 'RTCaster' and l['y'] < 80), None)
    if not titulo or any('Prontas para usar' in l['texto'] for l in textos):
        return campos, slots
    if _refs_rtc is None:
        _refs_rtc = {k: np.asarray(Image.open(io.BytesIO(base64.b64decode(v))).convert('RGB'))
                     for k, v in _json(AQUI / 'ui' / 'rtc_referencias.json').get('templates', {}).items()}
    a = np.asarray(imagem.convert('RGB'))
    tx, ty = titulo['x'], titulo['y']

    def recorte(dx, dy, w, h):
        x, y = tx+dx, ty+dy
        if x < 0 or y < 0 or x+w > a.shape[1] or y+h > a.shape[0]:
            return None
        return a[y:y+h, x:x+w]

    def similar(patch, nome):
        ref = _refs_rtc.get(nome)
        return patch is not None and ref is not None and patch.shape == ref.shape and float(np.abs(patch.astype(float)-ref).mean()) <= 2

    if not similar(recorte(-340,64,296,14), 'cabecalho_magias') or not similar(recorte(-31,64,213,14), 'cabecalho_runas'):
        return campos, slots
    campos.update({'rtc.slots_magia': 5, 'rtc.slots_runa': 2})
    # Ler preset no controle correspondente, não na lista de presets nem no chat.
    nomes = [l['texto'].strip() for l in textos if '?' not in l['texto'] and abs(l['y']-ty-41) <= 3 and -287 <= l['x']-tx <= -160]
    if len(nomes) == 1:
        campos['preset'] = nomes[0]

    def numero(dx, dy, largura, sufixo):
        p = recorte(dx,dy,largura,22)
        if p is None:
            return None
        hi, lo = p.max(2), p.min(2)
        # Texto desabilitado tem a textura do fundo e permanece desconhecido.
        mask = np.isin(hi, (144, 160, 164, 168, 176, 192, 200)) & (hi == lo)
        linhas(imagem) if _atlas is None else None
        texto = nameplates.decode_shape(mask, *_atlas).strip()
        m = re.fullmatch(r'(\d+)'+re.escape(sufixo), texto)
        return int(m[1]) if m else None

    for tipo, quantidade in (('magia',5),('runa',2)):
        for i in range(quantidade):
            dy = 85+40*i
            patch = recorte(-339 if tipo == 'magia' else -29,dy,32,32)
            registro = {'tipo': tipo, 'slot': i+1, 'id': None, 'nome': None, 'estado': 'icone_nao_identificado', 'atual': True,
                        'prioridade': numero(-100 if tipo == 'magia' else 127,dy+4,39,'º'),
                        'creatures': numero(-200 if tipo == 'magia' else 37,dy+4,42 if tipo == 'magia' else 34,'+')}
            if tipo == 'magia':
                registro['mana_percent'] = numero(-280,dy+4,39,'%')
            if similar(patch, 'vazio'):
                registro['estado'] = 'vazio_confirmado'
            else:
                import leitura_jogo
                catalogo=_json(AQUI/'ui'/'magias.json').get('magias',[])
                referencias={k:v for k,v in _refs_rtc.items() if k not in ('vazio','cabecalho_magias','cabecalho_runas','checkbox_marcado','checkbox_desmarcado')}
                ident=leitura_jogo.icone(patch,referencias,catalogo,AQUI)
                candidatos=[ident] if ident and any(m['id']==ident and bool(m.get('runa'))==(tipo=='runa') for m in catalogo) else []
                if len(candidatos) == 1:
                    m = next((m for m in _json(AQUI/'ui'/'magias.json').get('magias',[]) if m['id'] == candidatos[0]), None)
                    if m:
                        registro.update({'id':m['id'], 'nome':m['nome'], 'estado':'icone_identificado', 'icone_origem':'referencia_cliente'})
            if patch is not None:
                registro['icone_hash'] = hashlib.sha256(patch.tobytes()).hexdigest()
            slots.append(registro)
    for chave, dy in (('virar_para_alvo',299),('combo_em_ordem_de_prioridade',317),('hotkey_tem_prioridade',335)):
        p = recorte(-339,dy,12,12)
        if similar(p,'checkbox_marcado'):
            campos['rtc.'+chave] = True
        elif similar(p,'checkbox_desmarcado'):
            campos['rtc.'+chave] = False
    return campos, slots


def roda_da_imagem(imagem, textos, campos):
    """Descrições observadas, sem converter valores para BP ou inferir conexões."""
    global _refs_roda
    titulo = next((l for l in textos if l['texto'].casefold() == 'wheel of destiny' and l['y'] < 45), None)
    if not titulo:
        return {}
    import leitura_jogo
    catalogo=_json(AQUI/'ui'/'roda_catalogo.json')
    automaticos={**leitura_jogo.selecao_roda(imagem,catalogo,textos,campos),**leitura_jogo.gemas_textos(textos,catalogo),**leitura_jogo.codigo_visivel(textos,catalogo,campos.get('pontos.total'))}
    if 'selection.limite' not in campos:return automaticos
    if _refs_roda is None:
        _refs_roda = [(r,np.asarray(Image.open(io.BytesIO(base64.b64decode(r['template']))).convert('RGB')))
                      for r in _json(AQUI/'ui'/'roda_referencias.json').get('selecoes',[])]
    a=np.asarray(imagem.convert('RGB'))
    # O cliente possui título externo e nome da aba; os offsets aceitam ambos.
    dx,dy=(-423,178) if titulo['texto'] == 'Wheel Of Destiny' else (-100,139)
    x,y=titulo['x']+dx,titulo['y']+dy
    if x < 0 or y < 0 or x+201 > a.shape[1] or y+74 > a.shape[0]:
        return automaticos
    patch=a[y:y+74,x:x+201]
    candidatos=[r for r,ref in _refs_roda if campos['selection.limite']==r['limite_observado'] and float(np.abs(patch.astype(float)-ref).mean())<=2]
    if len(candidatos)!=1:
        return automaticos
    r=candidatos[0]
    return {**automaticos,'selection.id_observado':r['id'],'selection.nome':r['nome'],
            'selection.efeitos_texto':r['efeitos_texto'],'selection.texto_parcial':r['texto_parcial'],
            'selection.efeito_ativo_confirmado':False}


def cura_da_imagem(imagem, textos):
    titulo = next((l for l in textos if l['texto'] == 'Cura' and l['y'] < 80), None)
    if not titulo or not any(l['texto'] == 'Cura por magia' for l in textos):
        return {}, []
    refs = _json(AQUI/'ui'/'janelas_referencias.json').get('cura_icones', {})
    arr = np.asarray(imagem.convert('RGB'))
    tx, ty = titulo['x']-203, titulo['y']-41
    def patch(x,y,w,h):
        x,y=x+tx,y+ty
        return arr[y:y+h,x:x+w] if x>=0 and y>=0 and x+w<=arr.shape[1] and y+h<=arr.shape[0] else None
    def texto(x,y,w,h):
        p=patch(x,y,w,h)
        if p is None:return None
        hi,lo=p.max(2),p.min(2)
        mask=(hi>=140)&(hi.astype(int)-lo.astype(int)<15)
        return nameplates.decode_shape(mask,*_atlas).strip()
    preset = next((l['texto'] for l in textos if abs(l['x']-tx-202)<4 and abs(l['y']-ty-123)<4 and '?' not in l['texto']), None)
    campos={'preset':preset} if preset else {}
    slots=[]
    for i,y in enumerate((100,143,188)):
        icon=patch(255,y,32,32);ident=None;estado='icone_nao_identificado'
        import leitura_jogo
        key=leitura_jogo.icone(icon,refs,_json(AQUI/'ui'/'magias.json').get('magias',[]),AQUI)
        if key:ident=key if key!='vazio' else None;estado='icone_identificado' if ident else 'vazio_confirmado'
        pct=next((l['texto'] for l in textos if abs(l['y']-ty-(111,148,199)[i])<4 and abs(l['x']-tx-319)<4), '')
        m=re.fullmatch(r'(\d{1,3})%',pct)
        slots.append({'tipo':'autocura','slot':i+1,'id':ident,'estado':estado,
                      'vida_percent':int(m[1]) if m and int(m[1])<=100 else None,'atual':True})
    for magia,x in (('heal_friend',255),('nature_s_embrace',545)):
        rec=patch(x+2,269,108,105)
        nomes='\n'.join(l['texto'] for l in linhas(Image.fromarray(rec))) if rec is not None else None
        # Uma lista pode ter nomes ilegíveis: não atribuir a EK/RP pelo nome.
        campos[magia+'.destinos_texto']=nomes if nomes and '?' not in nomes else None
        for i,y in enumerate((284,340)):
            p=patch(x+178,y,12,12)
            ativo=None
            if p is not None:
                cores=p.max(2).astype(int)-p.min(2).astype(int)
                # Só uma marca clara na caixa prova ativação; fundo cinza pode ser desabilitado.
                if np.count_nonzero((p.max(2)>=160)&(cores<15))>=7:ativo=True
                elif np.std(p)>1 and p.max()<160:ativo=False
            pct=texto(x+190,y+14,44,18);m=re.fullmatch(r'(\d{1,3})%',pct or '')
            slots.append({'tipo':'party','slot':i+1,'id':magia,'destino_indice':i+1,'vocacao_destino':None,
                          'ativo':ativo,'vida_percent':int(m[1]) if m and int(m[1])<=100 else None,'atual':True})
    import leitura_jogo
    return campos,leitura_jogo.destinatarios(slots,campos,[])


def campos_das_linhas(tipo, textos):
    """Só textos integralmente decodificados. Não inferir investimento pela cor."""
    campos, slots = {}, []
    limpas = [l['texto'].strip() for l in textos if '?' not in l['texto']]
    if tipo == 'roda':
        for texto in limpas:
            m = re.fullmatch(r'(?:Points:?\s*)?(\d+)\s*/\s*(\d+)', texto)
            # Um 0/200 na Information não é o total: a posição é validada à parte.
            if m:
                campos.setdefault('pares_visiveis', []).append({'livres_ou_atual': int(m[1]), 'total_ou_limite': int(m[2])})
        for l in textos:
            if l['texto'].strip() == 'Selection':
                abaixo = [v for v in textos if 8 <= v['y']-l['y'] <= 30 and abs(v.get('x',0)-l.get('x',0)) < 100]
                for v in abaixo:
                    m = re.fullmatch(r'(\d+)\s*/\s*(\d+)',v['texto'].strip())
                    if m and int(m[1]) <= int(m[2]):
                        campos['selection.pontos'], campos['selection.limite'] = int(m[1]), int(m[2])
            if l['texto'].strip().casefold() != 'available promotion points':
                continue
            abaixo = [v for v in textos if 8 <= v['y']-l['y'] <= 30 and abs(v.get('x', 0)-l.get('x', 0)) < 100]
            for v in abaixo:
                m = re.fullmatch(r'(\d+)\s*/\s*(\d+)', v['texto'].strip())
                if m and 0 <= int(m[1]) <= int(m[2]):
                    campos['pontos.livres'], campos['pontos.total'] = int(m[1]), int(m[2])
                    campos['pontos.investidos'] = int(m[2])-int(m[1])
        grupos = {'Dedication Perks': 'dedication', 'Conviction Perks': 'conviction',
                  'Vessels': 'vessels', 'Revelation Perks': 'revelation',
                  'Information': 'information', 'Selection': 'selection'}
        cabecalhos = [(l['y'], l.get('x', 0), grupos[l['texto'].strip()]) for l in textos if l['texto'].strip() in grupos]
        rotulos = {'Hit Points', 'Mana', 'Capacity', 'Mitigation Mult.', 'Magic Skill Boost',
                   'Aug. Forked Spells', 'Aug. Mass Healing', 'Aug. Heal Friend', 'Aug. Strong Ice Wave',
                   'VR Top Left', 'VR Bottom Left', 'VR Bottom Right', 'Healing Link', 'Damage and Healing', 'Ice', 'Fire', 'Energy', 'Earth',
                   'Avatar of Nature', 'Twin Bursts', 'Gift of Life'}
        for l in textos:
            nome = l['texto'].strip()
            if nome not in rotulos:
                continue
            prox = [v for v in textos if abs(v['y']-l['y']) <= 2 and v.get('x', 0) > l.get('x', 0)+80]
            prox.sort(key=lambda v: v.get('x', 0))
            if not prox or '?' in prox[0]['texto']:
                continue
            anteriores = [(y, g) for y, x, g in cabecalhos if y < l['y'] and abs(x-l.get('x', 0)) < 120]
            if anteriores:
                grupo = max(anteriores)[1]
                campos[f'{grupo}.{nome}'] = prox[0]['texto'].strip()
    for texto in limpas:
        m = re.fullmatch(r'(?:Current\s+)?Preset\s*:?\s*(.+)', texto, re.I)
        if m and m[1].strip():
            campos['preset'] = m[1].strip()
    # Presença de nome/encantamento dentro da janela RTC; nunca cast no console.
    if tipo == 'rtc':
        magias = _json(AQUI / 'ui' / 'magias.json').get('magias', [])
        identificadas = []
        for m in magias:
            encontrados = [l for l in textos if l['texto'].strip().casefold() in {m['nome'].casefold(), (m.get('palavras') or '\0').casefold()}]
            for encontrado in encontrados:
                identificadas.append({'id': m['id'], 'nome': m['nome'], 'x': encontrado.get('x'), 'y': encontrado['y']})
                # Um nome numa lista de opções não prova presença num slot configurado.
                mesma_linha = [l['texto'].strip() for l in textos if abs(l['y']-encontrado['y']) <= 2]
                slot = next((re.fullmatch(r'Slot\s+(\d+):?', t, re.I) for t in mesma_linha if re.fullmatch(r'Slot\s+(\d+):?', t, re.I)), None)
                if slot:
                    registro = {'id': m['id'], 'nome': m['nome'], 'slot': int(slot[1]), 'prioridade': None, 'creatures': None}
                    for nome, chave in (('Priority', 'prioridade'), ('Creatures', 'creatures')):
                        leitura = next((re.fullmatch(nome+r'\s*:\s*(\d+)', t, re.I) for t in mesma_linha if re.fullmatch(nome+r'\s*:\s*(\d+)', t, re.I)), None)
                        if leitura:
                            registro[chave] = int(leitura[1])
                    slots.append(registro)
        if identificadas:
            campos['magias_identificadas_sem_confirmacao_de_slot'] = identificadas
    for texto in limpas:
        m = re.fullmatch(r'(?:Vocation|Vocação)\s*:\s*(Elder Druid|Master Sorcerer)', texto, re.I)
        if m:
            campos['vocacao'] = 'ED' if m[1].lower() == 'elder druid' else 'MS'
    return campos, slots

