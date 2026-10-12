"""Sinais da hunt: o que separa cacar de andar, e de ir ao depot (user, 22/09).

Toda decisao pede pelo menos DUAS confirmacoes independentes (user, 22/09). As fontes sao tres,
e cada uma erra sozinha numa das sessoes reais:

  LOG    Server Log / aba Loot: matar de verdade (XP, loot, XP dos membros da pt) e dano causado.
         Erra: na sessao de 21/09 manha o console so mostrou o Loot ate 07:45 (zero dano lido).
  LUGAR  minimapa: andar em circulo num raio pequeno, nao em linha reta.
         Erra: parado esperando a pt tambem da raio pequeno -> exige percurso minimo.
  PILHA  Battle List: monte de bicho junto, sustentado.
         Erra: solo (Book World) caca com 1-3 na lista; e passar pela Livraria de Gelo enche a
         lista sem matar nada (foi assim que o programa abriu a hunt as 06:24:45 de 22/09).

Os limiares sairam da medida janela a janela das tres sessoes de 21 e 22/09 (scratchpad
mede_sinais.py); os numeros de cada uma estao no comentario do limiar.

Tempo: tudo em segundos desde a meia-noite do dia da sessao (o mesmo lap_watch.fsec).
Amostra da trilha: {"t","z","x","y","battle"} (trilha.jsonl do ao_vivo). Sem trilha, o chamador
passa o que tiver do dead reckoning (z=None): os sinais de LUGAR continuam, area e andar nao.

Quem le (ao_vivo, tela):
  amostras(sessao, t0, t1)                    trilha.jsonl como lista de amostras
  linha_do_tempo(pontos, eventos, inicio_hunt, janelas)
                                              {"area","trechos","marcos","refis"} da sessao
  especies_vistas(eventos, pontos, area, inicio_hunt)
                                              por especie: onde e quando foi vista
  classifica_volta(lap, refis, medianas)      ("volta"|"deslocamento"|"refil", motivo)
Os `eventos` sao os do events_build (t em segundos); quando so interessam as areas, basta ler
areas.jsonl da sessao, que o lap_watch grava.
"""
import bisect
import collections
import json
import math
import statistics

import events_build as ev

JANELA_S = 90         # janela avaliada (a mesma de sempre)
MIN_JANELA_S = 30     # menos que isso nao e evidencia sustentada
CONFIRMA_S = 20       # as 2 confirmacoes tem que se manter por isto antes de valer

# LOG: cacando, a janela tem 8 a 43 sinais de kill por minuto (22/09 pt, 21/09 solo e 21/09 pt);
# andando/esperando, exatamente 0. 4/min ja separa com folga e aguenta box lento.
KILL_MIN = 4.0
KILL_ABS = 5          # e pelo menos tantos na janela (janela curta nao passa por acaso)

# LUGAR: volta da Fogo/Book tem raio 30-90 e percurso 150-310 tiles por janela; indo para a hunt
# o raio foi 700-1000 (teleporte) e parado esperando a pt o percurso foi 0-3.
RAIO_MAX = 90
PERCURSO_MIN = 60
RETO_MAX = 0.45       # liquido/percurso: em circulo da 0,1-0,4; andando para um lugar, 0,5-1,0
SALTO_TILES = 30      # entre amostras de 2 s: teleporte/escada, corta a janela de LUGAR
MIN_DEPOIS_CORTE_S = 30

# PILHA: cacando em pt a Battle List fica com >=3 em 81-98% das amostras (mediana 4,5-11); indo
# para a hunt deu no maximo 56% com mediana 3. Solo nao passa nunca (mediana 1-3) — e por isso
# que PILHA sozinha nunca abre hunt.
PILHA_FRACAO = 0.75
PILHA_MEDIANA = 4
PILHA_VAZIA = 0.15    # refil/depot: 0% nas tres sessoes

# PAROU: sem kill nenhum e (longe da ancora | Battle List vazia | mensagem de subarea).
PARADO_KILL_MIN = 1.0
LONGE_TILES = 200     # o refil de 22/09 afastou ~980 tiles da ancora da volta
MIN_JANELA_PAROU_S = 60

KILL_KINDS = ("xp_gain", "loot", "xp_player")   # o seu XP, o loot nomeado, o XP do membro da pt


