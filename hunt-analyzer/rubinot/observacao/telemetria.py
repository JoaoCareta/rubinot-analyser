"""Leituras conservadoras do quadro compartilhado, sem segunda captura.

Texto integral identifica contadores; ícone sem relógio não prova prontidão.
Ausência de efeito só é conhecida com uma região certificada e visível.
"""
import hashlib
import re


def contadores(textos, char, t, prova, serie):
    titulos = [r for r in textos if r['texto'] == 'Supply Analyser']
    if len(titulos) != 1:
        return []
    titulo = titulos[0]; saida = []
    # Exige nome explícito e contador na mesma linha do painel. Não converter
    # Gold Value nem quantidades da barra/inventário em uso.
    itens = [r for r in textos if titulo['y'] < r['y'] < titulo['y']+450
             and abs(r['x']-titulo['x']) < 260
             and re.fullmatch(r"[A-Za-z ']+(?:Potion|Rune)", r['texto'])]
    for item in itens:
        if sum(r['texto']==item['texto'] for r in itens) != 1:
            continue
        coluna = next((r for r in textos if r['texto'] in ('Used','Quantity Used')
                       and titulo['y'] < r['y'] < item['y'] and item['x'] < r['x'] <= titulo['x']+260), None)
        valores = [r for r in textos if abs(r['y']-item['y']) <= 2
                   and item['x'] < r['x'] <= titulo['x']+260
                   and (re.fullmatch(r'\d[\d,]*\s*(?:x|used)', r['texto'])
                        or coluna and abs(r['x']-coluna['x'])<=10 and re.fullmatch(r'\d[\d,]*',r['texto']))]
        if len(valores) != 1:
            continue
        valor = int(re.sub(r'[^\d]', '', valores[0]['texto']))
        nome = item['texto'].lower().replace(' ', '_')
        saida.append({'id': hashlib.sha256(f'{prova}:{nome}'.encode()).hexdigest(),
                      'char': char, 'item': nome, 'valor': valor, 't': t,
                      'serie': serie, 'unidade': 'unidades', 'origem': 'contador_uso',
                      'continuidade': False, 'prova': prova, 'qualidade': 'texto_integral',
                      'familia': 'hibrida' if 'spirit' in nome else 'mana' if 'mana' in nome
                          else 'vida' if 'health' in nome else 'runa'})
    return saida


def prontidao(textos, icones, t, prova):
    """Só números associados a um ícone identificado; não infere cast."""
    saida = {}
    for icone in icones:
        x, y, w, h = icone['regiao']
        valores = [r['texto'] for r in textos if x <= r['x'] < x+w and y <= r['y'] < y+h
                   and re.fullmatch(r'\d+(?:\.\d+)?s', r['texto'])]
        segundos = float(valores[0][:-1]) if len(valores) == 1 else None
        saida[icone['id']] = {'restante_s': segundos, 'pronta': segundos == 0 if segundos is not None else None,
                              't': t, 'prova': prova, 'precisao_s': 1,
                              'origem': 'icone_e_contagem_visual' if segundos is not None else 'icone_sem_relogio'}
    return saida


def identificar_icones(imagem, referencias):
    """Match integral do ícone: escurecido/oculto permanece desconhecido."""
    import cv2
    import numpy as np
    arr = np.asarray(imagem.convert('RGB')); out = []
    for ident, ref in referencias.items():
        h, w = ref.shape[:2]
        if min(h, w) < 8 or h > arr.shape[0] or w > arr.shape[1]:
            continue
        matches = cv2.matchTemplate(arr, ref, cv2.TM_SQDIFF_NORMED)
        ys, xs = np.nonzero(matches <= .002)
        # Mais de um ícone pode ser editor, barra ou lista: origem ambígua.
        if len(xs) == 1:
            out.append({'id': ident, 'regiao': [int(xs[0]), int(ys[0]), w, h]})
    return out


def escudo_certificado(imagem, presente, referencia):
    if presente:
        return True
    # Referência deve conter âncoras de ambos os lados da região de estados.
    # Não aprender ausência a partir da própria ausência.
    if not referencia or not referencia.get('certificada'):
        return None
    import numpy as np
    arr = np.asarray(imagem.convert('RGB'))
    for ancora in referencia.get('ancoras', []):
        x, y, w, h = ancora['regiao']; modelo = np.asarray(ancora['pixels'])
        patch = arr[y:y+h, x:x+w]
        if patch.shape != modelo.shape or not np.array_equal(patch, modelo):
            return None
    return False if len(referencia.get('ancoras', [])) >= 2 else None


def transicoes_escudo(recursos, gap=6):
    """Duração de efeito censurada nas extremidades e nas lacunas."""
    episodios = []; atual = None; anterior = None
    for q in sorted(recursos, key=lambda q:q['t']):
        estado = q.get('escudo'); t = q['t']
        continuo = anterior is not None and 0 < t-anterior['t'] <= gap
        if atual and (not continuo or estado is None):
            atual.update(fim=anterior['t'], fim_censurado=True); episodios.append(atual); atual = None
        if estado is True and atual is None:
            atual = {'inicio': t, 'inicio_censurado': not (continuo and anterior.get('escudo') is False),
                     'provas': [q.get('origem')]}
        elif estado is False and atual:
            atual.update(fim=t, fim_censurado=False, transicao_fim=[anterior['t'],t]); episodios.append(atual); atual = None
        anterior = q
    if atual:
        atual.update(fim=anterior['t'], fim_censurado=True); episodios.append(atual)
    for e in episodios:
        e['duracao_observada_s'] = e['fim']-e['inicio']
        e['duracao_integral_s'] = e['duracao_observada_s'] if not e['inicio_censurado'] and not e['fim_censurado'] else None
    return episodios
