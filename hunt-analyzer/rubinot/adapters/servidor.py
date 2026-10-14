"""Hunt Analyzer — programa local com interface no navegador.

Roda no PC de quem joga e serve a página em http://127.0.0.1:3312 (só nesta máquina).
Tela 1 = calibração: tira um print da janela do RubinOT, ACHA os painéis pelo cabeçalho
(botão × + título lido pelo atlas de glifos) e confere cada região com os MESMOS leitores
da análise. Grava em calibracao.json, em coordenadas relativas à janela do jogo (as mesmas
dos recortes do capture.py).
Tela 2 = hunt (/hunt): com a calibração salva o programa grava sozinho (ao_vivo.py) e a
página lê /api/hunt.

Uso: python app.py [--sem-navegador] [--sem-gravacao] [--sessao <pasta>]
  --sem-gravacao   não liga captura nem análise
  --sessao <pasta> teste/retomada: analisa uma pasta que já existe, sem capturar
  HUNT_PORTA=<n>   outra porta (teste ao lado do programa do usuário)
"""
import ctypes
import datetime as dt
import io
import json
import os
import pathlib
import re
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import mss
import numpy as np
from PIL import Image, PngImagePlugin

import atlas_build as ab
import auxiliares
import capture
import catalogo
import controle
import events_build as ev
import layout
import fontes
import stream_twitch
import nameplates
import ue_alerta
import configuracoes

AQUI = pathlib.Path(__file__).resolve().parents[2]
os.chdir(AQUI)
try:  # 21/09: o motor puxa os leitores da hunt; se um deles quebrar, a calibração continua de pé
    import ao_vivo
except Exception as e:
    ao_vivo, ERRO_AO_VIVO = None, f"{type(e).__name__}: {e}"
    print(f"ao_vivo não carregou: {ERRO_AO_VIVO}", flush=True)
UI = AQUI / "ui" / "index.html"
CALIB, PRINT = fontes.caminhos()
LEITOR_STREAM = None
MONITOR_CONFIGURACOES = None
TRAVA_FONTE = threading.RLock()


def fecha_stream():
    global LEITOR_STREAM
    if LEITOR_STREAM:
        LEITOR_STREAM.fechar()
        LEITOR_STREAM = None


def muda_fonte(dados):
    global CALIB, PRINT
    if ao_vivo and ao_vivo.ativo():
        return {'ok': False, 'erro': 'Encerre a hunt antes de mudar a fonte.'}
    try:
        fonte = fontes.normalizar(dados)
    except ValueError as e:
        return {'ok': False, 'erro': str(e)}
    fecha_stream()
    fontes.salvar(fonte)
    CALIB, PRINT = fontes.caminhos(fonte)
    return {'ok': True, 'fonte': fonte}
PORTA = int(os.environ.get("HUNT_PORTA") or 3312)
URL = f"http://127.0.0.1:{PORTA}"
TILES = (15, 11)          # o cliente mostra 15 x 11 tiles do mundo
ESPERA_JOGO_S = 20        # tempo para a pessoa trazer o jogo para a frente
LUM_TITULO = 115          # título do cabeçalho é um cinza mais escuro que o texto dos painéis (140)
GLYPHS, GAP = ab.load_atlas()
SIDX = nameplates.shape_index(GLYPHS)  # atlas indexado só pela forma da letra
BOTAO_X = np.asarray(Image.open(AQUI / "botao_x.png"), dtype=np.float32)  # × do cabeçalho dos painéis


def _r(x0, y0, x1, y1):
    return {"left": x0, "top": y0, "width": x1 - x0, "height": y1 - y0}


# 21/09 (user): todos os painéis da tela, menos Skills. Sem posição padrão: o layout do dono
# (1936x1048) virava a calibração de quem salvasse direto, e Server Log e Map View a detecção não acha.
# 24/09 (user): o Loot Analyser não ajudava em nada — saiu dos obrigatórios e o Supply Analyser
# entrou no lugar dele. Enquanto o leitor do Supply não estiver confirmado no print do user, ele
# fica FORA desta lista: calibração que não salva por causa de um painel novo é o pior dos mundos.
OBRIGATORIAS = layout.REGIOES_OBRIGATORIAS

# painéis de "Campo: valor". Os rótulos são as palavras-chave que identificam cada painel
# (user, 21/09): a região é do painel cujos rótulos mais batem, e troca de região é acusada.
PAINEIS = {
    "hunt": {"nome": "Hunt Analyser", "rotulos": ["Session", "Raw XP Gain", "XP Gain", "Raw XP/h", "XP/h", "Loot", "Supplies",
                         "Balance", "Damage", "Damage/h", "Healing", "Healing/h"],
             "mostra": {"Damage": "dano causado", "Supplies": "seus supplies", "Balance": "Balance"}},
    "xp": {"nome": "XP Analyser", "rotulos": ["Raw XP Gain", "XP Gain", "Raw XP/h", "XP/h", "Next Level"],
           "mostra": {"Raw XP/h": "Raw XP/h", "Next Level": "Next Level"}},
    "loot": {"nome": "Loot Analyser", "rotulos": ["Gold Value", "Per Hour", "Target"],
             "mostra": {"Gold Value": "Gold Value", "Per Hour": "Per Hour"}},
    # 24/09 (user): o painel dos consumíveis (poções, runas) e o quanto eles custaram. Os campos
    # são os MESMOS do Loot Analyser, então quem separa um do outro é o título do cabeçalho
    # (titulo_acima), não os rótulos.
    "supply": {"nome": "Supply Analyser", "rotulos": ["Gold Value", "Per Hour", "Target"],
               "mostra": {"Gold Value": "Gold Value", "Per Hour": "Per Hour"}},
    "party": {"nome": "Party Hunt", "rotulos": ["Session", "Loot Type", "Loot", "Supplies", "Balance"],
              "mostra": {"Supplies": "supplies da pt", "Balance": "Balance", "Loot Type": "Loot Type"}},
    "input": {"nome": "Input Analyser", "rotulos": ["Received Damage", "Total", "Max-DPS", "Damage Types", "Damage Sources"],
              "mostra": {"Total": "dano recebido", "Max-DPS": "Max-DPS"}},
}
TITULOS = {"battle": "Battle List", **{k: p["nome"] for k, p in PAINEIS.items()}}
NOMES = {"tela": "Tela do jogo", "server_log": "Server Log", "mapa": "Map View", **TITULOS}


# ---------------------------------------------------------------- leitura

def recorte(img, r):
    box = (r["left"], r["top"], r["left"] + r["width"], r["top"] + r["height"])
    return np.asarray(img.crop(box).convert("RGB"))


