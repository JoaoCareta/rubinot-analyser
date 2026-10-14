"""Auxiliadores de hunt: apito no momento em que uma jogada precisa sair (user, 28/09).

Hoje só o do **Utamo Vita**, o escudo do druida. O programa não abre a tela de novo: ele usa o que
a gravação já recorta — o Server Log a cada 0,5 s e o quadro cheio a cada 4 s —, então o auxiliador
só funciona com a gravação ligada (e, como a captura, só enquanto o jogo está na frente).

Sinais, todos medidos na hunt de 26/09 (2,4 h de pt x4 na cripta):
  · bichos em mim    "You lose N hitpoints due to an attack by a X" -> atacantes DISTINTOS. O que
                     bate nos outros chars fica de fora: o foco é individual (pedido do user).
  · dano em mim      o HP perdido na janela.
  · curas nos outros "You heal <Nome> for N hitpoints" — o sio no EK. É o turno que o druida gasta
                     com a pt e não usa em si mesmo (28/09: essa mensagem nem era reconhecida).
  · curas em mim     "You heal yourself for N hitpoints".
  · ESCUDO DE PÉ     o ÍCONE do utamo na tela (29/09). Até 28/09 isso era adivinhado pelo console
                     — "o dano voltou a bater no HP" — e ERRAVA: medido na hunt de 29/09, com o
                     escudo de pé 73 golpes ainda caíram no HP, e 37 dos 104 apitos de "escudo
                     caiu" saíram com o escudo INTEIRO (as duas reclamações do user: apitava com o
                     escudo acima de 60% e com o utamo em cooldown). O ícone não adivinha nada.

Quanto cada regra apita, medido na mesma hunt (janela de 8 s, 45 s sem repetir, escudo calando):
  3+ bichos em mim ........................... 3,0 apitos/h
  dano >= 2500 hp ............................ 1,7/h
  dano >= 2000 hp ............................ 8,0/h
  dano >= 1200 hp e 3+ curas nos outros ...... 4,2/h
  calmo = 3 bichos ou 2500 hp ................ 4,3/h
  normal = + 2000 hp ou (1200 e 3 curas) .... 12,7/h
  sensivel ................................... ~30/h

O escudo caiu, medido na hunt de 29/09 (2,4 h, 2.062 quadros cheios): o utamo cai 58x por hora,
mas em METADE das vezes o ícone volta no quadro seguinte (menos de 4 s: você já soltou, e apitar
ali é o apito em cima do cooldown). Por isso a queda só vale apito depois de CONFIRMADA e com
você tomando dano: sensível 4 s (58/h) · normal 8 s (25/h) · calmo 16 s (14/h).

Uso: python auxiliares.py capture/session_X [nivel]   # repassa uma hunt gravada e diz onde apitaria
"""
import collections
import json
import os
import pathlib
import re
import threading
import time

import numpy as np
from PIL import Image

import atlas_build as ab
import catalogo
import events_build as ev

JANELA_S = 8        # tudo é medido nos últimos 8 s
SILENCIO_S = 45     # não repete o apito antes disso
APITO_GAP_S = 8     # UM alarme por vez (user, 30/09): cada regra tinha o silêncio dela, mas nenhuma
                    # olhava o das outras — vida (som subindo) e escudo caiu (som descendo) saíam no
                    # mesmo segundo, em duas threads, e os dois apitos tocavam juntos. Quem cai
                    # dentro da janela vai só para a tela.
PASSO_S = 0.4       # ritmo da leitura (a captura grava um c_ a cada 0,5 s)
ATRASO_MAX_S = 20   # console parado há mais que isso: sem sinal (jogo atrás, gravação em espera)

# O nível só mexe nos NÚMEROS; quais regras valem é a lista de REGRAS, com interruptor na tela.
# "escudo" = segundos com o ícone do utamo fora da tela antes de apitar (ver ESCUDO_MOLDE).
# "box_nu" = segundos sem escudo para o aviso de box (chegar sem escudo é fato, não suspeita de
# cooldown, então ele é mais curto que o "escudo": medido em 30/09, 13/h com 8 s e 22/h com 4 s).
NIVEIS = {
    "calmo":    {"bichos": 3, "dano": 2500, "dano_curas": 2000, "curas": 3, "turnos": 4, "escudo": 16, "box_nu": 8},
    "normal":   {"bichos": 3, "dano": 2000, "dano_curas": 1200, "curas": 3, "turnos": 3, "escudo": 8, "box_nu": 4},
    "sensivel": {"bichos": 2, "dano": 1500, "dano_curas": 1000, "curas": 2, "turnos": 3, "escudo": 4, "box_nu": 4},
}
CAIU_SILENCIO_S = 25   # o "escudo caiu" tem silêncio próprio: é evento, não situação

# ---- escudo de pé = o ícone do utamo no quadro cheio (user, 29/09: "apitava com meu escudo acima
# de 60%" e "apitava com o utamo em cooldown"). O ícone é um escudinho dourado que o cliente
# desenha ao lado da mana; o molde é a máscara do dourado dele (o miolo muda com o fundo, a borda
# não). Achado sozinho no quadro inteiro — não precisa de região nova na calibração, e em 2.062
# quadros de 29/09 nunca casou em outro lugar da tela.
ESCUDO_MOLDE = ("#...#", "#####", "#...#", "#...#", "#...#", "#...#", "##.##", "..#..")
ESCUDO_OURO = (211, 198, 27)   # a cor da borda do ícone
ESCUDO_FRESCO_S = 20           # quadro cheio mais velho que isso: não sei se o escudo está de pé

# ---- aviso de box (user, 28/09): "apitar antes de entrar numa box complexa, para o cooldown do
# utamo não ser problema". Medido: o dano NÃO se concentra (as 8 piores células de 4 sqm somam 22%
# do dano), então avisar em toda box seria barulho — o aviso só sai com o ESCUDO CAÍDO.
CEL = 4                  # célula de 4 sqm, a mesma dos mapas da tela
BOX_FRACAO = 0.02        # célula com menos de 2% do dano da hunt não é box
BOX_JUNTA = 8            # células a menos de 8 tiles uma da outra são a mesma box
BOX_RAIO = 8             # avisa quando você chega a 8 tiles da box (2 a 3 s de caminhada)
BOX_SILENCIO_S = 90      # por box: a rota passa nela toda volta
POS_VALE_S = 8           # posição mais velha que isso não serve para decidir
VISITA_MIN_S = 8         # passada mais curta que isso é caminho, não parada na box

# ---- quanto o escudo DURA dentro de cada box (user, 30/09: "o tempo médio de duração do escudo
# por box, para que antes de chegar na box ele soe um alarme"). Medido na hunt de 30/09 na cripta
# (2,15 h, 1.840 quadros cheios cruzados com a trilha, 8 boxes, 195 passadas): o escudo aguenta
# 32 s de mediana na hunt inteira, mas dentro da box ele cai em 5 a 17 s, em 47% das passadas
# (box 1 da cripta: 76% das passadas, em 10 s). E em 59 passadas (27/h) você CHEGA sem escudo —
# esse é o número que o aviso ataca. O cooldown do utamo não é o gargalo: a menor volta medida
# entre a queda e o lançamento seguinte foi de 4-8 s, contra 14 a 26 s de parada em cada box.

