"""Encontra o PROBLEMA PRIMARIO de cada box e ordena pelo ganho de corrigir.

A pergunta que este modulo responde nao e "o que deu errado" (varias coisas dao
errado sempre), e sim: **qual correcao devolve mais para o time**.

Cada detector devolve uma ocorrencia com:
  severidade_s : custo estimado em SEGUNDOS DE HUNT (moeda comum)
  evidencia    : numeros crus, para o card e para o coach
  quando       : instante do pior momento (o frame que vira o print)
  tipo_coach   : como enquadrar a imagem (posicao / lure / cura)

Moeda comum = segundos. Justificativa: numa pt o que custa e tempo — HP perdido
vira tempo de cura, cura atrasada vira risco de morte (que custa a volta inteira),
bicho nao puxado vira kill perdido (tempo de spawn jogado fora).
"""
import collections

# quanto "tempo de hunt" vale cada coisa (calibrar com dados reais da pt)
SEG_POR_HP_EK = 0.0008      # 1k de HP no EK ~ 0,8s de cura/risco
SEG_POR_KILL_PERDIDO = 6.0  # um bicho que nao entrou na box
SEG_POR_MORTE = 300.0       # morte de membro = volta perdida + recovery


def _to_s(ts):
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def cura_atrasada(ev, box, ek, limiar_dano=2500, janela=6):
    """EK levou uma pancada grande e a sua cura demorou (ou nao veio).

    Mede o intervalo entre o dano acumulado no EK passar de `limiar_dano`
    e a sua proxima linha de cura nele.
    """
    dano = [(_to_s(e["ts"]), e.get("value") or 0) for e in ev
            if e["kind"] == "damage_taken_player" and e.get("victim") == ek]
    curas = sorted(_to_s(e["ts"]) for e in ev
                   if e["kind"] in ("healed_player", "heal_player")
                   and e.get("victim") == ek)
    out, acc, t_ini = [], 0, None
    for t, v in sorted(dano):
        if t_ini is None:
            t_ini = t
        acc += v
        if acc >= limiar_dano:
            prox = next((c for c in curas if c >= t_ini), None)
            atraso = (prox - t_ini) if prox else janela * 2
            if atraso >= 2:
                out.append({
                    "tipo": "cura_atrasada",
                    "tipo_coach": "cura",
                    "quando": t,
                    "severidade_s": acc * SEG_POR_HP_EK + max(0, atraso - 2) * 1.5,
                    "evidencia": {"hp_perdido_ek": acc, "atraso_s": atraso},
                    "texto": f"EK perdeu {acc:,} HP e sua cura levou {atraso}s",
                })
            acc, t_ini = 0, None
    return out


def fora_de_alcance(ev, box, ek, pos, alcance=7):
    """Voce estava longe demais do EK justamente quando ele apanhava."""
    dano_ek = [(_to_s(e["ts"]), e.get("value") or 0) for e in ev
               if e["kind"] == "damage_taken_player" and e.get("victim") == ek]
    out = []
    for t, v in dano_ek:
        d = pos.get(t, {}).get(ek)
        if d is not None and d > alcance:
            out.append({
                "tipo": "fora_de_alcance",
                "tipo_coach": "posicao",
                "quando": t,
                "severidade_s": v * SEG_POR_HP_EK + (d - alcance) * 0.8,
                "evidencia": {"dist_tiles": d, "hp_ek": v},
                "texto": f"EK apanhando com voce a {d:.0f} tiles (alcance {alcance})",
            })
    return out


def turno_gasto_em_si(ev, box, ek):
    """Curas em voce mesmo enquanto o EK precisava: turno de cura desperdicado."""
    self_heal = [_to_s(e["ts"]) for e in ev if e["kind"] == "heal_self"]
    dano_ek = collections.Counter()
    for e in ev:
        if e["kind"] == "damage_taken_player" and e.get("victim") == ek:
            dano_ek[_to_s(e["ts"])] += e.get("value") or 0
    out = []
    for t in self_heal:
        perto = sum(v for tt, v in dano_ek.items() if abs(tt - t) <= 2)
        if perto >= 1500:
            out.append({
                "tipo": "turno_em_si",
                "tipo_coach": "posicao",
                "quando": t,
                "severidade_s": perto * SEG_POR_HP_EK,
                "evidencia": {"hp_ek_no_momento": perto},
                "texto": f"voce curou a si com o EK levando {perto:,} HP no mesmo instante",
            })
    return out


