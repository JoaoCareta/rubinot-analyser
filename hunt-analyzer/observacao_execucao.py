"""Evidência numérica preservada; ausência de console nunca prova cast perdido."""
import hashlib
import json
import pathlib
import statistics
import time
import threading

import configuracoes as c

MODELO = 'observacao-3'
PROCESSAMENTO = threading.RLock()


def lancamentos_visiveis(imagem, char):
    """Fala amarela no quadro já capturado; não depende de aba/região Spells."""
    import numpy as np,atlas_build as ab,nameplates,re
    arr=np.asarray(imagem.convert('RGB'));b=(arr[:,:,0]>=220)&(arr[:,:,1]>=220)&(arr[:,:,2]<80)
    indice=nameplates.shape_index(ab.load_atlas()[0]);gap=ab.load_atlas()[1];saida=[]
    for a,z in ab.find_bands(b):
        if not 6<=z-a<=16:continue
        faixa=b[a:z];cols=np.flatnonzero(faixa.any(0))
        if not len(cols):continue
        cortes=np.flatnonzero(np.diff(cols)>22)
        for x0,x1 in zip([int(cols[0]),*[int(cols[i+1]) for i in cortes]],[*[int(cols[i]+1) for i in cortes],int(cols[-1]+1)]):
            texto=nameplates.decode_shape(faixa[:,x0:x1],indice,gap)
            m=re.fullmatch(r'(\d{2}:\d{2}:\d{2}) (.+?) \[(\d+)\]: (.+)',texto)
            if m and m[2].casefold()==char.casefold() and '?' not in m[4]:saida.append((m[1],texto[9:]))
    return saida


