"""Evidência numérica preservada; ausência de console nunca prova cast perdido."""
import hashlib
import json
import pathlib
import statistics
import time
import threading

import configuracoes as c

MODELO = 'observacao-4'
PROCESSAMENTO = threading.RLock()


def hazard_do_quadro(imagem, sessao, char, prova, integrantes=None, nomes_observados=None):
    import layout
    import nameplates
    import atlas_build
    import painel_stream
    from rubinot.conflitos.detector import Leitor
    from rubinot.observacao.hazard import ler
    lay = layout.da_sessao(sessao)
    reg = lay.get('tela', {})
    viewport = (reg.get('left',0),reg.get('top',0),
                reg.get('left',0)+reg.get('width',imagem.width),
                reg.get('top',0)+reg.get('height',imagem.height))
    glyphs,gap = atlas_build.load_atlas()
    if integrantes is None:
        integrantes = []
        party = lay.get('party', {})
        painel = painel_stream.recortar_painel(imagem,sessao,'party',party.get('box'),party.get('scroll_x'))
        if painel is not None:
            nomes, _, _, _ = Leitor.blocos_party(painel_stream.linhas(painel))
            if any(n.casefold()==char.casefold() for n in nomes):
                integrantes = nomes
    leitura = ler(imagem,char,viewport,c.ler_json(c.AQUI/'ui'/'hazard_referencias.json'),
                  nameplates.shape_index(glyphs),gap,integrantes=integrantes,nomes_observados=nomes_observados)
    return {**leitura, 'prova':str(prova)}