def linhas(arr):
    """Texto das linhas do recorte, letra por letra pela FORMA (nameplates.decode_shape).
    21/09: o atlas guarda a altura da letra dentro da banda; moeda do painel ou letra alta na
    mesma linha desloca a banda e nada casava (Loot/Input Analyser). Borda ou scrollbar que
    funde as bandas (coluna branca em >= 60% da altura) é apagada antes."""
    b = ab.binarize_arr(arr)
    # Bordas/scrollbars não podem unir todas as linhas de um painel alto.
    verticais = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_OPEN, np.ones((20, 1), np.uint8))
    horizontais = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, 100), np.uint8))
    b &= ~(verticais.astype(bool) | horizontais.astype(bool))
    out = []
    for y0, y1 in ab.text_bands(b, input_top=None):
        t = nameplates.decode_shape(b[y0:y1], SIDX, GAP).replace("?", "�")
        out.append(ev.TRAIL_JUNK.sub("", t).strip())
    return out


def _norm(s):
    return re.sub(r"[\s.]", "", s.lower())


def parecido(lido, alvo, minimo=0.6):
    """Rótulo lido = esperado; '�' (glifo que o atlas não tem, ex. y e p) vale qualquer letra."""
    a, b = _norm(lido), _norm(alvo)
    pares = list(zip(a, b))
    return (len(a) == len(b) and all(x == y or x == "�" for x, y in pares)
            and sum(x == y for x, y in pares) >= minimo * len(b))


def contem(texto, alvo, minimo=0.7):
    """Quanto do título está dentro do texto do cabeçalho (0 = não achou): ícone e botões viram
    lixo em volta e o fim pode vir cortado. 24/09: devolve a nota, não só sim/não — "Supply
    Analyser" e "Loot Analyser" batem um com o outro em 0,67, e quem decide é a melhor nota."""
    t, a = _norm(texto), _norm(alvo)
    melhor = 0.0
    for i in range(len(t)):
        pares = list(zip(t[i:i + len(a)], a))
        if len(pares) >= len(a) - 2 and all(x == y or x == "�" for x, y in pares):
            melhor = max(melhor, sum(x == y for x, y in pares) / len(a))
    return melhor if melhor >= minimo else 0.0


def titulo_acima(img, r):
    """Painel cujo título está escrito no cabeçalho logo acima da região, ou None.

    24/09: Loot e Supply Analyser têm os mesmos campos ("Gold Value", "Per Hour", "Target"), então
    os rótulos não separam um do outro — o título separa. Mesma faixa do detectar (título à esquerda
    do botão ×, num cinza mais escuro que o texto); o ícone e os botões fundiriam as bandas do
    leitor, por isso a faixa estreita. A região marcada na mão não encosta no cabeçalho na mesma
    altura que a detectada, então a faixa desliza alguns px e vale a melhor leitura.
    """
    dire = r["left"] + r["width"]
    achado = (None, 0.0)
    for y in range(r['top'] - 24, r['top'] + 12):
        b = recorte(img, _r(max(0, dire - 165), max(0, y + 1), max(1, dire - 40), max(1, y + 11)))
        binario = (b.min(axis=2) > LUM_TITULO) & (b.max(axis=2).astype(int) - b.min(axis=2) < 12)
        txt = nameplates.decode_shape(binario, SIDX, GAP).replace('?', '�')
        achado = max(achado, max(((k, contem(txt, t, 0.8)) for k, t in TITULOS.items()),
                                 key=lambda kv: kv[1]), key=lambda kv: kv[1])
    return achado[0] if achado[1] else None


def campos(arr):
    """[(rótulo, valor)] das linhas "Campo: valor"; linha sem ':' vira rótulo sem valor."""
    out = []
    for l in linhas(arr):
        rot, _, val = re.sub(r"[�\s]+$", "", l).partition(":")
        if rot.strip():
            out.append((rot.strip(), val.strip()))
    return out


def valor(pares, alvo):
    return next((v for rot, v in pares if parecido(rot, alvo)), None)


def notas(pares):
    """{painel: (fração dos rótulos dele achados, quantos)} — as palavras-chave de cada campo."""
    out = {}
    for k, p in PAINEIS.items():
        n = sum(valor(pares, a) is not None for a in p["rotulos"])
        out[k] = (n / len(p["rotulos"]), n)
    return out


def identifica(pares):
    """Painel que mais bate pelos rótulos (fração; empate pelo número). None se < 2 rótulos."""
    k, (f, n) = max(notas(pares).items(), key=lambda kv: kv[1])
    return (k, f) if n >= 2 else (None, 0.0)


def achar_nome(arr, nome):
    """(x do centro, y do topo, texto) do nome do personagem escrito sobre ele, ou None.
    Nome = cor de vida do cliente; lido letra por letra pela forma e comparado com o título."""
    if not nome:
        return None
    m = nameplates._mask(arr, ue_alerta.NAMEPLATE)
    for y0, y1 in ab.find_bands(m):
        if not 5 <= y1 - y0 <= 14:
            continue
        xs = np.flatnonzero(m[y0:y1].any(axis=0))
        cortes = np.flatnonzero(np.diff(xs) > 12)
        for s, e in zip(np.r_[0, cortes + 1], np.r_[cortes, len(xs) - 1]):
            x0, x1 = int(xs[s]), int(xs[e]) + 1
            txt = nameplates.decode_shape(m[y0:y1, x0:x1], SIDX).replace("?", "�")
            if contem(txt, nome, 0.6):
                return (x0 + x1) / 2, int(y0), txt
    return None


def achar_tela(img, nome):
    """Mundo do jogo: o personagem está sempre no centro (user, 21/09). Acha o nome dele e o
    par de bordas retas (coluna quase constante numa faixa alta) mais perto, com o meio a até
    40 px do nome (o cliente desenha o personagem ~1/4 de tile deslocado); depois a borda de
    cima, e a altura sai de 11 tiles."""
    a = np.asarray(img.convert("RGB"))
    H, W = a.shape[:2]
    busca = a.copy()
    busca[:, :int(W * .2)] = 0
    busca[:, int(W * .8):] = 0
    p = achar_nome(busca, nome)
    if not p:
        return None
    xp, yn, _ = p
    g = a.max(axis=2).astype(np.int16)
    reta = g[max(0, yn - 250):min(H, yn + 250)].std(axis=0) < 4
    esq = [x for x in range(int(xp) - 60, max(0, int(xp) - 800), -1) if reta[x]]
    dire = [x for x in range(int(xp) + 60, min(W, int(xp) + 800)) if reta[x]]
    par = next(((L, R) for L in esq for R in dire if abs((L + R) / 2 - xp) <= 40 and 600 <= R - L <= 1500), None)
    if not par:
        return None
    L, R = par
    tile = (R - L - 1) / TILES[0]
    linha_reta = g[:, L + 1:R].std(axis=1) < 4
    cima = next((y for y in range(yn - 30, max(0, yn - 800), -1) if linha_reta[y]), None)
    if cima is None:
        return None
    return _r(L + 1, cima + 1, R, cima + 1 + round(TILES[1] * tile))


def _maior_corrida(v):
    if not v.any():
        return 0
    d = np.diff(np.r_[0, v.astype(np.int8), 0])
    return int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())