def recursos(imagem, char=None):
    """Números brancos das barras superiores; nunca HP estimado a partir de BP."""
    import numpy as np
    import atlas_build as ab
    import nameplates
    import auxiliares
    import re
    arr=np.asarray(imagem.convert('RGB'));out={}
    c.linhas(imagem.crop((0,0,imagem.width,min(90,imagem.height))))
    alto=arr[:90];hi,lo=alto.max(2),alto.min(2)
    mask=lo>=170
    barra=auxiliares.acha_barra_vida(arr)
    if not barra:return {'icone_escudo_presente':auxiliares.acha_icone_escudo(arr) is not None}
    x0,y0,x1,y1=barra
    azuis=((alto[:,:,2].astype(int)-alto[:,:,0]>25)&(alto[:,:,2]>alto[:,:,1]))
    cols=np.flatnonzero(azuis[y0:y1].mean(0)>.5)
    direita=int(cols[-1])+1 if len(cols) else x1
    area=np.zeros_like(mask);area[max(0,y0-4):min(len(mask),y1+5),x0:direita]=True;mask &= area
    formas=c._json(c.AQUI/'ui'/'recursos_glifos.json').get('formas',[])
    pessoais=c.RAIZ/c._chave(char)/'recursos_glifos.json' if char else None
    if pessoais:formas+=c._json(pessoais).get('formas',[])
    independentes={}
    if char:
        textos=c.linhas(imagem)
        atributos={}
        for l in textos:
            if l['texto'] in ('Level','Magic','Critical Hit Chance','Critical Extra Damage','Life Leech Amount','Life Leech Chance','Mana Leech Amount','Mana Leech Chance'):
                valores=[t for t in textos if abs(t['y']-l['y'])<=2 and l['x']+45<t['x']<l['x']+200 and re.fullmatch(r'[\d,.]+%?',t['texto'])]
                if len(valores)==1:
                    label={'Level':'nivel','Magic':'magic_level','Critical Hit Chance':'critico_chance','Critical Extra Damage':'critico_extra','Life Leech Amount':'life_leech','Life Leech Chance':'life_leech_chance','Mana Leech Amount':'mana_leech','Mana Leech Chance':'mana_leech_chance'}[l['texto']]
                    texto=valores[0]['texto'];n=float(texto.rstrip('%').replace(',',''))
                    atributos[label]=n/100 if texto.endswith('%') else n
            if l['texto'] not in ('Hit Points','Mana'):continue
            valores=[t for t in textos if abs(t['y']-l['y'])<=2 and t['x']>l['x']+55 and re.fullmatch(r'[\d,]+',t['texto'])]
            if len(valores)==1:independentes['vida' if l['texto']=='Hit Points' else 'mana']=valores[0]['texto'].replace(',','')
        out['atributos']=atributos
    novas=[]
    def ler(b, esperado=None):
        cols=np.flatnonzero(b.any(0))
        if not len(cols):return ''
        cuts=np.flatnonzero(np.diff(cols)>1);letras=[]
        for indice,(a,z) in enumerate(zip([int(cols[0]),*[int(cols[i+1]) for i in cuts]],[*[int(cols[i]+1) for i in cuts],int(cols[-1]+1)])):
            g=b[:,a:z];ys=np.flatnonzero(g.any(1));g=g[ys[0]:ys[-1]+1]
            candidatos={f['caractere'] for f in formas if np.asarray(f['pixels']).shape==g.shape and np.array_equal(np.asarray(f['pixels']),g)}
            letra=next(iter(candidatos)) if len(candidatos)==1 else '?'
            if letra=='?' and esperado and len(esperado)==len(cuts)+1 and esperado[indice].isdigit():
                novas.append({'caractere':esperado[indice],'pixels':g.astype(int).tolist(),'origem':'Skills_e_barra_independentes'})
            letras.append(letra)
        return ''.join(letras)
    for y0,y1 in ab.find_bands(mask):
        if not 6<=y1-y0<=16:continue
        cols=np.flatnonzero(mask[y0:y1].any(0))
        if not len(cols):continue
        cuts=np.flatnonzero(np.diff(cols)>14)
        for x0,x1 in zip([int(cols[0]),*[int(cols[i+1]) for i in cuts]],[*[int(cols[i]+1) for i in cuts],int(cols[-1]+1)]):
            bloco=mask[y0:y1,x0:x1];txt=ler(bloco)
            fundo=alto[max(0,y0-3):min(len(alto),y1+3),max(0,x0-12):x1+12].astype(int)
            verde=((fundo[:,:,1]-fundo[:,:,0]>40)&(fundo[:,:,1]-fundo[:,:,2]>40)).sum()
            azul=((fundo[:,:,2]-fundo[:,:,0]>25)&(fundo[:,:,2]>fundo[:,:,1])).sum()
            chave='vida' if verde>azul and verde>10 else 'mana' if azul>10 else None
            if chave and chave in independentes and '?' in txt and txt.count('/')==1:
                prefixo,maximo=txt.split('/');esperado=independentes[chave]
                # Skills mostra o recurso atual, não seu máximo. A fonte é uma
                # segunda leitura independente da MESMA imagem e do mesmo valor.
                if re.fullmatch(r'[\d?]+',prefixo) and len(prefixo)==len(esperado) and all(a=='?' or a==b for a,b in zip(prefixo,esperado)):
                    antes=len(novas);ler(bloco,esperado+'/'+'?'*len(maximo))
                    formas.extend(novas[antes:]);txt=ler(bloco)
            m=re.fullmatch(r'(\d+)\s*/\s*(\d+)',txt.strip())
            if not m or int(m[2])<=0 or int(m[1])>int(m[2]):continue
            if chave:out[chave]={'atual':int(m[1]),'maxima':int(m[2]),'percentual':int(m[1])/int(m[2])*100,'origem':'barra_visual','qualidade':'texto_integral'}
    if pessoais and novas:
        anteriores=c._json(pessoais).get('formas',[]);unicas={c.assinatura(f):f for f in anteriores+novas}
        with c.TRAVA:c._grava(pessoais,{'versao':2,'formas':list(unicas.values()),'origem':'Skills_e_barra_independentes'})
    out['icone_escudo_presente']=auxiliares.acha_icone_escudo(arr) is not None
    return out


