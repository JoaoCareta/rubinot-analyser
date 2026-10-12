"""Aprendizado supervisionado de cadência RTC, com validação temporal.

Regressão quantílica regularizada, sem dependências além do NumPy. Só treina
intervalos entre lançamentos próprios identificados: console sem leitura não
vira zero e dano parcial não vira potência/quantidade de alvos. Os dados
compactos sobrevivem à limpeza de quadros e ficam separados por personagem.
"""
import collections
import datetime
import hashlib
import math
import bisect
import json

import numpy as np

import configuracoes as c
import contexto_execucao as cx

VERSAO = 'rtc-ml-1'
COMBATE_VERSAO = 'rtc-roda-ml-1'
QUANTIL = .2


def exemplos(char, sessao, eventos, magias, rtc, intervalos):
    if not rtc.get('instante') or rtc.get('char') != char or rtc.get('sessao') != sessao:
        return []
    dt = datetime.datetime.fromtimestamp(rtc['instante'])
    desde = dt.hour*3600+dt.minute*60+dt.second+dt.microsecond/1e6
    por_id = {m['id']: m for m in magias}
    slots = {s['id']: s for s in rtc.get('slots', []) if s.get('id')}
    unicos = {(e['t'], e['magia_id']): e for e in eventos
              if e.get('t', -1) >= desde and e.get('kind') == 'cast'
              and e.get('qualidade') == 'identificada' and e.get('ator') == char
              and e.get('magia_id') in slots and por_id.get(e.get('magia_id'), {}).get('tipo') == 'ofensiva'}
    por_magia = collections.defaultdict(list)
    for t, ident in sorted(unicos):
        por_magia[ident].append(t)
    fase = c.assinatura([cx.chave_rtc(rtc), rtc.get('roda_efeitos')])
    saida = []
    for ident, ts in por_magia.items():
        m, slot = por_id[ident], slots[ident]
        for a, b in zip(ts, ts[1:]):
            gap = b-a
            if not m['grupo'] <= gap <= max(12, m['cd']*2):
                continue
            if not any(ini <= a <= b <= fim for ini, fim in intervalos):
                continue
            chave = f'{sessao}:{fase}:{ident}:{a}:{b}'
            saida.append({'id': chave, 'sessao': sessao, 'fase': fase, 'magia_id': ident,
                          'instante': rtc['instante'] + b-desde, 'gap': gap,
                          'cd': m['cd'], 'grupo': m['grupo'],
                          'slot': slot['slot'], 'prioridade': slot.get('prioridade') or 1,
                          'creatures': slot.get('creatures') or 1})
    return saida