def barras_de_vida(arr):
    """Barras de vida da Battle List: faixa de poucos px numa cor de vida do cliente. Os ícones
    de filtro e os nomes são cinza, então só a barra conta (lista vazia = 0)."""
    m = nameplates._mask(arr, ue_alerta.NAMEPLATE, tol=60)
    tem = [_maior_corrida(row) >= 6 for row in m]
    return sum(1 for i, t in enumerate(tem) if t and (i == 0 or not tem[i - 1]))


def num(v):
    return f"{v:,}".replace(",", ".")


def conta(n, um, varios=None):
    return f"{n} {um if n == 1 else (varios or um + 's')}"


# ---------------------------------------------------------------- conferência por região

def v_tela(arr, r, nome):
    """Conferência pelo nome (user, 21/09): o personagem do título da janela tem que estar no centro."""
    tw, th = r["width"] / TILES[0], r["height"] / TILES[1]
    txt = f"tile de {tw:.0f} px"
    if abs(tw - th) / max(tw, th) > 0.08:
        return "aviso", txt + " · a proporção não fecha os 15 x 11 tiles: confira as bordas"
    p = achar_nome(arr, nome)
    if not nome:
        return "aviso", txt + " · sem o nome do personagem no título da janela para conferir"
    if not p:
        return "aviso", txt + f" · não li \"{nome}\" na tela: capture de novo com o nome aparecendo sobre o personagem"
    dx, dy = p[0] - r["width"] / 2, p[1] - r["height"] / 2
    if abs(dx) > tw or abs(dy) > 1.5 * th:
        return "erro", txt + f" · \"{nome}\" está fora do centro: a região está deslocada"
    return "ok", txt + f" · \"{nome}\" no centro, igual ao título da janela"


def titulo_console(img, r):
    """Só a aba ativa: texto cinza claro/branco; abas inativas ficam abaixo de 160.

    A faixa acompanha a região marcada, com cabeçalho dentro ou logo acima dela.
    Máscara de cinza exclui alertas vermelhos e anotações sobre o print.
    """
    y0 = max(0, r['top'] - 38)
    a = recorte(img, _r(r['left'], y0, r['left'] + r['width'], min(img.height, r['top'] + 25)))
    b = (a.min(axis=2) > 160) & (a.max(axis=2).astype(int) - a.min(axis=2) < 8)
    candidatos = []
    for ini, fim in ab.find_bands(b):
        if not 6 <= fim - ini <= 15:
            continue
        txt = nameplates.decode_shape(b[ini:fim], SIDX, GAP).replace('?', '�')
        for k, alvo in {'server_log': 'Server Log', 'spells': 'Spells', 'nearby': 'Nearby Chat', 'loot_chat': 'Loot', 'raids': 'Raids', 'support': 'Support'}.items():
            nota = contem(txt, alvo, 0.8)
            if nota:
                candidatos.append((nota, k, txt, y0 + ini))
    return max(candidatos, key=lambda c: c[0]) if candidatos else None


def v_server_log(arr, r, nome):
    ls = [l for l in linhas(arr) if l]
    com_hora = [ev.TS.match(l) for l in ls if ev.TS.match(l)]
    if not com_hora:
        if ls:
            return "erro", "leu texto sem a hora na frente: o recorte está cortando o começo das linhas"
        return "aviso", "console vazio agora: confira de novo quando aparecer mensagem"
    tipos = {ev.classify(m.group(2))[0] for m in com_hora}
    ultima = f"{com_hora[-1].group(1)} {com_hora[-1].group(2)}"[:80]
    if tipos <= {"speech", "npc_say"}:
        return "aviso", f"isso parece conversa, não o Server Log · última: {ultima}"
    return "ok", f"{len(com_hora)} mensagens lidas · última: {ultima}"


def v_console(k):
    def confere(arr, r, nome):
        with Image.open(PRINT) as img:
            titulo = titulo_console(img, r)
        esperado = 'Spells' if k == 'spells' else 'Server Log'
        if not titulo:
            return 'erro', f'Não li o título da aba ativa. Marque o texto com o cabeçalho {esperado} em cima, sem o campo de digitação.'
        if titulo[1] != k:
            lido = {'spells': 'Spells', 'server_log': 'Server Log', 'nearby': 'Nearby Chat', 'loot_chat': 'Loot', 'raids': 'Raids', 'support': 'Support'}[titulo[1]]
            return 'erro', f'A aba ativa aí é {lido}, não {esperado}.'
        pad = max(0, titulo[3] - r['top'] + 14)
        capacidade = max(0, (r['height'] - pad) // 13)
        minimo = 5
        linhas_lidas = [ev.TS.match(l) for l in linhas(arr) if ev.TS.match(l)]
        if capacidade < minimo:
            return 'aviso', f'{esperado} confirmado pelo título · cabem cerca de {capacidade} linhas. Ajuste para 5–6 linhas se possível.'
        return 'ok', f'{esperado} confirmado pelo título · cerca de {capacidade} linhas. ' + (f'{len(linhas_lidas)} mensagens lidas.' if linhas_lidas else 'Sem mensagens agora; pronto para a hunt.')
    return confere


def v_mapa(arr, r, nome):
    with Image.open(PRINT) as img:
        titulo = False
        for y in range(max(0, r['top'] - 24), r['top'] + 5):
            a = recorte(img, _r(r['left'], y, r['left'] + r['width'], y + 10))
            b = (a.min(axis=2) > LUM_TITULO) & (a.max(axis=2).astype(int) - a.min(axis=2) < 12)
            txt = nameplates.decode_shape(b, SIDX, GAP).replace('?', '�')
            if contem(txt, 'Map View', 0.8):
                titulo = True
                break
    if not titulo:
        return 'erro', 'Não li Map View no cabeçalho acima do minimapa. Inclua a área logo abaixo do título.'
    # o minimapa só usa a paleta de 216 cores do cliente (canais múltiplos de 51); UI e mundo não
    na_paleta = (np.abs(arr.astype(int) - 51 * np.round(arr / 51)).max(axis=2) <= 3).mean()
    if na_paleta < 0.85:
        return "erro", f"isso não parece o minimapa: só {na_paleta:.0%} das cores são de mapa"
    # 21/09: o recorte gravado (m_) tem tamanho fixo em volta do pin; Map View menor pega borda e painel
    m = layout.recorte_mapa(r)
    x0, y0 = m["left"] - r["left"], m["top"] - r["top"]
    folga = 2
    if x0 < -folga or y0 < -folga or x0 + m["width"] > r["width"] + folga or y0 + m["height"] > r["height"] + folga:
        (px, py), (w, h) = layout.PIN_TIP, layout.MAP_WH   # o pin fica 2,5 px à direita e acima do centro
        precisa = (round(2 * max(px - 2.5, w - px + 2.5)), round(2 * max(py + 2.5, h - py - 2.5)))
        return "erro", (f"Map View pequeno demais ({r['width']}x{r['height']} px): o programa precisa de pelo "
                        f"menos {precisa[0]}x{precisa[1]}. Deixe o Map View maior no jogo e capture de novo")
    # mesmo recorte que a gravação faz, procurado no minimapa do RubinOT: confere zoom e pasta do jogo
    import mapa_mundo as mm
    if not mm.MMDIR.is_dir():
        return "aviso", f"não achei a pasta do minimapa do RubinOT ({mm.MMDIR}): a hunt vai ficar sem mapa"
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(arr[max(0, y0):y0 + m["height"], max(0, x0):x0 + m["width"]])).save(buf, "PNG")
    buf.seek(0)
    p = mm.localizar(buf)
    if not p:
        return "ok", ("Map View confirmado pelo título e pelas cores · posição ainda não localizada no mapa do RubinOT. "
                      "A localização será tentada durante a hunt; não precisa sair do local seguro para calibrar.")
    return "ok", f"é o minimapa · achei você no mapa do jogo (andar {p['z']})"


