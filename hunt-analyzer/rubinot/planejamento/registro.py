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

VERSAO = 'hunt-aprendizado-1'
LEITOR = 'observacao-3'


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
    return dt.datetime.strptime(m[1], '%Y%m%d').timestamp() + segundos


def identidade(pasta, resumo=None):
    r = resumo or {}; s = r.get('sessao') or {}
    origem = r.get('pasta') or (s if isinstance(s,str) else pasta.name)
    m = re.search(r'(\d{8})_(\d{4,6})(?:_[a-f0-9]{8})?', origem)
    # Histórico antigo pode não conhecer o segundo da abertura: nunca colapsar
    # duas capturas reais do mesmo minuto quando a origem completa está presente.
    return assinatura(['sessao', m[0] if m else origem])


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
        for tipo in ('rtc', 'cura', 'roda'):
            s = observado.get(tipo) or {}
            # Configuração antiga não migra para outra sessão. Aplicação exige
            # evidência específica; confirmar uma sugestão não confirma o editor.
            valida = s.get('sessao') == sessao and s.get('instante', float('inf')) <= instante
            revisoes[tipo] = {'revisao': s.get('id') if valida else None,
                'estado': 'aplicado' if valida and s.get('aplicado_confirmado') else
                    'observado_sem_aplicacao' if valida else 'desconhecido',
                'completo': bool(valida and s.get('completo'))}
        regras = observado.get('regras_versao')
        chave = assinatura([char, revisoes, regras])
        fases = self.ler(sessao, 'fase')
        if fases and fases[-1]['chave'] == chave:
            return fases[-1]
        fase = {'id': assinatura([sessao, chave, instante]), 'chave': chave,
            'instante': instante, 'char': char, 'revisoes': revisoes,
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
                    normalizadas.append({**v,'dur':dur})
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
                    if len(registro['voltas']) > len(anterior['voltas']):
                        inventario[ident] = registro
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

    def consolidar(self, sessao, resumo=None, politica=None):
        from rubinot.hunt.metricas import taxas, especies
        eventos = self.ler(sessao, 'evento'); recursos = self.ler(sessao, 'recurso')
        fases = self.ler(sessao, 'fase'); saude = saude_party(recursos, eventos, politica)
        vs = (resumo or {}).get('voltas') or []
        resultado = {'versao': VERSAO, 'sessao': sessao, 'fases': fases,
            'taxas': taxas(vs), 'especies': especies(vs), 'saude': saude,
            'operacional': {'mortes_confirmadas': [e for e in eventos if e.get('kind')=='death'],
                'refis': (resumo or {}).get('refis'), 'trechos': (resumo or {}).get('trechos')},
            'cobertura': {'eventos': len(eventos), 'recursos': len(recursos),
                'fontes': self.ler(sessao, 'cobertura')},
            'estado': 'numeros_persistidos', 'personalizacao': 'avaliacao_posterior_necessaria'}
        with self.conexao() as con:
            con.execute('INSERT OR REPLACE INTO estados VALUES (?,?)', (sessao, json.dumps(resultado, ensure_ascii=False)))
        return resultado