# ---- vida (user, 28/09): lida da barra do jogo no quadro cheio, que a gravação já faz a cada 4 s.
# Medido na hunt de 28/09: 1.743 quadros, vida mediana 100%, mínima 52% — cruzou 60% duas vezes
# em 2,2 h. É alarme de emergência, tem que ser raro mesmo.
VIDA_LIMITE = 0.60
VIDA_SILENCIO_S = 30

# ---- regras que podem apitar, cada uma com seu interruptor na tela (user, 28/09). Só dá para
# mexer com o auxiliador DESLIGADO.
REGRAS = [
    ("escudo_caiu", "O escudo caiu", "o ícone do utamo sumiu da tela e não voltou: solte de novo"),
    ("box", "Box pesada sem escudo", "chegando numa box que já te machucou, com o escudo caído"),
    ("vida", "Vida em 60% ou menos", "lida da barra de vida do jogo"),
    ("bichos", "Muitos bichos em você", "atacantes distintos na janela de 8 s"),
    ("dano", "Dano forte em 8 s", "o total que você tomou na janela"),
    ("dano_curas", "Dano com você curando a pt", "tomando pancada com o turno indo no sio"),
    ("turnos", "Turnos seguidos em cura", "sua cura + a da pt, mesmo sem dano grande (~48 apitos/h)"),
]
PADRAO = {"escudo_caiu": True, "box": True, "vida": True, "bichos": True,
          "dano": True, "dano_curas": True, "turnos": False}
CONFIG = pathlib.Path(os.environ.get("HUNT_AUXILIARES_CONFIG") or pathlib.Path(__file__).resolve().parents[2] / "auxiliares.json")
HORA = re.compile(r"^(\d\d):(\d\d):(\d\d)$")
HUNT_DATA = pathlib.Path(os.environ.get("HUNT_DATA") or pathlib.Path(__file__).resolve().parents[2] / "hunt_data")


def seg(ts):
    m = HORA.match(ts)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m else None


def dispara(s, lim, regras=None):
    """As regras de situação (as de evento — escudo caiu, box, vida — não passam por aqui).
    Devolve o motivo em pt-BR, ou None. `regras` = quais estão ligadas na tela."""
    liga = (regras or PADRAO).get
    if liga("bichos") and s["bichos"] >= lim["bichos"]:
        return f"{s['bichos']} bichos batendo em você"
    if liga("dano") and s["dano"] >= lim["dano"]:
        return f"{s['dano']} de dano em {JANELA_S}s"
    if liga("dano_curas") and s["dano"] >= lim["dano_curas"] and s["curas_outros"] >= lim["curas"]:
        return f"{s['dano']} de dano enquanto você curava a pt {s['curas_outros']}x"
    turnos = s["curas_outros"] + s["curas_eu"]
    if liga("turnos") and turnos >= lim["turnos"]:
        return f"{turnos} turnos seguidos em cura ({s['curas_eu']} em você, {s['curas_outros']} na pt)"
    return None


def caiu_o_escudo(caido_s, dano, lim):
    """Regra do "escudo caiu" (user, 29/09): o ícone do utamo está fora da tela há `caido_s`
    segundos E você está tomando dano. Metade das quedas volta em menos de 4 s (você já soltou) e
    queda sem ninguém batendo não é perigo — as duas viravam apito à toa."""
    return caido_s >= lim["escudo"] and dano > 0


def acha_icone_escudo(arr):
    """(y, x) do ícone do utamo no quadro cheio, ou None. Procura no quadro inteiro: o ícone anda
    de lugar conforme o número da mana muda de largura."""
    a = arr.astype(int)
    ouro = ((abs(a[:, :, 0] - ESCUDO_OURO[0]) <= 10) & (abs(a[:, :, 1] - ESCUDO_OURO[1]) <= 10)
            & (a[:, :, 2] < 60))
    molde = np.array([[c == "#" for c in linha] for linha in ESCUDO_MOLDE])
    h, w = molde.shape
    for y, x in zip(*np.nonzero(ouro)):   # ~100 pixels dourados por quadro; o recorte da borda
        if np.array_equal(ouro[y:y + h, x:x + w], molde):   # decide sozinho (fatia curta = False)
            return int(y), int(x)
    return None


def acha_barra_vida(arr):
    """(x0, y0, x1, y1) da barra de vida no quadro cheio, ou None. Ela é o bloco VERDE largo do alto
    da janela; a de mana, do lado, é azul. Achada sozinha — não precisa de calibração nova."""
    alto = arr[:90]
    verde = (alto[:, :, 1].astype(int) - alto[:, :, 0] > 60) & (alto[:, :, 1].astype(int) - alto[:, :, 2] > 60)
    tem = verde.mean(axis=1) > 0.15
    # a maior FAIXA seguida de linhas verdes: no alto da janela há outros verdes (a barra de XP, o
    # ícone do boost) e pegar da primeira à última linha verde misturava tudo
    melhor, y0, y1, i = 0, 0, 0, 0
    while i < len(tem):
        if tem[i]:
            j = i
            while j < len(tem) and tem[j]:
                j += 1
            if j - i > melhor:
                melhor, y0, y1 = j - i, i, j
            i = j
        else:
            i += 1
    if melhor < 4:
        return None
    linhas = np.arange(y0, y1)
    cols = np.flatnonzero(verde[y0:y1].mean(axis=0) > 0.5)
    if len(cols) < 80:      # barra estreita demais: não é ela
        return None
    return int(cols[0]), int(linhas[0]), int(cols[-1]) + 1, int(linhas[-1]) + 1


def fracao_vida(arr):
    """Fração cheia da barra: a parte cheia é colorida (verde, amarela ou vermelha) e a vazia é
    cinza. Vale a coluna colorida mais à direita — os números escritos por cima não atrapalham."""
    a = arr.astype(int)
    colorida = (a.max(axis=2) - a.min(axis=2)) > 60
    cheias = np.flatnonzero(colorida.mean(axis=0) > 0.5)
    return (int(cheias[-1]) + 1) / arr.shape[1] if len(cheias) else 0.0