def v_battle(arr, r, nome):
    j, f = identifica(campos(arr))
    if j and f >= 0.6:
        return "erro", f"isso é o {PAINEIS[j]['nome']}, não a Battle List"
    n = barras_de_vida(arr)
    if n:
        return "ok", f"{conta(n, 'criatura')} na lista agora · tem que bater com o jogo"
    return "ok", "Battle List confirmada pelo título · lista vazia agora, pronta para a hunt"


def v_painel(k):
    p = PAINEIS[k]

    def conferir(arr, r, nome):
        pares = campos(arr)
        j, f = identifica(pares)
        if j and j != k and f > notas(pares)[k][0]:
            return "erro", f"isso é o {PAINEIS[j]['nome']}, não o {p['nome']}"
        achou = {a: v for a in p["rotulos"] if (v := valor(pares, a)) is not None}
        destaque = " · ".join(f"{rot} {achou[a].replace(chr(0xFFFD), '') or '–'}"
                              for a, rot in p["mostra"].items() if a in achou)
        import painel_stream
        from rubinot.observacao import paineis
        textos = painel_stream.linhas(Image.fromarray(arr))
        leitura = paineis.campos(k,textos)
        n, total = sum(v['valor'] is not None for v in leitura.values()), len(leitura)
        faltantes = [chave for chave,v in leitura.items() if v['valor'] is None]
        complemento = ' · estimativas auxiliares' if k in ('supply','loot') else ''
        if k == 'party':
            membros = paineis.membros_party(textos)
            if membros and (not all(m['completo'] for m in membros)
                    or sum(m['balance']['valor'] or 0 for m in membros) != leitura['Balance']['valor']):
                return 'aviso', f'{destaque} · membros parcialmente visíveis; confira a altura do painel'
        if n == total:
            return "ok", f"{destaque} · {n} valores lidos; listas podem estar parciais{complemento}"
        if n:
            return "aviso", f"{n} de {total} valores lidos · faltam {', '.join(faltantes)}{complemento}" + (f" · {destaque}" if destaque else "")
        return "erro", f"não achei os campos do {p['nome']}"
    return conferir


NOMES['spells'] = 'Spells'
VALIDA = {"tela": v_tela, "server_log": v_console('server_log'), "spells": v_console('spells'), "mapa": v_mapa, "battle": v_battle,
          **{k: v_painel(k) for k in PAINEIS}}


def validar(k, r, nome=None):
    if k not in VALIDA:
        return {"status": "erro", "texto": "região desconhecida"}
    if not PRINT.exists():
        return {"status": "erro", "texto": "capture a tela do jogo primeiro"}
    img = Image.open(PRINT)
    r = {c: int(round(r[c])) for c in ("left", "top", "width", "height")}
    fora = r["left"] < 0 or r["top"] < 0 or r["left"] + r["width"] > img.width or r["top"] + r["height"] > img.height
    if fora or r["width"] < 8 or r["height"] < 8:
        return {"status": "erro", "texto": "região fora do print ou pequena demais"}
    try:
        # 24/09: o título do cabeçalho vale mais que os campos — é o único jeito de saber se o
        # que está marcado é o Loot ou o Supply Analyser, que têm os mesmos rótulos
        outro = titulo_acima(img, r) if k in TITULOS else None
        if k in TITULOS:
            from rubinot.observacao.geometria_paineis import detectar as localizar
            for chave,reg in localizar(img)['regioes'].items():
                if chave not in TITULOS:
                    continue
                x,y,z,w = reg['box']
                area = max(0,min(z,r['left']+r['width'])-max(x,r['left'])) * max(0,min(w,r['top']+r['height'])-max(y,r['top']))
                if area/max(1,r['width']*r['height'])>.85:
                    outro = chave; break
        if k in TITULOS and not outro:
            return {'status': 'erro', 'texto': f'Não li o título {NOMES[k]} no cabeçalho. Marque o painel com o título em cima.'}
        if outro and outro != k:
            return {"status": "erro", "texto": f"o título aí em cima diz {NOMES[outro]}, não {NOMES[k]}"}
        st, txt = VALIDA[k](recorte(img, r), r, nome_do_print(img, nome))
    except Exception as e:  # leitor quebrou: mostrar na tela, nunca derrubar o programa
        st, txt = "erro", f"falha ao ler: {e}"
    return {"status": st, "texto": txt}


# ---------------------------------------------------------------- detecção pelos cabeçalhos

def detectar(img, nome=None):
    """Acha os painéis pelo cabeçalho: botão × no canto direito + título lido à esquerda dele.
    Conteúdo = logo abaixo do cabeçalho até o próximo cabeçalho da mesma coluna (ou o fim da janela)."""
    from rubinot.observacao.geometria_paineis import detectar as localizar
    achados = {k:_r(*r['box']) for k,r in localizar(img)['regioes'].items() if k in TITULOS}
    tela = achar_tela(img, nome_do_print(img, nome))
    if tela:
        achados["tela"] = tela
    return achados


# ---------------------------------------------------------------- janela, print e arquivo

def info_janela(g):
    t = g["title"]
    return {"titulo": t, "char": t.split(" - ", 1)[1].strip() if " - " in t else None,
            "largura": g["rect"]["width"], "altura": g["rect"]["height"]}


def nome_do_print(img, nome=None):
    """Personagem do título da janela: o gravado no print na captura, o que a página conhece ou o do jogo aberto."""
    return img.info.get("char") or nome or status().get("char")


def status():
    fonte = fontes.atual()
    if fonte['tipo'] == 'twitch':
        estado = LEITOR_STREAM.estado() if LEITOR_STREAM else {'conectado': False, 'mensagem': 'Capture para testar a live.'}
        return {'jogo': estado['conectado'], 'char': fonte['char'], 'fonte': fonte, 'stream': estado}
    g = capture.find_game_rect()
    return {"jogo": bool(g), 'fonte': fonte, **(info_janela(g) if g else {})}