def evento(registro, origem, char, indice=0):
    e = dict(registro)
    texto=e.get('body','')
    e.update({'versao':2,'origem':origem,'qualidade':'identificada' if e.get('magia_id') else 'parcial',
              'ator':e.get('actor') or (char if e.get('kind') in ('heal_self','heal_other','damage_dealt','cast') else None),
              'alvo':e.get('target') or e.get('victim') or (char if e.get('kind') in ('heal_self','damage_taken','healed') else None)})
    if e.get('kind')=='speech' and e.get('actor','').casefold()==char.casefold():
        e.update(kind='cast',words=e.get('text',''),ator=char)
    if e.get('kind')=='cast' and not e.get('magia_id'):
        magias=c._json(c.AQUI/'ui'/'magias.json').get('magias',[])
        words=(e.get('words') or texto).strip().rstrip('.')
        m=next((m for m in magias if words==(m.get('palavras') or '') or
                m.get('id') in ('heal_friend','nature_s_embrace') and words.startswith((m.get('palavras') or '\0')+' ')),None)
        if m:
            e.update(magia_id=m['id'],qualidade='identificada')
            alvo=words[len(m.get('palavras') or ''):].strip().strip('\"\'')
            if alvo:e['alvo']=alvo
    # Uma linha observada em dois consoles/quadro só é um evento. Linhas iguais no
    # mesmo segundo usam ocorrência local, pois o relógio do console tem resolução 1s.
    sessao=origem.split('/')[0]
    # t inclui o dia adicional depois da meia-noite; ts sozinho repete a cada dia.
    e['id']=hashlib.sha256(json.dumps([sessao,e.get('t'),e.get('kind'),e.get('ator'),e.get('alvo'),texto,e.get('words'),indice],sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()
    return e


def normalizar_cast(e,obs,recurso):
    if obs.get('concordancia',{}).get('estado')!='confere':return
    linha=next((m for m in obs.get('sugestao',{}).get('cura',{}).get('linhas',[]) if m['id']==e.get('magia_id')),None)
    if not linha or not linha.get('multiplicador_base'):return
    fator=linha['multiplicador_base'];blessing=linha.get('blessing',0)
    alvo=e.get('alvo');proprio=alvo in (None,obs['sugestao']['contexto'].get('char'))
    if blessing:
        vida=recurso.get('vida') if proprio else recurso.get('aliados',{}).get(alvo)
        if not vida or vida.get('percentual') is None or abs(e['t']-recurso.get('t',-999))>1:return
        pct=vida['percentual'];fator*=1+blessing*(2 if pct<30 else 1 if pct<60 else 0)
    if proprio and obs.get('contexto',{}).get('cura',{}).get('postura')=='shared_conservation':fator*=1.1
    e['base_multiplicador']=fator;e['fixo_hp']=obs['sugestao']['roda']['efeitos'].get('fixo_hp',0)


def avaliar(sugestao, eventos, intervalos, concordancia):
    unicos={e['id']:e for e in eventos if e.get('id')}
    casts=[e for e in unicos.values() if e.get('kind')=='cast' and e.get('qualidade')=='identificada' and e.get('magia_id')]
    identificados={}
    for e in casts:
        if any(a<=e.get('t',-1)<b for a,b in intervalos):identificados.setdefault(e['magia_id'],[]).append(e['t'])
    segundos=sum(max(0,b-a) for a,b in intervalos)
    grupos=[]
    for a,b in sorted(intervalos):
        if grupos and a<=grupos[-1][1]:grupos[-1][1]=max(b,grupos[-1][1])
        else:grupos.append([a,b])
    segundos=sum(b-a for a,b in grupos)
    frequencia={m:len(ts)/segundos*60 if segundos else None for m,ts in identificados.items()}
    divergencias=[]
    if concordancia.get('estado')=='divergente':divergencias.append({'tipo':'configuracao_diferente','campos':concordancia.get('diferencas',[])})
    if not casts:divergencias.append({'tipo':'falha_de_leitura','motivo':'nenhum lançamento identificável; ausência não prova falha'})
    for e in casts:
        if e.get('elegibilidade')=='condicao_ausente':divergencias.append({'tipo':'condicao_ausente','evento':e['id']})
        elif e.get('elegibilidade')=='inconclusiva':divergencias.append({'tipo':'inconclusiva','evento':e['id']})
    return {'versao':2,'modelo_versao':MODELO,'sugestao_id':sugestao.get('id'),'segundos_validos':segundos,
            'estado':'execução identificada parcialmente' if casts else 'aguardando lançamentos identificáveis',
            'frequencia_observada':frequencia,'concordancia':concordancia,
            'falhas_por_ausencia':None,'modelo_revisado':False,'divergencias':divergencias[-30:]}


def revisar_latencia(eventos, modelo=None):
    """Só ajusta latência do leitor/helper com elegibilidade identificada e holdout."""
    modelo=modelo or {'versao':MODELO,'latencia_s':None}
    eventos={e['id']:e for e in eventos if e.get('id')}
    provas=[e for e in eventos.values() if e.get('qualidade')=='identificada'
            and e.get('kind')=='cast' and isinstance(e.get('elegivel_em'),(int,float))
            and isinstance(e.get('t'),(int,float)) and 0<=e['t']-e['elegivel_em']<=4]
    provas.sort(key=lambda e:e['t'])
    if len(provas)<30:return {'aceita':False,'motivo':'Amostra identificada insuficiente','modelo':modelo}
    treino=provas[:-10];validacao=provas[-10:]
    candidato=statistics.median(e['t']-e['elegivel_em'] for e in treino)
    antes=modelo.get('latencia_s')
    if antes is None:antes=0
    erro=lambda n:statistics.mean(abs(e['t']-e['elegivel_em']-n) for e in validacao)
    if erro(candidato)>=erro(antes)*.9:return {'aceita':False,'motivo':'Sem melhora em validação separada','modelo':modelo}
    novo={'versao':MODELO+'-'+c.assinatura([candidato,[e['id'] for e in provas]])[:12],
          'latencia_s':candidato,'anterior':modelo.get('versao'),'treino':len(treino),'validacao':10,
          'erro_antes':erro(antes),'erro_depois':erro(candidato)}
    return {'aceita':True,'modelo':novo}


class Observador:
    def __init__(self):
        self.sessao=None;self.ultimo=None;self.prev=[];self.eventos=[];self.intervalos=[];self.ts=None;self.sugestao_id=None;self.recurso_quadro=None;self.quadros=[];self.publicado=-1;self.prev_por_fonte={}

    def processar(self, sessao, char, quadro_completo=None):
        with PROCESSAMENTO:
            return self._processar(sessao,char,quadro_completo)

    def _processar(self, sessao, char, quadro_completo=None):
        import events_build as ev
        import atlas_build as ab
        import contexto_execucao as contexto
        import rtc_ml
        import aprendizado_hunt as ah
        if self.sessao!=sessao:
            self.sessao=sessao;self.ultimo=None;self.prev=[];self.eventos=[];self.intervalos=[];self.ts=None;self.quadros=[];self.recurso_quadro=None;self.prev_por_fonte={};self.publicado=-1;self.sugestao_id=None
        obs=c.consultar(char, sessao.name);conf=obs.get('confirmacao',{})
        aplicada=all(obs.get(k,{}).get('aplicado_confirmado') for k in ('rtc','cura','roda'))
        # A sugestão é metadado, não a identidade do arquivo de observação.
        ident='observacao'
        pasta=c.RAIZ/c._chave(char)/'execucao'/sessao.name/ident;pasta.mkdir(parents=True,exist_ok=True)
        c._grava(sessao/'aprendizado_estado.json',{'estado':'coletando','versao':ah.VERSAO,'char':char})
        if self.sugestao_id!=ident:
            self.sugestao_id=ident;self.prev=[];self.eventos=[];self.intervalos=[];self.ultimo=None;self.ts=None;self.prev_por_fonte={}
            estado=c._json(pasta/'posicao.json');self.ultimo=estado.get('ultimo');self.prev=[tuple(v) for v in estado.get('prev',[])];self.ts=estado.get('t')
            self.prev_por_fonte=estado.get('prev_por_fonte',{})
            if (pasta/'eventos.jsonl').is_file():self.eventos=[json.loads(l) for l in (pasta/'eventos.jsonl').read_text(encoding='utf8').splitlines() if l]
            self.intervalos=estado.get('intervalos',[])
            if (pasta/'recursos.jsonl').is_file():self.quadros=[json.loads(l) for l in (pasta/'recursos.jsonl').read_text(encoding='utf8').splitlines() if l][-1000:]
        registro=ah.Registro(c.AQUI/'hunt_data'/'_aprendizado')
        regras=c._json(c.AQUI/'ui'/'roda_catalogo.json').get('versao')
        registro.fase(sessao.name,char,{**obs,'regras_versao':regras},time.time())
        visiveis=[];novos_recursos=[];cobertura=[]
        if quadro_completo and str(quadro_completo)!=self.recurso_quadro:
            from PIL import Image
            with Image.open(quadro_completo) as im:
                r=recursos(im,char);r.update(self._aliados(im,sessao,char));visiveis=lancamentos_visiveis(im,char)
            t=contexto.tempo_quadro(quadro_completo.name)
            r.update({'id':quadro_completo.name,'t':t,'instante':ah.absoluto(sessao.name,t) or quadro_completo.stat().st_mtime,'origem':quadro_completo.name,'sugestao_id':conf.get('sugestao_id') if conf.get('valida') else None,'precisao_s':4})
            novos_recursos.append(r)
            self.quadros.append(r)
            self.quadros=self.quadros[-1000:]
            with (pasta/'recursos.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
            self.recurso_quadro=str(quadro_completo)
        frames=sorted([*sessao.glob('c_*.png'),*sessao.glob('s_*.png')],key=lambda f:(contexto.tempo_quadro(f.name),f.name[0]))
        if not frames:
            registro.observar(sessao.name,char,{**obs,'regras_versao':regras},[],novos_recursos,[])
            return
        if self.ultimo:
            ultima=pathlib.Path(self.ultimo);chave=(contexto.tempo_quadro(ultima.name),ultima.name[0]);frames=[f for f in frames if (contexto.tempo_quadro(f.name),f.name[0])>chave]
        # Em retomada, consumir o atraso em lotes, sem descartar o início.
        frames=frames[:120]
        glyphs,gap=ab.load_atlas();registros=[];ids={e['id'] for e in self.eventos}
        for quadro in frames:
            t=contexto.tempo_quadro(quadro.name);msgs=ev.frame_messages(quadro,glyphs,gap)
            cobertura.append({'id':quadro.name,'t':t,'instante':ah.absoluto(sessao.name,t),'fonte':quadro.name[0],'legivel':bool(msgs),'estado':'texto_lido' if msgs else 'vazio_ou_ilegivel','precisao_s':1})
            if self.ts is not None and 0<t-self.ts<=6:
                if self.intervalos and self.intervalos[-1][1]==self.ts:self.intervalos[-1][1]=t
                else:self.intervalos.append([self.ts,t])
            fonte=quadro.name[0];anterior=self.prev_por_fonte.get(fonte,{})
            prev=[tuple(m) for m in anterior.get('mensagens',[])] if 0<=t-anterior.get('t',-999)<=6 else []
            novos=ev.new_tail(prev,msgs);self.prev_por_fonte[fonte]={'t':t,'mensagens':msgs};self.ultimo=str(quadro);self.ts=t
            repetidos={}
            for ts,body in novos:
                indice=repetidos.get((ts,body),0);repetidos[ts,body]=indice+1
                kind,d=ev.classify(body)
                horas,minutos,segundos=map(int,ts.split(':'));relogio=horas*3600+minutos*60+segundos
                instante=min((relogio+86400*k for k in (int(t//86400)-1,int(t//86400),int(t//86400)+1)),key=lambda v:abs(v-t))
                e=evento({'kind':kind,'t':instante,'instante':ah.absoluto(sessao.name,instante),'ts':ts,'body':body,'precisao_s':1,**d},f'{sessao.name}/{quadro.name}',char,indice)
                if e['id'] in ids:continue
                if e.get('kind')=='cast' and aplicada and conf.get('valida') and (e.get('instante') or 0)>=conf['instante']:
                    recurso=next((r for r in reversed(self.quadros) if r['t']<=instante),{})
                    e.update(contexto.elegibilidade(e,obs['sugestao'],self.eventos,recurso,obs.get('concordancia',{})))
                    normalizar_cast(e,obs,recurso)
                registros.append(e);self.eventos.append(e);ids.add(e['id'])
        if visiveis:
            t=contexto.tempo_quadro(quadro_completo.name)
            repetidos={}
            for ts,body in visiveis:
                indice=repetidos.get((ts,body),0);repetidos[ts,body]=indice+1
                horas,minutos,segundos=map(int,ts.split(':'));relogio=horas*3600+minutos*60+segundos
                instante=min((relogio+86400*k for k in (int(t//86400)-1,int(t//86400),int(t//86400)+1)),key=lambda v:abs(v-t))
                kind,d=ev.classify(body);e=evento({'kind':kind,'t':instante,'instante':ah.absoluto(sessao.name,instante),'ts':ts,'body':body,'precisao_s':1,**d},f'{sessao.name}/{quadro_completo.name}',char,indice)
                if e.get('kind')=='cast' and e['id'] not in ids:
                    if aplicada and conf.get('valida') and (e.get('instante') or 0)>=conf['instante']:
                        recurso=next((r for r in reversed(self.quadros) if r['t']<=instante),{})
                        e.update(contexto.elegibilidade(e,obs['sugestao'],self.eventos,recurso,obs.get('concordancia',{})));normalizar_cast(e,obs,recurso)
                    registros.append(e);self.eventos.append(e);ids.add(e['id'])
        if registros:
            with (pasta/'eventos.jsonl').open('a',encoding='utf8') as f:
                f.writelines(json.dumps(e,ensure_ascii=False)+'\n' for e in registros)
        registro.observar(sessao.name,char,{**obs,'regras_versao':regras},registros,novos_recursos,cobertura)
        fila=sorted([*sessao.glob('c_*.png'),*sessao.glob('s_*.png')],key=lambda f:(contexto.tempo_quadro(f.name),f.name[0]))
        pendentes=bool(fila and self.ultimo!=str(fila[-1]))
        c._grava(sessao/'aprendizado_estado.json',{'estado':'pendente' if pendentes else 'numeros_persistidos','versao':ah.VERSAO,'char':char,'ultimo':self.ultimo})
        r=avaliar(obs.get('sugestao',{}),self.eventos,self.intervalos,obs.get('concordancia',{}))
        atual=c._json(c.RAIZ/c._chave(char)/'modelo.json')
        revisao=revisar_latencia(self.eventos,atual) if conf.get('valida') and obs.get('concordancia',{}).get('estado')=='confere' else {'aceita':False,'motivo':'configuração ainda não conferida'}
        r['modelo_revisado']=revisao['aceita'];r['revisao']=revisao.get('motivo')
        with c.TRAVA:
            if self.ts is not None and self.ts-self.publicado>=60:
                ref=rtc_ml.referencia_roda(obs.get('roda',{}),c._json(c.AQUI/'ui'/'roda_catalogo.json'))
                rtc_fase={**obs.get('rtc',{}),'roda_efeitos':{k:ref[k] for k in ('ranks','revelation')}}
                # Cadência anterior à leitura da roda nova não é atribuída a ela.
                rtc_fase['instante']=max(rtc_fase.get('instante') or 0,obs.get('roda',{}).get('instante') or 0)
                ataque=contexto.calibrar_ataque(char,sessao.name,self.eventos,
                    c._json(c.AQUI/'ui'/'magias.json').get('magias',[]),rtc_fase)
                ataque['escopo']['roda_efeitos']=rtc_fase['roda_efeitos']
                aprendizado=rtc_ml.atualizar(c.RAIZ/c._chave(char),char,sessao.name,self.eventos,
                    c._json(c.AQUI/'ui'/'magias.json').get('magias',[]),rtc_fase,self.intervalos) if aplicada else {
                    'estado':'configuracao_aplicada_desconhecida','intervalos_efetivos':{},'versao':rtc_ml.VERSAO}
                if not aplicada:ataque['intervalos_efetivos']={}
                if aprendizado['intervalos_efetivos']:
                    ataque['intervalos_efetivos']=aprendizado['intervalos_efetivos']
                trilha=sessao/'trilha.jsonl'
                amostras=[]
                if trilha.is_file():
                    for linha in trilha.read_text(encoding='utf8').splitlines():
                        try:amostras.append(json.loads(linha))
                        except ValueError:continue # última linha pode estar sendo escrita
                else:amostras=self.quadros
                monstros={}
                for arq in (c.AQUI/'monstros').glob('*/*.json'):
                    mon=c._json(arq)
                    if mon.get('nome'):monstros[mon['nome'].casefold()]=mon
                combate=rtc_ml.atualizar_combate(c.RAIZ/c._chave(char),char,sessao.name,self.eventos,
                    c._json(c.AQUI/'ui'/'magias.json').get('magias',[]),amostras,self.intervalos,
                    c._json(c.AQUI/'ui'/'roda_catalogo.json'),monstros) if aplicada else {
                        'estado':'configuracao_aplicada_desconhecida','versao':rtc_ml.COMBATE_VERSAO,'perfis':{}}
                anterior=atual.get('rtc_calibracao',{})
                if anterior.get('escopo')==ataque['escopo']:
                    for k in ('prioridade_entre_tipos','runa_uso','validacao_prioridade','confirmado_por_usuario'):
                        if k in anterior:ataque[k]=anterior[k]
                atual={**atual,**(revisao['modelo'] if revisao['aceita'] else {}),'rtc_calibracao':ataque,'rtc_ml':aprendizado,'combate_ml':combate}
                c._grava(c.RAIZ/c._chave(char)/'modelo.json',atual)
            elif revisao['aceita']:c._grava(c.RAIZ/c._chave(char)/'modelo.json',{**atual,**revisao['modelo']})
            c._grava(pasta/'posicao.json',{'ultimo':self.ultimo,'prev':self.prev,'prev_por_fonte':self.prev_por_fonte,'t':self.ts,'intervalos':self.intervalos})
            c._grava(pasta/'avaliacao.json',r);c._grava(c.RAIZ/c._chave(char)/'avaliacao.json',r)
            if self.ts is not None and self.ts-self.publicado>=60:
                ctx=contexto.construir(char,sessao.name,sorted(self.eventos[-10000:],key=lambda e:e['t']),self.quadros,obs.get('contexto',{}).get('cura',{}).get('aliados',[]),c._json(c.AQUI/'ui'/'magias.json').get('magias',[]),atual)
                ctx['regras_versao']=c._json(c.AQUI/'ui'/'roda_catalogo.json').get('versao')
                anterior=c._json(c.RAIZ/c._chave(char)/'contexto_execucao.json')
                if aplicada and anterior.get('regras_versao')==ctx['regras_versao'] and anterior.get('atributos')==ctx.get('atributos'):
                    for campo in ('potencia_hp','qualidade'):
                        ctx['cura'][campo]={**anterior.get('cura',{}).get(campo,{}),**ctx['cura'][campo]}
                c._grava(c.RAIZ/c._chave(char)/'contexto_execucao.json',ctx);self.publicado=self.ts

    @staticmethod
    def _aliados(imagem,sessao,char):
        import layout,nameplates,numpy as np
        if c.ESTADO_LEITOR.get('janelas'):return {'aliados':{},'criaturas':None,'cobertos':[]}
        lay=layout.da_sessao(sessao);reg=lay.get('tela',{});viewport=(reg.get('left',0),reg.get('top',0),reg.get('left',0)+reg.get('width',imagem.width),reg.get('top',0)+reg.get('height',imagem.height))
        # Leitor existente usa o mesmo catálogo de nomes/cores. Vida vem da barra,
        # mas não inventa máximo de HP nem vocação a partir do nome.
        arr=np.asarray(imagem.crop(viewport).convert('RGB'));aliados={};criaturas=0
        nomes=nameplates.nameplates(imagem,viewport=viewport)
        tile=lay.get('tile',64)
        for nome in nomes:
            if nome['tipo']!='jogador':criaturas+=1;continue
            if nome['nome'].casefold()==char.casefold():continue
            x,y=nome['px'];linha=arr[max(0,y-5):min(arr.shape[0],y+4),max(0,x-15):min(arr.shape[1],x+16)]
            if not linha.size:continue
            pixels=linha.astype(int);cor=(pixels[:,:,1]>pixels[:,:,0]+35)|(pixels[:,:,0]>pixels[:,:,1]+35)
            cols=np.flatnonzero(cor.any(0))
            # Exigir uma linha contínua colorida delimitada por preto; texto ou
            # sprite colorido não é prova de uma barra de vida.
            linhas_barra=[]
            for faixa in linha.astype(int):
                colorida=(faixa[:,1]>faixa[:,0]+35)|(faixa[:,0]>faixa[:,1]+35)
                idx=np.flatnonzero(colorida)
                if len(idx)>=2 and idx[0]<=2 and np.all(colorida[idx[0]:idx[-1]+1]):linhas_barra.append(int(idx[-1])+1)
            if linhas_barra and len(linhas_barra)>=2:aliados[nome['nome']]={'percentual':min(100,max(linhas_barra)/linha.shape[1]*100),'atual':None,'maxima':None,'origem':'barra_nameplate','distancia_tiles':nome['dist_tiles']*64/tile}
        return {'aliados':aliados,'criaturas':criaturas,'cobertos':[]}