def reprocessar_consoles(sessao, char, registro):
    """Replay local sem abrir captura ou atribuir configuração atual ao passado."""
    import atlas_build as ab
    import events_build as ev
    import contexto_execucao as contexto
    from rubinot.planejamento.registro import absoluto
    glyphs,gap=ab.load_atlas()
    frames=sorted([*sessao.glob('c_*.png'),*sessao.glob('s_*.png')],
                  key=lambda p:(contexto.tempo_quadro(p.name),p.name[0]))
    anteriores={};vistos={e['id'] for e in registro.ler(sessao.name,'evento')}
    eventos=[];cobertura=[];falhas=[];novos=0
    for i,quadro in enumerate(frames):
        t=contexto.tempo_quadro(quadro.name)
        try:
            msgs=ev.frame_messages(quadro,glyphs,gap)
        except Exception as erro:
            falhas.append({'quadro':str(quadro),'erro':str(erro)});continue
        cobertura.append({'id':'replay:'+quadro.name,'instante':absoluto(sessao.name,t),
                          't':t,'fonte':quadro.name[0],'legivel':bool(msgs),
                          'prova':str(quadro),'modo':'replay_local'})
        anterior=anteriores.get(quadro.name[0],{})
        prev=anterior.get('msgs',[]) if 0<=t-anterior.get('t',-999)<=6 else []
        repetidos={}
        for ts,body in ev.new_tail(prev,msgs):
            indice=repetidos.get((ts,body),0);repetidos[ts,body]=indice+1
            h,m,s=map(int,ts.split(':'));relogio=h*3600+m*60+s
            rel=min((relogio+86400*k for k in (int(t//86400)-1,int(t//86400),int(t//86400)+1)),key=lambda v:abs(v-t))
            kind,d=ev.classify(body)
            e=evento({'kind':kind,'t':rel,'instante':absoluto(sessao.name,rel),
                      'ts':ts,'body':body,'precisao_s':1,**d},f'{sessao.name}/{quadro.name}',char,indice)
            e.update(modo='replay_local',prova=str(quadro),fase_id=None,
                     configuracao_aplicada=None)
            if e['id'] not in vistos:
                eventos.append(e);vistos.add(e['id']);novos+=1
        anteriores[quadro.name[0]]={'t':t,'msgs':msgs}
        if len(cobertura)>=120 or i==len(frames)-1:
            registro.guardar(sessao.name,'evento',eventos);registro.guardar(sessao.name,'cobertura',cobertura)
            eventos=[];cobertura=[]
    registro.guardar(sessao.name,'evento',eventos);registro.guardar(sessao.name,'cobertura',cobertura)
    return {'sessao':sessao.name,'quadros':len(frames),'eventos_novos':novos,'falhas':falhas,
            'atribuicao_retroativa':False}


def reprocessar_recursos(sessao, char, registro):
    from PIL import Image
    import contexto_execucao as contexto
    from rubinot.observacao.telemetria import contadores
    from rubinot.planejamento.registro import absoluto
    existentes={r.get('origem') for r in registro.ler(sessao.name,'recurso')}
    novos=0;falhas=[];itens=0
    for quadro in sorted([*sessao.glob('q_*.png'),*sessao.glob('f_*.png')]):
        if quadro.name in existentes: continue
        try:
            t=contexto.tempo_quadro(quadro.name)
            with Image.open(quadro) as imagem:
                r=recursos(imagem,char)
                r.update(Observador._aliados(imagem,sessao,char))
                r['hazard'] = hazard_do_quadro(imagem,sessao,char,quadro)
                cs=contadores(c.linhas(imagem),char,t,str(quadro),sessao.name)
            r.update(id=quadro.name,origem=quadro.name,t=t,instante=absoluto(sessao.name,t),
                     prova=str(quadro),modo='replay_local',fase_id=None,
                     precisao_s=1 if quadro.name.startswith('q_') else 4)
            # Só a presença é observável sem uma referência histórica de ausência.
            r['escudo']=True if r.get('icone_escudo_presente') else None
            for item in cs: item['instante']=absoluto(sessao.name,t)
            registro.guardar(sessao.name,'recurso',[r]);registro.guardar(sessao.name,'contador_item',cs)
            novos+=1;itens+=len(cs)
        except Exception as erro:
            falhas.append({'quadro':str(quadro),'erro':str(erro)})
    return {'sessao':sessao.name,'recursos_novos':novos,'contadores_lidos':itens,'falhas':falhas}


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


def recursos(imagem, char=None, rapido=False):
    """Números brancos das barras superiores; nunca HP estimado a partir de BP."""
    import numpy as np
    import atlas_build as ab
    import nameplates
    import auxiliares
    import re
    arr=np.asarray(imagem.convert('RGB'));out={}
    if not rapido:c.linhas(imagem.crop((0,0,imagem.width,min(90,imagem.height))))
    alto=arr[:90];hi,lo=alto.max(2),alto.min(2)
    mask=lo>=170
    barra=auxiliares.acha_barra_vida(arr)
    if not barra:
        # HP baixo deixa de ser verde. A barra azul, no mesmo alinhamento,
        # localiza a linha sem supor que a ausência de verde signifique 0 HP.
        azul=(alto[:,:,2].astype(int)-alto[:,:,0]>40)&(alto[:,:,2].astype(int)-alto[:,:,1]>20)
        ys=np.flatnonzero(azul.mean(axis=1)>.15)
        if len(ys)>=4:
            y0=int(ys[0]);y1=y0+1
            while y1<len(azul) and azul[y1].mean()>.15:y1+=1
            barra=(0,y0,imagem.width,y1) if y1-y0>=4 else None
        if not barra:
            presente = auxiliares.acha_icone_escudo(arr) is not None
            return {'icone_escudo_presente': presente, 'escudo': True if presente else None,
                    'escudo_origem': 'icone_identificado' if presente else 'regiao_nao_certificada'}
    x0,y0,x1,y1=barra
    azuis=((alto[:,:,2].astype(int)-alto[:,:,0]>25)&(alto[:,:,2]>alto[:,:,1]))
    cols=np.flatnonzero(azuis[y0:y1].mean(0)>.5)
    direita=int(cols[-1])+1 if len(cols) else x1
    area=np.zeros_like(mask);area[max(0,y0-4):min(len(mask),y1+5),x0:direita]=True;mask &= area
    formas=c.ler_json(c.AQUI/'ui'/'recursos_glifos.json').get('formas',[])
    pessoais=c.RAIZ/c.chave_personagem(char)/'recursos_glifos.json' if char else None
    if pessoais:formas+=c.ler_json(pessoais).get('formas',[])
    independentes={}
    if char and not rapido:
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
    novas=[];pares=[]
    def ler(b, esperado=None):
        cols=np.flatnonzero(b.any(0))
        if not len(cols):return ''
        cuts=np.flatnonzero(np.diff(cols)>1);letras=[]
        for indice,(a,z) in enumerate(zip([int(cols[0]),*[int(cols[i+1]) for i in cuts]],[*[int(cols[i]+1) for i in cuts],int(cols[-1]+1)])):
            g=b[:,a:z];ys=np.flatnonzero(g.any(1));g=g[ys[0]:ys[-1]+1]
            candidatos={f['caractere'] for f in formas if np.asarray(f['pixels']).shape==g.shape and np.array_equal(np.asarray(f['pixels']),g)}
            if not candidatos:
                # Antialiasing varia um pixel com a cor sob o número. Aceitar
                # apenas identidade única e margem clara para outro dígito.
                distancias={}
                for f in formas:
                    ref=np.asarray(f['pixels'])
                    if ref.shape==g.shape:
                        d=int(np.count_nonzero(ref!=g));letra=f['caractere']
                        distancias[letra]=min(distancias.get(letra,999),d)
                ordenadas=sorted(distancias.items(),key=lambda kv:kv[1])
                if ordenadas and ordenadas[0][1]<=1 and (len(ordenadas)==1 or ordenadas[1][1]>=3):
                    candidatos={ordenadas[0][0]}
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
            valor={'atual':int(m[1]),'maxima':int(m[2]),'percentual':int(m[1])/int(m[2])*100,'origem':'barra_visual','qualidade':'texto_integral'}
            pares.append((x0,y0,chave,valor))
            if chave:out[chave]=valor
    if 'vida' not in out:
        manas=[p for p in pares if p[2]=='mana']
        if len(manas)==1:
            mx,my,_,_=manas[0]
            vidas=[p for p in pares if p[2] is None and p[0]<mx and abs(p[1]-my)<=2]
            if len(vidas)==1:out['vida']={**vidas[0][3],'origem':'texto_integral_alinhado_a_mana'}
    if pessoais and novas:
        anteriores=c.ler_json(pessoais).get('formas',[]);unicas={c.assinatura(f):f for f in anteriores+novas}
        with c.TRAVA:c.gravar_json(pessoais,{'versao':2,'formas':list(unicas.values()),'origem':'Skills_e_barra_independentes'})
    out['icone_escudo_presente']=auxiliares.acha_icone_escudo(arr) is not None
    out['escudo'] = True if out['icone_escudo_presente'] else None
    out['escudo_origem'] = 'icone_identificado' if out['escudo'] else 'ausencia_nao_certificada'
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
        magias=c.ler_json(c.AQUI/'ui'/'magias.json').get('magias',[])
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
    # Configuração própria também é referência. O ramo legado abaixo continua
    # aceitando o conjunto sugerido quando a comparação está completa.
    uso = obs.get('uso_componentes', {})
    if all(uso.get(k, {}).get('uso_confirmado') for k in ('cura','roda')):
        from rubinot.planejamento.modelos import referencia_roda
        ref = referencia_roda(obs.get('roda', {}), c.ler_json(c.AQUI/'ui'/'roda_catalogo.json'))
        rank = ref['ranks'].get('32' if e.get('magia_id')=='mass_healing' else '33')
        gema_desconhecida = any(g.get('estado')!='vazio_confirmado' for g in ref['gemas'].values())
        if rank is not None and not gema_desconhecida and ref['completo'] and ref['revelation'].get('11')==0:
            fator = 1+(.04 if e.get('magia_id')=='mass_healing' and rank else
                       .10 if e.get('magia_id')=='heal_friend' and rank>=2 else
                       .04 if e.get('magia_id')=='heal_friend' and rank else 0)
            cat = c.ler_json(c.AQUI/'ui'/'roda_catalogo.json')
            if any(k not in ref['revelation'] for k in cat.get('revelation', {})): return
            fixo = sum(cat.get('composicao', {}).get('revelation_bonus_hp', {}).get(str(n),0) for n in ref['revelation'].values())
            e.update(base_multiplicador=fator, fixo_hp=fixo, normalizacao_origem='roda_detectada_declarada')
            return
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


def cadencia_fontes(cobertura, recursos):
    """Cadência efetivamente observada, não a frequência nominal do monitor."""
    fontes = {}
    for row in [*cobertura, *recursos]:
        fonte = row.get('fonte') or str(row.get('origem', '')).split('_')[0]
        if row.get('t') is not None: fontes.setdefault(fonte, {})[row.get('id') or row['t']] = row
    saida = {}
    for fonte, unicos in fontes.items():
        rows = sorted(unicos.values(), key=lambda r:r['t'])
        gaps = [b['t']-a['t'] for a,b in zip(rows, rows[1:]) if b['t'] > a['t']]
        latencias = [r['processado_em']-r['instante'] for r in rows if r.get('processado_em') is not None and r.get('instante') is not None]
        saida[fonte] = {'amostras': len(rows), 'intervalo_mediano_s': statistics.median(gaps) if gaps else None,
                        'maior_gap_s': max(gaps) if gaps else None,
                        'latencia_mediana_s': statistics.median(latencias) if latencias else None,
                        'legibilidade': sum(r.get('legivel') is True for r in rows) if fonte in ('c','s') else None,
                        'perda_quadros': None, 'cobertura_completa': False}
    return saida


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
    def __init__(self, registro_de=None, agora=None):
        from aprendizado_hunt import Registro
        self.registro_de = registro_de or Registro
        self.agora = agora or time.time
        self.sessao=None;self.char=None;self.ultimo=None;self.prev=[];self.eventos=[];self.intervalos=[];self.ts=None;self.sugestao_id=None;self.recurso_quadro=None;self.quadros=[];self.publicado=-1;self.prev_por_fonte={}

    def processar(self, sessao, char, quadro_completo=None):
        with PROCESSAMENTO:
            return self._processar(sessao,char,quadro_completo)

    def coletar_cura(self, sessao, char, limite=12):
        """Drena os q_ em ordem; cursor avança só após números e provas persistidos."""
        import shutil
        from PIL import Image
        from contexto_execucao import tempo_quadro
        from rubinot.planejamento.registro import absoluto
        with PROCESSAMENTO:
            estado = c.ler_json(sessao/'coleta_cura.json')
            ultimo = estado.get('ultimo','')
            ultima_amostra = estado.get('ultima_amostra')
            if ultima_amostra is None:ultima_amostra=-float('inf')
            fila = [p for p in sorted(sessao.glob('q_*.png')) if p.name>ultimo]
            reg = self.registro_de(c.raiz_aprendizado())
            fases = reg.ler(sessao.name,'fase')
            nomes = {e['alvo'] for e in reg.ler(sessao.name,'evento') if e.get('kind')=='cast'
                     and e.get('ator')==char and e.get('magia_id')=='heal_friend' and e.get('alvo')
                     and e.get('qualidade')=='identificada' and not e.get('qa') and not e.get('sintetico')}
            pasta = c.pasta_personagem(char)/'execucao'/sessao.name/'cura_provas'
            pasta.mkdir(parents=True,exist_ok=True)
            for p in fila[:limite]:
                t = tempo_quadro(p.name); instante = absoluto(sessao.name,t)
                # Série a 1 Hz, explícita. Captura segue a 2 Hz para os consoles.
                # Não pular uma cauda inteira: manter a ordem mesmo em atraso.
                if t-ultima_amostra<1:
                    ultimo=p.name
                    c.gravar_json(sessao/'coleta_cura.json',{'ultimo':ultimo,'ultima_amostra':ultima_amostra,'cadencia_alvo_s':1,'estado':'pendente'})
                    continue
                with Image.open(p) as im:
                    r = recursos(im,char,rapido=True)
                    r.update(self._aliados(im,sessao,char,nomes,com_nomes=True))
                    r['hazard']=hazard_do_quadro(im,sessao,char,p,integrantes=[],
                        nomes_observados=r.pop('_nomes',[]))
                # Configuração no instante do quadro, nunca a última referência
                # aplicada retrospectivamente aos quadros atrasados.
                fase = next((f for f in reversed(fases) if f['instante']<=instante),{})
                # Hazard é leitura independente. Reutilizar só o mesmo quadro
                # já processado pelo observador, sem carregar valor antigo.
                anterior = next((q for q in reversed(self.quadros) if q.get('origem')==p.name),{})
                if r['hazard'].get('nivel') is None and anterior.get('hazard'):
                    r['hazard'] = anterior['hazard']
                prova = pasta/p.name
                if not prova.exists():shutil.copy2(p,prova)
                r['hazard']['prova']=str(prova)
                r.update(id='cura:'+p.name,t=t,instante=instante,prova=str(prova),
                    origem=p.name,fase_id=fase.get('id'),
                    configuracoes=fase.get('revisoes',{}),
                    vigencia_inconclusiva=any(f.get('ultima_compativel_em',float('inf'))<=instante<f.get('primeira_divergente_em',0)
                        for ph in fases for f in ph.get('fronteiras_incertas',{}).values()),
                    precisao_s=1,leitor_versao='cura-densa-1')
                reg.guardar(sessao.name,'recurso_cura',[r])
                ultimo = p.name
                ultima_amostra=t
                c.gravar_json(sessao/'coleta_cura.json',{'ultimo':ultimo,'ultima_amostra':ultima_amostra,'cadencia_alvo_s':1,'estado':'pendente'})
            c.gravar_json(sessao/'coleta_cura.json',{'ultimo':ultimo,
                'ultima_amostra':ultima_amostra if ultima_amostra!=-float('inf') else None,'cadencia_alvo_s':1,
                'estado':'pendente' if len(fila)>limite else 'numeros_persistidos'})
            if fila and len(fila)<=limite:
                estudos=reg.ler(sessao.name,'estudo_cura')
                if estudos:
                    e=estudos[-1]
                    slots=e.get('configuracao_referencia') or [{**s,'tipo':'autocura' if s['alvo']=='eu' else 'party'} for s in e['referencia']]
                    reg.estudar_cura(sessao.name,e['contexto'],e.get('party',[]),slots)
            return len(fila[:limite])

    def _processar(self, sessao, char, quadro_completo=None):
        import events_build as ev
        import atlas_build as ab
        import contexto_execucao as contexto
        import rtc_ml
        import aprendizado_hunt as ah
        if self.sessao!=sessao or self.char!=char:
            self.sessao=sessao;self.char=char;self.ultimo=None;self.prev=[];self.eventos=[];self.intervalos=[];self.ts=None;self.quadros=[];self.recurso_quadro=None;self.prev_por_fonte={};self.publicado=-1;self.sugestao_id=None
        obs=c.consultar(char, sessao.name);conf=obs.get('confirmacao',{})
        tarefas=obs.get('elegibilidade_aprendizado',{})
        ataque_confirmado=tarefas.get('cadencia_ataque',False)
        aplicada=tarefas.get('efeitos_roda',False)
        desde_ataque=obs.get('uso_componentes',{}).get('rtc',{}).get('desde')
        desde_efeitos=max((obs.get('uso_componentes',{}).get(k,{}).get('desde') or float('inf') for k in ('rtc','roda')))
        eventos_ataque=lambda: [e for e in self.eventos if ataque_confirmado and (e.get('instante') or 0)>=(desde_ataque or float('inf'))]
        eventos_efeitos=lambda: [{**e, 'declaracao_uso_id':obs.get('declaracao_uso',{}).get('id')} for e in self.eventos if aplicada and (e.get('instante') or 0)>=desde_efeitos]
        # A sugestão é metadado, não a identidade do arquivo de observação.
        ident='observacao'
        pasta=c.RAIZ/c.chave_personagem(char)/'execucao'/sessao.name/ident;pasta.mkdir(parents=True,exist_ok=True)
        c.gravar_json(sessao/'aprendizado_estado.json',{'estado':'coletando','versao':ah.VERSAO,'char':char})
        if self.sugestao_id!=ident:
            self.sugestao_id=ident;self.prev=[];self.eventos=[];self.intervalos=[];self.ultimo=None;self.ts=None;self.prev_por_fonte={}
            estado=c.ler_json(pasta/'posicao.json');self.ultimo=estado.get('ultimo');self.prev=[tuple(v) for v in estado.get('prev',[])];self.ts=estado.get('t')
            self.prev_por_fonte=estado.get('prev_por_fonte',{})
            if (pasta/'eventos.jsonl').is_file():self.eventos=[json.loads(l) for l in (pasta/'eventos.jsonl').read_text(encoding='utf8').splitlines() if l]
            self.intervalos=estado.get('intervalos',[])
            if (pasta/'recursos.jsonl').is_file():self.quadros=[json.loads(l) for l in (pasta/'recursos.jsonl').read_text(encoding='utf8').splitlines() if l][-1000:]
        registro=self.registro_de(c.raiz_aprendizado())
        regras=c.ler_json(c.AQUI/'ui'/'roda_catalogo.json').get('versao')
        registro.fase(sessao.name,char,{**obs,'regras_versao':regras},self.agora())
        registro.acompanhar_adocao(sessao.name, obs)
        visiveis=[];novos_recursos=[];cobertura=[]
        if quadro_completo and str(quadro_completo)!=self.recurso_quadro:
            from PIL import Image
            with Image.open(quadro_completo) as im:
                nomes={e['alvo'] for e in self.eventos if e.get('kind')=='cast' and e.get('ator')==char
                       and e.get('magia_id')=='heal_friend' and e.get('alvo') and e.get('qualidade')=='identificada'}
                r=recursos(im,char);r.update(self._aliados(im,sessao,char,nomes));visiveis=lancamentos_visiveis(im,char)
                r['hazard'] = hazard_do_quadro(im,sessao,char,quadro_completo)
                from rubinot.observacao import telemetria
                import base64, io, numpy as np
                refs = c.ler_json(c.AQUI/'ui'/'rtc_referencias.json').get('templates', {})
                ids_slots = {s.get('id') for k in ('rtc','cura') for s in obs.get(k, {}).get('slots', [])} | {'magic_shield'}
                modelos_icones = {k:np.asarray(Image.open(io.BytesIO(base64.b64decode(v))).convert('RGB'))
                                  for k,v in refs.items() if k in ids_slots}
                textos = c.linhas(im)
                icones = telemetria.identificar_icones(im, modelos_icones)
                t = contexto.tempo_quadro(quadro_completo.name)
                r['prontidao'] = telemetria.prontidao(textos, icones, t, quadro_completo.name)
                r['escudo'] = telemetria.escudo_certificado(im, r.get('icone_escudo_presente'),
                    c.ler_json(c.pasta_personagem(char)/'estados_referencia.json'))
                contadores = telemetria.contadores(textos, char, t, quadro_completo.name, sessao.name)
                import painel_stream
                r['paineis'] = {'xp':painel_stream.ler_xp(im,sessao), 'input':painel_stream.ler_input(im,sessao)}
                from rubinot.observacao import paineis
                r['paineis']['observacao'] = paineis.ler(im, sessao, quadro_completo.name, t,
                    c.ler_json(c.pasta_personagem(char)/'supplies_referencias.json'))
                from rubinot.observacao.supplies import hotkeys
                estoque = hotkeys(im, c.ler_json(c.pasta_personagem(char)/'supplies_referencias.json'),
                                  char, t, quadro_completo.name, sessao.name)
            if contadores or estoque or r['paineis']['input'].get('total') is not None or r['hazard']['visiveis'] or any(v.get('restante_s') is not None for v in r['prontidao'].values()):
                import shutil
                prova = pasta/'provas'/quadro_completo.name; prova.parent.mkdir(exist_ok=True)
                if not prova.exists(): shutil.copy2(quadro_completo, prova)
                r['hazard']['prova'] = str(prova)
                for item in contadores: item['prova'] = str(prova)
                for item in estoque: item['prova'] = str(prova)
                for valor in r['prontidao'].values(): valor['prova'] = str(prova)
            anteriores_contadores = registro.ler(sessao.name, 'contador_item')
            for item in contadores:
                ultimo = next((a for a in reversed(anteriores_contadores) if a['item']==item['item']), None)
                item['continuidade'] = bool(ultimo and item['valor'] >= ultimo['valor']
                    and 0 < item['t']-ultimo['t'] <= 6)
                if ultimo and item['valor'] < ultimo['valor']:
                    item['serie'] = sessao.name+':reset:'+quadro_completo.name
                elif ultimo: item['serie'] = ultimo['serie']
                item['instante'] = ah.absoluto(sessao.name,t)
            registro.guardar(sessao.name, 'contador_item', contadores)
            registro.guardar(sessao.name, 'estoque_item', estoque)
            t=contexto.tempo_quadro(quadro_completo.name)
            r.update({'id':quadro_completo.name,'t':t,'instante':ah.absoluto(sessao.name,t) or quadro_completo.stat().st_mtime,'processado_em':self.agora(),'origem':quadro_completo.name,'sugestao_id':conf.get('sugestao_id') if conf.get('valida') else None,'precisao_s':1 if quadro_completo.name.startswith('q_') else 4})
            novos_recursos.append(r)
            import auxiliares
            contexto_aux = {'hunt':c.ler_json(sessao/'contexto_hunt.json').get('hunt'),
                'pt':c.ler_json(sessao/'contexto_hunt.json').get('pt'),
                'hazard':r.get('hazard',{}).get('nivel'),
                'party':obs.get('contexto',{}).get('cura',{}).get('aliados'),
                'rtc':obs.get('rtc',{}).get('id'),'cura':obs.get('cura',{}).get('id'),
                'roda':obs.get('roda',{}).get('id'),'regras':regras}
            ctx_hunt=c.ler_json(sessao/'contexto_hunt.json')
            r['contexto_twin']={'char':char,'hunt':contexto_aux['hunt'],'pt':contexto_aux['pt'],
                'hazard':contexto_aux['hazard'],
                'membros':sorted(m['nome'] for m in r['paineis']['observacao']['paineis']['party'].get('membros',[]) if m.get('identidade_completa')) or None,
                'roda':obs.get('roda',{}).get('assinatura_leitura'),
                'rota':ctx_hunt.get('rota'),'interferencias':ctx_hunt.get('interferencias')}
            r['contexto_aprendizado'] = contexto_aux
            auxiliares.AUX.receber_observacao(sessao,char,contexto_aux,r,c.pasta_personagem(char)/'assistencia')
            self.quadros.append(r)
            self.quadros=self.quadros[-1000:]
            with (pasta/'recursos.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
            self.recurso_quadro=str(quadro_completo)
        frames=sorted([*sessao.glob('c_*.png'),*sessao.glob('s_*.png')],key=lambda f:(contexto.tempo_quadro(f.name),f.name[0]))
        if not frames and not visiveis:
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
                if e.get('kind')=='cast' and tarefas.get('cura') and (e.get('instante') or 0)>=(obs.get('uso_componentes',{}).get('cura',{}).get('desde') or float('inf')):
                    recurso=next((r for r in reversed(self.quadros) if r['t']<=instante),{})
                    normalizar_cast(e,obs,recurso)
                registros.append(e);self.eventos.append(e);ids.add(e['id'])
        if visiveis:
            t=contexto.tempo_quadro(quadro_completo.name)
            if self.ts is None: self.ts=t
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
                    if tarefas.get('cura') and (e.get('instante') or 0)>=(obs.get('uso_componentes',{}).get('cura',{}).get('desde') or float('inf')):
                        recurso=next((r for r in reversed(self.quadros) if r['t']<=instante),{})
                        normalizar_cast(e,obs,recurso)
                    registros.append(e);self.eventos.append(e);ids.add(e['id'])
        if registros:
            with (pasta/'eventos.jsonl').open('a',encoding='utf8') as f:
                f.writelines(json.dumps(e,ensure_ascii=False)+'\n' for e in registros)
        registro.observar(sessao.name,char,{**obs,'regras_versao':regras},registros,novos_recursos,cobertura)
        from rubinot.planejamento.oportunidades import reconstruir
        if ataque_confirmado and registros:
            oportunidades = reconstruir(eventos_ataque(), self.quadros, obs.get('rtc', {}).get('slots', []),
                c.ler_json(c.AQUI/'ui'/'magias.json').get('magias', []), desde_ataque)
            registro.guardar(sessao.name, 'oportunidade', oportunidades)
        fila=sorted([*sessao.glob('c_*.png'),*sessao.glob('s_*.png')],key=lambda f:(contexto.tempo_quadro(f.name),f.name[0]))
        pendentes=bool(fila and self.ultimo!=str(fila[-1]))
        c.gravar_json(sessao/'aprendizado_estado.json',{'estado':'pendente' if pendentes else 'numeros_persistidos','versao':ah.VERSAO,'char':char,'ultimo':self.ultimo})
        r=avaliar(obs.get('sugestao',{}),self.eventos,self.intervalos,obs.get('concordancia',{}))
        r['cadencia_fontes'] = cadencia_fontes(registro.ler(sessao.name, 'cobertura'), self.quadros)
        atual=c.ler_json(c.RAIZ/c.chave_personagem(char)/'modelo.json')
        revisao=revisar_latencia(self.eventos,atual) if conf.get('valida') and obs.get('concordancia',{}).get('estado')=='confere' else {'aceita':False,'motivo':'configuração ainda não conferida'}
        r['modelo_revisado']=revisao['aceita'];r['revisao']=revisao.get('motivo')
        with c.TRAVA:
            if self.ts is not None and self.ts-self.publicado>=60:
                ref=rtc_ml.referencia_roda(obs.get('roda',{}),c.ler_json(c.AQUI/'ui'/'roda_catalogo.json'))
                rtc_fase={**obs.get('rtc',{}),'sessao':sessao.name,'roda_efeitos':{k:ref[k] for k in ('ranks','revelation')}}
                rtc_fase['declaracao_uso_id'] = obs.get('declaracao_uso',{}).get('id')
                # Cadência anterior à leitura da roda nova não é atribuída a ela.
                rtc_fase['instante']=max(rtc_fase.get('instante') or 0,desde_ataque or 0)
                if not aplicada:rtc_fase['roda_efeitos']={'ranks':{},'revelation':{}}
                ataque=contexto.calibrar_ataque(char,sessao.name,eventos_ataque(),
                    c.ler_json(c.AQUI/'ui'/'magias.json').get('magias',[]),rtc_fase)
                ataque['escopo']['roda_efeitos']=rtc_fase['roda_efeitos']
                ataque['escopo']['declaracao_uso_id']=rtc_fase.get('declaracao_uso_id')
                aprendizado=rtc_ml.atualizar(c.RAIZ/c.chave_personagem(char),char,sessao.name,eventos_ataque(),
                    c.ler_json(c.AQUI/'ui'/'magias.json').get('magias',[]),rtc_fase,self.intervalos) if ataque_confirmado else {
                    'estado':'configuracao_aplicada_desconhecida','intervalos_efetivos':{},'versao':rtc_ml.VERSAO}
                if not ataque_confirmado:ataque['intervalos_efetivos']={}
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
                    mon=c.ler_json(arq)
                    if mon.get('nome'):monstros[mon['nome'].casefold()]=mon
                combate=rtc_ml.atualizar_combate(c.RAIZ/c.chave_personagem(char),char,sessao.name,eventos_efeitos(),
                    c.ler_json(c.AQUI/'ui'/'magias.json').get('magias',[]),amostras,self.intervalos,
                    c.ler_json(c.AQUI/'ui'/'roda_catalogo.json'),monstros,
                    contexto={'hunt':c.ler_json(sessao/'contexto_hunt.json').get('hunt'),
                              'hazard':(self.quadros[-1].get('hazard',{}).get('nivel') if self.quadros else None),
                              'party':obs.get('contexto',{}).get('cura',{}).get('aliados')}) if aplicada else {
                        'estado':'configuracao_aplicada_desconhecida','versao':rtc_ml.COMBATE_VERSAO,'perfis':{}}
                from rubinot.planejamento.efetividade import uso_bonus_por_magia
                beneficios = []
                for magia in c.ler_json(c.AQUI/'ui'/'magias.json').get('magias', []):
                    estado_magia = rtc_ml.estado_magia(magia, ref)
                    if estado_magia and estado_magia['multiplicador_base'] > 1:
                        beneficios.append({'magia_id':magia['id'],'tipo':'passivo',
                            'atributo':'base_power', 'modificador':estado_magia['multiplicador_base']-1,
                            'unidade':'fracao_base', 'estagio':ref.get('ranks'),
                            'custo_investimento':None})
                bonus = uso_bonus_por_magia(eventos_efeitos(), beneficios, obs.get('declaracao_uso',{}).get('id'))
                registro.guardar(sessao.name, 'uso_bonus', [{'id':c.assinatura([obs.get('declaracao_uso',{}).get('id'),bonus]),
                    'instante':self.agora(),'declaracao_id':obs.get('declaracao_uso',{}).get('id'),'por_magia':bonus}])
                r['uso_bonus_por_magia'] = bonus
                anterior=atual.get('rtc_calibracao',{})
                if anterior.get('escopo')==ataque['escopo']:
                    for k in ('prioridade_entre_tipos','runa_uso','validacao_prioridade','confirmado_por_usuario'):
                        if k in anterior:ataque[k]=anterior[k]
                registro.guardar(sessao.name,'modelo_candidato',[{'id':c.assinatura([ataque,aprendizado,combate]),'instante':self.agora(),'rtc_calibracao':ataque,'rtc_ml':aprendizado,'combate_ml':combate}])
                execucao = registro.validar_execucao(sessao.name, ataque['escopo'], self.agora())
                atual['validacao_execucao'] = execucao
                # Auditoria interna aceita provas de episódios, não rótulos
                # gerados pelo próprio modelo nem sessões copiadas.
                auditados = c.ler_json(c.pasta_personagem(char)/'episodios_auditados.json').get('episodios', [])
                auditados = [a for a in auditados if a.get('char')==char and a.get('sessao')==sessao.name
                             and a.get('escopo')==ataque['escopo'] and a.get('provas')]
                registro.guardar(sessao.name, 'episodio_auditado', auditados)
                atual={**atual,**(revisao['modelo'] if revisao['aceita'] else {}),'rtc_calibracao':ataque,'rtc_ml':aprendizado,'combate_ml':combate,'elegibilidade_aprendizado':tarefas}
                c.gravar_json(c.RAIZ/c.chave_personagem(char)/'modelo.json',atual)
            elif revisao['aceita']:c.gravar_json(c.RAIZ/c.chave_personagem(char)/'modelo.json',{**atual,**revisao['modelo']})
            c.gravar_json(pasta/'posicao.json',{'ultimo':self.ultimo,'prev':self.prev,'prev_por_fonte':self.prev_por_fonte,'t':self.ts,'intervalos':self.intervalos})
            c.gravar_json(pasta/'avaliacao.json',r);c.gravar_json(c.RAIZ/c.chave_personagem(char)/'avaliacao.json',r)
            if self.ts is not None and self.ts-self.publicado>=60:
                desde_cura=obs.get('uso_componentes',{}).get('cura',{}).get('desde') or float('inf')
                eventos_cura=[e for e in self.eventos[-10000:] if (e.get('instante') or 0)>=desde_cura]
                quadros_cura=[q for q in self.quadros if (q.get('instante') or 0)>=desde_cura]
                ctx=contexto.construir(char,sessao.name,sorted(eventos_cura,key=lambda e:e['t']),quadros_cura,obs.get('contexto',{}).get('cura',{}).get('aliados',[]),c.ler_json(c.AQUI/'ui'/'magias.json').get('magias',[]),atual)
                ctx['regras_versao']=c.ler_json(c.AQUI/'ui'/'roda_catalogo.json').get('versao')
                anterior=c.ler_json(c.RAIZ/c.chave_personagem(char)/'contexto_execucao.json')
                if aplicada and anterior.get('regras_versao')==ctx['regras_versao'] and anterior.get('atributos')==ctx.get('atributos'):
                    for campo in ('potencia_hp','qualidade'):
                        ctx['cura'][campo]={**anterior.get('cura',{}).get(campo,{}),**ctx['cura'][campo]}
                c.gravar_json(c.RAIZ/c.chave_personagem(char)/'contexto_execucao.json',ctx);self.publicado=self.ts
                refs = obs.get('referencias_sio', {})
                party = refs.get('party') or ctx.get('cura',{}).get('aliados',[])
                if party:
                    registro.estudar_sio(sessao.name, {'char':char,
                        'hunt':c.ler_json(sessao/'contexto_hunt.json').get('hunt'),
                        'hazard':obs.get('hazard_confirmado',{}).get('hazard'),
                        'regras_versao':ctx['regras_versao']}, party, refs.get('configuracao'))
                registro.estudar_cura(sessao.name, {'char':char,
                    'hunt':c.ler_json(sessao/'contexto_hunt.json').get('hunt')},
                    party, obs.get('cura',{}).get('slots',[]))

    @staticmethod
    def _aliados(imagem,sessao,char,nomes_conhecidos=(),com_nomes=False):
        import layout,nameplates,numpy as np
        # O estado de uma janela AGORA não descreve o quadro na fila antiga.
        conhecidos={n.casefold() for n in nomes_conhecidos}
        lay=layout.da_sessao(sessao);reg=lay.get('tela',{});viewport=(reg.get('left',0),reg.get('top',0),reg.get('left',0)+reg.get('width',imagem.width),reg.get('top',0)+reg.get('height',imagem.height))
        # Leitor existente usa o mesmo catálogo de nomes/cores. Vida vem da barra,
        # mas não inventa máximo de HP nem vocação a partir do nome.
        arr=np.asarray(imagem.crop(viewport).convert('RGB'));aliados={};criaturas=0
        nomes=nameplates.nameplates(imagem,viewport=viewport)
        tile=lay.get('tile',64)
        for nome in nomes:
            if nome['tipo']!='jogador' and nome['nome'].casefold() not in conhecidos:
                criaturas+=1;continue
            if nome['nome'].casefold()==char.casefold():continue
            percentual=vida_nameplate(arr,*nome['px'])
            if percentual is not None:aliados[nome['nome']]={'percentual':percentual,'atual':None,'maxima':None,'origem':'barra_nameplate_integral','distancia_tiles':nome['dist_tiles']*64/tile}
        return {'aliados':aliados,'criaturas':criaturas,'cobertos':[],**({'_nomes':nomes} if com_nomes else {})}


def vida_nameplate(arr, x, y):
    """Lê a moldura completa de 31 pixels; centro do nome não é centro da barra."""
    import numpy as np
    candidatos=[]
    for yy in range(max(0,y-9),min(arr.shape[0]-3,y)):
        for xx in range(max(0,x-40),min(arr.shape[1]-30,x+10)):
            bloco=arr[yy:yy+4,xx:xx+31]
            if not (np.all(bloco[0]==0) and np.all(bloco[3]==0) and
                    np.all(bloco[:,0]==0) and np.all(bloco[:,-1]==0) and
                    np.array_equal(bloco[1],bloco[2])):continue
            faixa=bloco[1,1:-1];preenchido=np.any(faixa!=0,axis=1);n=int(preenchido.sum())
            if not n or not np.all(preenchido[:n]) or np.any(preenchido[n:]):continue
            cor=faixa[0].astype(int)
            if not np.all(faixa[:n]==cor) or max(cor)-min(cor)<35:continue
            if cor[2]>min(cor[0],cor[1])+10:continue  # mana azul
            candidatos.append((xx,yy,n/29*100))
    return candidatos[0][2] if len(candidatos)==1 else None