def escala_esticada(hwnd):
    """% da escala do Windows quando ela estica a janela do jogo, senão None. 21/09: o cliente não é
    DPI-aware; acima de 100% o Windows amplia a imagem dele e nenhum molde de letra casa mais."""
    u = ctypes.windll.user32
    try:
        u.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
        u.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        ciente = u.GetAwarenessFromDpiAwarenessContext(u.GetWindowDpiAwarenessContext(ctypes.c_void_p(hwnd)))
        dpi = u.GetDpiForSystem()   # este processo é DPI-aware (capture.py): a escala de verdade
    except (AttributeError, OSError):   # Windows antigo sem essas funções
        return None
    return round(dpi * 100 / 96) if dpi != 96 and ciente == 0 else None


def capturar():
    """Espera o jogo vir para a frente (senão o print pega a página) e grava a janela inteira.
    O cliente roda como administrador: o Windows não deixa ler a janela dele por trás."""
    global LEITOR_STREAM
    fonte = fontes.atual()
    if fonte['tipo'] == 'twitch':
        if ao_vivo and ao_vivo.ativo():
            return {'ok': False, 'erro': 'Encerre a hunt antes de capturar para recalibrar a live.'}
        if not LEITOR_STREAM:
            LEITOR_STREAM = stream_twitch.Leitor(fonte['canal'])
        fim = time.monotonic() + 25
        while time.monotonic() < fim:
            img, _ = LEITOR_STREAM.ultimo()
            if img is not None:
                PRINT.parent.mkdir(parents=True, exist_ok=True)
                meta = PngImagePlugin.PngInfo()
                meta.add_text('char', fonte['char'])
                tmp = PRINT.with_suffix('.tmp')
                img.save(tmp, format='PNG', pnginfo=meta)
                tmp.replace(PRINT)
                return {'ok': True, 'char': fonte['char'], 'titulo': 'Twitch · ' + fonte['canal'],
                        'largura': img.width, 'altura': img.height, 'fonte': fonte}
            time.sleep(0.2)
        return {'ok': False, 'erro': LEITOR_STREAM.estado()['mensagem']}
    g = capture.find_game_rect()
    if not g:
        return {"ok": False, "erro": "Janela do RubinOT não encontrada. Abra o jogo e entre com o personagem."}
    fim = time.time() + ESPERA_JOGO_S
    while time.time() < fim:
        g = capture.find_game_rect() or g
        if ctypes.windll.user32.GetForegroundWindow() == g["hwnd"]:
            time.sleep(0.4)  # o jogo redesenha depois de vir para a frente
            with mss.MSS() as sct:
                shot = sct.grab(g["rect"])
            info = info_janela(g)
            meta = PngImagePlugin.PngInfo()
            meta.add_text("char", info["char"] or "")
            Image.frombytes("RGB", shot.size, shot.rgb).save(PRINT, pnginfo=meta)
            pct = escala_esticada(g["hwnd"])
            if pct:
                info["aviso"] = (f"O Windows está com a escala em {pct}% e estica a imagem do RubinOT: assim o programa "
                                 "não lê nada. Deixe a escala em 100% (Configurações > Sistema > Tela) ou, no arquivo "
                                 "bin\\x64\\rubinot_dx.exe do jogo: botão direito > Propriedades > Compatibilidade > "
                                 "Alterar configurações de DPI alto > marque \"Substituir o comportamento de "
                                 "dimensionamento de DPI alto\" com \"Aplicativo\". Depois feche o jogo, abra de novo e capture.")
            return {"ok": True, **info}
        time.sleep(0.2)
    return {"ok": False, "erro": f"O jogo não veio para a frente em {ESPERA_JOGO_S} s. Clique em Capturar e depois na janela do RubinOT."}


def carregar():
    salvo = json.loads(CALIB.read_text(encoding="utf-8")) if CALIB.exists() else {}
    janela = salvo.get("janela")
    if not janela and PRINT.exists():  # print sem calibração salva: nome vem do jogo aberto
        w, h = Image.open(PRINT).size
        janela = {"largura": w, "altura": h, "char": status().get("char")}
    return {'fonte': fontes.atual(), "regioes": salvo.get("regioes") or {}, "janela": janela,
            "salvo_em": salvo.get("salvo_em"), "tem_print": PRINT.exists()}


def salvar(dados):
    regs = {k: {c: int(round(v[c])) for c in ("left", "top", "width", "height")}
            for k, v in (dados.get("regioes") or {}).items() if k in VALIDA and v}
    faltam = [NOMES[k] for k in OBRIGATORIAS if k not in regs]
    if faltam:
        return {"ok": False, "erro": "Falta marcar: " + ", ".join(faltam)}
    if not PRINT.exists():
        return {"ok": False, "erro": "Capture a tela do jogo antes de salvar."}
    janela = dados.get("janela") or {}
    with Image.open(PRINT) as imagem:
        w, h = imagem.size
    if (janela.get('largura'), janela.get('altura')) != (w, h):
        return {'ok': False, 'erro': 'O print mudou. Capture e confira as regiões novamente.'}
    if any(r['left'] < 0 or r['top'] < 0 or r['width'] <= 0 or r['height'] <= 0
           or r['left'] + r['width'] > w or r['top'] + r['height'] > h for r in regs.values()):
        return {'ok': False, 'erro': 'Mantenha todas as regiões dentro da imagem capturada.'}
    # 21/09: região que não lê grava horas de hunt sem nenhum número; a pessoa corrige antes
    erradas = [NOMES[k] for k in OBRIGATORIAS if validar(k, regs[k], janela.get("char"))["status"] == "erro"]
    if erradas:
        return {"ok": False, "erro": "Região que não lê: " + ", ".join(erradas) +
                ". Clique nela na lista, veja o motivo e marque de novo."}
    out = {'fonte': fontes.atual(), "versao": 2, "salvo_em": dt.datetime.now().isoformat(timespec="seconds"),
           "janela": janela, "char": janela.get("char"),
           "tile_px": round(regs["tela"]["width"] / TILES[0], 2), "regioes": regs}
    fontes.grava_json(CALIB, out)
    return {"ok": True, "salvo_em": out["salvo_em"]}


# ---------------------------------------------------------------- servidor

