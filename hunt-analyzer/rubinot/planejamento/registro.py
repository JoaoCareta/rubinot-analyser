"""Registro interno de hunts: evidência, fases, cobertura e referências.

Não transforma leitura de editor em configuração aplicada nem promove modelos
por ausência de mortes. Os originais são preservados; SQLite faz o registro
numérico transacional, repetível e independente da interface.
"""
import datetime as dt
import contextlib
import hashlib
import json
import pathlib
import re
import sqlite3
import time

from rubinot.planejamento.avaliacao import saude_party, comparar_resultados

VERSAO = 'hunt-aprendizado-2'
LEITOR = 'observacao-4'


def assinatura(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()


def json_de(p, padrao=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {} if padrao is None else padrao


def linhas(p):
    if not p.is_file():
        return
    with p.open(encoding='utf8') as f:
        for linha in f:
            try:
                yield json.loads(linha)
            except ValueError:
                continue  # fragmento de escrita interrompida não é uma amostra


def absoluto(sessao, segundos):
    """O carimbo 24:xx da captura continua no dia seguinte, sem modulo 24."""
    m = re.search(r'(\d{8})_\d{4,6}', str(sessao))
    if not m or segundos is None:
        return None
    if isinstance(segundos,str) and re.fullmatch(r'\d{1,3}:\d{2}:\d{2}',segundos):
        h, minuto, segundo = map(int,segundos.split(':'))
        if minuto>=60 or segundo>=60: return None
        segundos=h*3600+minuto*60+segundo
    if not isinstance(segundos,(int,float)) or isinstance(segundos,bool):
        return None
    return dt.datetime.strptime(m[1], '%Y%m%d').timestamp() + segundos


def identidade(pasta, resumo=None):
    r = resumo or {}; s = r.get('sessao') or {}
    origem = r.get('pasta') or (s if isinstance(s,str) else pasta.name)
    m = re.search(r'(\d{8})_(\d{4,6})(?:_[a-f0-9]{8})?', origem)
    # Histórico antigo pode não conhecer o segundo da abertura: nunca colapsar
    # duas capturas reais do mesmo minuto quando a origem completa está presente.
    return assinatura(['sessao', m[0] if m else origem])


def vincular_voltas(sessao, voltas, fases):
    """Interpretação separada: não altera nem rateia os totais das voltas."""
    saida = []
    for v in voltas:
        a = absoluto(sessao, v.get('ini', v.get('inicio')))
        b = absoluto(sessao, v.get('fim'))
        vigente = next((f for f in reversed(fases) if a is not None and f['instante'] <= a), None)
        mista = bool(a is not None and b is not None and
            (any(a < f['instante'] < b for f in fases) or any(
                fronteira.get('ultima_compativel_em', b) < b and fronteira.get('primeira_divergente_em', a) > a
                for f in fases for fronteira in f.get('fronteiras_incertas', {}).values())))
        estado = 'mista' if mista else 'parcial' if v.get('parcial') or a is None or b is None or b <= a or v.get('tipo', 'volta') != 'volta' else \
                 'completa_com_uso_declarado' if vigente and vigente['revisoes']['rtc']['estado'] == 'uso_declarado' else 'uso_desconhecido'
        saida.append({'n': v.get('n'), 'fase_id': vigente['id'] if vigente else None,
                      'estado': estado, 'inicio': a, 'fim': b, 'totais_rateados': False})
    return saida


class Registro:
    def __init__(self, raiz):
        self.raiz = pathlib.Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.db = self.raiz / 'aprendizado.sqlite3'
        with self.conexao() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS sessoes (
                    id TEXT PRIMARY KEY, dados TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS fontes (
                    caminho TEXT PRIMARY KEY, sessao TEXT, assinatura TEXT, dados TEXT);
                CREATE TABLE IF NOT EXISTS registros (
                    sessao TEXT, tipo TEXT, id TEXT, instante REAL, dados TEXT,
                    PRIMARY KEY(sessao,tipo,id));
                CREATE INDEX IF NOT EXISTS linha_tempo ON registros(sessao,instante);
                CREATE TABLE IF NOT EXISTS estados (
                    sessao TEXT PRIMARY KEY, dados TEXT NOT NULL);
            ''')

    @contextlib.contextmanager
    def conexao(self):
        con = sqlite3.connect(self.db, timeout=30)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute('PRAGMA busy_timeout=30000')
            with con:
                yield con
        finally:
            con.close()

    def guardar(self, sessao, tipo, registros):
        with self.conexao() as con:
            for r in registros:
                ident = r.get('id') or assinatura(r)
                con.execute('INSERT OR IGNORE INTO registros VALUES (?,?,?,?,?)',
                    (sessao, tipo, ident, r.get('instante'), json.dumps(r, ensure_ascii=False)))

    def backup(self, destino):
        """Snapshot consistente de SQLite, com todas as conexões fechadas."""
        destino = pathlib.Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with self.conexao() as origem:
            con = sqlite3.connect(destino)
            try:
                origem.backup(con)
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup SQLite inválido.')
            finally:
                con.close()
        return destino

    def ler(self, sessao, tipo):
        with self.conexao() as con:
            return [json.loads(r[0]) for r in con.execute(
                'SELECT dados FROM registros WHERE sessao=? AND tipo=? ORDER BY instante,id', (sessao, tipo))]

    def fase(self, sessao, char, observado, instante):
        revisoes = {}
        from rubinot.configuracao_combate.vigencia import resolver
        componentes = resolver(observado.get('declaracao_uso', {}), observado, char, sessao, instante)
        for tipo in ('rtc', 'cura', 'roda'):
            s = observado.get(tipo) or {}
            # Configuração antiga não migra para outra sessão. Aplicação exige
            # evidência específica; confirmar uma sugestão não confirma o editor.
            valida = (s.get('sessao') == sessao or componentes[tipo]['uso_confirmado']) and s.get('instante', float('inf')) <= instante
            revisoes[tipo] = {'revisao': s.get('id') if valida else None,
                'declaracao_id': componentes[tipo]['declaracao_id'],
                'uso_desde': componentes[tipo]['desde'],
                'estado': 'uso_declarado' if componentes[tipo]['uso_confirmado'] else
                    componentes[tipo]['estado'] if componentes[tipo]['estado'] in ('outro_rtc', 'rtc_desligado') else
                    'aplicado' if valida and s.get('aplicado_confirmado') else
                    'observado_sem_aplicacao' if valida else 'desconhecido',
                'completo': bool(valida and s.get('completo'))}
        regras = observado.get('regras_versao')
        chave = assinatura([char, revisoes, regras, LEITOR])
        fases = self.ler(sessao, 'fase')
        if fases and fases[-1]['chave'] == chave:
            return fases[-1]
        fase = {'id': assinatura([sessao, chave, instante]), 'chave': chave,
            'instante': instante, 'char': char, 'revisoes': revisoes,
            'fronteiras_incertas': {tipo: observado[tipo]['fronteira_anterior'] for tipo in revisoes
                if observado.get(tipo, {}).get('fronteira_anterior') and fases
                and fases[-1]['revisoes'][tipo]['revisao'] != revisoes[tipo]['revisao']},
            'regras_versao': regras, 'leitor_versao': LEITOR}
        self.guardar(sessao, 'fase', [fase])
        return fase

    def observar(self, sessao, char, observado, eventos, recursos, cobertura):
        instante = max([r.get('instante') or 0 for r in recursos] +
                       [e.get('instante') or 0 for e in eventos] + [time.time()])
        fase = self.fase(sessao, char, observado, instante)
        # Fase vinculada ao instante do evento, jamais a revisão mais recente.
        fases = self.ler(sessao, 'fase')
        for tipo, rows in (('evento', eventos), ('recurso', recursos), ('cobertura', cobertura)):
            preparados = []
            for r in rows:
                r = dict(r)
                r['instante'] = r.get('instante') or absoluto(sessao, r.get('t'))
                vigente = next((f for f in reversed(fases) if f['instante'] <= (r['instante'] or 0)), None)
                r['fase_id'] = vigente['id'] if vigente else None
                incerta = any(fronteira.get('ultima_compativel_em', float('inf')) <= (r['instante'] or 0)
                    < fronteira.get('primeira_divergente_em', 0)
                    for f in fases for fronteira in f.get('fronteiras_incertas', {}).values())
                r['vigencia_inconclusiva'] = incerta
                r['leitor_versao'] = LEITOR
                preparados.append(r)
            self.guardar(sessao, tipo, preparados)
        return fase

    def inventariar(self, raizes):
        """Cópias com a mesma origem têm uma identidade; modalidade ausente é nula."""
        inventario = {}; erros = []; ignoradas = []
        for raiz in map(pathlib.Path, raizes):
            pastas = set(raiz.glob('hunt_data/*/sessoes/*'))
            pastas.update(raiz.glob('hunt_data/_capture_antigo/session_*'))
            pastas.update(raiz.glob('capture/session_*'))
            for pasta in sorted(pastas):
                resumo = json_de(pasta/'resumo.json') or json_de(pasta/'summary.json')
                if resumo.get('sintetico') or resumo.get('previa') or resumo.get('qa'):
                    ignoradas.append(str(pasta)); continue
                # QA só entra se explicitamente rotulado como real; nomes não
                # substituem origem, mas pastas de testes não são inventariadas.
                ident = identidade(pasta, resumo)
                voltas = resumo.get('voltas')
                if not isinstance(voltas, list):
                    voltas = list(linhas(pasta/'laps.jsonl'))
                if not resumo and not voltas:
                    continue
                from rubinot.hunt.metricas import taxas, especies
                normalizadas = []
                for v in voltas:
                    if not isinstance(v,dict): continue
                    dur = v.get('dur',v.get('dur_s'))
                    if not isinstance(dur,(int,float)): continue
                    # Raw do chat antigo não é raw do painel; preservar sem
                    # conversão por multiplicador presumido. Supplies antigos
                    # também não identificam automaticamente pessoal/party.
                    normalizadas.append({**v,'dur':dur, **({'xp_raw':None,'xp_raw_15min':None} if v.get('xp_origem')!='XP Analyser' else {})})
                registro = {'id': ident, 'versao': VERSAO,
                    'origem': resumo.get('pasta') or pasta.name,
                    'sessao': resumo.get('sessao') if isinstance(resumo.get('sessao'),dict) else {},
                    'taxas': taxas(normalizadas) if normalizadas else None,
                    'especies': especies(normalizadas) if normalizadas else None,
                    'voltas': normalizadas, 'totais_observados': resumo.get('totais'),
                    'painel_final': resumo.get('painel_final'),
                    'cobertura': {'resumo': bool(resumo), 'voltas': len(normalizadas),
                        'voltas_sem_contrato': len(voltas)-len(normalizadas),
                        'eventos': (pasta/'events.jsonl').is_file(),
                        'trilha': (pasta/'trilha.jsonl').is_file(),
                        'configuracao_aplicada': None},
                    'fontes': [str(pasta)], 'regras_versao': resumo.get('regras_versao'),
                    'fechada': resumo.get('fechada'), 'configuracoes': None}
                anterior = inventario.get(ident)
                if anterior:
                    fontes = anterior['fontes'] + registro['fontes']
                    # Usar a cópia mais completa, nunca somar voltas de cópias.
                    def riqueza(r):
                        return (len(r['voltas']), sum(v.get(k) is not None for v in r['voltas']
                            for k in ('xp_raw','xp_raw_15min','profit','sup_pt','sup_eu')), bool(r['sessao']))
                    if riqueza(registro) > riqueza(anterior):
                        inventario[ident] = registro
                    if not inventario[ident]['sessao']:
                        inventario[ident]['sessao'] = registro['sessao'] or anterior['sessao']
                    inventario[ident]['fontes'] = fontes
                else:
                    inventario[ident] = registro
        with self.conexao() as con:
            for ident, r in inventario.items():
                con.execute('INSERT OR REPLACE INTO sessoes VALUES (?,?)', (ident, json.dumps(r, ensure_ascii=False)))
                for fonte in r['fontes']:
                    con.execute('INSERT OR REPLACE INTO fontes VALUES (?,?,?,?)',
                        (fonte, ident, assinatura(r['voltas']), json.dumps(r['cobertura'])))
        return {'versao': VERSAO, 'sessoes': len(inventario),
            'copias': sum(len(r['fontes'])-1 for r in inventario.values()),
            'erros': erros, 'ignoradas': ignoradas, 'inventario': list(inventario.values())}

    def referencias(self, contexto):
        """Dimensões compatíveis sem preencher as desconhecidas."""
        with self.conexao() as con:
            rows=[json.loads(r[0]) for r in con.execute('SELECT dados FROM sessoes')]
        compativeis=[]
        for r in rows:
            s=r['sessao']
            if not contexto.get('char') or not contexto.get('hunt'): continue
            if s.get('char')!=contexto['char'] or s.get('hunt')!=contexto['hunt']: continue
            if contexto.get('pt') and s.get('pt')!=contexto['pt']: continue
            if contexto.get('hazard') is not None and s.get('hazard')!=contexto['hazard']: continue
            if contexto.get('antes') and absoluto(r['origem'],0) and absoluto(r['origem'],0)>=contexto['antes']:continue
            compativeis.append(r)
        return {'estado':'referencia_parcial' if compativeis else 'referencia_propria_em_coleta',
            'sessoes':compativeis,'atribuicao_configuracao':False,
            'limites':['Composição detalhada e configuração aplicada históricas podem ser desconhecidas.']}

    def importar_observacoes(self, raizes):
        contagem=0
        for raiz in map(pathlib.Path,raizes):
            for pasta in raiz.glob('configuracoes_player/*/execucao/session_*/*'):
                sessao=pasta.parent.name
                for arquivo,tipo in (('eventos.jsonl','evento'),('recursos.jsonl','recurso')):
                    rows=[]
                    for r in linhas(pasta/arquivo):
                        if r.get('qa') or r.get('sintetico'):continue
                        r=dict(r);r['instante']=r.get('instante') or absoluto(sessao,r.get('t'))
                        r['fase_id']=None;r['origem_importacao']=str(pasta)
                        if tipo=='recurso':r['id']=r.get('origem') or assinatura([r.get('t'),r.get('vida'),r.get('aliados')])
                        rows.append(r)
                    self.guardar(sessao,tipo,rows);contagem+=len(rows)
        return {'registros_lidos':contagem,'atribuicao_retroativa':False}

    def estudar_voltas(self, sessao, resumo, historico=False):
        """Preserva previsto original; somente observações anteriores treinam o próximo."""
        from rubinot.planejamento.previsao import prever, comparar
        from rubinot.hunt.metricas import taxas, PAUSA_S
        from rubinot.hunt.hazard import area, regras, trecho
        contexto = {k:resumo.get('sessao', {}).get(k) for k in ('char','hunt','pt')}
        area_hazard = area(contexto.get('hunt'))
        recursos_hazard = self.ler(sessao, 'recurso') if area_hazard else []
        contexto['sessao_sem_contexto'] = sessao if not all(contexto.values()) else None
        contexto['atribuicao_configuracao'] = False
        with self.conexao() as con:
            anteriores = [json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='estudo_previsto'")]
        existentes = {r['id']:r for r in anteriores}
        previsoes = {r['id']:r for r in self.ler(sessao, 'previsao_volta')}
        saida = []
        def instante(valor):
            return absoluto(sessao, valor)
        voltas = resumo.get('voltas', [])
        for indice, v in enumerate(voltas):
            if v.get('xp_origem')!='XP Analyser':v={**v,'xp_raw':None,'xp_raw_15min':None}
            dur = v.get('dur', v.get('dur_s'))
            inicio = instante(v.get('ini',v.get('inicio')))
            fim = instante(v.get('fim'))
            if not isinstance(dur,(int,float)) or not 0 < dur < PAUSA_S or v.get('parcial') or v.get('tipo','volta') != 'volta':
                continue
            if inicio is None or fim is None or fim <= inicio:
                continue
            n = v.get('n',v.get('volta',indice+1))
            normal = {**v, 'dur':dur}
            hz = trecho(recursos_hazard,inicio,fim,contexto.get('char') or '') if area_hazard else None
            contexto_volta = {**contexto}
            if hz is not None:
                contexto_volta.update(area_hazard=area_hazard, hazard=hz['nivel'],
                                     hazard_regras=regras(inicio)['versao'],
                                     hazard_sem_contexto=sessao if hz['nivel'] is None else None)
            t = taxas([normal])
            medidas = {'duracao_s':dur, 'raw_h':t['raw_h'], **t['taxa'],
                'dmg_in_input_h':v['dmg_in_painel']*3600/dur if v.get('dmg_in_painel') is not None else None}
            # Dano de console permanece explicitamente parcial, distinto de dano total.
            for campo in ('dmg_out','dmg_in','heal'):
                valor = v.get(campo)
                medidas[campo+'_observado_h'] = valor*3600/dur if isinstance(valor,(int,float)) else None
            for metrica, observado in medidas.items():
                ctx = {**contexto_volta, 'origem_raw':t['raw_de'] if metrica=='raw_h' else None,
                       **({'fonte_xp':'XP Analyser'} if metrica=='raw_h' else {})}
                ident = assinatura([sessao,n,metrica,ctx])
                if ident in existentes:
                    saida.append(existentes[ident]); continue
                treino = [r for r in anteriores if r['contexto']==ctx and r['metrica']==metrica
                          and r.get('fim',float('inf')) <= inicio and r.get('observado') is not None]
                treino.sort(key=lambda r:(r['fim'],r['id']))
                congelada = previsoes.get(ident)
                prospectiva = bool(congelada and congelada['emitida_em'] <= inicio)
                pred = congelada['previsao'] if prospectiva else prever([r['observado'] for r in treino])
                r = {'id':ident, 'instante':fim, 'inicio':inicio, 'fim':fim, 'sessao':sessao,
                     'volta':n, 'metrica':metrica, 'contexto':ctx,
                     'modo':'prospectivo' if prospectiva else 'replay_cronologico',
                     'emitida_em':congelada['emitida_em'] if prospectiva else None,
                     'treino_ids':congelada['treino_ids'] if prospectiva else [a['id'] for a in treino],
                     'prova':resumo.get('fontes',resumo.get('pasta')),
                     'hazard_leitura':hz,
                     **comparar(pred, observado)}
                self.guardar(sessao,'estudo_previsto',[r]); anteriores.append(r); existentes[ident]=r; saida.append(r)
        if not historico and voltas:
            ultima = voltas[-1]; n = ultima.get('n',ultima.get('volta',len(voltas)))
            if isinstance(n,int):
                for metrica in sorted({r['metrica'] for r in saida}):
                    ctx = next(r['contexto'] for r in reversed(saida) if r['metrica']==metrica)
                    treino = sorted([r for r in anteriores if r['contexto']==ctx and r['metrica']==metrica
                                     and r.get('observado') is not None],key=lambda r:(r['fim'],r['id']))
                    agora = time.time()
                    # Também reserva a volta seguinte à próxima: o fechamento
                    # pode ser detectado depois que a próxima já começou.
                    self.guardar(sessao,'previsao_volta',[{'id':assinatura([sessao,alvo,metrica,ctx]),
                        'instante':agora,'emitida_em':agora,'volta':alvo,'horizonte_voltas':alvo-n,
                        'metrica':metrica,'contexto':ctx,
                        'treino_ids':[r['id'] for r in treino], 'previsao':prever([r['observado'] for r in treino])}
                        for alvo in (n+1,n+2)])
        return {'estado':'estudo_descritivo', 'comparacoes':saida,
                'proxima_volta':self.ler(sessao,'previsao_volta'), 'ajuste_rtc_automatico':False}

    def consolidar(self, sessao, resumo=None, politica=None):
        from rubinot.hunt.metricas import taxas, especies, pressao, consumo_itens, variacoes_estoque
        eventos = self.ler(sessao, 'evento'); recursos = self.ler(sessao, 'recurso')
        fases = self.ler(sessao, 'fase'); saude = saude_party(recursos, eventos, politica)
        vs = (resumo or {}).get('voltas') or []
        # Só janelas próximas de dano explícito entram como combate. Silêncio
        # permanece desconhecido; pausas não viram exposição segura.
        import bisect
        danos = sorted(e['t'] for e in eventos if e.get('kind') in ('damage_dealt', 'damage_taken') and e.get('t') is not None)
        recursos_pressao = []
        for q in recursos:
            q = dict(q)
            t = q.get('t')
            if t is not None and q.get('combate') is None:
                i = bisect.bisect_left(danos, t-1)
                q['combate'] = True if i < len(danos) and danos[i] <= t+1 else None
                q['combate_origem'] = 'dano_identificado_proximo_da_leitura'
            recursos_pressao.append(q)
        from rubinot.observacao.telemetria import transicoes_escudo
        politicas = self.ler(sessao, 'politica_pressao')
        politica = politica or (politicas[-1] if politicas else {})
        from rubinot.planejamento.validacao import classificar_pressao
        medidas = {}
        for nome, s in saude.items():
            qs = [q for q in recursos_pressao if q.get('combate') is True]
            observadas = [{**q, 'vida':q.get('vida') if nome=='eu' else q.get('aliados', {}).get(nome)} for q in qs]
            metrica = pressao(observadas)
            cob = metrica['vida_cobertura_s']
            mana = [(q.get('mana') or {}).get('percentual') for q in qs]
            mana = [v for v in mana if v is not None]
            curas = [e for e in eventos if e.get('kind')=='cast' and e.get('magia_id') in
                     ('heal_friend','nature_s_embrace','mass_healing','intense_healing','ultimate_healing','magic_shield')]
            medidas[nome] = {**s, 'cobertura_s':cob, 'minimo_observado':metrica['vida_minima_observada'],
                'mana_minima':min(mana) if mana and nome=='eu' else None,
                'esforco_por_min':len(curas)*60/cob if cob else None,
                'fracao_coberta':cob/metrica['combate_observavel_s'] if metrica['combate_observavel_s'] else None}
        esperados = ['eu', *[p.get('nome') for p in (resumo or {}).get('party', []) if isinstance(p,dict) and p.get('nome')]]
        modalidade = (resumo or {}).get('sessao', {}).get('pt')
        if modalidade not in (1,'x1','solo') and len(esperados)==1:
            esperados.append('integrantes_sem_identidade_confirmada')
        interpretacao = classificar_pressao(medidas, politica, esperados)
        interpretacao['abrangencia'] = 'personagem_e_integrantes_identificados'
        resultado = {'versao': VERSAO, 'sessao': sessao, 'fases': fases,
            'estudo_previsto':self.estudar_voltas(sessao, resumo or {}),
            'voltas_por_fase': vincular_voltas(sessao, vs, fases),
            'contexto':{k:(resumo or {}).get('sessao', {}).get(k) for k in ('char','hunt','pt','objetivo','postura','hazard')},
            'periodo':{'inicio':min((r.get('instante') for r in [*recursos,*eventos] if r.get('instante')),default=None),
                       'fim':max((r.get('instante') or 0 for r in [*recursos,*eventos]),default=0)},
            'taxas': taxas(vs), 'especies': especies(vs), 'saude': saude,
            'pressao': {**pressao(recursos_pressao), **interpretacao,
                        'limites': ['Faixas descritivas não certificam segurança nem pressão de toda a party.']},
            'ativacoes_escudo':transicoes_escudo(recursos),
            'consumo_itens': consumo_itens(self.ler(sessao, 'contador_item')),
            'supplies': {'estoque':variacoes_estoque(self.ler(sessao, 'estoque_item')),
                         'unidade_gasto':'gold','origem_gasto':'paineis_por_volta',
                         'gasto':{grupo:{k:v for k,v in taxas(vs)[grupo].items() if k.startswith('sup')} for grupo in ('media','taxa')},
                         'limite':'Gold não identifica item; estoque é estimativa, contador de uso é consumo.'},
            'observabilidade': {'alvos_atingidos':'por_oportunidade_quando_identificados',
                'orientacao':'por_oportunidade_quando_identificada', 'cooldowns':'catalogo_e_prontidao_visual',
                'pods_hazard':'leitor_nao_implementado','esquivas_hazard':'leitor_nao_implementado',
                'criticos_especiais_hazard':'leitor_nao_implementado',
                'pressao':'depende_de_cobertura_e_politica_validada'},
            'operacional': {'mortes_confirmadas': [e for e in eventos if e.get('kind')=='death'],
                'refis': (resumo or {}).get('refis'), 'trechos': (resumo or {}).get('trechos')},
            'cobertura': {'eventos': len(eventos), 'recursos': len(recursos),
                'fontes': self.ler(sessao, 'cobertura')},
            'estado': 'numeros_persistidos', 'personalizacao': 'avaliacao_posterior_necessaria'}
        estudos_hz = resultado['estudo_previsto']['comparacoes']
        dur_hz = [e for e in estudos_hz if e['metrica']=='duracao_s']
        niveis_hz = {e['contexto'].get('hazard') for e in dur_hz}
        resultado['contexto']['hazard'] = next(iter(niveis_hz)) if len(niveis_hz)==1 else None
        with self.conexao() as con:
            con.execute('INSERT OR REPLACE INTO estados VALUES (?,?)', (sessao, json.dumps(resultado, ensure_ascii=False)))
        fim = max((r.get('instante') or 0 for r in [*recursos,*eventos]),default=0)
        inicio = min((r.get('instante') for r in [*recursos,*eventos] if r.get('instante')),default=0)
        medidas_referencia = self._medidas_resultado(resultado, resultado['contexto'], inicio)
        medidas_referencia['fim'] = fim
        self.guardar(sessao, 'resultado_referencia', [{'id':assinatura([resultado, fim]),
            'instante':fim, 'medidas':medidas_referencia}])
        self.estudar_twin(sessao,(resumo or {}).get('sessao',{}).get('char',''),resumo)
        return resultado

    def estudar_cura(self, sessao, contexto, party, slots):
        from rubinot.planejamento.cura import estudar, identidade
        # Série densa nova complementa os recursos antigos sem substituí-los.
        por_t = {q['t']:q for q in self.ler(sessao, 'recurso') if 't' in q}
        por_t.update({q['t']:q for q in self.ler(sessao, 'recurso_cura') if 't' in q})
        eventos = self.ler(sessao, 'evento')
        # Look explícito resolve vocação; receber sio não identifica EK/RP.
        conhecidos = {p['nome']:p for p in party if p.get('nome')}
        destinos = {e.get('alvo') for e in eventos if e.get('kind')=='cast' and e.get('ator')==contexto.get('char') and e.get('magia_id')=='heal_friend'}
        vocs = {'elite knight':'EK','knight':'EK','royal paladin':'RP','paladin':'RP'}
        for e in eventos:
            nome = e.get('target') or e.get('alvo')
            voc = vocs.get(str(e.get('vocation','')).casefold())
            if e.get('kind')=='player_info' and nome in destinos and voc and not e.get('qa') and not e.get('sintetico'):
                conhecidos[nome] = {'nome':nome,'vocacao':voc,'identidade_confirmada':True,'origem':'look_do_cliente'}
        estudo = estudar(eventos, list(por_t.values()),
                         {**contexto,'sessao':sessao}, list(conhecidos.values()), slots)
        estudo.update(id=identidade(estudo), instante=time.time(),
                      ultima_amostra_em=max((q.get('instante') or 0 for q in por_t.values()),default=0))
        self.guardar(sessao, 'estudo_cura', [estudo])
        return estudo

    def estudar_sio(self, sessao, contexto, party, configuracao=None, recursos_revisados=None):
        """Novos estudos e exemplos são anexados; previsões antigas permanecem."""
        from rubinot.planejamento.sio import estudar
        eventos = self.ler(sessao, 'evento')
        recursos = self.ler(sessao, 'recurso')
        # Revisão tem prova própria; não substitui nem corrige silenciosamente
        # as barras antigas, que continuam disponíveis para auditoria.
        if recursos_revisados is not None:
            self.guardar(sessao, 'recurso_sio_revisado', recursos_revisados)
        revisados = self.ler(sessao, 'recurso_sio_revisado')
        if revisados:
            por_t = {q['t']:q for q in recursos if 't' in q}
            for q in revisados:
                por_t[q['t']] = {**por_t.get(q['t'],{}),**q}
            recursos = sorted(por_t.values(),key=lambda q:q['t'])
        resultado = estudar(eventos, recursos, {**contexto,'sessao':sessao}, party, configuracao)
        instante = max((e.get('instante') or 0 for e in eventos),default=0)
        for membro in resultado['membros']:
            self.guardar(sessao, 'amostra_sio', [{**j,'instante':absoluto(sessao,j['fim']),
                'alvo':membro['nome'],'contexto':resultado['contexto'],'versao':resultado['versao']}
                for j in membro['balanco']['janelas']])
        resultado.update(id=assinatura(resultado), instante=instante)
        self.guardar(sessao, 'estudo_sio', [resultado])
        return resultado

    def validar_execucao(self, sessao, escopo, agora):
        from rubinot.planejamento.validacao import validar_execucao, calibrar_politica
        politicas = self.ler(sessao, 'reserva_avaliacao')
        if not politicas:
            self.guardar(sessao, 'reserva_avaliacao', [{'id':assinatura(escopo), 'instante':agora,
                'escopo':escopo, 'definida_em':agora}])
            return {'estado':'coletando', 'promover':False, 'escopo':escopo}
        reserva = next((p for p in reversed(politicas) if p['escopo']==escopo), None)
        if not reserva:
            self.guardar(sessao, 'reserva_avaliacao', [{'id':assinatura(escopo), 'instante':agora,
                'escopo':escopo, 'definida_em':agora}])
            return {'estado':'coletando', 'promover':False, 'escopo':escopo}
        # Episódios são boxes/fases auditados, não quadros correlacionados nem
        # cópias. A reserva permanece anterior ao teste futuro.
        episodios = self.ler(sessao, 'episodio_auditado')
        anteriores = self.ler(sessao, 'validacao_execucao')
        encerrada = next((r for r in reversed(anteriores) if r.get('escopo')==escopo and r.get('teste_n')), None)
        if encerrada:
            # Resultado final é selado: novos dados não transformam o teste já
            # aberto em seleção de outra hipótese. Nova fase abre outra reserva.
            return encerrada
        anterior = next((r for r in reversed(anteriores) if r.get('promover') and r.get('escopo')==escopo), None)
        avaliacao = validar_execucao(episodios, escopo, reserva['definida_em'], anterior)
        self.guardar(sessao, 'validacao_execucao', [{**avaliacao, 'id':assinatura(avaliacao), 'instante':agora}])
        politica = calibrar_politica(episodios, reserva['definida_em'])
        self.guardar(sessao, 'politica_pressao', [{**politica, 'id':assinatura(politica), 'instante':agora}])
        return avaliacao

    def registrar_recomendacao(self, sessao, recomendacao):
        """Previsão e margem anteriores à adoção, imutáveis."""
        if recomendacao.get('personalizada') and len(recomendacao.get('alteracoes', [])) > 2:
            raise ValueError('Uma recomendação personalizada permite no máximo dois ajustes.')
        import statistics
        contexto = {k:recomendacao.get('contexto', {}).get(k) for k in ('char','hunt','pt','objetivo','postura','hazard')}
        with self.conexao() as con:
            referencias = [json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='resultado_referencia' ORDER BY instante")]
        referencias = [r['medidas'] for r in referencias if r['medidas'].get('contexto')==contexto
            and (r['medidas'].get('fim') or float('inf')) < recomendacao['instante']]
        referencias = list({r['origem_id']:r for r in referencias if r.get('origem_id')}.values())
        medida = 'potions_por_min' if recomendacao.get('objetivo_declarado')=='sustentacao' else 'producao'
        valores = [r['medidas'][medida] for r in referencias if r.get('medidas', {}).get(medida) is not None]
        antes = referencias[-1] if referencias else {}
        politica = recomendacao.get('politica') or {'definida_em':recomendacao['instante'],
            'exposicao_min_s':min((r['exposicao_s'] for r in referencias),default=None),
            'margem_pratica':statistics.stdev(valores) if len(valores)>=2 else None,
            'medida':medida, 'direcao':-1 if medida=='potions_por_min' else 1,
            'origem_margem':'variabilidade_referencias_anteriores'}
        self.guardar(sessao, 'recomendacao', [{**recomendacao,'antes':antes,'referencias_antes':referencias,
            'contexto_comparacao':contexto,'politica':politica}])

    def acompanhar_adocao(self, sessao, observado):
        declaracao = observado.get('declaracao_uso', {})
        sugestao = observado.get('sugestao', {})
        # Uma intenção ou um ID sozinho não comprova adoção. Exigir comparação
        # de todo o pacote e revisões apresentadas na declaração.
        if declaracao.get('resposta') != 'uso_confirmado' or observado.get('concordancia', {}).get('estado') != 'confere':
            return None
        if not all(observado.get('uso_componentes', {}).get(k, {}).get('uso_confirmado') for k in ('rtc','cura','roda')):
            return None
        adocao = {'id':assinatura([sugestao.get('id'),declaracao.get('id')]),
            'instante':declaracao['confirmado_em'], 'recomendacao_id':sugestao.get('id'),
            'declaracao_id':declaracao['id'], 'revisoes':declaracao['revisoes'], 'uso_confirmado':True}
        self.guardar(sessao, 'adocao', [adocao]); return adocao

    def estudar_twin(self, sessao, char, resumo=None):
        """Interpretação derivada e versionada; nenhum registro original é reescrito."""
        from rubinot.planejamento import twin
        with self.conexao() as con:
            contagens=list(con.execute("SELECT tipo,COUNT(*) FROM registros WHERE sessao=? AND tipo IN ('configuracao_leitura','recurso','recurso_cura','fase','evento') GROUP BY tipo",(sessao,)))
        fonte=assinatura([sessao,char,'twin-xp-2',contagens,resumo])
        anteriores=self.ler(sessao,'estudo_twin')
        ultimo=max(anteriores,key=lambda e:e.get('instante',0),default={})
        if ultimo.get('fonte_assinatura')==fonte:
            return ultimo
        leituras=[l for l in self.ler(sessao,'configuracao_leitura') if l.get('char')==char]
        recursos=self.ler(sessao,'recurso')
        fases_uso=self.ler(sessao,'fase')
        vs=[]
        for v in (resumo or {}).get('voltas',[]):
            a=absoluto(sessao,v.get('ini')); b=absoluto(sessao,v.get('fim'))
            fase=next((f for f in reversed(fases_uso) if a is not None and f['instante']<=a),{})
            uso=fase.get('revisoes',{}).get('rtc',{})
            vs.append({'inicio':a,'fim':b,'completa':not v.get('parcial') and v.get('tipo','volta')=='volta',
                'uso_confirmado':uso.get('estado') in ('uso_declarado','aplicado') and
                    a is not None and b is not None and not any(a<f['instante']<b for f in fases_uso),
                'seguranca':v.get('seguranca_twin')})
        periodos=twin.medir(leituras,recursos,vs,self.ler(sessao,'recurso_cura'),
            [e for e in self.ler(sessao,'evento') if e.get('kind')=='death'])
        for p in periodos:
            p['sessao']=sessao
        resultado={'id':assinatura([sessao,periodos,fonte]),'instante':time.time(),
                   'sessao':sessao,'periodos':periodos,'versao':'twin-xp-2','fonte_assinatura':fonte}
        self.guardar(sessao,'estudo_twin',[resultado])
        with self.conexao() as con:
            propostas=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='experimento_twin' ORDER BY instante")]
            previas=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='resultado_twin' ORDER BY instante")]
        for e in propostas:
            if e['contexto'].get('char')!=char:
                continue
            for p in periodos:
                if p['twin']!=e['candidato'] or p['inicio']<=e['instante']:
                    continue
                por_sessao={}
                for a in sorted(previas,key=lambda a:a.get('instante',0)):
                    if a.get('experimento_id')==e['id'] and a.get('resultado',{}).get('contexto')==e['contexto']:
                        por_sessao[a['resultado'].get('sessao')]=a
                anteriores=list(por_sessao.values())
                avaliacao=twin.avaliar(e,p,anteriores)
                self.guardar(sessao,'resultado_twin',[{**avaliacao,'id':assinatura([e['id'],avaliacao,fonte]),
                    'instante':time.time(),'experimento_id':e['id']}])
        return resultado

    def propor_twin(self, sessao, char, candidato, instante):
        from rubinot.planejamento.twin import propor
        with self.conexao() as con:
            estudos=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='estudo_twin' ORDER BY instante DESC")]
            anteriores=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='experimento_twin' ORDER BY instante")]
            resultados=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='resultado_twin' ORDER BY instante")]
        anteriores=[{**e,'estado':next((r['estado'] for r in reversed(resultados) if r.get('experimento_id')==e['id']),e['estado'])} for e in anteriores]
        locais=self.ler(sessao,'estudo_twin')
        contexto_alvo=next((p['contexto'] for estudo in reversed(locais) for p in reversed(estudo['periodos']) if p.get('voltas',0)>=3),None)
        for estudo in estudos:
            for p in reversed(estudo['periodos']):
                if p['contexto'].get('char')!=char or p['contexto']!=contexto_alvo:
                    continue
                vencedor=next((r for r in reversed(resultados) if r['estado']=='validado_posteriormente'
                    and r.get('resultado',{}).get('contexto')==p['contexto']),None)
                if p['twin']!=(vencedor['manter'] if vencedor else 5):
                    continue
                e=propor(p,anteriores,instante,candidato)
                if e:
                    e['id']=assinatura(e)
                    self.guardar(sessao,'experimento_twin',[e])
                    return e
        raise ValueError('Aguardando referência recente, três voltas estáveis, contexto, cobertura e segurança avaliados.')

    def resumo_twin(self, sessao, char, contexto=None):
        """Contrato de apresentação; estudos e treinamento permanecem internos."""
        estudos=self.ler(sessao,'estudo_twin')
        estudo=estudos[-1] if estudos else {}
        with self.conexao() as con:
            fatos=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='twin_retrospectiva' ORDER BY instante")]
            propostas=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='experimento_twin' ORDER BY instante")]
        fatos=[f for f in fatos if f.get('contexto',{}).get('char')==char]
        resultados=self.ler(sessao,'resultado_twin')
        proposta=next((e for e in reversed(propostas) if e.get('contexto',{}).get('char')==char),None)
        ultimo=next((r.get('contexto_twin',{}) for r in reversed(self.ler(sessao,'recurso')) if r.get('contexto_twin')),{})
        ctx={**(contexto or {}),**ultimo}
        from rubinot.planejamento.twin import CONTEXTO
        resultados=[r for r in resultados if all(ctx.get(k)==r.get('resultado',{}).get('contexto',{}).get(k) for k in CONTEXTO)]
        if proposta and (not ctx or any(ctx.get(k)!=proposta['contexto'].get(k) for k in ('char','hunt','pt','hazard'))):
            proposta=None
        if proposta:
            with self.conexao() as con:
                todos=[json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='resultado_twin' AND json_extract(dados,'$.experimento_id')=? ORDER BY instante",(proposta['id'],))]
            resultados=[r for r in todos if all(ctx.get(k)==r.get('resultado',{}).get('contexto',{}).get(k) for k in CONTEXTO)]
            if resultados and resultados[-1]['estado'] in ('pior','inconclusivo','validado_posteriormente'):
                proposta=None
        atual=next((p for p in reversed(estudo.get('periodos',[])) if p.get('twin') is not None),{})
        ctx=ctx or atual.get('contexto',{})
        referencia=5 if any(f.get('referencia_escolhida')==5 and (f.get('sessao')==sessao or
            all(ctx.get(k) is not None and str(ctx[k]).lower().replace('pt ','').replace('x','')==str(f['contexto'].get(k)).lower().replace('pt ','').replace('x','') for k in ('hunt','pt'))) for f in fatos) else None
        if resultados and resultados[-1]['estado']=='validado_posteriormente':
            referencia=resultados[-1]['manter']
        from rubinot.hunt.metricas import taxas_intervalos
        from rubinot.planejamento.twin import elegivel
        historico=[{'sessao':f['sessao'],'twin':f['twin'],'inicio':f['inicio'],'fim':f['fim'],
            'taxas':taxas_intervalos([f]),'ressalvas':f['ressalvas'],'origem':'analise_retrospectiva'} for f in fatos]
        agrupado=taxas_intervalos([f for f in fatos if f['twin']==5]) if fatos else None
        return {'referencia':referencia,'candidatos':[n for n in (4,6) if n!=referencia],'estado':resultados[-1]['estado'] if resultados else proposta['estado'] if proposta else 'aguardando referência recente',
            'periodo':{k:atual.get(k) for k in ('inicio','fim_observado','tempo_s','voltas','cobertura','uso_confirmado')},
            'proposta':{k:proposta.get(k) for k in ('id','candidato','instante','motivo')} if proposta else None,
            'resultado':{k:resultados[-1].get(k) for k in ('estado','ganho_raw_h','intervalo','manter')} if resultados else None,
            'historico':historico,'agrupado_5':agrupado,
            'pode_propor':bool(referencia in (4,5,6) and atual.get('twin')==referencia and elegivel(atual)),
            'limite':'Raw XP/h do personagem como indicador da hunt em PT. Configuração visível não comprova uso automático.'}

    def avaliar_resultado_posterior(self, sessao, resultado):
        """Fecha ligação sugestão→adoção→hunt; mantém inconclusivos e negativos."""
        with self.conexao() as con:
            recomendacoes = [json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='recomendacao'")]
        avaliacoes = []
        for adocao in self.ler(sessao, 'adocao'):
            rec = next((r for r in recomendacoes if r['id']==adocao['recomendacao_id']), None)
            if not rec: continue
            depois = self._medidas_resultado(resultado, resultado.get('contexto'), adocao['instante'])
            fases = resultado.get('fases', [])
            depois['vigencia_estavel'] = bool(fases) and all(
                f.get('revisoes', {}).get('rtc', {}).get('declaracao_id') == adocao.get('declaracao_id')
                for f in fases) and (resultado.get('periodo', {}).get('inicio') or 0) >= adocao['instante']
            self.guardar(sessao, 'resultado_adotado', [{'id':assinatura([rec['id'],depois]),
                'instante':depois.get('fim'), 'recomendacao_id':rec['id'],'medidas':depois}])
            with self.conexao() as con:
                posteriores = [json.loads(r[0])['medidas'] for r in con.execute(
                    "SELECT dados FROM registros WHERE tipo='resultado_adotado' AND json_extract(dados,'$.recomendacao_id')=?",(rec['id'],))]
            from rubinot.planejamento.efetividade import contraste_temporal
            contraste = contraste_temporal(rec.get('referencias_antes', []),posteriores,
                rec.get('politica', {}).get('medida'),rec.get('politica', {}).get('direcao',1))
            depois.update(contraste)
            antes = rec.get('antes', {})
            if contraste.get('estado')=='contraste_observado':
                medida = rec['politica']['medida']
                antes = {**antes,'medidas':{**antes.get('medidas', {}),medida:contraste['media_antes']}}
                depois['medidas'][medida] = contraste['media_depois']
                if any(p.get('seguranca')!='avaliada_sem_piora' for p in posteriores): depois['seguranca']='inconclusiva'
            avaliacao = self.registrar_efetividade(sessao, {**rec,'adocao':adocao},
                antes, depois, rec.get('politica', {}))
            avaliacoes.append(avaliacao)
        return avaliacoes

    @staticmethod
    def _medidas_resultado(resultado, contexto, inicio):
        recursos = resultado.get('pressao', {})
        # Só avaliação por integrante com política e cobertura certificadas.
        membros = recursos.get('por_membro', {})
        seguro = bool(membros) and all(not m.get('limites') and m['estado'] in
            ('tranquila','pressionada_mas_controlada') for m in membros.values())
        if resultado.get('operacional', {}).get('mortes_confirmadas'): seguro = False
        contadores = [c for c in resultado.get('consumo_itens', []) if 'mana' in c['item']]
        limites = {(c['inicio'],c['fim']) for c in contadores}
        taxa_potions = sum(c['quantidade'] for c in contadores)*60/contadores[0]['duracao_s'] if len(limites)==1 else None
        return {'contexto':contexto, 'inicio':inicio, 'origem_id':resultado.get('sessao'),
            'fim':resultado.get('periodo', {}).get('fim'),
            'exposicao_s':recursos.get('combate_observavel_s',0),
            'medidas':{'producao':(resultado.get('taxas') or {}).get('raw_h'),
                'potions_por_min':taxa_potions},
            'seguranca':'avaliada_sem_piora' if seguro else 'inconclusiva',
            'intervalo_ganho':None, 'origem_incerteza':'contraste_posterior_em_coleta'}

    def perfis_efetividade(self, contexto):
        with self.conexao() as con:
            rows = [json.loads(r[0]) for r in con.execute("SELECT dados FROM registros WHERE tipo='efetividade' ORDER BY instante,id")]
        return [r for r in rows if r['antes'].get('contexto') == contexto
                and r['avaliacao'].get('estado') != 'inconclusivo']

    def registrar_efetividade(self, sessao, recomendacao, antes, depois, politica):
        from rubinot.planejamento.efetividade import avaliar_ajuste
        resultado = avaliar_ajuste(recomendacao, antes, depois, politica)
        registro = {'id': assinatura([recomendacao, antes, depois, politica, resultado]),
                    'instante': time.time(), 'recomendacao': recomendacao,
                    'antes': antes, 'depois': depois, 'politica': politica, 'avaliacao': resultado}
        self.guardar(sessao, 'efetividade', [registro])
        return resultado