def _celula(x, y):
    return int(x // CEL), int(y // CEL)


def agrupa_boxes(dano):
    """{(z, cx, cy): dano} -> [{z, x, y, dano}], juntando células vizinhas numa box só.
    A posição da box é o centro pesado pelo dano; a lista sai da mais pesada para a mais leve."""
    total = sum(dano.values())
    quentes = sorted(((c, v) for c, v in dano.items() if total and v >= BOX_FRACAO * total),
                     key=lambda cv: -cv[1])
    boxes = []
    for (z, cx, cy), v in quentes:
        x, y = (cx + 0.5) * CEL, (cy + 0.5) * CEL
        perto = next((b for b in boxes if b["z"] == z and abs(b["x"] - x) <= BOX_JUNTA
                      and abs(b["y"] - y) <= BOX_JUNTA), None)
        if perto:
            p = perto["dano"] + v
            perto["x"] = (perto["x"] * perto["dano"] + x * v) / p
            perto["y"] = (perto["y"] * perto["dano"] + y * v) / p
            perto["dano"] = p
            perto["celulas"] += 1
        else:
            boxes.append({"z": z, "x": x, "y": y, "dano": v, "celulas": 1})
    for b in boxes:
        b["x"], b["y"] = round(b["x"], 1), round(b["y"], 1)
    return sorted(boxes, key=lambda b: -b["dano"])


def arquivo_boxes(hunt):
    return HUNT_DATA / catalogo.slug(hunt) / "boxes.json"


def le_boxes(hunt):
    try:
        d = json.loads(arquivo_boxes(hunt).read_text(encoding="utf-8"))
        boxes = d["boxes"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    for b in boxes:
        e = escudo_da_box(d.get("escudo") or {}, b)
        if e:
            b["escudo"] = e
    return boxes


def _mediana(v):
    """Mediana com o de cima nos pares, como o resto do programa (`ao_vivo.taxas`)."""
    return sorted(v)[len(v) // 2] if v else None


def escudo_da_box(guardado, b):
    """A medida de escudo guardada mais perto do centro desta box, ou None. A chave e a celula de
    quando foi medida: o centro da box anda um pouco a cada hunt que engorda o mapa de dano."""
    melhor = None
    for k, v in guardado.items():
        try:
            z, cx, cy = map(int, k.split(","))
        except ValueError:
            continue
        dist = max(abs((cx + 0.5) * CEL - b["x"]), abs((cy + 0.5) * CEL - b["y"]))
        if z == b["z"] and dist <= BOX_JUNTA and (melhor is None or dist < melhor[0]):
            melhor = (dist, v)
    if melhor is None:
        return None
    v = melhor[1]
    vidas = v.get("vidas") or []
    return {"passadas": v.get("passadas", 0), "de_pe": v.get("de_pe", 0), "nu": v.get("nu", 0),
            "cai_em_s": _mediana(vidas),
            "cai_pct": round(len(vidas) / v["de_pe"], 2) if v.get("de_pe") else None}


def guarda_boxes(hunt, dano, sessao=""):
    """Soma o dano por célula ao que a hunt já tinha e regrava as boxes (user, 28/09)."""
    p = arquivo_boxes(hunt)
    antigo, escudo = {}, {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        antigo = {tuple(map(int, k.split(","))): v for k, v in d.get("celulas", {}).items()}
        sessoes, escudo = d.get("sessoes", []), d.get("escudo") or {}
    except (OSError, ValueError, AttributeError):
        sessoes = []
    for c, v in dano.items():
        antigo[c] = antigo.get(c, 0) + v
    boxes = agrupa_boxes(antigo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"hunt": hunt, "celula_sqm": CEL,
                             "sessoes": sorted(set(sessoes + ([sessao] if sessao else []))),
                             "boxes": boxes, "escudo": escudo,
                             "celulas": {",".join(map(str, c)): v for c, v in antigo.items()}},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    return boxes


def visitas_box(pontos, b, raio=BOX_RAIO, min_s=VISITA_MIN_S):
    """[(entrada, saida)] das passadas pela box, da trilha que o motor ja grava (ponto a cada 2 s).
    Passada de menos de `min_s` e caminho de rota, nao parada para cacar."""
    out, cur = [], None
    for p in pontos:
        if p["z"] == b["z"] and abs(p["x"] - b["x"]) <= raio and abs(p["y"] - b["y"]) <= raio:
            cur = [p["t"], p["t"]] if cur is None else [cur[0], p["t"]]
        elif cur is not None:
            if cur[1] - cur[0] >= min_s:
                out.append((cur[0], cur[1]))
            cur = None
    if cur is not None and cur[1] - cur[0] >= min_s:
        out.append((cur[0], cur[1]))
    return out


def mede_escudo(linha, pontos, boxes):
    """Quanto o escudo dura DENTRO de cada box (user, 30/09): cruza a linha do icone do utamo (uma
    amostra a cada 4 s) com a trilha e as boxes da hunt. Uma medida por box, na ordem delas.
    `vidas` = segundos entre entrar na box e o icone sumir, so nas passadas em que ele caiu la
    dentro; passada que acaba com o escudo ainda de pe nao tem tempo para medir e entra so como
    passada. `nu` = chegou sem escudo, que e o que o aviso de box ataca."""
    import bisect
    linha = sorted(linha)
    ts = [t for t, _ in linha]

    def estado(t):
        """(de pe?, ha quantos segundos nesse estado), ou (None, None) se nao deu para ler."""
        i = bisect.bisect_right(ts, t) - 1
        if i < 0 or t - ts[i] > ESCUDO_FRESCO_S:
            return None, None
        j = i
        while j > 0 and linha[j - 1][1] == linha[i][1]:
            j -= 1
        return linha[i][1], t - ts[j]

    def cai_depois(t):
        i = bisect.bisect_left(ts, t)
        while i < len(linha):
            if not linha[i][1]:
                return ts[i]
            i += 1
        return None

    medidas = []
    for b in boxes:
        m = {"z": b["z"], "x": b["x"], "y": b["y"], "dano": b.get("dano", 0),
             "passadas": 0, "de_pe": 0, "nu": 0, "nu_confirmado": 0, "vidas": [], "paradas": []}
        for t0, t1 in visitas_box(pontos, b):
            de_pe, ha = estado(t0)
            if de_pe is None:          # gravacao parada na hora da passada: nao conta
                continue
            m["passadas"] += 1
            m["paradas"].append(t1 - t0)
            if not de_pe:
                m["nu"] += 1
                if ha >= NIVEIS["normal"]["box_nu"]:
                    m["nu_confirmado"] += 1
                continue
            m["de_pe"] += 1
            q = cai_depois(t0)
            if q is not None and q <= t1:
                m["vidas"].append(q - t0)
        medidas.append(m)
    return medidas


def guarda_escudo(hunt, medidas, sessao=""):
    """Soma a medida desta sessao a que a hunt ja tinha. As AMOSTRAS e que somam: a mediana sai na
    leitura (`escudo_da_box`), senao mediana de mediana viraria outro numero."""
    p = arquivo_boxes(hunt)
    d = json.loads(p.read_text(encoding="utf-8"))
    guardado = d.get("escudo") or {}
    for m in medidas:
        if not m["passadas"]:
            continue
        a = guardado.setdefault(f"{m['z']},{int(m['x']) // CEL},{int(m['y']) // CEL}",
                                {"passadas": 0, "de_pe": 0, "nu": 0, "vidas": [], "sessoes": []})
        if sessao and sessao in a["sessoes"]:
            continue                       # amostra ja somada: medir de novo dobraria a conta
        a["vidas"] = (a.get("vidas") or []) + [int(v) for v in m["vidas"]]
        for campo in ("passadas", "de_pe", "nu"):
            a[campo] = a.get(campo, 0) + m[campo]
        if sessao:
            a["sessoes"].append(sessao)
    d["escudo"] = guardado
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return guardado


def sessoes_medidas(hunt):
    """Sessoes que ja entraram na medida de escudo desta hunt."""
    try:
        d = json.loads(arquivo_boxes(hunt).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {x for v in (d.get("escudo") or {}).values() for x in v.get("sessoes") or []}


def escudo_da_sessao(sessao, hunt):
    """Mede o escudo por box de uma sessao GRAVADA (precisa dos f_) e guarda no boxes.json."""
    ses = pathlib.Path(sessao)
    if ses.name in sessoes_medidas(hunt):
        raise SystemExit(f"{ses.name} ja esta na medida de {hunt} — apague a sessao do 'escudo' do "
                         f"{arquivo_boxes(hunt)} para medir de novo")
    pontos = [json.loads(l) for l in
              (ses / "trilha.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    boxes = le_boxes(hunt)
    if not boxes:
        raise SystemExit(f"{hunt} ainda nao tem mapa de boxes: rode primeiro --boxes")
    medidas = mede_escudo(linha_do_escudo(ses), pontos, boxes)
    guarda_escudo(hunt, medidas, ses.name)
    return medidas


class Utamo:
    """Motor do auxiliador. Uma instância por programa (o singleton lá embaixo)."""

    def __init__(self):
        self.ligado = False
        self.nivel = "normal"
        self.som = True
        self.regras = dict(PADRAO)
        self.auto = False     # ligar sozinho quando o analisador abrir
        self._le_config()
        self.parar = threading.Event()
        self.sessao_de = self.hunt_de = None
        self.hunt = None
        self.zerar()

    # ------------------------------------------------------------ configuração que fica

    def _le_config(self):
        """Nível, som e regras escolhidos ficam no auxiliares.json: o auxiliador volta como estava."""
        try:
            d = json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if d.get("nivel") in NIVEIS:
            self.nivel = d["nivel"]
        if isinstance(d.get("som"), bool):
            self.som = d["som"]
        if isinstance(d.get("auto"), bool):
            self.auto = d["auto"]
        for k, _, _ in REGRAS:
            if isinstance((d.get("regras") or {}).get(k), bool):
                self.regras[k] = d["regras"][k]

    def _grava_config(self):
        try:
            CONFIG.write_text(json.dumps({"nivel": self.nivel, "som": self.som, "auto": self.auto,
                                          "regras": self.regras},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def muda_auto(self, v):
        """Ligar sozinho quando o analisador abrir (user, 28/09). Vale para as próximas aberturas;
        não mexe no auxiliador de agora, então pode ser marcado a qualquer momento."""
        self.auto = bool(v)
        self._grava_config()
        return self.auto

    def muda_regras(self, regras):
        """Só com o auxiliador DESLIGADO (user, 28/09): regra não muda no meio da hunt."""
        if self.ligado:
            return False
        for k, v in (regras or {}).items():
            if k in self.regras and isinstance(v, bool):
                self.regras[k] = v
        self._grava_config()
        return True

    def zerar(self):
        self.eventos = collections.deque()    # (t, kind, value, actor) dos últimos JANELA_S
        self.pasta = None                     # sessão que está sendo lida
        self.pos = None                       # (t, z, x, y) da trilha do motor
        self.trilha_pos = 0                   # byte já lido da trilha.jsonl
        self.boxes, self.box_ult = [], {}     # boxes da hunt e quando cada uma avisou
        self.dano_celula = collections.Counter()   # dano por célula, para melhorar o mapa
        self.vida = None                      # fração da barra de vida (None = não li)
        self.barra = None                     # retângulo da barra no quadro cheio
        self.visto_f = None                   # último f_ lido (vida e escudo vêm dele)
        self.ult_vida = -10 ** 9
        self.escudo_on = None                 # ícone do utamo no último quadro cheio (None = não li)
        self.escudo_t = -10 ** 9              # relógio desse quadro
        self.caiu_desde = None                # desde quando o ícone está fora da tela
        self.visto = None                     # último c_ lido
        self.prev = []                        # últimas linhas lidas (dedupe do events_build)
        self.agora = None                     # relógio do jogo, do último quadro lido
        self.ult_apito = self.ult_caiu = self.ult_som = -10 ** 9
        self.historico = []                   # últimos apitos, para a tela
        self.erro = None
        self.input_danos = collections.deque(maxlen=30)
        self.observacao = None
        self.diario = None
        self.politica_contexto = None
        self.vida_t = -10 ** 9
        self.aprendizado_erro = None

    def receber_observacao(self, sessao, char, contexto, recurso, raiz):
        """Publicação do observador existente; uma referência atômica, sem captura."""
        self.observacao = (str(sessao), char, dict(contexto), dict(recurso), str(raiz))

    def _compartilhada(self):
        obs = self.observacao
        if not obs or obs[0] != self.pasta:
            return None
        _, char, contexto, r, raiz = obs
        if not 0 <= time.time()-r.get('processado_em', 0) <= 6:
            return None
        if r.get('t', -1)<self.escudo_t:
            return None
        self.escudo_on, self.escudo_t = r.get('escudo'), r['t']
        vida = r.get('vida') or {}
        self.vida = vida.get('percentual')/100 if vida.get('percentual') is not None else None
        self.vida_t = r['t']
        total = r.get('paineis',{}).get('input',{}).get('total')
        if total is not None and (not self.input_danos or r['t']>self.input_danos[-1][0]):
            self.input_danos.append((r['t'],total))
        contexto = {**contexto, 'char':char, 'nivel':self.nivel, 'regras_ativas':dict(self.regras)}
        if self.politica_contexto != contexto or self.diario is None or self.diario.sessao != pathlib.Path(self.pasta).name:
            from rubinot.adapters.diario_assistencia import Diario
            try:
                self.diario = Diario(raiz, pathlib.Path(self.pasta).name, contexto, NIVEIS[self.nivel]['escudo'], r['instante'])
                self.politica_contexto = contexto
            except (OSError, ValueError) as e:
                self.aprendizado_erro = str(e)
        return r

    def _limites(self):
        lim = dict(NIVEIS[self.nivel])
        obs = self.observacao
        contexto = {**obs[2], 'char':obs[1], 'nivel':self.nivel, 'regras_ativas':dict(self.regras)} if obs else None
        if (self.diario and obs and obs[0]==self.pasta and contexto==self.politica_contexto
                and self.diario.politica.get('promover')
                and (obs[3].get('prontidao',{}).get('magic_shield') or {}).get('pronta') is True):
            lim['escudo'] = self.diario.politica['escudo_s']
        return lim

    def _registrar(self, row):
        if not self.diario:
            return
        try:
            self.diario.guardar(row)
        except (OSError, ValueError) as e:
            self.aprendizado_erro = str(e)

    # ------------------------------------------------------------ ciclo de vida

    def ligar(self, sessao_de, nivel=None, som=None, hunt_de=None):
        """sessao_de / hunt_de = funções que devolvem a pasta da sessão gravando agora e o nome da
        hunt (para carregar as boxes dela)."""
        self.sessao_de, self.hunt_de = sessao_de, hunt_de or self.hunt_de
        if nivel in NIVEIS:
            self.nivel = nivel
        if som is not None:
            self.som = bool(som)
        if not self.ligado:
            self.zerar()
            self.parar = threading.Event()
            self.ligado = True
            threading.Thread(target=self._laco, args=(self.parar,), daemon=True).start()
        return self.estado()

    def desligar(self):
        self.parar.set()
        self.ligado = False
        self.guarda()
        return self.estado()

    def guarda(self):
        """Soma o dano por célula desta sessão no mapa de boxes da hunt (user, 28/09: o mapa
        melhora a cada hunt com o auxiliador ligado)."""
        if self.hunt and self.dano_celula:
            try:
                self.boxes = guarda_boxes(self.hunt, dict(self.dano_celula), self.pasta or "")
                self.dano_celula.clear()
            except OSError as e:
                self.erro = f"não deu para guardar as boxes: {e}"

    def _laco(self, parar):
        glyphs, gap = ab.load_atlas()
        while not parar.is_set():
            t0 = time.time()
            try:
                self._passo(glyphs, gap)
                self.erro = None
            except Exception as e:     # um quadro estranho não pode derrubar o auxiliador
                self.erro = f"{type(e).__name__}: {e}"
            parar.wait(max(0.0, PASSO_S - (time.time() - t0)))

    # ------------------------------------------------------------ leitura

    def _passo(self, glyphs, gap):
        ses = self.sessao_de() if self.sessao_de else None
        if not ses or not pathlib.Path(ses).is_dir():
            return
        if str(ses) != self.pasta:
            # Encerrar/Iniciar hunt troca a sessão. Sem zerar aqui, o nome do último quadro lido
            # (HHMMSS) podia ser MAIOR que os da sessão nova e o auxiliador ficava mudo para sempre.
            self.pasta, self.visto, self.prev, self.agora = str(ses), None, [], None
            self.diario = self.politica_contexto = None
            self.vida_t = self.ult_som = self.ult_vida = self.ult_caiu = self.ult_apito = -10 ** 9
            self.input_danos.clear()
            self.eventos.clear()
            self.trilha_pos, self.pos, self.box_ult = 0, None, {}
            self.barra, self.visto_f, self.vida = None, None, None
            self.escudo_on, self.escudo_t, self.caiu_desde = None, -10 ** 9, None
        self._le_trilha(ses)
        self._le_quadro(ses)
        hunt = self.hunt_de() if self.hunt_de else None
        if hunt and hunt != self.hunt:
            self.hunt, self.boxes = hunt, le_boxes(hunt)
            self.registra_boxes = bool(self.boxes)
        quadros = sorted(pathlib.Path(ses).glob("c_*.png"))
        if self.visto is None:
            # ligou no meio da hunt: começa de AGORA. Sem isso ele reprocessaria a sessão inteira e
            # apitaria por causa de perrengue que já passou.
            novos = quadros[-2:]
        else:
            novos = [f for f in quadros if f.name > self.visto][-12:]   # atrasou: pega só o fim
        # a regra é avaliada a CADA quadro, não a cada tique: quando o auxiliador atrasa e lê um
        # punhado de quadros de uma vez, um pico de 3 s no meio da leva passaria batido
        for f in novos:
            self.visto = f.name
            linhas = ev.frame_messages(f, glyphs, gap)
            if not linhas:
                continue
            for ts, corpo in ev.new_tail(self.prev, linhas):
                t = seg(ts)
                if t is None:
                    continue
                kind, dados = ev.classify(corpo)
                self.agora = t if self.agora is None else max(self.agora, t)
                if kind == "damage_taken":
                    if self.pos and t - self.pos[0] <= POS_VALE_S:   # engorda o mapa de boxes
                        _, z, x, y = self.pos
                        self.dano_celula[(z, *_celula(x, y))] += dados.get("value") or 0
                if kind in ("damage_taken", "heal_other", "heal_self"):
                    self.eventos.append((t, kind, dados.get("value") or 0, dados.get("actor")))
            self.prev = linhas
            self._avalia()

    def _apita(self, motivo, caiu=False, t=None):
        """Único lugar que toca som (user, 30/09: "alguns alarmes de som descendo apitavam junto com
        o de som subindo. Apenas um alarme deve soar"). O motivo continua indo para a tela; só o
        apito espera APITO_GAP_S. `ult_apito` segue marcando qualquer alarme, porque é ele que
        segura as regras de situação por SILENCIO_S."""
        t = self.agora if t is None else t
        toca = t - self.ult_som >= APITO_GAP_S
        self.ult_apito = t
        if toca:
            self.ult_som = t
        self._anota(motivo if toca else f"{motivo} (sem apito: outro alarme acabou de soar)", t)
        self._registrar({'id':f'aviso:{t}:{motivo}', 'tipo':'aviso', 't':t, 'instante':time.time(),
                         'motivo':motivo, 'emitido':bool(toca and self.som),
                         'suprimido_por':'som_desligado' if not self.som else 'arbitragem' if not toca else None,
                         'escudo':self.escudo(), 'vida':self.vida, 'sinais':self.sinais()})
        if toca and self.som:
            threading.Thread(target=apita, args=(caiu,), daemon=True).start()
        return toca

    def _anota(self, motivo, t=None):
        t = self.agora if t is None else t
        self.historico = ([{"quando": f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}",
                            "motivo": motivo}] + self.historico)[:12]

    def _le_trilha(self, ses):
        """Posição de agora, da trilha que o motor já grava (um ponto a cada 2 s)."""
        p = pathlib.Path(ses) / "trilha.jsonl"
        try:
            tam = p.stat().st_size
        except OSError:
            return
        if tam < self.trilha_pos:      # sessão nova ou arquivo refeito
            self.trilha_pos = 0
        if tam == self.trilha_pos:
            return
        with p.open("rb") as fh:
            fh.seek(self.trilha_pos)
            bruto = fh.read()
        self.trilha_pos = tam - len(bruto.split(b"\n")[-1])   # a última linha pode estar pela metade
        for linha in bruto.decode("utf-8", "replace").splitlines()[:-1] or []:
            try:
                d = json.loads(linha)
                self.pos = (d["t"], d["z"], d["x"], d["y"])
            except (ValueError, KeyError):
                pass

    def _le_quadro(self, ses):
        """Quadro cheio mais novo (a gravação faz um a cada 4 s): barra de vida e ícone do escudo.
        Os dois saem da MESMA leitura — nada de abrir o PNG duas vezes."""
        anterior_escudo = self.escudo_on
        compartilhada = self._compartilhada()
        if compartilhada is not None:
            if self.escudo_on is True:
                self.caiu_desde = None
            elif self.escudo_on is False and anterior_escudo is True:
                self.caiu_desde = self.escudo_t
            elif self.escudo_on is None:
                self.caiu_desde = None
            return
        fs = sorted(pathlib.Path(ses).glob("f_*.png"))
        if not fs or fs[-1].name == self.visto_f:
            return
        self.visto_f = fs[-1].name
        arr = np.asarray(Image.open(fs[-1]).convert("RGB"))
        if self.regras.get("vida"):
            if not self.barra:
                self.barra = acha_barra_vida(arr)
            if self.barra:
                x0, y0, x1, y1 = self.barra
                self.vida = fracao_vida(arr[y0:y1, x0:x1])
        n = self.visto_f
        t = seg(f"{n[2:4]}:{n[4:6]}:{n[6:8]}")     # f_HHMMSS_mmm, o mesmo relógio do console
        if t is None:
            return
        tem = acha_icone_escudo(arr) is not None
        if tem:
            self.caiu_desde = None
        elif self.escudo_on:        # estava de pé no quadro anterior: a queda começa agora
            self.caiu_desde = t
        self.escudo_on, self.escudo_t = tem, t
        self.vida_t = t

    def caido_ha(self):
        """Há quantos segundos o ícone do utamo está fora da tela. None = de pé, ou não sei."""
        return None if self.escudo() is not False or self.caiu_desde is None else self.agora - self.caiu_desde

    def _box_perto(self):
        """Box pesada a menos de BOX_RAIO tiles, ou None. Só vale com posição fresca."""
        if not self.pos or not self.boxes or self.agora is None or self.agora - self.pos[0] > POS_VALE_S:
            return None
        _, z, x, y = self.pos
        for i, b in enumerate(self.boxes):
            if b["z"] == z and abs(b["x"] - x) <= BOX_RAIO and abs(b["y"] - y) <= BOX_RAIO:
                return i, b
        return None

    def _caiu(self, t, caido_s):
        """Escudo caído e confirmado: apita, com silêncio próprio. False = ficou no silêncio."""
        if t - self.ult_caiu < CAIU_SILENCIO_S:
            return False
        self.ult_caiu = t
        self._apita(f"o escudo caiu — o ícone do utamo está fora há {caido_s}s", caiu=True, t=t)
        return True

    def _avalia(self):
        if self.agora is None:
            return
        while self.eventos and self.eventos[0][0] <= self.agora - JANELA_S:
            self.eventos.popleft()
        recurso = self.observacao[3] if self.observacao and self.observacao[0]==self.pasta else {}
        fresca = 0 <= self.agora-self.escudo_t <= 6
        if not (recurso and 0 <= self.agora-recurso.get('t', -1e9) <= 6
                and 0 <= time.time()-recurso.get('processado_em', 0) <= 6):
            recurso = {}
        pronta = (recurso.get('prontidao', {}).get('magic_shield') or {}).get('pronta') if fresca else None
        caido = self.caido_ha()
        if recurso and fresca and 0 <= self.agora-recurso['t'] <= 1:
            self._registrar({'id':'observacao:'+str(recurso['id']), 'tipo':'observacao',
                't':recurso['t'], 'instante':recurso['instante'], 'vida':self.vida,
                'escudo':self.escudo(), 'caido_s':caido, 'pronta':pronta,
                'certificado':recurso.get('escudo') is not None and (recurso.get('vida') or {}).get('percentual') is not None,
                'combate':self.sinais()['dano']>0, 'dano':self.sinais()['dano'],
                'som_recente':self.som and self.agora-self.ult_som<8, 'prova':recurso.get('origem')})
        # vida baixa vem antes de tudo (user, 28/09): medido, cruza 60% ~1x por hora
        if (self.regras.get("vida") and self.vida is not None and 0 <= self.agora-self.vida_t <= 6 and self.vida <= VIDA_LIMITE
                and self.agora - self.ult_vida >= VIDA_SILENCIO_S):
            self.ult_vida = self.agora
            self._apita(f"vida em {self.vida:.0%}")
            return
        # Prontidão negativa comprovada cala pedido de recast, nunca emergência.
        # Quadro futuro/antigo ou região ilegível não certifica escudo ausente.
        if not fresca or pronta is False or self.escudo() is None:
            return
        # o escudo caiu: o ícone do utamo sumiu e CONTINUA fora, com você apanhando (user, 29/09)
        caido, lim = self.caido_ha(), self._limites()
        if (self.regras.get("escudo_caiu") and caido is not None
                and caiu_o_escudo(caido, self.sinais()["dano"], lim) and self._caiu(self.agora, caido)):
            return
        # box pesada chegando SEM escudo (user, 28/09): o aviso sai antes de entrar, para dar tempo
        # de soltar o utamo. Pede a MESMA queda confirmada do apito de escudo (29/09) — com o
        # escudo de pé, sem saber, ou numa queda que já voltou, a rota passaria apitando nas boxes.
        perto = (self._box_perto() if self.regras.get("box") and caido is not None
                 and caido >= lim["box_nu"] else None)
        if perto:
            i, b = perto
            if self.agora - self.box_ult.get(i, -10 ** 9) >= BOX_SILENCIO_S:
                self.box_ult[i] = self.agora
                # o tempo medido de escudo nesta box e o que diz se da para entrar e soltar o utamo
                # la dentro ou se ele tem que sair agora, antes de chegar (user, 30/09)
                e = b.get("escudo") or {}
                quanto = (f"o escudo dura {e['cai_em_s']}s aí dentro" if e.get("cai_em_s")
                          else f"{b['dano'] // 1000}k de dano tomado ali nas hunts anteriores")
                self._apita(f"box pesada à frente e você está sem escudo ({quanto})", caiu=True)
                return
        motivo = dispara(self.sinais(), lim, self.regras)
        if motivo and not self.escudo() and self.agora - self.ult_apito >= SILENCIO_S:
            self._apita(motivo)

    # ------------------------------------------------------------ estado

    def sinais(self):
        e = self.eventos
        dano = sum(v for _, k, v, _ in e if k == 'damage_taken'); origem = 'log_parcial'
        rows = [(t,v) for t,v in self.input_danos if self.agora is not None and 0<=self.agora-t<=JANELA_S]
        if (len(rows)>=2 and self.agora-rows[-1][0]<=3 and rows[-1][0]-rows[0][0]>=6
                and all(0<b[0]-a[0]<=4 and b[1]>=a[1] for a,b in zip(rows,rows[1:]))):
            dano = rows[-1][1]-rows[0][1]; origem = 'Input Analyser'
        return {"dano_origem":origem, "bichos": len({a for _, k, _, a in e if k == "damage_taken"}),
                "dano": dano,
                "curas_outros": sum(1 for _, k, _, _ in e if k == "heal_other"),
                "curas_eu": sum(1 for _, k, _, _ in e if k == "heal_self")}

    def escudo(self):
        """Escudo de pé: o ícone do utamo estava na tela no último quadro cheio. None = não sei —
        gravação parada, jogo atrás de outra janela ou ícone que nunca apareceu."""
        if self.escudo_on is None or self.agora is None or self.agora - self.escudo_t > ESCUDO_FRESCO_S:
            return None
        return self.escudo_on

    def estado(self):
        atraso = None
        if self.agora is not None:
            hora = time.localtime()
            atraso = max(0, hora.tm_hour * 3600 + hora.tm_min * 60 + hora.tm_sec - self.agora)
        return {"ligado": self.ligado, "nivel": self.nivel, "som": self.som, "auto": self.auto,
                "limites": self._limites(), "janela_s": JANELA_S, "silencio_s": SILENCIO_S,
                "aprendizado":self.diario.politica if self.diario else {'estado':'aguardando_observacao'},
                "aprendizado_erro":self.aprendizado_erro,
                "sinais": self.sinais(), "escudo": self.escudo(), "erro": self.erro,
                "vida": self.vida, "boxes": len(self.boxes), "hunt": self.hunt,
                "regras": self.regras, "lista_regras": [{"id": k, "nome": n, "texto": d} for k, n, d in REGRAS],
                "lendo": bool(self.agora is not None and atraso is not None and atraso <= ATRASO_MAX_S),
                "atraso_s": atraso, "historico": self.historico,
                "niveis": {n: NIVEIS[n] for n in NIVEIS}}


def apita(caiu=False):
    """Dois apitos diferentes: escudo caiu = duas notas caindo (solta de novo); perigo = três
    subindo. Nenhum deles é o da UE (duas agudas iguais + uma grave)."""
    try:
        import winsound
        for hz in ((1500, 1000) if caiu else (900, 1200, 1500)):
            winsound.Beep(hz, 110 if caiu else 90)
    except Exception:     # sem winsound (outro sistema) ou placa muda: o aviso fica só na tela
        pass


AUX = Utamo()


def linha_do_escudo(sessao):
    """[(t, ícone na tela)] dos quadros cheios da sessão — o escudo de verdade, quadro a quadro."""
    linha = []
    for f in sorted(pathlib.Path(sessao).glob("f_*.png")):
        t = seg(f"{f.name[2:4]}:{f.name[4:6]}:{f.name[6:8]}")
        if t is not None:
            linha.append((t, acha_icone_escudo(np.asarray(Image.open(f).convert("RGB"))) is not None))
    return linha


def _replay(sessao, nivel="normal", regras=None):
    """Repassa uma hunt gravada e diz onde teria apitado — é o teste e também o jeito de
    experimentar um nível novo sem precisar caçar. Lê os quadros cheios (escudo) e o console."""
    import bisect
    ses = pathlib.Path(sessao)
    glyphs, gap = ab.load_atlas()
    lim, liga = NIVEIS[nivel], (regras or PADRAO).get
    escudos = linha_do_escudo(ses)
    ts_escudo = [t for t, _ in escudos]

    def escudo_em(agora):
        """De pé / caído / None (não sei), como o Utamo.escudo() faz ao vivo."""
        i = bisect.bisect_right(ts_escudo, agora) - 1
        return None if i < 0 or agora - ts_escudo[i] > ESCUDO_FRESCO_S else escudos[i][1]

    def caido_desde(agora):
        """Desde quando o ícone está fora, olhando só os quadros até agora. None = de pé/não sei."""
        i = bisect.bisect_right(ts_escudo, agora) - 1
        if i < 0 or escudos[i][1] or agora - ts_escudo[i] > ESCUDO_FRESCO_S:
            return None
        while i > 0 and not escudos[i - 1][1]:
            i -= 1
        return ts_escudo[i] if i > 0 else None     # queda começa quando o ícone SAI de pé

    janela, apitos = collections.deque(), []
    ult_apito = ult_caiu = ult_som = -10 ** 9
    prev, agora = [], None
    for f in sorted(ses.glob("c_*.png")):
        linhas = ev.frame_messages(f, glyphs, gap)
        if not linhas:
            continue
        for ts, corpo in ev.new_tail(prev, linhas):
            t = seg(ts)
            if t is None:
                continue
            kind, dados = ev.classify(corpo)
            agora = t if agora is None else max(agora, t)
            if kind in ("damage_taken", "heal_other", "heal_self"):
                janela.append((t, kind, dados.get("value") or 0, dados.get("actor")))
        prev = linhas
        if agora is None:
            continue
        while janela and janela[0][0] <= agora - JANELA_S:
            janela.popleft()
        s = {"bichos": len({a for _, k, _, a in janela if k == "damage_taken"}),
             "dano": sum(v for _, k, v, _ in janela if k == "damage_taken"),
             "curas_outros": sum(1 for _, k, _, _ in janela if k == "heal_other"),
             "curas_eu": sum(1 for _, k, _, _ in janela if k == "heal_self")}
        desde = caido_desde(agora)
        if (liga("escudo_caiu") and desde is not None and agora - ult_caiu >= CAIU_SILENCIO_S
                and caiu_o_escudo(agora - desde, s["dano"], lim)):
            ult_caiu = ult_apito = agora
            if agora - ult_som >= APITO_GAP_S:        # um alarme por vez, como ao vivo
                ult_som = agora
                apitos.append((agora, f"o escudo caiu — o ícone do utamo está fora há {agora - desde}s"))
            continue
        motivo = dispara(s, lim, regras)
        if motivo and not escudo_em(agora) and agora - ult_apito >= SILENCIO_S:
            ult_apito = agora
            if agora - ult_som >= APITO_GAP_S:
                ult_som = agora
                apitos.append((agora, motivo))
    return apitos


def constroi_boxes(sessao, hunt):
    """Mapa de boxes a partir de uma hunt GRAVADA: dano por célula, cruzando o Server Log com a
    trilha. É como o mapa nasce para quem já tem sessões antes do auxiliador existir."""
    import bisect
    ses = pathlib.Path(sessao)
    pontos = sorted((d["t"], d["z"], d["x"], d["y"]) for d in
                    map(json.loads, (ses / "trilha.jsonl").read_text(encoding="utf-8").splitlines()))
    ts = [p[0] for p in pontos]
    glyphs, gap = ab.load_atlas()
    dano, prev, last = collections.Counter(), [], ""
    for f in sorted(ses.glob("c_*.png")):
        linhas = ev.frame_messages(f, glyphs, gap)
        if not linhas or (last and all(t < last for t, _ in linhas)):
            continue
        for tsx, corpo in ev.new_tail(prev, linhas):
            t = seg(tsx)
            last = max(last, tsx)
            kind, dados = ev.classify(corpo)
            if t is None or kind != "damage_taken":
                continue
            i = bisect.bisect_left(ts, t)
            for j in (i, i - 1):
                if 0 <= j < len(pontos) and abs(pontos[j][0] - t) <= POS_VALE_S:
                    _, z, x, y = pontos[j]
                    dano[(z, *_celula(x, y))] += dados.get("value") or 0
                    break
        prev = linhas
    return guarda_boxes(hunt, dict(dano), ses.name)


def main():
    import sys
    if len(sys.argv) > 3 and sys.argv[1] == "--boxes":
        for b in constroi_boxes(sys.argv[2], sys.argv[3]):
            print(f"  box z{b['z']} ({b['x']:.0f}, {b['y']:.0f}) · {b['dano']//1000}k de dano · {b['celulas']} células")
        print(f"mapa de boxes de {sys.argv[3]} atualizado")
    elif len(sys.argv) > 3 and sys.argv[1] == "--escudo":
        medidas = escudo_da_sessao(sys.argv[2], sys.argv[3])
        print(f"{'box':>3} {'dano':>6} {'passadas':>9} {'parada':>7} | "
              f"{'de pé':>6} {'caiu dentro':>12} {'em':>5} | {'sem escudo':>10}")
        for i, m in enumerate(medidas, 1):
            cai = f"{len(m['vidas']) / m['de_pe']:.0%}" if m["de_pe"] else "—"
            print(f"{i:>3} {m['dano'] // 1000:>5}k {m['passadas']:>9} "
                  f"{(_mediana(m['paradas']) or 0):>6}s | {m['de_pe']:>6} {cai:>12} "
                  f"{(_mediana(m['vidas']) or 0):>4}s | {m['nu']:>10}")
        tot = {k: sum(m[k] for m in medidas) for k in ("passadas", "de_pe", "nu", "nu_confirmado")}
        vidas = [v for m in medidas for v in m["vidas"]]
        print(f"{tot['passadas']} passadas · {tot['nu']} sem escudo · o escudo caiu dentro da box "
              f"{len(vidas)}x, mediana {_mediana(vidas)}s")
        print(f"o aviso de box sairia {tot['nu_confirmado']}x nesta hunt (sem escudo há "
              f"{NIVEIS['normal']['box_nu']}s ou mais, o limite do nível normal) · guardado em "
              f"{arquivo_boxes(sys.argv[3])}")
    elif len(sys.argv) > 1:
        alvo, nivel = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "normal")
        aps = _replay(alvo, nivel)
        for t, motivo in aps:
            print(f"  {t//3600:02d}:{t%3600//60:02d}:{t%60:02d}  {motivo}")
        print(f"{len(aps)} apitos no nível {nivel}")
    else:
        # os números medidos na hunt de 26/09, sem precisar dos quadros
        s = {"bichos": 3, "dano": 900, "curas_outros": 0, "curas_eu": 1}
        assert dispara(s, NIVEIS["normal"]) == "3 bichos batendo em você"
        assert dispara(s, NIVEIS["calmo"]) == "3 bichos batendo em você"
        s = {"bichos": 1, "dano": 2100, "curas_outros": 0, "curas_eu": 2}
        assert dispara(s, NIVEIS["normal"]) and not dispara(s, NIVEIS["calmo"]), "2100 hp: normal sim, calmo não"
        s = {"bichos": 1, "dano": 1300, "curas_outros": 3, "curas_eu": 0}
        assert "curava a pt" in dispara(s, NIVEIS["normal"]), "dano com turno na pt tem que apitar"
        s = {"bichos": 1, "dano": 1300, "curas_outros": 2, "curas_eu": 0}
        assert dispara(s, NIVEIS["normal"]) is None, "2 curas ainda não é turno perdido no normal"
        assert seg("06:35:27") == 23727 and seg("bagunça") is None
        # o escudo caiu (29/09): metade das quedas volta em 4 s e queda sem dano não é perigo
        assert caiu_o_escudo(8, 400, NIVEIS["normal"]), "8 s fora com dano: apita no normal"
        assert not caiu_o_escudo(4, 400, NIVEIS["normal"]), "4 s fora é o utamo que você já soltou"
        assert caiu_o_escudo(4, 400, NIVEIS["sensivel"]), "no sensível 4 s já vale"
        assert not caiu_o_escudo(60, 0, NIVEIS["calmo"]), "escudo fora sem ninguém batendo não apita"
        # o ícone do utamo, achado sozinho num quadro desenhado na mão
        quadro = np.full((40, 40, 3), 30, dtype=np.uint8)
        for y, linha in enumerate(ESCUDO_MOLDE):
            for x, c in enumerate(linha):
                if c == "#":
                    quadro[10 + y, 20 + x] = ESCUDO_OURO
        assert acha_icone_escudo(quadro) == (10, 20), "molde do escudo tem que ser achado"
        quadro[13, 20] = (30, 30, 30)      # borda furada: não é o ícone
        assert acha_icone_escudo(quadro) is None
        # o escudo dentro da box (30/09), com trilha e linha de escudo desenhadas na mão
        bx = {"z": 13, "x": 100.0, "y": 100.0, "dano": 9000}
        pontos = ([{"t": t, "z": 13, "x": 200, "y": 200} for t in range(0, 20, 2)]
                  + [{"t": t, "z": 13, "x": 100, "y": 100} for t in range(20, 60, 2)]
                  + [{"t": t, "z": 13, "x": 200, "y": 200} for t in range(60, 80, 2)])
        assert visitas_box(pontos, bx) == [(20, 58)], visitas_box(pontos, bx)
        assert visitas_box(pontos[:12], bx) == [], "passar de raspão não é parada na box"
        m = mede_escudo([(t, t < 32) for t in range(0, 80, 4)], pontos, [bx])[0]
        assert m["passadas"] == 1 and m["de_pe"] == 1 and m["vidas"] == [12], m
        m = mede_escudo([(t, False) for t in range(0, 80, 4)], pontos, [bx])[0]
        assert m["nu"] == 1 and m["nu_confirmado"] == 1 and m["vidas"] == [], m
        m = mede_escudo([(t, True) for t in range(0, 80, 4)], pontos, [bx])[0]
        assert m["de_pe"] == 1 and m["vidas"] == [], "escudo que não caiu lá dentro não tem tempo"
        g = {"13,25,25": {"passadas": 10, "de_pe": 8, "nu": 2, "vidas": [8, 10, 12]}}
        assert escudo_da_box(g, bx) == {"passadas": 10, "de_pe": 8, "nu": 2,
                                        "cai_em_s": 10, "cai_pct": 0.38}, escudo_da_box(g, bx)
        assert escudo_da_box(g, {"z": 12, "x": 100.0, "y": 100.0}) is None, "outro andar, outra box"
        # um alarme por vez (user, 30/09): vida (som subindo) e escudo caiu (som descendo) no
        # mesmo segundo tocavam os dois juntos
        u = Utamo()
        u.som, u.agora = False, 1000
        assert u._apita("vida em 55%"), "o primeiro alarme toca"
        assert not u._apita("o escudo caiu", caiu=True), "o segundo no mesmo segundo só vai para a tela"
        assert "sem apito" in u.historico[0]["motivo"], "e a tela diz que ele não apitou"
        u.agora = 1000 + APITO_GAP_S
        assert u._apita("o escudo caiu", caiu=True), "passado o gap, volta a tocar"
        print("auxiliares: regra do Utamo Vita ok (rode com uma sessão para ver os apitos dela)")
