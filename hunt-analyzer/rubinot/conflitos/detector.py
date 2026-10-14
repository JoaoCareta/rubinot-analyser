"""KS pelo dano nomeado no Server Log; provas sobrevivem à limpeza de quadros.

python ks.py capture/session_X --replay
O dano é o OBSERVADO no console, nunca uma estimativa do total real.
"""
import argparse
import collections
import copy
import datetime as dt
import functools
import hashlib
import json
import os
import pathlib
import re
import statistics
import time
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import atlas_build as ab
import events_build as ev
import layout
import lap_watch as lw
import painel_stream

AQUI = pathlib.Path(__file__).resolve().parents[2]
RAIZ = pathlib.Path(os.environ.get('HUNT_KS_RAIZ') or AQUI / 'KS')
SILENCIO_S = None  # confirmação após o tempo de duas voltas da hunt


def nome_key(nome):
    """Espaços podem desaparecer entre glifos no cabeçalho estreito do painel."""
    return re.sub(r'\s+', '', nome).casefold()


def escreve(p, dados):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(p)


def dano_periodo(ep):
    """Uma conta para a tela e o relatório: início até o último golpe de fora observado."""
    if 'golpes_observados' not in ep:
        return ep['dano']
    saida = {'party': {}, 'fora': {}}
    for e in ep['golpes_observados']:
        if e['t'] <= ep['ultimo_t']:
            Detector.soma(saida[e['grupo']], e)
    return saida


def declaracao_party(sessao):
    """Correção explícita do usuário, restrita à gravação; nunca inferida de sio."""
    try:
        dados = json.loads((AQUI / 'ui' / 'party_correcoes.json').read_text(encoding='utf-8'))
        d = dados.get(sessao, {})
        return d if d.get('origem') == 'usuario' and isinstance(d.get('aliados'), list) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def corrigir_relatorio(r, declaracao=None):
    """Reclassifica uma cópia e conserva episódios invalidados para auditoria."""
    d = declaracao_party(r.get('sessao', '')) if declaracao is None else declaracao
    if not d or d.get('origem') != 'usuario' or not d.get('aliados'):
        return r
    nomes = [n for n in d['aliados'] if isinstance(n, str) and n.strip()]
    if not nomes:
        return r
    saida = copy.deepcopy(r)
    releitura = d.get('relatorio_releitura', {})
    if releitura.get('origem') == 'releitura_paineis_e_console' and releitura.get('provas'):
        for campo in ('party_paineis', 'dano_hunt_observado'):
            if campo in releitura:
                saida[campo] = copy.deepcopy(releitura[campo])
    detector = Detector.__new__(Detector)
    detector.party = saida.get('party') or []
    detector.dano_hunt = saida.setdefault('dano_hunt_observado', {'party': {}, 'fora': {}})
    detector.golpes = [e for ep in saida.get('episodios', []) for e in ep.get('golpes_observados', [])]
    detector.eventos = []
    detector.episodios = saida.get('episodios') or []
    detector.atual = None
    originais = copy.deepcopy(detector.episodios)
    detector.confirma_party(nomes, 0)
    saida['party'] = detector.party
    saida['episodios'] = detector.episodios
    ids = {ep['id'] for ep in detector.episodios}
    auditoria = saida.setdefault('episodios_reclassificados', [])
    conhecidos = {ep['id'] for ep in auditoria}
    auditoria.extend(dict(ep, motivo_reclassificacao='aliado_confirmado_pelo_usuario')
                     for ep in originais if ep['id'] not in ids and ep['id'] not in conhecidos)
    saida['correcao_party'] = d
    for ep in d.get('episodios_recuperados', []):
        if (ep.get('origem') != 'releitura_server_log' or
                not ep.get('prova_inicio', {}).get('sha256_log_original') or
                not ep.get('dano', {}).get('fora')):
            continue
        if any(nome_key(n) in {nome_key(p) for p in saida['party']} for n in ep['dano']['fora']):
            continue
        golpes = {e.get('id') for e in ep.get('golpes_observados', [])}
        if any(e['id'] == ep['id'] or
               any(g.get('id') in golpes for g in e.get('golpes_observados', [])) or
               (e['inicio'] <= ep['inicio'] <= (e.get('fim') or e.get('ultimo_evento', {}).get('ts') or e['inicio']) and
                set(e['dano']['fora']) & set(ep['dano']['fora'])) for e in saida['episodios']):
            continue
        saida['episodios'].append(copy.deepcopy(ep))
    ocultos = set(d.get('episodios_baixo_impacto', []))
    saida['episodios_ocultos'] = [e for e in saida['episodios'] if e['id'] in ocultos]
    saida['episodios'] = [e for e in saida['episodios'] if e['id'] not in ocultos]
    saida['episodios'].sort(key=lambda e: e['inicio'])
    saida['estatisticas_party'] = estatisticas_party([saida])
    return saida


