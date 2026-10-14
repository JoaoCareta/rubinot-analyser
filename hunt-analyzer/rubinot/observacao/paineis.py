"""Observações visuais com origem, precisão e lacunas explícitas por campo.

Não soma painéis, não reconstrói contadores pelos logs e não treina com estimativas.
"""
import re

import painel_stream as ps
from rubinot.observacao import geometria_paineis as geo

VERSAO = 1
ESQUEMA = {
    'xp': ('RawXPGain', 'XPGain', 'RawXP/h', 'XP/h', 'NextLevel'),
    'hunt': ('Loot', 'Supplies', 'Balance', 'Damage', 'Damage/h', 'Healing'),
    'party': ('Session', 'LootType', 'Loot', 'Supplies', 'Balance'),
    'input': ('Total', 'Max-DPS'),
    'supply': ('GoldValue', 'PerHour', 'Target'),
    'loot': ('GoldValue', 'PerHour', 'Target'),
    'skills': ('Level', 'XP', 'XPGainRate', 'HitPoints', 'Mana', 'SoulPoints',
               'Capacity', 'Speed', 'Food', 'Stamina', 'Magic', 'StoreBoost', 'OfflineTraining'),
    'battle': (),
}


def medida(valor, texto, painel, unidade=None):
    abreviado = bool(re.search(r'\dk\s*$', texto))
    return {'valor': valor, 'texto': texto, 'origem': geo.TITULOS[painel],
            'estado': 'ilegivel' if valor is None else 'lido',
            'resolucao': 1000 if abreviado else 1, 'abreviado': abreviado,
            'unidade': unidade, 'estimativa': painel in ('supply', 'loot'),
            'janela': 'desconhecida' if painel in ('input', 'supply', 'loot') else 'painel'}


def campos(painel, textos):
    valores = ps.campos(textos)
    if painel == 'input':
        dano = False; valores = {}
        for texto in textos:
            if texto.replace(' ','') == 'ReceivedDamage':
                dano = True
            elif 'Received' in texto or texto.replace(' ','') in ('DamageTypes','DamageSources'):
                dano = False
            elif dano:
                valores.update(ps.campos([texto]))
    originais = {a.replace(' ', ''): b.strip() for t in textos
                 for a, sep, b in [t.partition(':')] if sep}
    if painel == 'party':
        valores['Session'] = ps.tempo_sessao(textos)
    if painel == 'xp':
        # O N pode estar fora do atlas antigo, mas nunca aceitar dígitos desconhecidos.
        original = originais.get('NextLevel', originais.get('?extLevel', ''))
        m = re.fullmatch(r'(\d+) (minute|minutes|hour|hours|day|days)', original)
        valores['NextLevel'] = int(m[1])*({'minute':60,'hour':3600,'day':86400}[m[2].rstrip('s')]) if m else None
        originais['NextLevel'] = original
    if painel == 'skills':
        for texto in textos:
            for rotulo in sorted(ESQUEMA['skills'], key=len, reverse=True):
                rx = ''.join(re.escape(c)+r'\s*' for c in rotulo)
                m = re.fullmatch(rx+r'(.+)', texto)
                if not m:
                    continue
                bruto = m[1].strip(); originais[rotulo] = bruto
                if rotulo in ('Food','Stamina','StoreBoost','OfflineTraining'):
                    valores[rotulo] = bruto if re.fullmatch(r'\d{2,3}:[0-5]\d',bruto) else None
                elif rotulo == 'XPGainRate':
                    valores[rotulo] = ps.numero(bruto[:-1]) if bruto.endswith('%') else None
                else:
                    valores[rotulo] = ps.numero(bruto)
                break
    out = {k: medida(valores.get(k), originais.get(k,''), painel) for k in ESQUEMA[painel]}
    if painel == 'party':
        out['Session'].update(unidade='s', resolucao=60)
    if painel == 'xp':
        out['NextLevel'].update(unidade='s', estimativa=True)
    return out



