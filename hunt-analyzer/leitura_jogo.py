"""Leitores genéricos de campos visíveis; nenhuma ação no cliente do jogo."""
import base64
import io
import math
import pathlib
import re
import zlib

import cv2
import numpy as np
from PIL import Image

_icones = None


def icone(patch, referencias, catalogo, pasta):
    """Molde real primeiro; sprites públicos só com casamento único do miolo."""
    global _icones
    if patch is None or patch.shape[:2] != (32, 32):
        return None
    candidatos=[]
    for key, ref in referencias.items():
        if isinstance(ref,str):
            ref=np.asarray(Image.open(io.BytesIO(base64.b64decode(ref))).convert('RGB'))
        if ref.shape==patch.shape:
            erro=float(np.abs(ref.astype(float)-patch).mean())
            if erro<=2:candidatos.append((erro,key.split('#',1)[0]))
    if candidatos:
        ids={key for _,key in candidatos}
        return next(iter(ids)) if len(ids)==1 else None
    if _icones is None:
        _icones=[]
        for magia in catalogo:
            p=pathlib.Path(pasta)/(magia.get('imagem') or '').lstrip('/')
            if not p.is_file():continue
            with Image.open(p) as im:
                rgba=im.convert('RGBA');rgb=np.asarray(rgba.resize((32,32),Image.Resampling.NEAREST))
            _icones.append((magia['id'],rgb[:,:,:3],rgb[:,:,3]>=230))
    # O fundo/quadro do helper não faz parte do sprite; não aprender ícone errado.
    for key,ref,mask in _icones:
        mask=mask.copy();mask[:3]=False;mask[-3:]=False;mask[:,:3]=False;mask[:,-3:]=False
        color=ref.max(2).astype(int)-ref.min(2).astype(int)
        mask &= color>25
        if np.count_nonzero(mask)<35:continue
        erro=float(np.abs(ref.astype(float)-patch)[mask].mean())
        if erro<=8:candidatos.append((erro,key))
    candidatos.sort()
    return candidatos[0][1] if candidatos and (len(candidatos)==1 or candidatos[1][0]-candidatos[0][0]>3) else None