def painel_party(relatorios):
    """Acumulado visível: inclui o que aconteceu antes de abrir o analisador.

    Uma redução de dano/supplies confirma reset. Quadros/gravações sobrepostos
    substituem a mesma leitura acumulada; nunca somam duas vezes o mesmo painel.
    """
    quadros = {}
    for r in relatorios:
        ps = r.get('party_paineis')
        if ps is None:  # sessões antigas ainda guardam os dois limites do painel
            ps = [r.get('party_painel_primeiro'), r.get('party_painel_ultimo')]
        tem_party = any(p and not p.get('solo') and p.get('danos') for p in ps)
        for p in ps:
            # O painel vazio ao sair da PT não substitui o acumulado da hunt em grupo.
            if p and tem_party and p.get('solo'):
                continue
            if p and (p.get('danos') or not p.get('solo')):
                quadros[(r.get('sessao', '')[8:16], p['t'], p.get('frame', ''))] = p
    segmentos, atual, anterior, ultimos_danos = [], {}, None, {}
    for _, p in sorted(quadros.items()):
        comuns = set((anterior or {}).get('danos', {})) & set(p.get('danos', {}))
        reset = anterior and (any(v < ultimos_danos[nome_key(n)] for n, v in p.get('danos', {}).items()
                                 if v is not None and nome_key(n) in ultimos_danos)
                              or (not comuns and p.get('tipo') == anterior.get('tipo')
                                  and p.get('supplies') is not None and anterior.get('supplies') is not None
                                  and p['supplies'] < anterior['supplies']))
        if reset:
            segmentos.append(atual)
            atual = {}
            ultimos_danos = {}
        for n, v in p.get('danos', {}).items():
            if v is not None:
                ultimos_danos[nome_key(n)] = v
            jogadores = atual.setdefault('jogadores', {})
            identidade = next((nome for nome in jogadores if nome_key(nome) == nome_key(n)), n)
            jogador = jogadores.setdefault(identidade, {})
            for campo, valor in {'dano': v, 'profit': (p.get('profits') or {}).get(n),
                                 'cura': (p.get('curas') or {}).get(n)}.items():
                if valor is not None:
                    jogador[campo] = valor
                else:
                    jogador.setdefault(campo, None)
        if p.get('fonte_dano'):
            atual['fonte_dano'] = p['fonte_dano']
        elif not p.get('solo'):
            atual['fonte_dano'] = 'Party Hunt'
        for k in ('loot', 'supplies', 'profit', 'tipo', 't'):
            if p.get(k) is not None:
                atual[k] = p[k]
        anterior = p
    if atual:
        segmentos.append(atual)
    pessoas = {}
    for seg in segmentos:
        for n, v in seg.get('jogadores', {}).items():
            dest = pessoas.setdefault(nome_key(n), dict(nome=n, dano=0, profit=0, cura=0))
            for k in ('dano', 'profit', 'cura'):
                dest[k] = dest[k] + v[k] if dest[k] is not None and v[k] is not None else None
    fontes = {s['fonte_dano'] for s in segmentos if s.get('fonte_dano')}
    return {'jogadores': pessoas, 'resets': max(0, len(segmentos)-1),
            'fonte_dano': ' / '.join(sorted(fontes)) if fontes else 'Party Hunt',
            **{k: sum(s[k] for s in segmentos) if segmentos and all(k in s for s in segmentos) else None
               for k in ('loot', 'supplies', 'profit')},
            'tipo': segmentos[-1].get('tipo') if segmentos else None,
            'painel_t': segmentos[-1].get('t') if segmentos else None}


def estatisticas_party(relatorios):
    """A mesma soma alimenta a sessão ao vivo e gravações reunidas no histórico.

    Contagens são linhas de dano por alvo, não lançamentos de magia. Métricas
    que o relatório antigo não mediu ficam nulas, inclusive ao reunir sessões.
    """
    pessoas = {}
    extras = ('fatais', 'dano_critico', 'dano_fatal', 'maior_golpe')
    for r in relatorios:
        for nome, p in (r.get('dano_hunt_observado', {}).get('party') or {}).items():
            chave = nome_key(nome)
            dest = pessoas.setdefault(chave, dict(nome=nome, dano=0, golpes=0, criticos=0,
                                                 **{k: 0 for k in extras}))
            for k in ('dano', 'golpes', 'criticos'):
                dest[k] += p.get(k, 0)
            for k in extras:
                if dest[k] is None or p.get(k) is None:
                    dest[k] = None
                elif k == 'maior_golpe':
                    dest[k] = max(dest[k], p[k])
                else:
                    dest[k] += p[k]
    painel = painel_party(relatorios)
    for chave, p in painel['jogadores'].items():
        pessoas.setdefault(chave, dict(nome=p['nome'], golpes=None, criticos=None,
                                       **{k: None for k in extras}))
    for chave, p in pessoas.items():
        p['dano_observado'] = p.get('dano')
        p.update({k: painel['jogadores'].get(chave, {}).get(k) for k in ('dano', 'profit', 'cura')})
    valores = [p['dano'] for p in pessoas.values()]
    total = sum(valores) if valores and all(v is not None for v in valores) else None
    for p in pessoas.values():
        p['participacao'] = p['dano'] / total * 100 if total and p['dano'] is not None else None
        p['criticos_pct'] = p['criticos'] / p['golpes'] * 100 if p['golpes'] else None
        p['fatais_pct'] = p['fatais'] / p['golpes'] * 100 if p['golpes'] and p['fatais'] is not None else None
    return {'jogadores': sorted(pessoas.values(), key=lambda p: -(p['dano'] or 0)),
            'total': total, 'fonte_dano': painel['fonte_dano'],
            **{k: painel[k] for k in ('loot', 'supplies', 'profit', 'tipo', 'painel_t', 'resets')}}