def membros_party(textos):
    """Cada nome mantém seu próprio snapshot; nome cortado não vira membro completo."""
    membros = []; pendente = None
    for texto in textos:
        nome = texto.strip(' ?�')
        if ':' in nome or nome in ('Split Loot','Party Hunt') or not nome:
            continue
        numero = re.sub(r'^[?�]+\s+', '', texto.strip()).lstrip('+ ')
        valor = ps.numero(numero)
        if re.fullmatch(r"[A-Za-z?�][A-Za-z ?�'\-]{2,59}", nome):
            pendente = {'nome':nome,'identidade_completa':'?' not in nome and '�' not in nome,
                        'valores':[],'textos':[]}; membros.append(pendente)
        elif pendente is not None and len(pendente['valores'])<3:
            if valor is not None or re.search(r'\d',numero):
                pendente['valores'].append(valor); pendente['textos'].append(numero)
    for m in membros:
        valores = m.pop('valores'); m['completo'] = m['identidade_completa'] and len(valores)==3 and all(v is not None for v in valores)
        for i,chave in enumerate(('balance','dano','cura')):
            m[chave] = medida(valores[i] if len(valores)>i else None,
                             m['textos'][i] if len(m['textos'])>i else '', 'party')
    return membros


def listas_hunt(textos):
    secao = None; saida = {'criaturas': [], 'itens': []}
    for texto in textos:
        if texto.replace(' ','') in ('KilledMonsters:','KilledMonsters'):
            secao = 'criaturas'; continue
        if texto.replace(' ','') in ('LootedItems:','LootedItems'):
            secao = 'itens'; continue
        if secao:
            m = re.fullmatch(r"(\d+)x?\s+([A-Za-z][A-Za-z '\-]+)",texto)
            if m:
                saida[secao].append({'nome':m[2],'quantidade':int(m[1]),'texto':texto})
    return {**saida,'cobertura':'somente_linhas_visiveis'}


def ler(imagem, sessao, frame=None, t=None, refs_itens=None):
    geometria = geo.detectar(imagem); paineis = {}
    for painel in ESQUEMA:
        regiao = geometria['regioes'].get(painel)
        im = geo.recorte(imagem,regiao) if regiao else None
        if im is None:
            paineis[painel] = {'estado':'ambiguo' if painel in geometria['ambiguos'] else 'nao_identificado',
                              'campos':campos(painel,[]),'textos':[]}
            continue
        textos = ps.linhas(im); leituras = campos(painel,textos)
        p = {'campos':leituras,'textos':textos,'regiao':regiao,
             'estado':'lendo' if leituras and all(v['valor'] is not None for v in leituras.values()) else 'parcial',
             'cobertura':'campos_visiveis', 'prova':frame}
        if painel == 'party':
            p['membros'] = membros_party(textos)
            balance = leituras['Balance']['valor']
            p['membros_completos'] = bool(p['membros']) and all(m['completo'] for m in p['membros']) and sum(m['balance']['valor'] for m in p['membros'])==balance
            if p['membros'] and not p['membros_completos']:
                p['estado'] = 'parcial'
        if painel == 'input':
            p.update(ps.distribuicao_input(im))
            # Não capturar Total de Received Healing como dano recebido.
            entrada = ps.ler_input(imagem,sessao)
            for chave,v in [('Total',entrada.get('total')),('Max-DPS',entrada.get('max_dps'))]:
                p['campos'][chave]['valor'] = v
                p['campos'][chave]['estado'] = 'lido' if v is not None else 'ilegivel'
        if painel == 'hunt':
            p['listas'] = listas_hunt(textos)
        if painel in ('supply','loot'):
            from rubinot.observacao import itens_painel
            from rubinot.observacao.supplies import hotkeys
            itens = hotkeys(im,refs_itens or {},None,t,frame or '',str(sessao))
            p['lista_itens'] = itens_painel.ler(im)
            p['itens'] = p['lista_itens']['itens']
            p['itens_referenciados'] = [dict(i,origem=geo.TITULOS[painel],estimativa=True) for i in itens]
            p['cobertura_itens'] = 'somente_contadores_visiveis'
            p['estimativa'] = True
        paineis[painel] = p
    return {'versao':VERSAO,'frame':frame,'t':t,'layout':geometria,
            'paineis':paineis,'tempo_sessao_s':paineis['party']['campos']['Session']['valor'],
            'tempo_sessao_origem':'Party Hunt','tempo_sessao_resolucao_s':60}