class Handler(BaseHTTPRequestHandler):
    # 21/09: em HTTP/1.0 o servidor fecha o socket logo depois do envio e, no Windows, o print
    # de ~2 MB chegava cortado (ERR_CONNECTION_RESET). Em 1.1 quem fecha é o navegador.
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # console limpo para quem usa
        pass

    def _local(self):
        # só a própria página: bloqueia site de fora mandando comando para o programa
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORTA}", f"localhost:{PORTA}")

    def _envia(self, corpo, tipo, codigo=200, guardar=False):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "max-age=86400" if guardar else "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        for i in range(0, len(corpo), 1 << 18):  # em pedaços, como o http.server padrão
            self.wfile.write(corpo[i:i + (1 << 18)])

    def _json(self, obj, codigo=200):
        self._envia(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", codigo)

    def do_GET(self):
        if not self._local():
            return self._json({"erro": "acesso só local"}, 403)
        rota = self.path.split("?")[0]
        if rota == "/":
            return self._envia(UI.read_bytes(), "text/html; charset=utf-8")
        if rota == "/hunt":
            return self._envia((AQUI / "ui" / "hunt.html").read_bytes(), "text/html; charset=utf-8")
        if rota == '/configuracoes':
            return self._envia((AQUI / 'ui' / 'configuracoes.html').read_bytes(), 'text/html; charset=utf-8')
        if rota == '/api/configuracoes':
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            return self._json(configuracoes.consultar(q.get('char', [''])[0], q.get('sessao', [''])[0],
                                                     q.get('historico', ['false'])[0] == 'true'))
        if rota.startswith('/api/configuracoes/prova/'):
            png = configuracoes.prova(rota.removeprefix('/api/configuracoes/prova/'))
            return self._envia(png.read_bytes(), 'image/png') if png else self._json({'erro': 'prova não encontrada'}, 404)
        if rota == "/evolucao":   # 24/09 (user): gráficos da pt por período e por hunt
            return self._envia((AQUI / "ui" / "evolucao.html").read_bytes(), "text/html; charset=utf-8")
        if rota == "/auxiliadores":   # 28/09 (user): apitos que ajudam no meio da luta
            return self._envia((AQUI / "ui" / "auxiliadores.html").read_bytes(), "text/html; charset=utf-8")
        estatico = re.fullmatch(r"/ui/((?:[a-z0-9_]+/)*[a-z0-9_]+)\.(json|png|mp3|js|css)", rota)  # só arquivos simples da pasta ui
        if estatico and (AQUI / "ui" / f"{estatico[1]}.{estatico[2]}").is_file():
            tipo = {"json": "application/json; charset=utf-8", "png": "image/png", "mp3": "audio/mpeg",
                    "js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}[estatico[2]]
            return self._envia((AQUI / "ui" / f"{estatico[1]}.{estatico[2]}").read_bytes(), tipo)
        if rota == "/api/status":
            return self._json(status())
        if rota == "/api/hunt":
            if not ao_vivo:
                return self._json({"estado": {"calibrado": CALIB.exists(), "mensagem": "A análise da hunt não abriu; o motivo está no app.log.",
                                              "mapa": {"fonte": "mundo", "ancorado": True, "planos": []}},
                                   "sessao": {}, "andares": {}, "voltas": [], "amostras": [],
                                   "refis": [], "refil": {}, "trechos": [], "entradas": [], "especies_fora": {}})
            return self._json(ao_vivo.json_hunt())
        # 23/09 (user): histórico das hunts guardadas — a lista e, por sessão, o mesmo JSON do
        # /api/hunt montado do disco (a tela reusa o painel). Funciona com a gravação desligada.
        if rota == "/api/historico":
            return self._json({"sessoes": ao_vivo.historico() if ao_vivo else []})
        gravacao = re.fullmatch(r'/api/gravacoes/(session_[a-z0-9_]+)/([qf]_\d+_\d+\.png)', rota)
        if gravacao and ao_vivo:
            from rubinot.adapters.gravacoes import quadro
            png = quadro(ao_vivo.CAPTURAS, gravacao[1], gravacao[2])
            return self._envia(png.read_bytes(), 'image/png') if png else self._json({'erro': 'quadro não encontrado'}, 404)
        curas = re.fullmatch(r'/api/historico/([a-z0-9_.\-]{1,60}/\d{8}_\d{4}(?:\d{2}(?:_[a-f0-9]{8})?)?)/curas', rota)
        if curas and ao_vivo:
            dados = ao_vivo.historico_curas(curas[1])
            return self._json(dados if dados is not None else {'erro': 'Hunt não encontrada'}, 200 if dados is not None else 404)
        replay = re.fullmatch(r'/api/historico/([a-z0-9_.\-]{1,60}/\d{8}_\d{4}(?:\d{2}(?:_[a-f0-9]{8})?)?)/gravacao', rota)
        if replay and ao_vivo:
            dados = ao_vivo.historico_gravacao(replay[1])
            return self._json(dados) if dados is not None else self._json({'erro': 'sessão não encontrada'}, 404)
        prova_ks = re.fullmatch(r'/api/ks/(session_[a-z0-9_]+/(?:[a-zA-Z0-9_]+/){0,4}[a-zA-Z0-9_]+\.png)', rota)
        if prova_ks and ao_vivo:
            png = ao_vivo.ks.RAIZ / prova_ks[1]
            return self._envia(png.read_bytes(), 'image/png') if png.is_file() else self._json({'erro': 'prova não encontrada'}, 404)
        hist = re.fullmatch(r"/api/historico/([a-z0-9_.\-]{1,60}/\d{8}_\d{4}(?:\d{2}(?:_[a-f0-9]{8})?)?)(/mapa\.png)?", rota)
        if hist and ao_vivo:
            if hist[2]:
                png = ao_vivo.historico_mapa(hist[1])
                return self._envia(png, "image/png", guardar=True) if png else self._json({"erro": "sem mapa"}, 404)
            d = ao_vivo.historico_um(hist[1])
            return self._json(d) if d else self._json({"erro": "sessão não encontrada"}, 404)
        if rota == "/api/log":   # 22/09 (user item 6): as últimas decisões, para auditar
            n = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("n", ["200"])[0]
            linhas = ao_vivo.ler_log(max(1, min(int(n) if n.isdigit() else 200, 5000))) if ao_vivo else []
            return self._json({"linhas": linhas})
        if rota == "/api/auxiliares":
            return self._json({**auxiliares.AUX.estado(), "gravando": bool(ao_vivo and ao_vivo.sessao_atual())})
        if rota == "/api/calibracao":
            return self._json(carregar())
        if rota == "/api/print.png" and PRINT.exists():
            return self._envia(PRINT.read_bytes(), "image/png")
        if rota == "/api/monstro":   # do catálogo; o que falta vem do TibiaWiki na hora
            nome = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("nome", [""])[0].strip()
            if not re.fullmatch(r"[A-Za-z0-9 '.\-]{2,60}", nome):
                return self._json({"nome": nome, "erro": "nome inválido"}, 400)
            try:
                return self._json(catalogo.buscar(nome) or {"nome": nome, "erro": "o TibiaWiki não conhece esse nome"})
            except (OSError, ValueError, LookupError):   # sem internet ou resposta estranha: nada gravado, tenta depois
                return self._json({"nome": nome, "erro": "sem resposta do TibiaWiki agora"}, 502)
        gif = re.fullmatch(r"/monstros/([a-z0-9_]+)\.gif", rota)
        if gif and (arq := catalogo.imagem(gif[1])):
            return self._envia(arq.read_bytes(), "image/gif", guardar=True)   # a lista redesenha sem baixar de novo
        self._json({"erro": "não encontrado"}, 404)

    def do_POST(self):
        with TRAVA_FONTE:
            return self._post()

    def _post(self):
        json_ok = self.headers.get("Content-Type", "").startswith("application/json")
        if not (self._local() and json_ok):
            return self._json({"erro": "acesso só local"}, 403)
        from rubinot.adapters.http import EntradaInvalida, ler_objeto
        try:
            dados = ler_objeto(self.headers, self.rfile)
        except EntradaInvalida as erro:
            self.close_connection = True
            return self._json({'ok': False, 'erro': str(erro)}, erro.status)
        if self.path == '/api/fonte':
            return self._json(muda_fonte(dados))
        if self.path == '/api/configuracoes':
            try:
                char=dados.get('char','');acao=dados.get('acao')
                if acao=='pontos':resultado=configuracoes.pontos_total(char,dados.get('valor'))
                elif acao=='sugestao':resultado=configuracoes.guardar_sugestao(char,dados.get('sugestao'))
                elif acao=='confirmar':resultado=configuracoes.confirmar(char,dados.get('id'))
                elif acao=='declarar_uso':resultado=configuracoes.declarar_uso(char,dados.get('sessao'),dados.get('revisoes'),dados.get('resposta'),dados.get('sugestao_id'))
                elif acao=='experimento_twin':resultado=configuracoes.propor_twin(char,dados.get('sessao'),dados.get('candidato'))
                else:raise ValueError('Operação não reconhecida.')
                return self._json({'ok':True,'resultado':resultado})
            except (ValueError,TypeError,KeyError) as erro:
                return self._json({'ok':False,'erro':str(erro)},400)
        if '_fonte' in dados and dados['_fonte'] != fontes.atual():
            return self._json({'ok': False, 'erro': 'A fonte mudou em outra tela. Recarregue esta página.'}, 409)
        if self.path == "/api/capturar":
            return self._json(capturar())
        if self.path == '/api/configuracoes/calibrar':
            try:
                if not PRINT.is_file():
                    raise ValueError('Capture a janela do jogo primeiro.')
                with Image.open(PRINT) as img:
                    char = img.info.get('char')
                # A identidade vem da prova, nunca do texto enviado pelo navegador.
                if not char:
                    raise ValueError('Personagem não identificado no print. Capture novamente.')
                sessao = ao_vivo.sessao_atual() if ao_vivo else None
                resultado = configuracoes.calibrar(dados.get('tipo'), dados.get('regiao') or {}, PRINT,
                    char, sessao.name if sessao else 'calibracao')
                print(f"[{time.strftime('%d/%m %H:%M:%S')}] Configuração {dados.get('tipo')}: referência e leitura guardadas", flush=True)
                return self._json(resultado)
            except (ValueError, KeyError, TypeError, OSError) as erro:
                print(f"[{time.strftime('%d/%m %H:%M:%S')}] Configuração {dados.get('tipo')}: {erro}", flush=True)
                return self._json({'ok': False, 'erro': str(erro)}, 400)
        if self.path == "/api/detectar":
            if not PRINT.exists():
                return self._json({"ok": False, "erro": "capture a tela do jogo primeiro"})
            return self._json({"ok": True, "regioes": detectar(Image.open(PRINT), dados.get("nome")), "procurados": TITULOS})
        if self.path == "/api/validar":
            return self._json(validar(dados.get("k"), dados.get("r") or {}, dados.get("nome")))
        if self.path == "/api/salvar":
            r = salvar(dados)
            if r["ok"] and ao_vivo and ao_vivo.ativo():
                # 21/09: a captura segue o layout.json da própria sessão até o próximo Ligar
                r["aviso"] = "A gravação que está rodando segue com a calibração anterior; a nova vale no próximo Ligar."
            elif r["ok"]:  # calibrou: começa a gravar
                gravar((dados.get("janela") or {}).get("char"))
            return self._json(r)
        if self.path == "/api/auxiliares":
            # 28/09 (user): o auxiliador do Utamo Vita liga, desliga, troca de nível e testa o som
            if dados.get("testar"):
                # 28/09 (user): são DOIS apitos, e dá para ouvir os dois — "caiu" (duas notas
                # caindo) e "perigo" (três subindo). Sem valor, toca o de perigo, como antes.
                caiu = str(dados["testar"]).lower() == "caiu"
                threading.Thread(target=auxiliares.apita, args=(caiu,), daemon=True).start()
                return self._json(auxiliares.AUX.estado())
            if dados.get("ligar"):
                if not ao_vivo:
                    return self._json({"ok": False, "erro": "a análise da hunt não abriu (app.log)"})
                return self._json({"ok": True, **auxiliares.AUX.ligar(ao_vivo.sessao_atual, dados.get("nivel"),
                                                                     dados.get("som"), ao_vivo.hunt_atual)})
            if "auto" in dados:   # ligar sozinho quando o analisador abrir (user, 28/09)
                auxiliares.AUX.muda_auto(dados["auto"])
                # marcar quer dizer "eu quero o auxiliador": liga agora também. Desmarcar só tira
                # das próximas aberturas — quem quer parar agora clica em Desligar.
                if dados["auto"] and not auxiliares.AUX.ligado and ao_vivo:
                    auxiliares.AUX.ligar(ao_vivo.sessao_atual, hunt_de=ao_vivo.hunt_atual)
                return self._json({"ok": True, **auxiliares.AUX.estado()})
            if "regras" in dados:   # só com o auxiliador desligado (user, 28/09)
                ok = auxiliares.AUX.muda_regras(dados["regras"])
                # o estado vem primeiro: ele também traz "erro" e apagaria a mensagem daqui
                return self._json({**auxiliares.AUX.estado(), "ok": ok,
                                   "erro": None if ok else "desligue o auxiliador para mudar as regras"})
            if "ligar" not in dados and ("nivel" in dados or "som" in dados):   # ajuste sem ligar/desligar
                if dados.get("nivel") in auxiliares.NIVEIS:
                    auxiliares.AUX.nivel = dados["nivel"]
                if "som" in dados:
                    auxiliares.AUX.som = bool(dados["som"])
                auxiliares.AUX._grava_config()
                return self._json({"ok": True, **auxiliares.AUX.estado()})
            return self._json({"ok": True, **auxiliares.AUX.desligar()})
        if self.path == "/api/gravacao":
            # 24/09 (user): iniciar e encerrar a hunt na própria tela. Antes só havia Desligar, que
            # encerra o programa inteiro — a pessoa tinha que abrir tudo de novo pelo painel.
            if not ao_vivo:
                return self._json({"ok": False, "erro": "a análise da hunt não abriu (o motivo está no app.log)"})
            if not dados.get("ligar"):
                if not ao_vivo.ativo():
                    return self._json({"ok": False, "erro": "a gravação já está parada"})
                ao_vivo.desligar()   # guarda a sessão no histórico; o servidor continua no ar
                return self._json({"ok": True})
            if ao_vivo.ativo():
                return self._json({"ok": False, "erro": "a gravação já está ligada"})
            if not CALIB.exists() or not layout.calibrada(json.loads(CALIB.read_text(encoding='utf-8'))):
                return self._json({"ok": False, "erro": "Complete a calibração da fonte selecionada antes de iniciar."})
            s = gravar(json.loads(CALIB.read_text(encoding="utf-8")).get("char"), nova=True)
            return self._json({"ok": bool(s), "sessao": s.name if s else None,
                               "erro": None if s else "este programa está rodando sem gravação"})
        if self.path == "/api/reiniciar":
            # 22/09 (user item 7): fecha a sessão (salvando o histórico) e começa outra, sem fechar
            # o programa. O servidor continua no ar; a captura volta no próximo tique do supervisor.
            if not (ao_vivo and ao_vivo.ativo()):
                return self._json({"ok": False, "erro": "a gravação não está ligada"})
            nova = ao_vivo.reiniciar()
            return self._json({"ok": bool(nova), "sessao": nova.name if nova else None})
        if self.path == "/api/desligar":
            self._json({"ok": True})
            threading.Thread(target=desligar, daemon=True).start()
            return
        self._json({"erro": "não encontrado"}, 404)


class Servidor(ThreadingHTTPServer):
    # 21/09: no Windows o SO_REUSEADDR deixa DOIS servidores ouvindo a mesma porta (achamos 2
    # rodando, cada um respondendo metade dos pedidos). Porta exclusiva: o segundo não sobe.
    allow_reuse_address = False
    daemon_threads = True


SERVIDOR = None


def gravar(char, nova=False):
    """Liga a gravação da hunt (captura + lap_watch + análise), salvo --sem-gravacao ou já ligada.
    Devolve a sessão, ou None se não ligou."""
    if ao_vivo and CALIB.exists() and layout.calibrada(json.loads(CALIB.read_text(encoding='utf-8'))) and "--sem-gravacao" not in sys.argv and not ao_vivo.ativo():
        fecha_stream()
        return ao_vivo.ligar(char, nova=nova)


_DESLIGANDO = threading.Lock()


def desligar():
    """Desligar pedido pela página: encerra o analisador inteiro; o supervisor fecha junto com a interface."""
    if not _DESLIGANDO.acquire(blocking=False):
        return
    # 28/09: o log tem que dizer QUEM encerrou — sem isso, "fechou sozinho" e "clicaram em Desligar"
    # ficam iguais no dia seguinte
    print(f"[{dt.datetime.now():%d/%m %H:%M:%S}] DESLIGAR pedido pela página", flush=True)
    if MONITOR_CONFIGURACOES:MONITOR_CONFIGURACOES.fechar()
    if ao_vivo:
        ao_vivo.desligar()
    fecha_stream()
    controle.encerrar()
    SERVIDOR.shutdown()


def _demo():
    """Confere o que separa Loot e Supply Analyser (24/09): eles têm os MESMOS campos, então quem
    decide é o título do cabeçalho. Roda com `python app.py --demo`."""
    lido = "Loot Anal�ser"   # o atlas não tem o glifo do y: ele entra como coringa
    assert contem(lido, "Loot Analyser") > contem(lido, "Supply Analyser"), "título ambíguo"
    assert not contem(lido, "Supply Analyser"), "Supply não pode casar com o cabeçalho do Loot"
    assert not contem("Part� Hunt", "Hunt Analyser"), "Party Hunt não é Hunt Analyser"
    if not (PRINT.exists() and CALIB.exists()):
        return print("app: contem separa Loot de Supply (sem print salvo: pulei o resto)")
    img, salvo = Image.open(PRINT), json.loads(CALIB.read_text(encoding="utf-8"))
    for k, r in salvo["regioes"].items():
        if k in TITULOS:
            t = titulo_acima(img, r)
            assert t == k, f"{k}: o título acima da região diz {t}"
        elif k in ('server_log', 'spells'):
            t = titulo_console(img, r)
            assert t and t[1] == k, f"{k}: aba ativa não confere"
        v = validar(k, r, salvo.get('char'))
        assert v['status'] != 'erro', (k, v)
    if "loot" in salvo["regioes"]:  # marcar o Loot Analyser como Supply tem que dar erro
        v = validar("supply", salvo["regioes"]["loot"], salvo.get("char"))
        assert v["status"] == "erro" and "Loot" in v["texto"], v
    print(f"app: títulos lidos nas {len(salvo['regioes'])} regiões do print e Loot ≠ Supply")


def main():
    global SERVIDOR, MONITOR_CONFIGURACOES
    try:
        srv = SERVIDOR = Servidor(("127.0.0.1", PORTA), Handler)
    except OSError as e:  # já está aberto: só mostra a página
        print(f"A porta {PORTA} já está em uso (o Hunt Analyzer já aberto ou outro programa): {e}", flush=True)
        if "--sem-navegador" not in sys.argv:
            webbrowser.open(URL)
        return
    print(f"Hunt Analyzer rodando em {URL}. Feche esta janela para sair.", flush=True)
    from rubinot.bootstrap.monitor import Monitor
    MONITOR_CONFIGURACOES=Monitor(
        lambda:ao_vivo.sessao_atual() if ao_vivo else None,
        lambda:bool(ao_vivo and ao_vivo.ativo()),fontes.atual)
    if '--sem-observacao' not in sys.argv:MONITOR_CONFIGURACOES.iniciar()
    # só o servidor que ficou com a porta grava: o segundo clique no atalho não abre outra captura
    char = (json.loads(CALIB.read_text(encoding="utf-8")).get("char") if CALIB.exists() else None)
    if "--sessao" in sys.argv and ao_vivo:
        ao_vivo.anexar(sys.argv[sys.argv.index("--sessao") + 1], char)
    elif CALIB.exists():
        gravar(char)
    # 28/09 (user): quem marcou "ligar sozinho" não quer clicar em Ligar toda vez
    if ao_vivo and auxiliares.AUX.auto and "--sem-gravacao" not in sys.argv:
        auxiliares.AUX.ligar(ao_vivo.sessao_atual, hunt_de=ao_vivo.hunt_atual)
        print(f"[{dt.datetime.now():%d/%m %H:%M:%S}] auxiliador do Utamo Vita ligado sozinho "
              f"(nível {auxiliares.AUX.nivel})", flush=True)
    if "--sem-navegador" not in sys.argv:
        webbrowser.open(URL)
    # 28/09 (user, "o programa fechou 2x"): se o servidor cair por conta própria, o log tem que
    # mostrar o motivo. Saída limpa e queda deixavam o mesmo silêncio no app.log.
    try:
        srv.serve_forever()
    except BaseException:
        print(f"[{dt.datetime.now():%d/%m %H:%M:%S}] SERVIDOR CAIU:", flush=True)
        traceback.print_exc()
        raise
    finally:
        if MONITOR_CONFIGURACOES and MONITOR_CONFIGURACOES.thread.is_alive():MONITOR_CONFIGURACOES.fechar()
        print(f"[{dt.datetime.now():%d/%m %H:%M:%S}] servidor encerrado", flush=True)


if __name__ == "__main__":
    _demo() if "--demo" in sys.argv else main()