class Leitor:
    """Mesmo atlas, lookup por bytes. Não adivinha glifos desconhecidos."""
    def __init__(self):
        glyphs, self.gap = ab.load_atlas()
        self.idx = {}
        for key, ch in glyphs.items():
            top, w, rows = json.loads(key)
            arr = np.array([[(r >> (w - 1 - x)) & 1 for x in range(w)] for r in rows], dtype=bool)
            self.idx[(top, arr.shape, arr.tobytes())] = ch

    @functools.lru_cache(maxsize=12000)
    def banda(self, shape, dados):
        b = np.frombuffer(dados, dtype=bool).reshape(shape)
        cols = b.any(axis=0)
        edges = np.diff(np.r_[False, cols, False].astype(int))
        starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
        out, prev = [], None
        for x0, x1 in zip(starts, ends):
            g = b[:, x0:x1]
            ys = np.flatnonzero(g.any(axis=1))
            tight = g[ys[0]:ys[-1] + 1]
            if prev is not None and x0 - prev >= self.gap:
                out.append(' ')
            out.append(self.idx.get((int(ys[0]), tight.shape, tight.tobytes()), '�'))
            prev = x1
        return ''.join(out)

    def linhas(self, img):
        b = ab.binarize_arr(np.asarray(img.convert('RGB')))
        return [(self.banda(b[a:z].shape, b[a:z].tobytes()), a, z)
                for a, z in ab.find_bands(b) if 6 <= z - a <= 15]

    def mensagens(self, p):
        with Image.open(p) as img:
            linhas = self.linhas(img)
        msgs = []
        for linha, a, z in linhas:
            linha = ev.TRAIL_JUNK.sub('', linha)
            m = ev.TS.match(linha)
            if m:
                msgs.append({'ts': m[1], 'body': m[2], 'y0': a, 'y1': z})
            elif msgs:
                msgs[-1]['body'] += ' ' + linha
                msgs[-1]['y1'] = z
        return [m for m in msgs if '�' not in m['body']]

    def party(self, p, lay, char):
        with Image.open(p) as img:
            im = painel_stream.recortar_painel(img, p.parent, 'party', lay['party']['box'], lay['party']['scroll_x'])
            if im is None:
                return None
            linhas = [s for s, _, _ in self.linhas(im)]
            # O atlas por forma tolera diferenças de alinhamento da fonte nos painéis.
            formas = painel_stream.linhas(im)
            pessoal, _ = painel_stream.ler_quadro(img, p.parent, lay['hunt']['box'], lay['hunt']['scroll_x'])
            xp = painel_stream.ler_xp(img, p.parent)
        nomes, danos, profits, curas = [], {}, {}, {}
        totais, _ = painel_stream.ler(im)
        # Nome seguido das três linhas numéricas (balance, dano, cura).
        for i, s in enumerate(linhas[:-3]):
            nome = s.strip(' �')
            seguintes = linhas[i + 1:i + 4]
            if re.fullmatch(r"[A-Za-z][A-Za-z '\-]{2,59}", nome) and all(
                    re.fullmatch(r'[� +\-]*[\d,]+k?[� ]*', x) for x in seguintes):
                nomes.append(nome)
                for destino, valor in zip((profits, danos, curas), seguintes):
                    # Apenas ícones nas pontas saem; um dígito desconhecido invalida a leitura.
                    valor = valor.strip('� +')
                    destino[nome] = painel_stream.numero(valor)
        # Se algum bloco numérico perdeu o nome, não aceitar uma party parcial.
        blocos = sum(1 for i in range(len(linhas) - 2)
                     if all(re.fullmatch(r'[� +\-]*[\d,]+k?[� ]*', x) for x in linhas[i:i + 3]))
        valido = any(nome_key(n) == nome_key(char or '') for n in nomes) and len(nomes) >= 2 and len(nomes) == blocos
        if not valido and formas != linhas:
            nomes, danos, profits, curas = self.blocos_party(formas)
            blocos = sum(1 for i in range(len(formas) - 2)
                         if all(re.fullmatch(r'[?� +\-]*[\d,?]+k?[?� ]*', x) for x in formas[i:i + 3]))
            valido = any(nome_key(n) == nome_key(char or '') for n in nomes) and len(nomes) >= 2 and len(nomes) == blocos
        solo = not nomes and all(totais.get(k) == 0 for k in ('Loot', 'Supplies', 'Balance'))
        # Um quarto nome cortado não transforma três membros em uma PT completa.
        # A soma de balances confere a cobertura, sem exigir igualdade de cura pessoal/PT.
        from rubinot.observacao.paineis import membros_party
        blocos_visiveis = membros_party(formas)
        parcial = (not solo and (not valido or any(not m['completo'] for m in blocos_visiveis)
                   or len(blocos_visiveis) != len(nomes) or any(v is None for v in profits.values())
                   or totais.get('Balance') != sum(v for v in profits.values() if v is not None)))
        if parcial:
            return None
        return {'nomes': nomes if valido else [char],
                'danos': danos if valido else {char: pessoal.get('Damage')},
                'profits': profits if valido else {char: pessoal.get('Balance')},
                'curas': curas if valido else {char: pessoal.get('Healing')},
                'fonte_dano': 'Party Hunt' if valido else 'Hunt Analyser',
                'loot': pessoal.get('Loot') if solo else totais.get('Loot'),
                'supplies': pessoal.get('Supplies') if solo else totais.get('Supplies'),
                'profit': pessoal.get('Balance') if solo else totais.get('Balance'),
                'tipo': None if solo else totais.get('LootType'),
                'xp_raw': xp.get('RawXPGain'), 'fonte_xp': 'XP Analyser',
                'loot_periodo': pessoal.get('Loot') if solo else totais.get('Loot'),
                'fonte_loot': 'Hunt Analyser' if solo else 'Party Hunt',
                'tempo_sessao_s': painel_stream.tempo_sessao(formas), 'tempo_sessao_origem': 'Party Hunt',
                'solo': solo, 'frame': p.name, 't': lw.fsec(p.name)} if valido or (solo and char) else None

    @staticmethod
    def blocos_party(linhas):
        nomes, danos, profits, curas = [], {}, {}, {}
        for i, s in enumerate(linhas[:-3]):
            nome = s.strip(' ?�')
            seguintes = linhas[i + 1:i + 4]
            if re.fullmatch(r"[A-Za-z][A-Za-z '\-]{2,59}", nome) and all(
                    re.fullmatch(r'[?� +\-]*[\d,?]+k?[?� ]*', x) for x in seguintes):
                nomes.append(nome)
                for destino, valor in zip((profits, danos, curas), seguintes):
                    # Ícone separado por espaço é descartável; '?' colado ao número
                    # pode ser um dígito perdido e continua invalidando a medida.
                    valor = re.sub(r'^[?�]+\s+', '', valor.strip())
                    destino[nome] = painel_stream.numero(valor.lstrip('+ '))
        return nomes, danos, profits, curas