def treinar(dados, atuais, rtc):
    escopo = {'char': rtc.get('char'), 'sessao': rtc.get('sessao'), 'preset': rtc.get('preset'), 'rtc_chave': cx.chave_rtc(rtc)}
    if rtc.get('roda_efeitos') is not None:
        escopo['roda_efeitos'] = rtc['roda_efeitos']
    base = {'versao': VERSAO, 'algoritmo': 'regressao_quantilica_regularizada', 'quantil': QUANTIL,
            'escopo': escopo, 'amostras': len(dados), 'intervalos_efetivos': {}, 'validacao': {},
            'estado': 'coletando', 'cobertura_completa': False}
    if len(atuais) < 50:
        return base
    atuais = sorted(atuais, key=lambda d: (d['instante'], d['id']))
    corte = atuais[-max(10, math.ceil(len(atuais)*.2))]['instante']
    treino = [d for d in dados if d['instante'] < corte]
    teste = [d for d in atuais if d['instante'] >= corte]
    if len(treino) < 30:
        return base
    ids = sorted({d['magia_id'] for d in treino})
    colunas = ['bias', 'cd', 'grupo', 'slot', 'prioridade', 'creatures'] + ['magia:'+ident for ident in ids]

    def features(d):
        return [1, d['cd']/40, d['grupo']/4, d['slot']/5, d['prioridade']/5, d['creatures']/8] + [float(d['magia_id'] == ident) for ident in ids]

    x = np.asarray([features(d) for d in treino], dtype=float)
    # Aprende diferença para o catálogo, sem editar a regra normativa.
    y = np.asarray([d['gap']-d['cd'] for d in treino], dtype=float)
    pesos = np.zeros(len(colunas), dtype=float)
    for epoca in range(1200):
        residuo = y-x@pesos
        gradiente = -(x.T@(QUANTIL-(residuo < 0)))/len(y) + .002*pesos
        pesos -= (.15/(1+epoca/600))*gradiente
    perda = lambda erro: float(np.mean(np.maximum(QUANTIL*erro, (QUANTIL-1)*erro)))
    base.update({'estado': 'validado_sem_melhoria', 'colunas': colunas, 'coeficientes': pesos.tolist(),
                 'treino': len(treino), 'teste': len(teste), 'treino_ate': max(d['instante'] for d in treino),
                 'teste_desde': min(d['instante'] for d in teste),
                 'perda_treino': perda(y-x@pesos)})
    por_id = collections.defaultdict(list)
    for d in teste:
        por_id[d['magia_id']].append(d)
    for ident, validacao in por_id.items():
        referentes = [d for d in treino if d['magia_id'] == ident and d['fase'] == atuais[-1]['fase'] and d['sessao'] == rtc.get('sessao')]
        if len(referentes) < 25 or len(validacao) < 8:
            continue
        d = validacao[-1]
        candidato = int(round(d['cd']+float(np.asarray(features(d))@pesos)))
        candidato = max(d['grupo'], candidato)
        gaps = np.asarray([v['gap'] for v in validacao], dtype=float)
        antes, depois = perda(gaps-d['cd']), perda(gaps-candidato)
        suporte = int(np.count_nonzero(gaps >= candidato-1))
        aceita = candidato < d['cd'] and suporte >= math.ceil(len(gaps)*.8) and depois < antes*.9
        base['validacao'][ident] = {'candidato_s': candidato, 'treino_fase': len(referentes), 'teste': len(gaps),
                                   'perda_antes': antes, 'perda_depois': depois, 'suporte': suporte, 'aceita': aceita}
        if aceita:
            base['intervalos_efetivos'][ident] = {'segundos': candidato, 'base_catalogo': d['cd'],
                                                'treino': len(referentes), 'validacao': len(gaps), 'suporte_validacao': suporte,
                                                'origem': VERSAO, 'precisao_s': 1, 'erro_antes': antes, 'erro_depois': depois}
    if base['intervalos_efetivos']:
        base['estado'] = 'aprendizado_validado'
    return base


def atualizar(pasta, char, sessao, eventos, magias, rtc, intervalos):
    atuais = exemplos(char, sessao, eventos, magias, rtc, intervalos)
    caminho = pasta/'rtc_ml_dados.json'
    arquivo = c._json(caminho)
    anteriores = arquivo.get('amostras', []) if arquivo.get('char') == char and arquivo.get('versao') == VERSAO else []
    unicos = {d['id']: d for d in [*anteriores, *atuais]}
    dados = sorted(unicos.values(), key=lambda d: (d['instante'], d['id']))[-5000:]
    c._grava(caminho, {'versao': VERSAO, 'char': char, 'amostras': dados})
    return treinar(dados, atuais, rtc)


