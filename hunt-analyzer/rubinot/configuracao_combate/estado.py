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

AQUI = pathlib.Path(__file__).resolve().parents[2]
RAIZ = pathlib.Path(os.environ.get('HUNT_CONFIGURACOES_RAIZ') or AQUI / 'configuracoes_player')
TRAVA = threading.RLock()
TITULOS = {'roda': ('Wheel of Destiny',), 'rtc': ('RTC', 'Real Time Combat', 'RTCaster'), 'cura': ('Cura',)}
_atlas = None
_refs_rtc = None
_refs_roda = None
_refs_janelas = None
ESTADO_LEITOR = {'estado': 'aguardando leitura', 'char': None, 'instante': None}


from rubinot.adapters.arquivos import ler_json as _json, gravar_json as _grava


def chave_personagem(char):
    return _chave(char)


def pasta_personagem(char):
    return RAIZ / chave_personagem(char)


def catalogo_produto(nome):
    return _json(AQUI / 'ui' / nome)


def raiz_aprendizado():
    return pathlib.Path(os.environ.get('HUNT_APRENDIZADO_RAIZ') or AQUI / 'hunt_data' / '_aprendizado')


ler_json, gravar_json = _json, _grava


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


from rubinot.configuracao_combate.concordancia import comparar as comparar_configuracao


def concordancia(sugestao, observado):
    return comparar_configuracao(sugestao, observado, catalogo_produto('roda_catalogo.json'))


def _chave(char):
    return hashlib.sha256(' '.join(char.lower().split()).encode('utf-8')).hexdigest()[:24]


from rubinot.observacao.configuracao import linhas, rtc_da_imagem, roda_da_imagem, cura_da_imagem, campos_das_linhas


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