class Detector:
    def __init__(self, sessao, char=None, silencio=SILENCIO_S):
        self.sessao = pathlib.Path(sessao)
        self.lay = layout.da_sessao(self.sessao)
        log = self.sessao / 'capture.log'
        titulo = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        m = re.search(r"RubinOT Client - ([^']+)'", titulo)
        self.char = char or (m[1].strip() if m else None)
        self.data = dt.datetime.strptime(self.sessao.name[8:16], '%Y%m%d').date()
        self.silencio = silencio
        self.leitor = Leitor()
        self.monstros = {json.loads(p.read_text(encoding='utf-8')).get('nome', '').casefold()
                        for p in (AQUI / 'monstros').glob('*/*.json')}
        self.monstros |= {s.strip().casefold() for s in (AQUI / 'monstros_nomes.txt').read_text(encoding='utf-8').splitlines()}
        self._pasta = None
        self.vistos, self.prev, self.ultimo_ts = set(), [], ''
        self.party, self.candidata, self.party_t = None, None, -1
        self.episodios, self.atual = [], None
        self.eventos = []
        self.golpes = []
        self._reescrever_ledger = False
        self._ledger_iniciado = False
        self.ultimo_quadro, self.lacunas = None, []
        self.contagem = collections.Counter()
        self.dano_hunt = {'party': {}, 'fora': {}}
        self.paineis, self.magias, self.prev_spells = [], [], []
        self.cache_quadros = []
        cache = self.sessao / 'ks_quadros.jsonl'
        self.cache = {}
        if cache.exists():
            for linha in cache.read_text(encoding='utf-8').splitlines():
                try:
                    d = json.loads(linha)
                    self.cache[d['frame']] = d['mensagens']
                except (ValueError, KeyError):
                    continue

    @property
    def pasta(self):
        if self._pasta is None:
            hunt = 'hunt_nao_identificada'
            for p in (AQUI / 'hunt_data').glob('*/sessoes/*/resumo.json'):
                try:
                    r = json.loads(p.read_text(encoding='utf-8'))
                    if r.get('pasta') == self.sessao.name:
                        hunt = r['sessao']['hunt']
                        break
                except (ValueError, KeyError):
                    continue
            slug = re.sub(r'[^a-z0-9]+', '_', unicodedata.normalize('NFKD', hunt).encode('ascii', 'ignore').decode().lower()).strip('_')
            pasta = RAIZ / ('session_' + self.data.strftime('%Y_%m_%d') + '_' + slug)
            if hunt != 'hunt_nao_identificada':
                self._pasta = pasta
            return pasta
        return self._pasta

    @property
    def logs(self):
        return self.pasta / 'logs'

    @property
    def relatorio_path(self):
        return self.logs / (self.sessao.name + '_relatorio.json')

    @property
    def dano_path(self):
        return self.logs / (self.sessao.name + '_dano.jsonl')

    def dano_painel(self, ep):
        inicio = ep.get('painel_inicio')
        fim = min(self.paineis, key=lambda p: abs(p['t'] - ep['ultimo_t']), default=None)
        if not inicio or not fim or abs(fim['t'] - ep['ultimo_t']) > 5:
            return {'individual': {}, 'total': None, 'motivo': 'Painel ausente na fronteira do KS'}
        valores = {}
        for nome in ep['party']:
            a, b = inicio['danos'].get(nome), fim['danos'].get(nome)
            # Reset, jogador não lido ou valor ausente = lacuna.
            valores[nome] = b - a if a is not None and b is not None and b >= a else None
        return {'individual': valores, 'total': sum(valores.values()) if all(v is not None for v in valores.values()) else None,
                'inicio': inicio, 'fim': fim, 'limite': 'Delta do Party Hunt entre quadros de 4 s; fronteiras aproximadas, não separa alvos.'}

    def ganhos_painel(self, ep):
        """Ganhos pessoais de raw e loot da party/solo entre fronteiras próximas do KS."""
        vazio = {'xp_raw': None, 'loot': None, 'limite': 'Sem leitura dos painéis nas fronteiras do KS.'}
        if not self.paineis:
            return vazio
        ini = lw.to_s(ep['inicio'])
        a = min(self.paineis, key=lambda p: abs(p['t']-ini))
        b = min(self.paineis, key=lambda p: abs(p['t']-ep['ultimo_t']))
        if abs(a['t']-ini) > 5 or abs(b['t']-ep['ultimo_t']) > 5 or b['t'] <= a['t']:
            return vazio
        ps = sorted((p for p in self.paineis if a['t'] <= p['t'] <= b['t']),key=lambda p:p['t'])
        def delta(chave):
            vals = [p[chave] for p in ps if p.get(chave) is not None]
            if a.get(chave) is None or b.get(chave) is None or any(y < x for x,y in zip(vals,vals[1:])):
                return None
            return b[chave]-a[chave]
        bases = {(p.get('fonte_loot'),p.get('tipo') if p.get('fonte_loot') == 'Party Hunt' else None) for p in ps}
        xp_valida = all(p.get('fonte_xp') == 'XP Analyser' for p in (a, b))
        return {'xp_raw': delta('xp_raw') if xp_valida else None, 'loot': delta('loot_periodo') if len(bases)==1 else None,
                'inicio_t':a['t'],'fim_t':b['t'],'fonte_loot':b.get('fonte_loot'),
                'limite':'Raw XP do personagem e loot do painel entre quadros próximos (até 5 s de cada fronteira). Não mede os ganhos da outra party.'}

    def silencio_da_hunt(self, t):
        if self.silencio is not None:
            return self.silencio
        p = self.sessao / 'laps.jsonl'
        duracoes = []
        if p.exists():
            for linha in p.read_text(encoding='utf-8').splitlines():
                try:
                    v = json.loads(linha)
                    fim = lw.to_s(v['fim'])
                    dur = v.get('dur_s') or (fim - lw.to_s(v['inicio']))
                    if fim <= t and 0 < dur < 360 and v.get('fechada_por') not in ('sessao parou', 'gravacao parou'):
                        duracoes.append(dur)
                except (ValueError, KeyError, TypeError):
                    continue
        return round(statistics.mean(duracoes[-5:]) * 2) if duracoes else None

    def instante(self, ts):
        # carimbo() do capture usa horas 24+ no dia seguinte.
        h, m, s = map(int, ts.split(':'))
        return dt.datetime.combine(self.data, dt.time()) + dt.timedelta(hours=h, minutes=m, seconds=s)

    def prova(self, evento, tipo, episodio):
        base = ('ultimo' if tipo == 'ultimo' else self.instante(evento['ts']).strftime(tipo + '_%Y_%m_%d_%H_%M'))
        pasta = self.logs
        if tipo == 'ultimo':
            base = self.sessao.name + '_' + episodio['id'] + '_ultimo'
        elif episodio['id'] != '001':
            base += '_' + episodio['id']
        pasta.mkdir(parents=True, exist_ok=True)
        src = self.sessao / evento['frame']
        original = pasta / (base + '_log_original.png')
        original.write_bytes(src.read_bytes())
        with Image.open(src) as img:
            im = img.convert('RGB')
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, evento['y0'] - 1, im.width - 1, evento['y1'] + 1), outline='#ff5555', width=1)
        detalhe = im.resize((im.width * 2, im.height * 2), Image.Resampling.NEAREST)
        log_destino = pasta / (base + '_log_destacado.png')
        detalhe.save(log_destino)
        destino = (pasta if tipo == 'ultimo' else self.pasta) / (base + '.png')
        # O quadro inteiro é contexto; só o recorte c_ prova a linha exata.
        fs = sorted(self.sessao.glob('f_*.png'))
        perto = min(fs, key=lambda p: abs(lw.fsec(p.name) - evento['capturado_t']), default=None)
        exato = self.sessao / ('q_' + evento['frame'][2:])
        sincronizado = False
        if exato.exists():
            # A comparação também protege contra layout incorreto ou arquivo trocado.
            r = self.lay['chat']
            with Image.open(exato) as full, Image.open(src) as chat:
                corte = full.crop((r['left'], r['top'], r['left'] + r['width'], r['top'] + r['height']))
                sincronizado = corte.convert('RGB').tobytes() == chat.convert('RGB').tobytes()
            if sincronizado:
                perto = exato
        contexto = None
        if perto and abs(lw.fsec(perto.name) - evento['capturado_t']) <= 5:
            contexto = pasta / (base + '_tela.png')
            contexto.write_bytes(perto.read_bytes())
        # Nunca colar a linha antiga dentro do console do quadro seguinte.
        # A janela inteira permanece intacta; o recorte exato é um anexo separado.
        with Image.open(contexto or original) as img:
            tela = img.convert('RGB')
        largura = max(tela.width, detalhe.width + 32)
        saida = Image.new('RGB', (largura, tela.height + detalhe.height + 100), '#11141b')
        saida.paste(tela, (0, 0))
        try:
            fonte = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
        except OSError:
            fonte = ImageFont.load_default()
        d = ImageDraw.Draw(saida)
        delta = lw.fsec(perto.name) - evento['capturado_t'] if contexto else None
        hora_tela = ':'.join(perto.stem[i:i + 2] for i in (2, 4, 6)) if contexto else None
        legenda = (f'Tela inteira: {hora_tela} | diferença para a captura do log: {delta:+g} s'
                   if contexto else 'Tela inteira indisponível neste evento; somente o recorte foi preservado.')
        d.text((16, tela.height + 12), legenda, font=fonte, fill='#e5be67')
        d.text((16, tela.height + 42), f'Evidência separada — Server Log às {evento["ts"]} (linha destacada)', font=fonte, fill='#eeeeee')
        saida.paste(detalhe, (16, tela.height + 76))
        if sincronizado:
            saida = tela.copy()
            r = self.lay['chat']
            ImageDraw.Draw(saida).rectangle(
                (r['left'], r['top'] + evento['y0'] - 1,
                 r['left'] + r['width'] - 1, r['top'] + evento['y1'] + 1),
                outline='#ff5555', width=2)
        saida.save(destino)
        prova = {'print': destino.relative_to(RAIZ).as_posix(),
                 'log_destacado': log_destino.relative_to(RAIZ).as_posix(),
                 'original': original.relative_to(RAIZ).as_posix(),
                 'tela': contexto.relative_to(RAIZ).as_posix() if contexto else None,
                 'evento': evento, 'party': list(self.party or []),
                 'sha256_log_original': hashlib.sha256(original.read_bytes()).hexdigest(),
                 'sha256_tela_original': hashlib.sha256(contexto.read_bytes()).hexdigest() if contexto else None,
                 'sincronizado': sincronizado,
                 'formato': 'tela_inteira_log_destacado' if sincronizado else ('tela_inteira_com_log_separado' if contexto else 'somente_log'),
                 'quadro_contexto': perto.name if contexto else None,
                 'defasagem_contexto_s': lw.fsec(perto.name) - evento['capturado_t'] if contexto else None}
        escreve(pasta / (base + '.json'), prova)
        return prova

    @staticmethod
    def soma(grupo, e):
        pessoa = grupo.setdefault(e['actor'], {'dano': 0, 'golpes': 0, 'criticos': 0,
                                             'fatais': 0, 'dano_critico': 0, 'dano_fatal': 0,
                                             'maior_golpe': 0, 'alvos': {}})
        pessoa['dano'] += e['value']
        pessoa['golpes'] += 1
        pessoa['criticos'] += bool(e.get('crit'))
        fatal = e.get('fatal') or e.get('tag', '').casefold() == 'onslaught' or bool(
            re.search(r'\(Onslaught\)', e.get('body', ''), re.I))
        pessoa['fatais'] += bool(fatal)
        pessoa['dano_critico'] += e['value'] if e.get('crit') else 0
        pessoa['dano_fatal'] += e['value'] if fatal else 0
        pessoa['maior_golpe'] = max(pessoa['maior_golpe'], e['value'])
        pessoa['alvos'][e['target']] = pessoa['alvos'].get(e['target'], 0) + e['value']

    def fecha(self, t, encerrar=False):
        if self.atual:
            self.atual['silencio_s'] = self.silencio_da_hunt(t)
        if self.atual and (encerrar or (self.atual['silencio_s'] and t - max(self.atual['ultimo_t'], self.atual.get('silencio_desde', 0)) >= self.atual['silencio_s'])):
            ep = self.atual
            ep['fim'] = ep['ultimo_evento']['ts']
            ep['confirmado_t'] = t
            ep['motivo_fim'] = 'gravacao_encerrada' if encerrar else 'silencio_observado'
            ep['aberto'] = False
            # Usa a cópia permanente da última linha, mesmo se o c_ já foi limpo.
            candidato = ep.get('prova_ultimo') or {}
            base = self.instante(ep['fim']).strftime('fim_%Y_%m_%d_%H_%M')
            if ep['id'] != '001':
                base += '_' + ep['id']
            prova = dict(candidato)
            if not candidato:
                prova['limite'] = 'Quadro da última linha indisponível após a conversão de aliado; não exibir a prova de outro instante.'
            for chave, sufixo in (('print', '.png'), ('original', '_log_original.png'), ('tela', '_tela.png'), ('log_destacado', '_log_destacado.png')):
                if candidato.get(chave):
                    dst = (self.pasta if chave == 'print' else self.logs) / (base + sufixo)
                    dst.write_bytes((RAIZ / candidato[chave]).read_bytes())
                    prova[chave] = dst.relative_to(RAIZ).as_posix()
            ep['prova_fim'] = prova
            escreve(self.logs / (base + '.json'), prova)
            ep['dano'] = dano_periodo(ep)
            ep.pop('golpes_observados', None)
            ep['dano_party_painel'] = self.dano_painel(ep)
            ep['ganhos'] = self.ganhos_painel(ep)
            ep['magias_observadas'] = self.magias_periodo(ep)
            self.atual = None

    def evento(self, e, roster):
        if e['kind'] not in ('damage_dealt', 'damage_dealt_player') or e.get('target', '').casefold() not in self.monstros:
            return
        if not roster:
            self.contagem['dano_sem_party_confirmada'] += 1
            return
        # Proc aparece DEPOIS do nome e antes do ponto: não faz parte do jogador.
        ator = self.char if e['kind'] == 'damage_dealt' else re.sub(r' \([^()]+\)$', '', e['actor'])
        e = dict(e, actor=ator)
        grupo = 'party' if nome_key(e['actor']) in {nome_key(n) for n in roster} else 'fora'
        self.soma(self.dano_hunt[grupo], e)
        self.golpes.append(dict(e, grupo=grupo))
        if grupo == 'fora' and self.atual is None:
            self.atual = {'id': str(len(self.episodios) + 1).zfill(3), 'inicio': e['ts'], 'aberto': True,
                          'party': list(roster), 'dano': {'party': {}, 'fora': {}},
                          'ultimo_t': e['t'], 'ultimo_evento': e, 'fim': None, 'golpes_observados': []}
            self.atual['painel_inicio'] = next((p for p in reversed(self.paineis) if p['t'] <= e['t'] and e['t'] - p['t'] <= 5), None)
            self.episodios.append(self.atual)
            self.atual['prova_inicio'] = self.prova(e, 'inicio', self.atual)
        if self.atual:
            self.soma(self.atual['dano'][grupo], e)
            self.atual['golpes_observados'].append(dict(e, grupo=grupo))
            if grupo == 'fora':
                self.atual.update(ultimo_t=e['t'], ultimo_evento=e)
                # Guarda IMEDIATAMENTE a última prova candidata: pode desaparecer antes do timeout.
                self.atual['prova_ultimo'] = self.prova(e, 'ultimo', self.atual)
        self.eventos.append(dict(e, grupo=grupo))

    def confirma_party(self, nomes, t):
        """Pedido do usuário: quem entra torna-se aliado na hunt inteira."""
        novos = {nome_key(n) for n in nomes} - {nome_key(n) for n in self.party or []}
        self.party, self.party_t = sorted(set(self.party or []) | set(nomes)), t
        if not novos:
            return
        for nome in list(self.dano_hunt['fora']):
            if nome_key(nome) in novos:
                p = self.dano_hunt['fora'].pop(nome)
                dest = self.dano_hunt['party'].get(nome)
                if dest is None:
                    self.dano_hunt['party'][nome] = dict(p, alvos=dict(p['alvos']))
                else:
                    for k in ('dano','golpes','criticos','fatais','dano_critico','dano_fatal'):
                        dest[k] += p[k]
                    dest['maior_golpe'] = max(dest['maior_golpe'], p['maior_golpe'])
                    for alvo, dano in p['alvos'].items():
                        dest['alvos'][alvo] = dest['alvos'].get(alvo, 0) + dano
        for e in self.golpes + self.eventos:
            if nome_key(e['actor']) in novos:
                e['grupo'] = 'party'
        self._reescrever_ledger = True
        mantidos = []
        for ep in self.episodios:
            golpes = [dict(e, grupo='party' if nome_key(e['actor']) in novos else e['grupo'])
                      for e in ep.get('golpes_observados', [])]
            if not golpes:
                # Episódio fechado: o ledger integral permite recompor o período.
                golpes = [e for e in self.golpes if lw.to_s(ep['inicio']) <= e['t'] <= ep['ultimo_t']]
            if not golpes:
                # Relatórios antigos podem ter somente totais: não apagar um intruso
                # real porque suas linhas individuais já não estão no relatório.
                for nome in list(ep['dano']['fora']):
                    if nome_key(nome) in novos:
                        ep['dano']['party'][nome] = ep['dano']['fora'].pop(nome)
                if ep['dano']['fora']:
                    ep['party'] = list(self.party)
                    mantidos.append(ep)
                    continue
            fora = [e for e in golpes if e['grupo'] == 'fora']
            if not fora:
                if self.atual is ep:
                    self.atual = None
                continue
            primeiro, ultimo = fora[0], fora[-1]
            if primeiro['ts'] != ep['inicio']:
                ep.pop('prova_inicio', None)
            if ultimo['t'] != ep['ultimo_t']:
                for k in ('prova_fim', 'prova_ultimo'):
                    ep.pop(k, None)
            ep.update(inicio=primeiro['ts'], ultimo_t=ultimo['t'], ultimo_evento=ultimo,
                      party=list(self.party), golpes_observados=[e for e in golpes if e['t'] >= primeiro['t']])
            if not ep['aberto']:
                ep['fim'] = ultimo['ts']
            ep['dano'] = dano_periodo(ep)
            mantidos.append(ep)
        self.episodios = mantidos

    def processa(self, p):
        t = lw.fsec(p.name)
        if p.name.startswith('f_'):
            painel = self.leitor.party(p, self.lay, self.char)
            nomes = painel['nomes'] if painel else None
            if painel:
                self.paineis.append(painel)
            if nomes and nomes == self.candidata:
                # O Party Hunt é acumulado e também guarda quem saiu. Nunca transformar um
                # aliado já comprovado em adversário porque uma linha ficou ilegível/resetou.
                self.confirma_party(nomes, t)
            self.candidata = nomes
            return
        if p.name.startswith('s_'):
            cur = self.leitor.mensagens(p)
            pares = [(m['ts'], m['body']) for m in cur]
            tail = ev.new_tail(self.prev_spells, pares)
            for m in cur[len(cur) - len(tail):] if tail else []:
                kind, dados = ev.classify(m['body'])
                if kind == 'speech' and dados.get('text', '').startswith(lw.SPELL_PREFIXES):
                    self.magias.append(dict(dados, t=lw.to_s(m['ts']), ts=m['ts'], frame=p.name))
            self.prev_spells = pares
            return
        if self.ultimo_quadro is not None and t - self.ultimo_quadro > 3:
            self.lacunas.append([self.ultimo_quadro, t])
            # Ausência de captura NÃO prova que o adversário parou.
            if self.atual:
                self.atual['lacuna_observacao'] = True
                self.atual['silencio_desde'] = t
        self.ultimo_quadro = t
        cur = self.cache.get(p.name)
        if cur is None:
            cur = self.leitor.mensagens(p)
            self.cache_quadros.append({'frame': p.name, 'mensagens': cur})
        if not cur or (self.ultimo_ts and all(m['ts'] < self.ultimo_ts for m in cur)):
            return  # console vazio/rolado não zera o overlap nem prova silêncio
        pares = [(m['ts'], m['body']) for m in cur]
        tail = ev.new_tail(self.prev, pares)
        roster = self.party if t - self.party_t <= 60 else None
        if self.atual and not roster:
            self.atual['lacuna_party'] = True
            self.atual['silencio_desde'] = t  # party ilegível não confirma ausência de adversário
        for m in cur[len(cur) - len(tail):] if tail else []:
            if self.ultimo_ts and m['ts'] < self.ultimo_ts:
                continue
            kind, dados = ev.classify(m['body'])
            self.contagem[kind] += 1
            e = dict(m, **dados, kind=kind, t=lw.to_s(m['ts']), frame=p.name, capturado_t=t)
            if self.atual and roster:
                self.fecha(e['t'])
            self.evento(e, roster)
            self.ultimo_ts = max(self.ultimo_ts, m['ts'])
        self.prev = pares
        if self.atual and cur and roster:
            self.fecha(min(t, lw.to_s(cur[-1]['ts'])))

    def magias_periodo(self, ep):
        saida = {}
        for m in self.magias:
            if lw.to_s(ep['inicio']) <= m['t'] <= ep['ultimo_t']:
                pessoa = saida.setdefault(m['actor'], {})
                pessoa[m['text']] = pessoa.get(m['text'], 0) + 1
        return saida

    def salva(self):
        if self.atual:
            self.atual['dano'] = dano_periodo(self.atual)
            self.atual['ganhos'] = self.ganhos_painel(self.atual)
        r = {'sessao': self.sessao.name, 'char': self.char, 'party': self.party,
             'silencio_s': self.silencio, 'episodios': self.episodios,
             'regra_fim': 'Término no horário do último dano adversário e sua prova. Episódio consolidado após duas voltas sem dano observado ou ao encerrar a gravação.',
             'regra_party': 'Nomes confirmados em dois quadros do Party Hunt. Aliados já confirmados são preservados durante a sessão; a saída da party não é inferida de uma linha ausente.',
             'dano_hunt_observado': self.dano_hunt, 'contagem': dict(self.contagem),
             'party_paineis': self.paineis,
             'lacunas_captura': self.lacunas,
             'spells_capturado': bool(self.lay.get('spell')), 'magias_hunt_observadas': self.magias,
             'party_painel_primeiro': self.paineis[0] if self.paineis else None,
             'party_painel_ultimo': self.paineis[-1] if self.paineis else None,
             'limite': 'Dano observado nas linhas legíveis do Server Log. Console curto perde golpes; não é dano total. Ausência de linha não prova ausência de dano. Guild não é identificada.'}
        r['estatisticas_party'] = estatisticas_party([r])
        r = corrigir_relatorio(r)
        escreve(self.relatorio_path, r)
        escreve(self.sessao / 'ks.json', r)
        if self.eventos or self._reescrever_ledger:
            self.logs.mkdir(parents=True, exist_ok=True)
            with self.dano_path.open('a' if self._ledger_iniciado and not self._reescrever_ledger else 'w', encoding='utf-8') as f:
                f.writelines(json.dumps(e, ensure_ascii=False) + '\n' for e in
                             (self.golpes if self._reescrever_ledger else self.eventos))
            self._ledger_iniciado = True
            self._reescrever_ledger = False
        self.eventos.clear()
        if self.cache_quadros:
            with (self.sessao / 'ks_quadros.jsonl').open('a', encoding='utf-8') as f:
                f.writelines(json.dumps(e, ensure_ascii=False) + '\n' for e in self.cache_quadros)
            self.cache_quadros.clear()
        return r

    def atualiza(self, completo=False):
        fs = sorted(self.sessao.glob('f_*.png'))
        cs = sorted(self.sessao.glob('c_*.png'))
        ss = sorted(self.sessao.glob('s_*.png'))
        fila = sorted((p for p in fs + cs + ss if p.name not in self.vistos), key=lambda p: (lw.fsec(p.name), p.name[0] != 'f', p.name))
        # Ordem só por segundo mantém o f_ como referência antes das linhas daquele segundo.
        if not completo and fila:
            limite = max(lw.fsec(p.name) for p in fila) - 1
            fila = [p for p in fila if lw.fsec(p.name) <= limite]
        for i, p in enumerate(fila):
            try:
                self.processa(p)
            except OSError:
                if completo:
                    raise
                break
            self.vistos.add(p.name)
            if i % 500 == 499:
                self.salva()
                print(f'{i + 1}/{len(fila)} quadros; {len(self.episodios)} KS', flush=True)
        return self.salva()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sessao')
    parser.add_argument('char', nargs='?')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--silencio', type=int, default=SILENCIO_S)
    args = parser.parse_args()
    if args.silencio is not None and args.silencio < 1:
        parser.error('silêncio precisa ser positivo')
    detector = Detector(args.sessao, args.char, args.silencio)
    # Releitura determinística: ledger não duplica em replay/reinício do processo.
    if args.replay:
        r = detector.atualiza(completo=True)
        print(json.dumps({k: r[k] for k in ('party', 'contagem', 'dano_hunt_observado')}, ensure_ascii=False), flush=True)
        return
    while True:
        if (detector.sessao / 'ks_encerrar').exists():
            detector.atualiza(completo=True)
            if detector.atual:
                detector.fecha(detector.atual['ultimo_t'], encerrar=True)
                detector.salva()
            (detector.sessao / 'ks_encerrar').unlink(missing_ok=True)
            break
        detector.atualiza()
        time.sleep(2)


if __name__ == '__main__':
    main()