def referencia_roda(roda, catalogo):
    """Semente factual: fatias ausentes ficam desconhecidas, nunca zeradas.

    Assinatura por efeitos ofensivos permite aproveitar observações da mesma
    build entre leituras, sem atribuir o preset novo a eventos antigos.
    """
    campos = roda.get('campos', {})
    ranks, revelation = {}, {}
    for grupo, destino in (('conviction', ranks), ('revelation', revelation)):
        for ident, perk in catalogo.get(grupo, {}).items():
            if not isinstance(perk, dict):
                continue
            for nome in perk.get('Name', '').split('|'):
                campo = campos.get(grupo+'.'+nome, {})
                if campo.get('qualidade') != 'texto_integral':
                    continue
                texto = str(campo.get('valor', '')).strip()
                n = {'I': 1, 'II': 2, 'III': 3, 'Locked': 0}.get(texto)
                if grupo == 'revelation' and texto in ('Stage 1', 'Stage 2', 'Stage 3'):
                    n = int(texto[-1])
                if n is not None:
                    destino[str(ident)] = n
    fatias = {k[7:]: v['valor'] for k, v in campos.items() if k.startswith('fatias.')}
    gemas = {k[6:]: v['valor'] for k, v in campos.items() if k.startswith('gemas.')}
    fatos = {'ranks': ranks, 'revelation': revelation, 'gemas': gemas}
    return {'id': roda.get('id'), 'char': roda.get('char'), 'preset': roda.get('preset'), 'instante': roda.get('instante'),
            'prova': roda.get('prova'), 'completo': roda.get('completo', False),
            'total': campos.get('pontos.total', {}).get('valor'), 'fatias': fatias,
            **fatos, 'chave': c.assinatura(fatos)}


def estado_magia(m, roda):
    ident = m['id']
    rank = roda['ranks'].get({'strong_ice_wave': '31', 'terra_wave': '30',
                             'forked_glacier': '29', 'forked_thorns': '29',
                             'energy_wave': '25', 'great_fire_wave': '24'}.get(ident))
    # Sem efeito necessário lido, não normalizar dano sob uma build presumida.
    if ident in ('strong_ice_wave', 'terra_wave', 'forked_glacier', 'forked_thorns') and rank is None:
        return None
    twin = roda['revelation'].get('10') if m.get('familia') == 'bursts' else 0
    if twin is None or m.get('familia') == 'bursts' and twin == 0:
        return None
    area = bool(ident == 'strong_ice_wave' and rank >= 2 or ident == 'energy_wave' and rank)
    adicional = bool(ident.startswith('forked_') and rank >= 2)
    fator = 1 + (.06 if ident == 'strong_ice_wave' and rank else
                 .065 if ident == 'terra_wave' and rank else .10 if ident == 'energy_wave' and rank == 2 else 0)
    return {'chave': f'{ident}|area:{int(area)}|extra:{int(adicional)}|twin:{twin}',
            'area_ampliada': area, 'alvo_adicional': adicional, 'twin_estagio': twin,
            'multiplicador_base': fator}