def seg(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def _fsec(nome):   # c_HHMMSS_mmm.png -> segundos (o mesmo lap_watch.fsec, sem importar de volta)
    return int(nome[2:4]) * 3600 + int(nome[4:6]) * 60 + int(nome[6:8])


# --------------------------------------------------------------------- leitura


def amostras(sessao, t0=None, t1=None):
    """Trilha do ao_vivo (trilha.jsonl) como lista de dicts, ordenada. [] se ainda nao existe."""
    p = sessao / "trilha.jsonl"
    if not p.exists():
        return []
    out = []
    for linha in p.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            a = json.loads(linha)
        except ValueError:      # ultima linha pela metade (o ao_vivo esta escrevendo)
            continue
        if (t0 is None or a["t"] >= t0) and (t1 is None or a["t"] <= t1):
            out.append(a)
    return out


class Chat:
    """Le so os c_ novos da sessao e guarda os eventos recentes (ts em segundos).

    O lap_watch chama isto a cada volta do laco: reler tudo a cada 5 s custaria a janela inteira.
    """

    def __init__(self, guarda_s=900):
        self.guarda_s = guarda_s
        self.eventos = []
        self._prev, self._visto, self._ultimo_ts = [], set(), ""

    def atualiza(self, sessao, glyphs, gap, desde=0):
        # `desde` so vale na PRIMEIRA leitura: o vigia relancado no meio de uma hunt de 2 h gastaria
        # minutos relendo o chat inteiro antes da 1a decisao. Depois disso nada e pulado — pular
        # quadro atrasado perderia os ultimos kills antes de um refil.
        corte = desde - 60 if desde and not self._ultimo_ts else 0
        novos = []
        for f in sorted(sessao.glob("c_*.png")):
            if f.name in self._visto:
                continue
            self._visto.add(f.name)
            if _fsec(f.name) < corte:
                continue
            try:
                cur = ev.frame_messages(f, glyphs, gap)
            except OSError:     # quadro pego no meio da gravacao
                continue
            if not cur or (self._ultimo_ts and all(t < self._ultimo_ts for t, _ in cur)):
                continue
            for ts, corpo in ev.new_tail(self._prev, cur):
                kind, dados = ev.classify(corpo)
                t = seg(ts)
                if t >= corte:
                    novos.append({"t": t, "ts": ts, "kind": kind, "body": corpo, **dados})
                self._ultimo_ts = max(self._ultimo_ts, ts)
            self._prev = cur
        self.eventos += novos
        if self.eventos:
            corte = self.eventos[-1]["t"] - self.guarda_s
            self.eventos = [e for e in self.eventos if e["t"] >= corte]
        return novos


# ----------------------------------------------------------------- sinais crus


CAMPO_ESPECIE = {"damage_dealt": "target", "damage_taken": "actor", "loot": "target",
                 "damage_dealt_player": "target", "damage_taken_player": "actor"}


def especie_do_evento(e):
    """Nome do bicho que o evento cita (sem artigo), ou None."""
    alvo = e.get(CAMPO_ESPECIE.get(e["kind"], ""))
    return alvo.lower().removeprefix("a ").removeprefix("an ").removeprefix("the ") if alvo else None


def sinal_log(eventos, t0, t1):
    """Server Log na janela: kills, dano causado, mensagens de subarea, especies vistas."""
    janela = [e for e in eventos if t0 <= e["t"] <= t1]
    mins = max(t1 - t0, 1) / 60
    # um kill acende varios sinais (seu XP + XP de cada membro + loot): conta SEGUNDO com sinal
    segundos = {e["t"] for e in janela if e["kind"] in KILL_KINDS}
    especies = collections.Counter()
    for e in janela:
        nome = especie_do_evento(e)
        if nome:
            especies[nome] += 1
    return {
        "kills": len(segundos),
        "kills_min": len(segundos) / mins,
        "dano_min": sum(e.get("value", 0) for e in janela if e["kind"] == "damage_dealt") / mins,
        "dano_recebido_min": sum(e.get("value", 0) for e in janela if e["kind"] == "damage_taken") / mins,
        "areas": [{"t": e["t"], "acao": e["acao"], "area": e["area"]} for e in janela if e["kind"] == "area"],
        "especies": dict(especies),
        "kill_ts": sorted(segundos),
    }


def sinal_lugar(pontos, t0, t1):
    """Minimapa na janela, CORTADO no ultimo salto (teleporte/escada).

    Sem o corte, os 90 s depois do teleporte carregam um raio de mil tiles e o lugar nunca
    confirmaria — foi o que aconteceu ao entrar no Book World em 21/09 as 19:48:29.
    """
    p = [a for a in pontos if t0 <= a["t"] <= t1]
    d = {"pontos": len(p), "corte": None, "corte_desde": None, "raio": None, "percurso": 0.0,
         "liquido": 0.0, "reto": None, "andares": [], "salto": 0.0}
    if len(p) < 2:
        return d
    saltos = [(p[i - 1]["t"], p[i]["t"], math.dist((p[i - 1]["x"], p[i - 1]["y"]), (p[i]["x"], p[i]["y"])))
              for i in range(1, len(p))]
    d["salto"] = max(s for _, _, s in saltos)
    ult = [(antes, depois) for antes, depois, s in saltos if s > SALTO_TILES]
    if ult:
        # corte = 1o ponto do lugar novo (para medir o raio); corte_desde = ultimo ponto do lugar
        # velho — o rastreio some durante o teleporte e a caca comeca antes do 1o ponto novo
        d["corte"], d["corte_desde"] = ult[-1][1], ult[-1][0]
        p = [a for a in p if a["t"] >= ult[-1][1]]
    d["pontos"], d["andares"] = len(p), sorted({a["z"] for a in p if a.get("z") is not None})
    if len(p) < 2 or p[-1]["t"] - p[0]["t"] < MIN_DEPOIS_CORTE_S:
        d["janela_s"] = p[-1]["t"] - p[0]["t"] if len(p) > 1 else 0
        return d
    cx, cy = statistics.median(a["x"] for a in p), statistics.median(a["y"] for a in p)
    d["raio"] = max(math.dist((a["x"], a["y"]), (cx, cy)) for a in p)
    d["percurso"] = sum(math.dist((p[i - 1]["x"], p[i - 1]["y"]), (p[i]["x"], p[i]["y"]))
                        for i in range(1, len(p)))
    d["liquido"] = math.dist((p[0]["x"], p[0]["y"]), (p[-1]["x"], p[-1]["y"]))
    d["reto"] = d["liquido"] / d["percurso"] if d["percurso"] else 1.0
    d["janela_s"] = p[-1]["t"] - p[0]["t"]
    return d


def sinal_pilha(contagens):
    """Battle List na janela. contagens = lista de inteiros (trilha["battle"] ou lw.battle_count)."""
    if not contagens:
        return {"amostras": 0, "fracao_ge3": None, "mediana": None, "pico": None, "pulls": 0}
    pulls, armado = 0, True
    for n in contagens:
        if n <= 2:
            armado = True
        elif n >= 6 and armado:
            pulls, armado = pulls + 1, False
    return {"amostras": len(contagens),
            "fracao_ge3": sum(1 for n in contagens if n >= 3) / len(contagens),
            "mediana": statistics.median(contagens), "pico": max(contagens), "pulls": pulls}


# -------------------------------------------------------------------- decisoes


def confirmacoes(log, lugar, pilha):
    """Quais das tres fontes dizem "isto e hunt". Devolve (quantas, {fonte: bool}, texto)."""
    c = {
        "log": log["kills_min"] >= KILL_MIN and log["kills"] >= KILL_ABS,
        "lugar": (lugar["raio"] is not None and lugar["raio"] <= RAIO_MAX
                  and lugar["percurso"] >= PERCURSO_MIN and lugar["reto"] <= RETO_MAX),
        "pilha": (pilha["fracao_ge3"] is not None and pilha["fracao_ge3"] >= PILHA_FRACAO
                  and pilha["mediana"] >= PILHA_MEDIANA),
    }
    txt = (f"log {log['kills']} kills ({log['kills_min']:.1f}/min, min {KILL_MIN:.0f})"
           f" · lugar raio {_n(lugar['raio'])} percurso {_n(lugar['percurso'])} reto {_f(lugar['reto'])}"
           f" · pilha {_p(pilha['fracao_ge3'])} mediana {_n(pilha['mediana'])}")
    return sum(c.values()), c, txt


def comecou(log, lugar, pilha):
    """Hunt comecou? Precisa do LOG (matar de verdade) mais uma segunda fonte (user, 22/09).

    O LOG e obrigatorio porque lugar+pilha juntos acontecem em cidade: em 21/09 as 09:02 o char
    voltava para Carlin dando a volta com a Battle List cheia de player, sem matar nada.
    Devolve (bool, {fonte: bool}, texto para o log de decisoes).
    """
    n, c, txt = confirmacoes(log, lugar, pilha)
    return bool(c["log"] and n >= 2), c, txt


def _n(v):
    return "-" if v is None else f"{v:.0f}"


def _f(v):
    return "-" if v is None else f"{v:.2f}"


def _p(v):
    return "-" if v is None else f"{v:.0%}"


GAP_KILL_S = 45   # dois kills mais afastados que isto nao sao a mesma sequencia de caca


def inicio_retroativo(kill_ts, t_det, piso, gap_max=GAP_KILL_S):
    """Onde a caca comecou, andando para tras a partir da confirmacao.

    A confirmacao so fecha depois de ~90 s de evidencia sustentada; abrir a volta no instante em
    que ela fechou jogaria fora o comeco da hunt (no Book World seriam 100 s dos 108 da volta 1).
    Volta enquanto os kills estiverem encadeados (gap <= gap_max) e nunca antes de `piso` — o
    ultimo salto de lugar, que e a entrada nesta cave.
    """
    ts = sorted(t for t in kill_ts if piso <= t <= t_det)
    if not ts:
        return None
    i = len(ts) - 1
    while i > 0 and ts[i] - ts[i - 1] <= gap_max:
        i -= 1
    return ts[i]


def piso_do_inicio(lugar, t_min):
    """Chao do inicio_retroativo: o ultimo salto de lugar da janela, senao o comeco dos dados."""
    return max(t_min, lugar.get("corte_desde") or 0)


def parou(log, pilha, dist_ancora=None):
    """Refil/pausa: parou de matar E alguma segunda confirmacao (longe, lista vazia, subarea)."""
    sem_kill = log["kills_min"] < PARADO_KILL_MIN
    outras = {
        "longe": dist_ancora is not None and dist_ancora > LONGE_TILES,
        "lista_vazia": pilha["fracao_ge3"] is not None and pilha["fracao_ge3"] <= PILHA_VAZIA,
        "subarea": bool(log["areas"]),
    }
    quais = [k for k, v in outras.items() if v]
    txt = (f"{log['kills']} kills ({log['kills_min']:.1f}/min) · lista >=3 em {_p(pilha['fracao_ge3'])}"
           f" · {_n(dist_ancora)} tiles da ancora · {', '.join(quais) or 'nenhuma 2a confirmacao'}")
    return bool(sem_kill and quais), {"sem_kill": sem_kill, **outras}, txt


# ------------------------------------------------------- linha do tempo (pos-hoc)


def area_hunt(pontos, janelas):
    """Onde a hunt acontece: centro, raio e andares das amostras dentro das voltas.

    janelas = [(inicio_s, fim_s)] das voltas de verdade. Sem janelas, usa tudo.
    """
    p = [a for a in pontos if not janelas or any(i <= a["t"] <= f for i, f in janelas)]
    if not p:
        return None
    cx, cy = statistics.median(a["x"] for a in p), statistics.median(a["y"] for a in p)
    ds = sorted(math.dist((a["x"], a["y"]), (cx, cy)) for a in p)
    return {"x": cx, "y": cy,
            # p95 e nao o maximo: um ponto perdido do rastreio nao estica a area da hunt
            "raio": ds[int(0.95 * (len(ds) - 1))],
            "andares": sorted({a["z"] for a in p if a.get("z") is not None})}


def _dentro(a, area, folga=1.5):
    return math.dist((a["x"], a["y"]), (area["x"], area["y"])) <= max(area["raio"] * folga, 60)


def linha_do_tempo(pontos, eventos, inicio_hunt=None, janelas=(), min_trecho_s=60):
    """Sessao dividida em trechos, com os marcos que o user pediu (user, 22/09).

    Devolve {"area", "trechos", "marcos", "refis"}:
      trechos: [{"tipo","inicio","fim","dur_s","andares","areas","kills","raio","percurso"}]
               tipo = "cidade" (fora da area da hunt), "espera" (dentro, antes do inicio),
                      "hunt" (dentro, depois do inicio) ou "refil" (fora, depois do inicio)
      marcos:  [{"tipo","t"}] com "entrada_hunt" (entrou na area para ficar), "entrada_cave"
               (1a descida para o andar mais fundo da hunt) e "inicio_hunt"
      refis:   os trechos de tipo "refil", so com inicio/fim/dur_s/areas
    """
    area = area_hunt(pontos, janelas)
    if not pontos or not area:
        return {"area": area, "trechos": [], "marcos": [], "refis": []}
    evs = sorted(eventos, key=lambda e: e["t"])
    trechos, atual = [], None
    for a in pontos:
        dentro = _dentro(a, area)
        if atual is None or atual["dentro"] != dentro:
            atual = {"dentro": dentro, "inicio": a["t"], "fim": a["t"], "pts": [a]}
            trechos.append(atual)
        else:
            atual["fim"], _ = a["t"], atual["pts"].append(a)
    # trecho curto = passagem (o rastreio perde um ponto): funde no vizinho
    juntos = []
    for t in trechos:
        if juntos and (t["fim"] - t["inicio"] < min_trecho_s or juntos[-1]["dentro"] == t["dentro"]):
            juntos[-1]["fim"], juntos[-1]["pts"] = t["fim"], juntos[-1]["pts"] + t["pts"]
        else:
            juntos.append(t)
    saida = []
    for t in juntos:
        log = sinal_log(evs, t["inicio"], t["fim"])
        lugar = sinal_lugar(t["pts"], t["inicio"], t["fim"])
        # "depois do inicio" pelo meio do trecho: o inicio da hunt cai bem na borda entre dois
        # trechos (22/09) ou 3 s depois do 1o quadro da sessao (21/09 manha)
        depois = inicio_hunt is not None and (t["inicio"] + t["fim"]) / 2 >= inicio_hunt
        saida.append({
            "tipo": ("hunt" if depois else "espera") if t["dentro"] else ("refil" if depois else "cidade"),
            "inicio": t["inicio"], "fim": t["fim"], "dur_s": t["fim"] - t["inicio"],
            "andares": sorted({a["z"] for a in t["pts"] if a.get("z") is not None}),
            "areas": [a["area"] for a in _areas_unicas(log["areas"])],
            "kills": log["kills"], "raio": lugar["raio"], "percurso": lugar["percurso"],
        })
    marcos, t_entrada = [], pontos[0]["t"]
    if inicio_hunt is not None:
        marcos.append({"tipo": "inicio_hunt", "t": inicio_hunt})
        # entrada da hunt = comeco do 1o trecho dentro da area que ainda estava aberto no inicio
        # (em 22/09 ele entrou na livraria, voltou para a cidade e so entrou para valer as 06:35:46)
        entrada = next((t for t in saida if t["tipo"] in ("hunt", "espera") and t["fim"] >= inicio_hunt), None)
        if entrada:
            t_entrada = entrada["inicio"]
            marcos.append({"tipo": "entrada_hunt", "t": t_entrada})
    fundo = max(area["andares"], default=None)   # z maior = mais fundo
    if fundo is not None and len(area["andares"]) > 1:
        desce = next((a["t"] for a in pontos
                      if a["t"] >= t_entrada and a.get("z") == fundo and _dentro(a, area)), None)
        if desce is not None:
            marcos.append({"tipo": "entrada_cave", "t": desce, "z": fundo})
    refis = [{"inicio": t["inicio"], "fim": t["fim"], "dur_s": t["dur_s"], "areas": t["areas"],
              "kills": t["kills"]} for t in saida if t["tipo"] == "refil"]
    return {"area": area, "trechos": saida, "marcos": sorted(marcos, key=lambda m: m["t"]), "refis": refis}


def identifica_house(trechos, pontos, house):
    """Marca somente a área pessoal confirmada, em coordenadas absolutas do mundo."""
    if not house or not pontos:
        return trechos
    def dentro(p):
        return (p.get('z') == house['z'] and
                abs(p['x'] - house['x']) <= house.get('raio', 3) and
                abs(p['y'] - house['y']) <= house.get('raio', 3))
    pts = sorted(pontos, key=lambda p: p['t'])
    saida = []
    for trecho in trechos:
        selecao = [p for p in pts if trecho['inicio'] <= p['t'] <= trecho['fim']]
        if not selecao:
            saida.append(dict(trecho))
            continue
        inicio, casa = trecho['inicio'], dentro(selecao[0])
        for p in selecao[1:] + [dict(selecao[-1], t=trecho['fim'])]:
            nova = dentro(p)
            if nova != casa or p['t'] == trecho['fim']:
                if p['t'] > inicio:
                    saida.append(dict(trecho, inicio=inicio, fim=p['t'], dur_s=p['t']-inicio,
                                      tipo='house' if casa else trecho['tipo']))
                inicio, casa = p['t'], nova
    return saida


def _areas_unicas(areas, gap_s=15):
    """Mensagem de subarea repete (o cliente manda de novo a cada passo na borda): so a 1a de cada."""
    out = []
    for a in areas:
        if not out or (out[-1]["area"], out[-1]["acao"]) != (a["area"], a["acao"]) or a["t"] - out[-1]["t"] > gap_s:
            out.append(a)
    return out


def especies_vistas(eventos, pontos, area, inicio_hunt):
    """Por especie: onde e quando ela apareceu, para o filtro do agente 2 (user, 22/09 item 3).

    {especie: {"n", "primeira", "ultima", "dentro", "fora", "antes_inicio", "depois_inicio"}}
    "fora" e "antes_inicio" altos = bicho do caminho (icecold book, squid warden de 22/09), nao da hunt.
    """
    pontos = sorted(pontos, key=lambda a: a["t"])
    ts = [a["t"] for a in pontos]
    out = {}
    for e in sorted(eventos, key=lambda e: e["t"]):
        nome = especie_do_evento(e)
        if not nome:
            continue
        d = out.setdefault(nome, {"n": 0, "primeira": e["t"], "ultima": e["t"],
                                  "dentro": 0, "fora": 0, "antes_inicio": 0, "depois_inicio": 0})
        d["n"] += 1
        d["ultima"] = e["t"]
        d["antes_inicio" if inicio_hunt is not None and e["t"] < inicio_hunt else "depois_inicio"] += 1
        if area and ts:
            i = bisect.bisect_left(ts, e["t"])
            perto = min((j for j in (i - 1, i) if 0 <= j < len(ts)), key=lambda j: abs(ts[j] - e["t"]),
                        default=None)
            if perto is not None and abs(ts[perto] - e["t"]) <= 10:
                d["dentro" if _dentro(pontos[perto], area) else "fora"] += 1
    return out


def classifica_volta(lap, refis=(), medianas=None):
    """Volta de verdade, deslocamento ou refil (user, 22/09 item 2).

    lap = o dict que o lap_watch grava (precisa de inicio/fim em "HH:MM:SS", dur_s, kills_total,
    raio_max_tiles, percurso_tiles, fechada_por). medianas = {"kills","raio"} das voltas boas ja
    fechadas (None = usa os absolutos). Devolve (tipo, motivo).
    """
    i, f = seg(lap["inicio"]), seg(lap["fim"])
    if any(r["inicio"] < f and i < r["fim"] for r in refis):
        return "refil", "cai dentro de um refil detectado"
    kills, raio = lap.get("kills_total") or 0, lap.get("raio_max_tiles") or 0
    # sem voltas boas ainda (a 1a volta da sessao) os absolutos sao frouxos de proposito: so
    # descarta o que nao matou quase nada; da 2a em diante a propria hunt da a referencia
    k_ref = (medianas or {}).get("kills") or 8
    r_ref = (medianas or {}).get("raio") or 70
    if kills <= 0.25 * k_ref:
        return "deslocamento", f"{kills} kills, menos de 1/4 da mediana das voltas ({k_ref:.0f})"
    if lap.get("fechada_por", "").startswith("tempo maximo") and raio > 2 * r_ref:
        return "deslocamento", f"fechou no teto de tempo com raio {raio:.0f} (mediana {r_ref:.0f})"
    return "volta", ""


def _demo():
    """Confere os limiares contra os numeros medidos nas 3 sessoes reais (22/09)."""
    def L(kills, mins=1.5, dano=0, areas=()):
        return {"kills": kills, "kills_min": kills / mins, "dano_min": dano, "dano_recebido_min": 0,
                "areas": list(areas), "especies": {}, "kill_ts": list(range(kills))}

    def U(raio, perc, liq, corte=None):
        return {"pontos": 45, "corte": corte, "corte_desde": corte, "raio": raio, "percurso": perc,
                "liquido": liq, "reto": liq / perc if perc else 1.0, "andares": [12],
                "salto": 0.0, "janela_s": 90}

    def P(frac, med):
        return {"amostras": 45, "fracao_ge3": frac, "mediana": med, "pico": 10, "pulls": 1}

    # 22/09 06:24:45 — o falso comeco: andar pela cidade da volta parecida com rotacao (lugar
    # sozinho confirma), mas sem kill nao abre hunt
    ok, c, _ = comecou(L(0), U(70, 198, 74), P(0.52, 3))
    assert not ok and not c["log"] and not c["pilha"], c
    # 21/09 09:02 voltando para Carlin: lugar + pilha (player na Battle List) sem matar nada
    ok, c, _ = comecou(L(1, 1.5), U(50, 200, 50), P(0.92, 5))
    assert not ok and c["lugar"] and c["pilha"], c
    # 22/09 06:36:40 — hunt de verdade: log + pilha
    ok, c, _ = comecou(L(8), U(64, 222, 106), P(0.95, 5))
    assert ok and c["log"] and c["pilha"] and not c["lugar"], c
    # 21/09 Book World solo: pilha nunca confirma, log + lugar sim
    ok, c, _ = comecou(L(36, 1.5), U(37, 215, 18), P(0.42, 2))
    assert ok and c["log"] and c["lugar"] and not c["pilha"], c
    # 22/09 06:30:40 — parado esperando a pt dentro da livraria: raio 1, percurso 1
    ok, _, _ = comecou(L(0), U(1, 1, 1), P(0.0, 2))
    assert not ok
    # 21/09 manha: console so com a aba Loot (sem dano) e pt x4 -> as tres fontes
    ok, c, _ = comecou(L(16, 1.5), U(53, 155, 57), P(1.0, 11))
    assert ok and all(c.values()), c
    # refil de 22/09 (08:04): sem kill, longe e lista vazia
    ok, q, _ = parou(L(0), P(0.0, 2), dist_ancora=976)
    assert ok and q["longe"] and q["lista_vazia"], q
    # meio da hunt nao pode virar refil
    ok, _, _ = parou(L(15), P(0.9, 8), dist_ancora=40)
    assert not ok
    # retroativo: a janela confirmou as 06:36:48 mas a sequencia de kills comeca as 06:35:44
    ks = [23744, 23754, 23758, 23771, 23775, 23808]
    assert inicio_retroativo(ks, 23808, 23700) == 23744
    # kill de antes do teleporte nao conta (o piso manda)
    assert inicio_retroativo(ks, 23808, piso_do_inicio(U(50, 200, 40, corte=23750), 23700)) == 23754
    # kill solto, separado por mais de 45 s, fica de fora
    assert inicio_retroativo([23000] + ks, 23808, 22000) == 23744
    lap = {"inicio": "06:24:45", "fim": "06:32:45", "dur_s": 480, "kills_total": 0,
           "raio_max_tiles": 265, "percurso_tiles": 655, "fechada_por": "tempo maximo (8min)"}
    assert classifica_volta(lap, medianas={"kills": 30, "raio": 60})[0] == "deslocamento"
    assert classifica_volta(lap)[0] == "deslocamento"          # 1a volta da sessao, sem referencia
    boa = dict(lap, kills_total=34, raio_max_tiles=60, fechada_por="retorno ao ponto de partida")
    assert classifica_volta(boa, medianas={"kills": 30, "raio": 60})[0] == "volta"
    assert classifica_volta(boa)[0] == "volta"
    # 22/09 volta 3 (06:35:27-06:43:27): fechou no teto, mas ja era caca — 62 kills, raio normal
    assert classifica_volta(dict(lap, kills_total=62, raio_max_tiles=65),
                            medianas={"kills": 30, "raio": 60})[0] == "volta"
    assert classifica_volta(boa, refis=[{"inicio": 23000, "fim": 24000}])[0] == "refil"
    print("sinais: limiares batem com as 3 sessoes")


if __name__ == "__main__":
    _demo()
