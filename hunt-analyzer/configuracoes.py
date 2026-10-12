"""Leituras parciais de RTC/roda; provas independentes dos quadros descartáveis.

Contrato v1: personagem/sessão/preset, campos com valor/unidade/origem/instante/
qualidade/prova. Observado nunca equivale a aplicado. Sem escrever no cliente.
"""
import hashlib
import base64
import io
import json
import os
import pathlib
import re
import threading
import time

import cv2
import numpy as np
from PIL import Image
import atlas_build as ab
import nameplates

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = pathlib.Path(os.environ.get('HUNT_CONFIGURACOES_RAIZ') or AQUI / 'configuracoes_player')
TRAVA = threading.RLock()
TITULOS = {'roda': ('Wheel of Destiny',), 'rtc': ('RTC', 'Real Time Combat', 'RTCaster'), 'cura': ('Cura',)}
_atlas = None
_refs_rtc = None
_refs_roda = None
_refs_janelas = None
ESTADO_LEITOR = {'estado': 'aguardando leitura', 'char': None, 'instante': None}


def _json(p, padrao=None):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {} if padrao is None else padrao


def _grava(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(p)


def assinatura(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def pontos_total(char, valor=None):
    """Total informado é persistente; leitura visual posterior tem precedência."""
    if not char or len(char) > 80:
        raise ValueError('Personagem não identificado.')
    with TRAVA:
        p = RAIZ / _chave(char) / 'pontos.json'
        if valor is not None:
            if not isinstance(valor, int) or isinstance(valor, bool) or not 0 <= valor <= 10000:
                raise ValueError('Informe o total de pontos exibido na roda.')
            _grava(p, {'valor': valor, 'origem': 'informado', 'instante': time.time()})
        return _json(p)


def guardar_sugestao(char, sugestao):
    if not char or len(char) > 80 or not isinstance(sugestao, dict):
        raise ValueError('Sugestão ou personagem inválido.')
    if sugestao.get('contexto', {}).get('char') != char:
        raise ValueError('A sugestão pertence a outro personagem.')
    if len(json.dumps(sugestao)) > 1500000:
        raise ValueError('Sugestão excede o limite local.')
    payload = {k:v for k,v in sugestao.items() if k not in ('id', 'instante')}
    if not all(k in payload for k in ('regras_versao', 'modelo_versao', 'contexto', 'rtc', 'cura', 'roda')):
        raise ValueError('Conjunto incompleto.')
    total = consultar(char).get('pontos', {}).get('valor')
    if payload['contexto'].get('total') != total:
        raise ValueError('Os pontos mudaram. Aguarde o novo cálculo.')
    ident = assinatura(payload)
    registro = {**payload, 'id': ident, 'instante': time.time()}
    with TRAVA:
        pasta = RAIZ / _chave(char)
        caminho = pasta / f'sugestao_{ident}.json'
        if not caminho.exists():
            _grava(caminho, registro)
        _grava(pasta / 'sugestao_atual.json', registro)
    return registro


def confirmar(char, ident):
    with TRAVA:
        pasta = RAIZ / _chave(char)
        s = _json(pasta / 'sugestao_atual.json')
        if not re.fullmatch('[a-f0-9]{64}', ident or '') or s.get('id') != ident:
            raise ValueError('A sugestão mudou. Confira o conjunto atual antes de confirmar.')
        estado = consultar(char)
        if estado.get('pontos', {}).get('valor') != s['contexto'].get('total'):
            raise ValueError('O total de pontos mudou.')
        preset = estado.get('rtc', {}).get('preset')
        if s['contexto'].get('preset') != preset:
            raise ValueError('O preset mudou. Aguarde a leitura do conjunto atual.')
        c = {'versao': 2, 'sugestao_id': ident, 'char': char, 'preset': preset,
             'instante': time.time(), 'origem': 'confirmado_por_usuario', 'aplicado_lido': False}
        _grava(pasta / 'confirmacao.json', c)
        return c


def concordancia(sugestao, observado):
    diferencas, pendentes = [], []
    for linha in sugestao.get('rtc', {}).get('linhas', []):
        slot = next((s for s in observado.get('rtc', {}).get('slots', [])
                     if s.get('tipo') == linha.get('tipo') and s.get('slot') == linha.get('slot')), {})
        for campo in ('id', 'creatures', 'prioridade', *(() if linha.get('tipo') == 'runa' else ('mana_percent',))):
            if campo=='creatures' and linha.get('runa') and linha.get('alvos')==1:continue
            if slot.get(campo) is None or slot.get('atual') is False:
                pendentes.append(f"RTC {linha['slot']}: {campo}")
            elif slot[campo] != linha.get(campo):
                diferencas.append(f"RTC {linha['slot']}: {campo}")
    for linha in sugestao.get('cura',{}).get('linhas',[]):
        if linha.get('ativo') is False:continue
        slots=observado.get('cura',{}).get('slots',[])
        slot=next((s for s in slots if s.get('id')==linha.get('id') and (s.get('vocacao_destino')==linha.get('vocacao_destino') if linha.get('vocacao_destino') else s.get('tipo')=='autocura')),None)
        if not slot or slot.get('vida_percent') is None or linha.get('vida_percent') is None:pendentes.append('cura '+linha.get('id',''))
        elif slot['vida_percent']!=linha['vida_percent']:diferencas.append('cura '+linha['id']+': vida_percent')
    for fatia,pontos in sugestao.get('roda',{}).get('pontos',{}).items():
        valor=observado.get('roda',{}).get('campos',{}).get('fatias.'+fatia,{}).get('valor')
        if valor is None:pendentes.append('roda '+fatia)
        elif valor!=pontos:diferencas.append('roda '+fatia)
    for campo,lido in observado.get('roda',{}).get('campos',{}).items():
        if campo.startswith('fatias.') and lido.get('valor')!=sugestao.get('roda',{}).get('pontos',{}).get(campo[7:],0):
            if 'roda '+campo[7:] not in diferencas:diferencas.append('roda '+campo[7:])
    for gema in sugestao.get('roda',{}).get('gemas',[]):
        lida=observado.get('roda',{}).get('campos',{}).get('gemas.'+gema['dominio'],{}).get('valor')
        if not lida:pendentes.append('gema '+gema['dominio'])
        elif lida.get('tier')!=gema.get('tier'):diferencas.append('gema '+gema['dominio']+': qualidade')
        elif gema.get('mod') is not None and not any(m.get('mod')==gema['mod'] and m.get('grau')==gema.get('grau') for m in lida.get('modificadores',[])):pendentes.append('gema '+gema['dominio']+': modificador')
        if lida:
            for basico in gema.get('basicos',[]):
                if not any(m.get('mod')==basico['mod'] and m.get('grau')==basico['grau'] for m in lida.get('basicos',[])):pendentes.append('gema '+gema['dominio']+': básico')
    dominios={g['dominio'] for g in sugestao.get('roda',{}).get('gemas',[])}
    cat=_json(AQUI/'ui'/'roda_catalogo.json');voc=sugestao.get('contexto',{}).get('vocacao','ED')
    campos_roda=observado.get('roda',{}).get('campos',{})
    ativos={f['dominio'] for f in cat.get('vocacoes',{}).get(voc,{}).get('fatias',[]) if 37<=f.get('conviction_id',0)<=40 and campos_roda.get('fatias.'+f['id'],{}).get('valor')==f['limite']}
    for dominio in ativos:
        g=campos_roda.get('gemas.'+dominio,{}).get('valor',{})
        if g.get('estado') not in ('vazio_confirmado','observado_completo'):pendentes.append('gema '+dominio+': equipamento não lido')
    for campo,lido in observado.get('roda',{}).get('campos',{}).items():
        if campo.startswith('gemas.') and campo[6:] not in dominios and lido.get('valor',{}).get('equipada'):diferencas.append('gema extra '+campo[6:])
    for tipo in ('cura','roda'):
        if not observado.get(tipo,{}).get('completo'):pendentes.append(tipo)
    return {'estado': 'divergente' if diferencas else 'parcial' if pendentes else 'confere',
            'diferencas': diferencas, 'pendentes': pendentes}


def _chave(char):
    return hashlib.sha256(' '.join(char.lower().split()).encode('utf-8')).hexdigest()[:24]


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


def calibrar(tipo, regiao, quadro, char, sessao='calibracao'):
    if tipo not in TITULOS or not char or len(char) > 80:
        raise ValueError('Tipo ou personagem não identificado na captura.')
    with Image.open(quadro) as img:
        imagem = img.convert('RGB')
    valores = [int(regiao[k]) for k in ('left', 'top', 'width', 'height')]
    x, y, w, h = valores
    if x < 0 or y < 0 or w < 80 or h < 40 or x+w > imagem.width or y+h > imagem.height:
        raise ValueError('Marque a janela inteira dentro da captura, incluindo seu título.')
    recorte = imagem.crop((x, y, x+w, y+h))
    textos = linhas(recorte)
    titulo = next((l for l in textos if l['y'] < 45 and l['texto'].strip().casefold() in [t.casefold() for t in TITULOS[tipo]]), None)
    if not titulo:
        raise ValueError('Título não reconhecido. Inclua o cabeçalho legível; nenhuma configuração foi confirmada.')
    # Molde apenas do texto do cabeçalho, sem posição fixa na tela.
    yy = titulo['y']
    arr = np.asarray(recorte)
    mascara = (arr[yy:yy+16].max(axis=2) >= 115) & (arr[yy:yy+16].max(axis=2).astype(int)-arr[yy:yy+16].min(axis=2).astype(int)<25)
    cols = np.flatnonzero(mascara.any(axis=0))
    if len(cols) < 8:
        raise ValueError('Cabeçalho insuficiente para reconhecer outra abertura.')
    x0 = titulo.get('x', int(cols[0]))
    # Só o bloco do título, não o texto de outro painel na mesma altura.
    texto_cols = cols[cols >= x0]
    saltos = np.flatnonzero(np.diff(texto_cols) > 14)
    x1 = int(texto_cols[saltos[0]]+1 if len(saltos) else texto_cols[-1]+1)
    with TRAVA:
        pasta = RAIZ / _chave(char)
        pasta.mkdir(parents=True, exist_ok=True)
        molde = pasta / f'{tipo}_titulo.png'
        recorte.crop((x0, yy, x1, yy+16)).save(molde)
        _grava(pasta / f'{tipo}_calibracao.json', {'versao': 1, 'char': char, 'regiao': regiao,
            'offset': [x0, yy], 'titulo': titulo['texto'].strip(), 'instante': time.time()})
        return observar(tipo, recorte, char, sessao, textos=textos, origem='calibracao')


def observar(tipo, imagem, char, sessao, textos=None, origem='captura_existente', imagem_leitura=None):
    textos = linhas(imagem) if textos is None else textos
    campos, slots = campos_das_linhas(tipo, textos)
    if tipo == 'rtc':
        geometricos, reconhecidos = rtc_da_imagem(imagem_leitura or imagem, textos)
        campos.update(geometricos)
        if reconhecidos:
            slots = reconhecidos
    elif tipo == 'roda':
        campos.update(roda_da_imagem(imagem_leitura or imagem, textos, campos))
    elif tipo == 'cura':
        geometricos,slots=cura_da_imagem(imagem_leitura or imagem,textos)
        campos.update(geometricos)
    instante = time.time()
    versao = f'{time.time_ns()}'
    pasta = RAIZ / _chave(char)
    relativa = f'{_chave(char)}/{versao}_{tipo}.png'
    snapshot = {'versao': 2, 'id': versao, 'tipo': tipo, 'char': char, 'sessao': sessao,
        'preset': campos.get('preset'), 'instante': instante, 'origem': origem, 'prova': relativa,
        'completo': False, 'aplicado_confirmado': False, 'estado': 'observado_parcial', 'campos': {}, 'slots': slots,
        'vocacao': campos.get('vocacao'),
        'linhas': textos, 'pendencias': ['Campos ocultos e aplicação não confirmados']}
    if tipo=='cura':
        import leitura_jogo
        party=_json(pasta/'contexto_execucao.json').get('cura',{}).get('aliados',[])
        snapshot['slots']=leitura_jogo.destinatarios(slots,campos,party)
    for s in slots:
        s.update({'instante':instante,'prova':relativa})
    snapshot['slots_lidos'] = bool(slots)
    for k, v in campos.items():
        snapshot['campos'][k] = {'valor': v, 'unidade': 'pontos' if k.startswith('pontos.') else None,
            'origem': origem, 'instante': instante, 'qualidade': 'texto_integral', 'prova': relativa}
    with TRAVA:
        pasta.mkdir(parents=True, exist_ok=True)
        anterior = _json(pasta / f'{tipo}_atual.json')
        conteudo={'campos':campos,'slots':[{k:v for k,v in s.items() if k not in ('instante','prova')} for s in slots], 'preset':snapshot['preset']}
        snapshot['assinatura']=assinatura(conteudo)
        if anterior.get('assinatura')==snapshot['assinatura'] and anterior.get('sessao')==sessao:
            return {'ok':True,'snapshot':anterior,'alterou':False}
        imagem.save(RAIZ / relativa)
        # Só acumular no mesmo personagem/sessão/preset identificado. Não mesclar presets ocultos.
        if snapshot['preset'] and time.strftime('%Y%m%d',time.localtime(anterior.get('instante',0)))==time.strftime('%Y%m%d',time.localtime(snapshot['instante'])) and all(anterior.get(k) == snapshot.get(k) for k in ('char', 'sessao', 'preset')):
            # A descrição de uma seleção não pode migrar para outra fatia.
            # Investimentos não migram após mudança do total investido: a edição pode
            # ter redistribuído casas ainda não abertas novamente.
            mudou_roda=tipo=='roda' and (campos.get('pontos.investidos') is not None and campos['pontos.investidos']!=anterior.get('campos',{}).get('pontos.investidos',{}).get('valor') or any(k.startswith('fatias.') and k in anterior.get('campos',{}) and v!=anterior['campos'][k]['valor'] for k,v in campos.items()))
            herdados={k:v for k,v in anterior.get('campos',{}).items() if not k.startswith('selection.') and not (mudou_roda and k.startswith(('fatias.','gemas.')))}
            snapshot['campos'] = {**herdados, **snapshot['campos']}
            # Um slot novo desconhecido/vazio deve retirar a identificação antiga.
            if not slots:
                snapshot['slots'] = [{**s,'atual':False} for s in anterior.get('slots', [])]
        if tipo=='rtc':snapshot['completo']=len(snapshot['slots'])==7 and all(s.get('estado')=='vazio_confirmado' or s.get('id') and all(s.get(k) is not None for k in ('prioridade','creatures',*(() if s['tipo']=='runa' else ('mana_percent',)))) for s in snapshot['slots'])
        if tipo=='cura':snapshot['completo']=len(snapshot['slots'])==7 and all(s.get('estado')=='vazio_confirmado' or s.get('id') and s.get('vida_percent') is not None and (s['tipo']!='party' or s.get('vocacao_destino')) for s in snapshot['slots'])
        if tipo=='roda':
            lidos={k[7:]:v['valor'] for k,v in snapshot['campos'].items() if k.startswith('fatias.')}
            import leitura_jogo
            snapshot['casas_lidas']=len(lidos);snapshot['completo']=len(lidos)==36 and sum(lidos.values())==snapshot['campos'].get('pontos.investidos',{}).get('valor') and leitura_jogo.validar_roda(_json(AQUI/'ui'/'roda_catalogo.json'),snapshot.get('vocacao') or 'ED',lidos,snapshot['campos'].get('pontos.total',{}).get('valor',0))
        snapshot['estado']='observado_completo' if snapshot['completo'] else 'observado_parcial'
        _grava(pasta / f'{versao}_{tipo}.json', snapshot)
        _grava(pasta / f'{tipo}_atual.json', snapshot)
        if isinstance(campos.get('pontos.total'),int):
            _grava(pasta/'pontos.json',{'valor':campos['pontos.total'],'origem':'visual','instante':instante,'prova':relativa})
    return {'ok': True, 'snapshot': snapshot}


def consultar(char, sessao='', historico=False):
    if not char and not historico:
        char=ESTADO_LEITOR.get('char')
    if not char or len(char) > 80:
        return {}
    pasta = RAIZ / _chave(char)
    out = {'versao': 2, 'char': char, 'contexto': {}, 'calibracoes': {}}
    with TRAVA:
        for tipo in TITULOS:
            calib = _json(pasta / f'{tipo}_calibracao.json')
            if calib:
                out['calibracoes'][tipo] = calib
            snapshots = [_json(p) for p in pasta.glob(f'[0-9]*_{tipo}.json')]
            if historico:
                snapshots = [s for s in snapshots if s.get('sessao') == sessao]
            elif sessao:
                snapshots = [s for s in snapshots if s.get('sessao') in (sessao, 'calibracao')]
            if snapshots:
                out[tipo] = max(snapshots, key=lambda s: s.get('instante', 0))
        out['pontos']=_json(pasta/'pontos.json')
        if not out['pontos'] and (total:=out.get('roda',{}).get('campos',{}).get('pontos.total',{}).get('valor')) is not None:
            out['pontos']={'valor':total,'origem':'visual_anterior'}
        if not historico:
            out['leitor']={**ESTADO_LEITOR}
            out['sugestao']=_json(pasta/'sugestao_atual.json')
            c=_json(pasta/'confirmacao.json');s=out['sugestao']
            c['valida']=bool(c.get('sugestao_id') and c.get('sugestao_id')==s.get('id') and
                c.get('preset')==out.get('rtc',{}).get('preset') and s.get('contexto',{}).get('total')==out['pontos'].get('valor'))
            if s and s.get('regras_versao') != _json(AQUI/'ui'/'roda_catalogo.json').get('versao'):
                c['valida']=False;c['motivo']='As regras foram atualizadas; confirme a nova sugestão.'
            out['confirmacao']=c
            out['concordancia']=concordancia(s,out) if s else {}
            out['avaliacao']=_json(pasta/'avaliacao.json')
            contexto=_json(pasta/'contexto_execucao.json')
            if not sessao or contexto.get('sessao')==sessao:
                out['contexto']=contexto
            out['modelo']=_json(pasta/'modelo.json')
    return out


def prova(relativa):
    if not re.fullmatch(r'[a-f0-9]{24}/[0-9]+_(?:rtc|roda|cura)\.png', relativa):
        return None
    p = RAIZ / relativa
    return p if p.is_file() else None


class Leitor:
    """Consome o f_ existente; não abre câmera/captura nem inicia gravação."""
    def __init__(self, estabilizar=False):
        self.ultimo = None
        self.assinaturas = {}
        self.estabilizar = estabilizar
        self.candidatos = {}

    def processar(self, quadro, char, sessao):
        if not char or quadro == self.ultimo:
            return
        pasta = RAIZ / _chave(char)
        with Image.open(quadro) as img:
            imagem = img.convert('RGB')
        gray = cv2.cvtColor(np.asarray(imagem), cv2.COLOR_RGB2GRAY)
        for tipo in TITULOS:
            c = _json(pasta / f'{tipo}_calibracao.json')
            if not c:
                continue
            molde = cv2.imread(str(pasta / f'{tipo}_titulo.png'), cv2.IMREAD_GRAYSCALE)
            if molde is None:
                continue
            melhor = None
            for escala in (1., .75, 1.25, 1.5, 2.):
                modelo = cv2.resize(molde, None, fx=escala, fy=escala, interpolation=cv2.INTER_NEAREST)
                if min(modelo.shape) < 3 or modelo.shape[0] >= gray.shape[0] or modelo.shape[1] >= gray.shape[1]:
                    continue
                r = cv2.matchTemplate(gray, modelo, cv2.TM_CCOEFF_NORMED)
                _, score, _, (x,y) = cv2.minMaxLoc(r)
                if score < .97:
                    continue
                # Outra correspondência forte em local distinto é ambígua.
                r[max(0,y-modelo.shape[0]):y+modelo.shape[0],max(0,x-modelo.shape[1]):x+modelo.shape[1]] = 0
                if float(r.max()) >= .97:
                    continue
                if melhor is None or score > melhor[0]:
                    melhor = (score, x, y, escala)
            if not melhor:
                continue
            _, x, y, escala = melhor
            ox, oy = c['offset']; reg = c['regiao']
            left, top = round(x-ox*escala), round(y-oy*escala)
            w, h = round(reg['width']*escala), round(reg['height']*escala)
            if left < 0 or top < 0 or left+w > imagem.width or top+h > imagem.height:
                continue
            crop = imagem.crop((left,top,left+w,top+h))
            normal = crop.resize((reg['width'],reg['height']), Image.Resampling.NEAREST)
            textos = linhas(normal)
            if not any(l['y'] < 45 and l['texto'].strip() == c['titulo'] for l in textos):
                continue
            assinatura = hashlib.sha256(crop.tobytes()).hexdigest()
            chave = (char, sessao, tipo, 'calibrado')
            anterior=self.candidatos.get(chave);self.candidatos[chave]=assinatura
            if self.estabilizar and anterior!=assinatura:continue
            if self.assinaturas.get(chave) != assinatura:
                observar(tipo, crop, char, sessao, textos, origem='captura_existente', imagem_leitura=normal)
                self.assinaturas[chave] = assinatura
        self.processar_imagem(imagem,char,sessao)
        self.ultimo = quadro

    def processar_imagem(self, imagem, char, sessao='observacao'):
        global _refs_janelas
        if not char:return
        if _refs_janelas is None:
            _refs_janelas=_json(AQUI/'ui'/'janelas_referencias.json').get('janelas',[])
        gray=cv2.cvtColor(np.asarray(imagem.convert('RGB')),cv2.COLOR_RGB2GRAY)
        vistos=[]
        for ref in _refs_janelas:
            modelo=np.asarray(Image.open(io.BytesIO(base64.b64decode(ref['titulo']))).convert('L'))
            matches=[]
            for escala in (1.,.75,1.25,1.5,2.):
                molde=cv2.resize(modelo,None,fx=escala,fy=escala,interpolation=cv2.INTER_NEAREST)
                if min(molde.shape)<3 or molde.shape[0]>=gray.shape[0] or molde.shape[1]>=gray.shape[1]:continue
                r=cv2.matchTemplate(gray,molde,cv2.TM_CCOEFF_NORMED);_,score,_,(x,y)=cv2.minMaxLoc(r)
                if score<.97:continue
                r[max(0,y-molde.shape[0]):y+molde.shape[0],max(0,x-molde.shape[1]):x+molde.shape[1]]=0
                if r.max()>=.97:continue
                ox,oy=ref['offset'];w,h=ref['tamanho'];left,top=round(x-ox*escala),round(y-oy*escala)
                if left<0 or top<0 or left+round(w*escala)>imagem.width or top+round(h*escala)>imagem.height:continue
                crop=imagem.crop((left,top,left+round(w*escala),top+round(h*escala)))
                normal=crop.resize((w,h),Image.Resampling.NEAREST);txt=linhas(normal)
                tipo=ref['tipo']
                if tipo=='rtc' and not rtc_da_imagem(normal,txt)[1]:continue
                if tipo=='cura' and not cura_da_imagem(normal,txt)[1]:continue
                if tipo=='roda' and not any(l['texto'].casefold()=='available promotion points' for l in txt):continue
                matches.append((score,crop,normal,txt))
            if not matches:continue
            _,crop,normal,txt=max(matches,key=lambda r:r[0]);tipo=ref['tipo'];vistos.append(tipo)
            campos,slots=campos_das_linhas(tipo,txt)
            if tipo=='rtc':campos,slots=rtc_da_imagem(normal,txt)
            elif tipo=='cura':campos,slots=cura_da_imagem(normal,txt)
            key=(char,sessao,tipo);sig=assinatura({'campos':campos,'slots':slots})
            anterior=self.candidatos.get(key);self.candidatos[key]=sig
            if self.estabilizar and anterior!=sig:continue
            if self.assinaturas.get(key)!=sig:
                observar(tipo,crop,char,sessao,txt,origem='observacao_automatica',imagem_leitura=normal)
                self.assinaturas[key]=sig
        for key in list(self.candidatos):
            if key[:2]==(char,sessao) and key[2] not in vistos:self.candidatos.pop(key,None)
        ESTADO_LEITOR.update({'estado':'janela observada' if vistos else 'aguardando RTC, Cura ou Roda',
                             'char':char,'instante':time.time(),'janelas':vistos})


class Monitor:
    """Um consumidor: gravação compartilha f_; modo leve só captura o jogo à frente."""
    def __init__(self, sessao_de, ativo_de, fonte_de):
        self.sessao_de,self.ativo_de,self.fonte_de=sessao_de,ativo_de,fonte_de
        self.parar=threading.Event();self.leitor=Leitor(estabilizar=True)
        self.thread=threading.Thread(target=self._rodar,daemon=True)

    def iniciar(self):self.thread.start()
    def fechar(self):
        self.parar.set()
        if self.thread.is_alive():self.thread.join(timeout=5)

    def _rodar(self):
        import capture
        import ctypes
        import mss
        import observacao_execucao
        observador=observacao_execucao.Observador()
        while not self.parar.is_set():
            try:
                if self.ativo_de():
                    sessao=self.sessao_de()
                    frames=sorted(sessao.glob('f_*.png')) if sessao else []
                    if frames and time.time()-frames[-1].stat().st_mtime<12:
                        layout=_json(sessao/'layout.json');fonte=self.fonte_de();char=layout.get('char') or (fonte.get('char') if fonte.get('tipo')=='twitch' else None)
                        if not char:
                            info=capture.find_game_rect();char=self._char(info)
                        self.leitor.processar(frames[-1],char,sessao.name)
                        if char:observador.processar(sessao,char,frames[-1])
                    else:ESTADO_LEITOR.update({'estado':'aguardando quadro atual','janelas':[]})
                elif self.fonte_de().get('tipo','janela')=='janela':
                    info=capture.find_game_rect()
                    char=self._char(info)
                    if info and char and ctypes.windll.user32.GetForegroundWindow()==info['hwnd']:
                        with mss.mss() as camera:
                            quadro=camera.grab(info['rect']);img=Image.frombytes('RGB',quadro.size,quadro.rgb)
                        self.leitor.processar_imagem(img,char)
                    else:ESTADO_LEITOR.update({'estado':'aguardando jogo em primeiro plano','janelas':[]})
            except Exception as erro:
                ESTADO_LEITOR.update({'estado':'aguardando leitura','erro':str(erro),'janelas':[]})
            self.parar.wait(4)

    @staticmethod
    def _char(info):
        if not info:return None
        titulo=info.get('title','');m=re.search(r'RubinOT Client\s*-\s*(.+)',titulo)
        return m[1].strip() if m else None