def exemplos_combate(char, sessao, eventos, magias, rtcs, rodas, amostras, intervalos, catalogo, monstros):
    """Aprende rendimento associado parcial; não conta espécies como instâncias.

    Só associa um ataque explícito sem concorrente no segundo atual/anterior.
    Crítico, fatal, prey e lacuna de leitura não entram como dano base ou zero.
    """
    rtcs = sorted([s for s in rtcs if s.get('char') == char and s.get('sessao') == sessao], key=lambda s: s['instante'])
    rodas = sorted([s for s in rodas if s.get('char') == char and s.get('sessao') == sessao], key=lambda s: s['instante'])
    if not rtcs or not rodas:
        return []
    por_id = {m['id']: m for m in magias}
    unicos = {e.get('id', str(i)): e for i, e in enumerate(eventos)}
    casts = sorted({(e['t'], e['magia_id']): e for e in unicos.values()
                    if e.get('kind') == 'cast' and e.get('qualidade') == 'identificada'
                    and e.get('ator') == char and por_id.get(e.get('magia_id'), {}).get('tipo') == 'ofensiva'}.values(), key=lambda e: e['t'])
    por_t = collections.defaultdict(list)
    for e in casts:
        por_t[e['t']].append(e)
    danos = collections.defaultdict(list)
    for e in unicos.values():
        if e.get('kind') != 'damage_dealt' or e.get('ator') != char:
            continue
        if e.get('crit') or e.get('fatal') or e.get('tag') or e.get('value', 0) <= 0:
            continue
        perto = por_t[e['t']]+por_t[e['t']-1]
        if len(perto) == 1:
            danos[(perto[0]['t'], perto[0]['magia_id'])].append(e)
    def segundos(s):
        dt = datetime.datetime.fromtimestamp(s['instante'])
        try:
            dia = datetime.datetime.strptime(sessao.split('_')[1], '%Y%m%d').date()
        except (ValueError, IndexError):
            dia = dt.date()
        return (dt.date()-dia).days*86400+dt.hour*3600+dt.minute*60+dt.second+dt.microsecond/1e6
    # Snapshots da mesma sessão usam o mesmo relógio dos eventos e da trilha.
    rtc_ts, roda_ts = [segundos(s) for s in rtcs], [segundos(s) for s in rodas]
    amostras = sorted([a for a in amostras if isinstance(a.get('t'), (float, int))], key=lambda a: a['t'])
    amostra_ts = [a['t'] for a in amostras]
    saida = []
    for cast in casts:
        t, ident = cast['t'], cast['magia_id']
        ir, iw, iq = bisect.bisect_right(rtc_ts, t)-1, bisect.bisect_right(roda_ts, t)-1, bisect.bisect_right(amostra_ts, t)-1
        if min(ir, iw, iq) < 0 or not any(a <= t and t+1 < b for a, b in intervalos):
            continue
        rtc, ref, a = rtcs[ir], referencia_roda(rodas[iw], catalogo), amostras[iq]
        if not any(s.get('id') == ident and s.get('atual') is not False for s in rtc.get('slots', [])):
            continue
        n = a.get('battle', a.get('criaturas'))
        if t-a['t'] > 4 or not isinstance(n, int) or n < 1:
            continue
        m, ds = por_id[ident], danos[(t, ident)]
        estado = estado_magia(m, ref)
        if not ds or not estado or not m.get('bp'):
            continue
        equivalentes = []
        for d in ds:
            resistencia = monstros.get(str(d.get('target', d.get('alvo', ''))).casefold(), {}).get('toma', {}).get(m.get('elemento'))
            if not isinstance(resistencia, (int, float)) or resistencia <= 0:
                continue
            equivalentes.append(d['value']/(resistencia/100))
        if not equivalentes:
            continue
        rendimento = sum(equivalentes)/(m['bp']*estado['multiplicador_base'])
        chave = c.assinatura([sessao, t, ident, cx.chave_rtc(rtc), ref['chave'], catalogo['versao']])
        saida.append({'id': chave, 'char': char, 'sessao': sessao, 't': t,
                      'instante': rtc['instante']+t-rtc_ts[ir], 'magia_id': ident,
                      'rtc_chave': cx.chave_rtc(rtc), 'roda_chave': ref['chave'], 'roda_preset': ref['preset'],
                      'regras_versao': catalogo['versao'], 'estado_magia': estado['chave'],
                      'criaturas': n, 'rendimento': rendimento, 'dano_associado': sum(d['value'] for d in ds),
                      'cobertura_completa': False, 'origem': 'cast_e_dano_associado_parcial'})
    return saida