def bicho_perdido(ev, box, vistos_fora):
    """Bicho apareceu em tela e a box fechou sem ele."""
    out = []
    for nome, t in vistos_fora:
        out.append({
            "tipo": "lure_incompleto",
            "tipo_coach": "lure",
            "quando": t,
            "severidade_s": SEG_POR_KILL_PERDIDO,
            "evidencia": {"criatura": nome},
            "texto": f"{nome} ficou fora da box",
        })
    return out


def apanhando_sem_necessidade(ev, box, pos, limite_bichos=4):
    """Voce parado com muitos bichos em cima: dano que nao precisava tomar."""
    out = []
    for t, viz in pos.items():
        n = viz.get("_monstros_adjacentes", 0)
        if n >= limite_bichos and viz.get("_parado"):
            dano = sum(e.get("value") or 0 for e in ev
                       if e["kind"] == "damage_taken" and abs(_to_s(e["ts"]) - t) <= 2)
            if dano > 800:
                out.append({
                    "tipo": "aggro_evitavel",
                    "tipo_coach": "posicao",
                    "quando": t,
                    "severidade_s": dano * SEG_POR_HP_EK * 0.6,
                    "evidencia": {"bichos": n, "dano": dano},
                    "texto": f"parado com {n} bichos em cima, {dano:,} de dano evitavel",
                })
    return out


def mana_seca(ev, box, ek, mana_pct=None, piso=15):
    """Voce ficou sem mana para curar — o pior estado possivel para o ED."""
    out = []
    faltou = [_to_s(e["ts"]) for e in ev
              if e["kind"] == "raw" and "not have enough mana" in e.get("body", "")]
    for t in faltou:
        out.append({
            "tipo": "mana_seca", "tipo_coach": "cura", "quando": t,
            "severidade_s": 8.0,
            "evidencia": {"motivo": "sem mana no cast"},
            "texto": "voce tentou curar e nao tinha mana",
        })
    for t, pc in (mana_pct or {}).items():
        if pc <= piso:
            out.append({
                "tipo": "mana_seca", "tipo_coach": "cura", "quando": t,
                "severidade_s": 4.0,
                "evidencia": {"mana_pct": pc},
                "texto": f"mana em {pc}% no meio da box",
            })
    return out


def sobrecura(ev, box, hp_pct=None, teto=92):
    """Cura gasta em quem estava quase cheio: turno e mana jogados fora."""
    out = []
    for e in ev:
        if e["kind"] not in ("healed_player", "heal_player"):
            continue
        t = _to_s(e["ts"])
        alvo = e.get("victim")
        pc = (hp_pct or {}).get(t, {}).get(alvo)
        if pc is not None and pc >= teto:
            out.append({
                "tipo": "sobrecura", "tipo_coach": "cura", "quando": t,
                "severidade_s": 1.2,
                "evidencia": {"alvo": alvo, "hp_pct": pc},
                "texto": f"cura em {alvo} com {pc}% de vida",
            })
    return out


def alvo_de_cura_errado(ev, box, hp_pct=None, margem=20):
    """Curou o membro X enquanto outro estava bem pior."""
    out = []
    for e in ev:
        if e["kind"] not in ("healed_player", "heal_player"):
            continue
        t, alvo = _to_s(e["ts"]), e.get("victim")
        estado = (hp_pct or {}).get(t, {})
        if not estado or alvo not in estado:
            continue
        pior = min(estado, key=estado.get)
        if pior != alvo and estado[alvo] - estado[pior] >= margem:
            out.append({
                "tipo": "alvo_errado", "tipo_coach": "cura", "quando": t,
                "severidade_s": (estado[alvo] - estado[pior]) * 0.12,
                "evidencia": {"curou": alvo, "precisava": pior,
                              "hp": {alvo: estado[alvo], pior: estado[pior]}},
                "texto": f"curou {alvo} ({estado[alvo]}%) com {pior} em {estado[pior]}%",
            })
    return out


def hp_critico(ev, box, hp_pct=None, critico=35):
    """Alguem chegou perto da morte: o evento mais caro que existe."""
    out = []
    for t, estado in (hp_pct or {}).items():
        for quem, pc in estado.items():
            if pc <= critico:
                out.append({
                    "tipo": "hp_critico", "tipo_coach": "cura", "quando": t,
                    "severidade_s": (critico - pc) * 2.5 + 10,
                    "evidencia": {"quem": quem, "hp_pct": pc},
                    "texto": f"{quem} chegou a {pc}% de vida",
                })
    return out