def selecao_roda(imagem, catalogo, textos, campos):
    """A borda branca identifica a casa; só o N/L textual dá investimento."""
    limite=campos.get('selection.limite');pontos=campos.get('selection.pontos')
    if not isinstance(limite,int) or not isinstance(pontos,int):return {}
    titulo=next((t for t in textos if t['texto'].casefold()=='wheel of destiny' and t['y']<45),None)
    if not titulo:return {}
    # Layout normalizado pelo detector; é transladado com a janela, não com o desktop.
    arr=np.asarray(imagem.convert('RGB'));tx,ty=titulo['x']-444,titulo['y']-3
    white=(arr.min(2)>=215)&(arr.max(2).astype(int)-arr.min(2).astype(int)<=20)
    dil=cv2.dilate(white.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
    candidatos=[]
    for voc in ('ED','MS'):
        for f in catalogo['vocacoes'][voc]['fatias']:
            if f['limite']!=limite:continue
            g=f['geometria'];r0,r1={1:(0,53),2:(55,105),3:(107,157),4:(159,209),5:(211,261)}.get(g['ring'],(0,0))
            # Perímetros do planner trazem raios explícitos; evitar aproximação dos anéis.
            raios=[float(x) for x in re.findall(r'A ([0-9.]+) ',f['perimetro'])]
            if raios:r1=max(raios);r0=min(raios) if len(raios)>1 else 0
            samples=[]
            for angle in np.linspace(g['start']+2,g['end']-2,48):
                for radius in (r0,r1):
                    if radius<3:continue
                    samples.append((round(500+tx+radius*math.cos(math.radians(angle))),round(333+ty+radius*math.sin(math.radians(angle)))))
            for angle in (g['start'],g['end']):
                for radius in np.linspace(r0+2,r1-2,20):samples.append((round(500+tx+radius*math.cos(math.radians(angle))),round(333+ty+radius*math.sin(math.radians(angle)))))
            if not samples or any(x<0 or y<0 or x>=arr.shape[1] or y>=arr.shape[0] for x,y in samples):continue
            score=sum(dil[y,x] for x,y in samples)/len(samples)
            candidatos.append((score,voc,f))
    candidatos.sort(key=lambda x:x[0],reverse=True)
    # ED/MS compartilham geometria. Vocação deve vir de perks/ícones ou contexto, nunca nome.
    if not candidatos or candidatos[0][0]<.50:return {}
    melhor=candidatos[0];diferentes=[v for v in candidatos if v[2]['id']!=melhor[2]['id']]
    if diferentes and melhor[0]-diferentes[0][0]<.12:return {}
    f=melhor[2]
    if pontos>f['limite']:return {}
    return {'selection.fatia':f['id'],'fatias.'+f['id']:pontos,'selection.qualidade':'borda_e_numero','selection.dominio':f['dominio']}


def gemas_textos(textos,catalogo):
    """Tooltips explícitos de vessel/gema, sem assumir equipamento por soma de bônus."""
    campos={};romanos={'I':1,'II':2,'III':3,'IV':4}
    grupos=[]
    for l in textos:
        m=re.fullmatch(r'(?:Vessel|Domain|Domínio) (Top Left|Top Right|Bottom Left|Bottom Right|TL|TR|BL|BR)',l['texto'].strip(),re.I)
        if m:grupos.append((l['x'],l['y'],{'top left':'TL','top right':'TR','bottom left':'BL','bottom right':'BR'}.get(m[1].lower(),m[1].upper())))
    for x,y,dom in grupos:
        linhas=[l['texto'].strip() for l in textos if y<l['y']<y+230 and abs(l['x']-x)<180 and '?' not in l['texto']]
        if any(t in ('Vessel contains no gem','No gem') for t in linhas):campos['gemas.'+dom]={'estado':'vazio_confirmado','equipada':False};continue
        tamanho=next((k for k in (1,2,3) if any(t==n for vs in catalogo['vessels']['GemNames'][str(k-1)].values() for n in [vs] for t in linhas)),None)
        if not tamanho:continue
        mods=[]
        nomes={t.removeprefix('Augmented ').removeprefix('Aug. ') for t in linhas if t.startswith(('Augmented ','Aug. '))}
        for t in linhas:
            m=re.fullmatch(r'(?:Grade |Grau )?(I|II|III|IV|[1-4])?\s*([+-][\d.]+(?:%|s)? .+)',t)
            if not m:continue
            grau=romanos.get(m[1],int(m[1]) if m[1] and m[1].isdigit() else None)
            matches=[]
            for key,e in catalogo['gemas_normalizadas'].items():
                raw=catalogo['gemas_supremas'].get(key,{})
                nome=(raw.get('Name','').split('|')[0]).removeprefix('Augmented ')
                if nomes and nome and nome not in nomes:continue
                for g,v in e['graus'].items():
                    if v['descricao']==m[2] and (grau is None or grau==int(g)):matches.append((key,int(g)))
            if len(matches)==1:mods.append({'mod':int(matches[0][0]),'grau':matches[0][1],'origem':'tooltip'})
        basicos=[]
        for slot in (1,2):
            cab=next((l for l in textos if l['texto'].strip()==f'Basic Mod {slot}' and y<l['y']<y+230 and abs(l['x']-x)<180),None)
            if not cab:continue
            itens=[l['texto'].strip() for l in textos if cab['y']<l['y']<=cab['y']+35 and abs(l['x']-cab['x'])<120]
            matches=[]
            for key,b in catalogo.get('basicos_normalizados',{}).items():
                for voc,grades in b['graus'].items():
                    for grau,es in grades.items():
                        expected={('+' if e['valor']>=0 else '')+format(e['valor']*(100 if e['unidade']=='fracao' else 1),'g')+('%' if e['unidade']=='fracao' else '')+' '+e['tipo'] for e in es}
                        if expected and expected==set(t for t in itens if t.startswith(('+','-'))):matches.append((key,int(grau)))
            unicos=set(matches)
            if len(unicos)==1:
                key,grade=next(iter(unicos));basicos.append({'slot':slot,'mod':int(key),'grau':grade,'origem':'tooltip'})
        completo=len(basicos)==min(2,tamanho) and (tamanho<3 or len(mods)==1)
        campos['gemas.'+dom]={'tier':tamanho,'dominio':dom,'qualidade':catalogo['tiers'][str(tamanho)]['qualidade'],'modificadores':mods,'basicos':basicos,'equipada':True,'estado':'observado_completo' if completo else 'observado_parcial'}
    return campos


def codigo_visivel(textos,catalogo,total):
    """Exportação aberta no próprio cliente: código lido, sem colagem/formulário."""
    codigos={l['texto'].strip() for l in textos if re.fullmatch(r'[DS]0[-_A-Za-z0-9]{3,90}',l['texto'].strip())}
    if len(codigos)!=1 or not isinstance(total,int):return {}
    codigo=next(iter(codigos));voc='ED' if codigo[0]=='D' else 'MS'
    try:
        payload=codigo[2:].replace('-','+').replace('_','/');raw=base64.b64decode(payload+'='*((-len(payload))%4));dados=zlib.decompress(raw,-15)
    except (ValueError,zlib.error):return {}
    if len(dados)!=48:return {}
    fatias=catalogo['vocacoes'][voc]['fatias'];pontos={f['id']:dados[f['indice']] for f in fatias}
    if not validar_roda(catalogo,voc,pontos,total):return {}
    return {**{'fatias.'+k:v for k,v in pontos.items()},'roda.codigo_observado':codigo,'vocacao':voc}


def validar_roda(catalogo,voc,pontos,total):
    fatias=catalogo['vocacoes'][voc]['fatias'];limites={f['id']:f['limite'] for f in fatias}
    if set(pontos)-set(limites) or sum(pontos.values())>total:return False
    if any(not isinstance(n,int) or isinstance(n,bool) or not 0<=n<=limites[k] for k,n in pontos.items()):return False
    alcancadas={f['id'] for f in fatias if f['raiz']}
    for _ in range(36):
        antes=len(alcancadas)
        alcancadas|={f['id'] for f in fatias if any(c in alcancadas and pontos.get(c)==limites[c] for c in f['conexoes'])}
        if len(alcancadas)==antes:break
    return all(n==0 or k in alcancadas for k,n in pontos.items())


def destinatarios(slots,campos,party):
    """Só o registro explícito da party resolve EK/RP; nome não contém vocação."""
    membros={p['nome'].casefold():p for p in party if p.get('nome') and p.get('vocacao') in ('EK','RP','ED','MS','MO')}
    for s in slots:
        if s.get('tipo')!='party':continue
        nomes=(campos.get(s['id']+'.destinos_texto') or '').splitlines();i=s['destino_indice']-1
        if i<len(nomes) and nomes[i].strip().casefold() in membros:
            p=membros[nomes[i].strip().casefold()];s.update(destinatario=p['nome'],vocacao_destino=p['vocacao'],destinatario_origem='party_identificada')
    return slots