def treinar_combate(dados, referencia, regras):
    """Ridge em log do rendimento por cast, validada no trecho posterior.

    Cada geometria/Twin tem perfil próprio: uma roda única não identifica o
    ganho causal de trocar estágio. O simulador fornece as regras normativas.
    """
    dados = sorted([d for d in dados if d['regras_versao'] == regras], key=lambda d: (d['instante'], d['id']))
    saida = {'versao': COMBATE_VERSAO, 'algoritmo': 'ridge_log_rendimento_por_estado',
             'regras_versao': regras, 'char': referencia.get('char'), 'referencia_inicial': referencia, 'perfis': {},
             'amostras': len(dados), 'cobertura_completa': False, 'estado': 'coletando',
             'uso': ['rtc', 'roda'], 'estagios_nao_observados': 'regras_e_intervalo_sem_ganho_aprendido'}
    por_estado = collections.defaultdict(list)
    for d in dados:
        por_estado[d['estado_magia']].append(d)
    escala = float(np.median([d['rendimento'] for d in dados])) if dados else 1
    saida['escala_comum'] = escala
    for estado, rows in por_estado.items():
        if len(rows) < 40:
            continue
        corte = len(rows)-max(8, math.ceil(len(rows)*.2))
        treino, teste = rows[:corte], rows[corte:]
        # Não separar dois exemplos com o mesmo instante entre treino e teste.
        treino = [d for d in treino if d['instante'] < teste[0]['instante']]
        if len(treino) < 30:
            continue
        x = np.asarray([[1, math.log1p(d['criaturas'])] for d in treino])
        y = np.log([d['rendimento'] for d in treino])
        regularizacao = np.diag([.05, 8.0])
        coef = np.linalg.solve(x.T@x+regularizacao, x.T@y)
        # População maior não pode aprender um ganho negativo por truncamento.
        coef[1] = max(0, min(1, coef[1]))
        coef[0] = float(np.sum(y-coef[1]*x[:, 1])/(len(y)+regularizacao[0, 0]))
        base = float(np.median(y))
        erros = [abs(math.log(d['rendimento'])-(coef[0]+coef[1]*math.log1p(d['criaturas']))) for d in teste]
        antes = float(np.mean([abs(math.log(d['rendimento'])-math.log(escala)) for d in teste]))
        depois = float(np.mean(erros))
        # Sem melhoria fora do treino, o modelo permanece coletando esse perfil.
        aceita = depois < antes*.95 or abs(base-math.log(escala)) < .05 and depois <= antes+.01
        if not aceita:
            continue
        saida['perfis'][estado] = {'magia_id': rows[-1]['magia_id'], 'coeficientes': coef.tolist(),
                                   'escala_comum': escala, 'treino': len(treino), 'validacao': len(teste),
                                   'treino_ate': treino[-1]['instante'], 'teste_desde': teste[0]['instante'],
                                   'erro_antes': antes, 'erro_depois': depois,
                                   'incerteza_log': float(np.quantile(erros, .8)),
                                   'criaturas_min': min(d['criaturas'] for d in treino),
                                   'criaturas_max': max(d['criaturas'] for d in treino),
                                   'cobertura_completa': False, 'roda_chaves': sorted({d['roda_chave'] for d in rows}),
                                   'sessao': rows[-1]['sessao']}
    if saida['perfis']:
        saida['estado'] = 'aprendizado_validado_parcial'
    return saida


def atualizar_combate(pasta, char, sessao, eventos, magias, amostras, intervalos, catalogo, monstros):
    rtcs = [c._json(p) for p in pasta.glob('[0-9]*_rtc.json')]
    rodas = [c._json(p) for p in pasta.glob('[0-9]*_roda.json')]
    conhecidas = [r for r in rodas if r.get('char') == char]
    referencia = referencia_roda(max(conhecidas, key=lambda r: r['instante']), catalogo) if conhecidas else {}
    arquivo = pasta/'combate_ml_dados.json'
    anterior = c._json(arquivo)
    dados = anterior.get('amostras', []) if anterior.get('char') == char and anterior.get('versao') == COMBATE_VERSAO else []
    atuais = exemplos_combate(char, sessao, eventos, magias, rtcs, rodas, amostras, intervalos, catalogo, monstros)
    unicos = {d['id']: d for d in [*dados, *atuais]}
    dados = sorted(unicos.values(), key=lambda d: (d['instante'], d['id']))[-10000:]
    c._grava(arquivo, {'versao': COMBATE_VERSAO, 'char': char, 'amostras': dados})
    semente = c._json(pasta/'roda_ml_inicio.json')
    if not semente and referencia:
        c._grava(pasta/'roda_ml_inicio.json', referencia)
    return treinar_combate(dados, semente or referencia, catalogo['versao'])