def chegada_tardia(ev, box, ek, pos=None, atraso_max=4):
    """O EK ja estava apanhando e voce ainda nao tinha chegado na box."""
    prim = min((_to_s(e["ts"]) for e in ev
                if e["kind"] == "damage_taken_player" and e.get("victim") == ek),
               default=None)
    if prim is None:
        return []
    chegou = next((t for t in sorted(pos or {})
                   if (pos[t].get(ek) or 99) <= 7), None)
    if chegou and chegou - prim >= atraso_max:
        d = chegou - prim
        return [{
            "tipo": "chegada_tardia", "tipo_coach": "posicao", "quando": prim,
            "severidade_s": d * 1.2,
            "evidencia": {"atraso_s": d},
            "texto": f"EK abriu a box e voce chegou {d}s depois",
        }]
    return []


def ocioso_sem_dano(ev, box, ek, hp_pct=None, seguro=85):
    """Ninguem precisando de cura e voce sem dar dano: turno desperdicado."""
    dur = box["t1"] - box["t0"]
    seus_hits = {_to_s(e["ts"]) for e in ev if e["kind"] == "damage_dealt"}
    ociosos = 0
    for t in range(box["t0"], box["t1"] + 1):
        estado = (hp_pct or {}).get(t)
        todos_ok = (not estado) or min(estado.values()) >= seguro
        if todos_ok and t not in seus_hits:
            ociosos += 1
    if dur >= 10 and ociosos / dur >= 0.5:
        return [{
            "tipo": "ocioso_sem_dano", "tipo_coach": "posicao", "quando": box["t0"],
            "severidade_s": ociosos * 0.35,
            "evidencia": {"segundos_ociosos": ociosos, "dur_box": dur},
            "texto": f"{ociosos}s da box sem dar dano com o time inteiro saudavel",
        }]
    return []


def paralisado_parado(ev, box, pos=None):
    """Paralisado e sem sair do lugar: alvo facil e fora de alcance de cura."""
    out = []
    for e in ev:
        if e["kind"] == "raw" and "paralyzed" in e.get("body", ""):
            t = _to_s(e["ts"])
            if (pos or {}).get(t, {}).get("_parado"):
                out.append({
                    "tipo": "paralisado", "tipo_coach": "posicao", "quando": t,
                    "severidade_s": 3.0,
                    "evidencia": {},
                    "texto": "paralisado e parado no lugar",
                })
    return out


DETECTORES = (cura_atrasada, fora_de_alcance, turno_gasto_em_si,
              apanhando_sem_necessidade, mana_seca, sobrecura, alvo_de_cura_errado,
              hp_critico, chegada_tardia, ocioso_sem_dano, paralisado_parado)


def diagnosticar(ev, boxes, ek, pos=None, vistos_fora=()):
    """Roda todos os detectores e devolve os problemas ordenados por ganho.

    Agrupa por TIPO: o que importa nao e a pior ocorrencia isolada, e sim o
    padrao que mais custa somando a volta inteira.
    """
    pos = pos or {}
    achados = []
    for box in boxes:
        janela = [e for e in ev if box["t0"] - 5 <= _to_s(e["ts"]) <= box["t1"] + 5]
        achados += cura_atrasada(janela, box, ek)
        achados += fora_de_alcance(janela, box, ek, pos)
        achados += turno_gasto_em_si(janela, box, ek)
        achados += apanhando_sem_necessidade(janela, box, pos)
    achados += bicho_perdido(ev, None, vistos_fora)

    por_tipo = collections.defaultdict(list)
    for a in achados:
        por_tipo[a["tipo"]].append(a)

    ranking = []
    for tipo, lista in por_tipo.items():
        total = sum(a["severidade_s"] for a in lista)
        pior = max(lista, key=lambda a: a["severidade_s"])
        ranking.append({
            "tipo": tipo,
            "ocorrencias": len(lista),
            "custo_total_s": round(total, 1),
            "pior_momento": pior["quando"],
            "tipo_coach": pior["tipo_coach"],
            "texto": pior["texto"],
            "exemplos": [a["texto"] for a in sorted(
                lista, key=lambda a: -a["severidade_s"])[:3]],
        })
    ranking.sort(key=lambda r: -r["custo_total_s"])
    return ranking
