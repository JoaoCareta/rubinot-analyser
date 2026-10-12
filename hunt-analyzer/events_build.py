"""Transforma os frames de chat de uma sessao em eventos unicos tipados.

Uso:  python events_build.py capture\\session_YYYYMMDD_HHMMSS
Saida: events.jsonl dentro da pasta da sessao + resumo no stdout.

Dedupe: cada frame e uma janela do log; alinha com o frame anterior pelo maior
overlap sufixo==prefixo e so o rabo novo vira evento.
"""
import collections
import json
import pathlib
import re
import sys

import atlas_build as ab

TS = re.compile(r"^(\d\d:\d\d:\d\d) (.*)$")
# 26/07: recorte do chat (3 linhas) inclui a coluna da scrollbar -> todo fim de
# linha ganha tokens desconhecidos; junk TRAILING sai, "�" no meio ainda descarta
TRAIL_JUNK = re.compile(r"(?: ?\uFFFD)+$")
# 22/09 (user): "You have left/entered the subarea X" marca cidade, entrada da hunt e da cave.
# O atlas nao tem o ligado "ft" nem maiuscula rara ("le\uFFFD the subarea Isle of the \uFFFDings"), entao
# a linha vem com \uFFFD e seria descartada; " the subarea " decodifica sempre e serve de ancora.
SUBAREA = " the subarea "

PATTERNS = [
    ('player_info', re.compile(r'^You see (?P<target>.+?) \(Level (?P<level>\d+)\)\. (?:He|She|They) (?:is|are) (?:an? )?(?P<vocation>elite knight|royal paladin|elder druid|master sorcerer|knight|paladin|druid|sorcerer)\.',re.I)),
    ("cast", re.compile(r'^You (?:cast |say: )(?P<words>(?:ex|ut)[a-z]+ .+?)\.?$')),
    # area vem antes de tudo: o corpo pode ter � e nenhum outro padrao casaria
    ("area", re.compile(r"^You have (?P<acao>\S+)" + SUBAREA + r"(?P<area>[^.]+)\.")),
    ("damage_taken", re.compile(r"^You lose (?P<value>\d+) hitpoints due to an? (?P<crit>critical )?attack by an? (?P<actor>.+?)\.(?: \((?P<tag>.+)\))?$")),
    ("damage_dealt", re.compile(r"^An? (?P<target>.+?) loses (?P<value>\d+) hitpoints due to your (?P<crit>critical )?attack\.(?: \((?P<tag>.+)\))?$")),
    # NB: (?!You\b) impede que os padroes de party engulam as SUAS mensagens
    ("damage_dealt_player", re.compile(r"^An? (?P<target>.+?) loses (?P<value>\d+) hitpoints due to an? (?P<crit>critical )?attack by (?!You\b)(?P<actor>[A-Z][^.]*?)\.(?: \((?P<tag>.+)\))?$")),
    ("damage_dealt_creature", re.compile(r"^An? (?P<target>.+?) loses (?P<value>\d+) hitpoints due to an? (?P<crit>critical )?attack by an? (?P<actor>[a-z][^.]*?)\.(?: \((?P<tag>.+)\))?$")),
    ("damage_taken_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) loses (?P<value>\d+) hitpoints due to an? (?P<crit>critical )?attack by an? (?P<actor>[a-z][^.]*?)\.$")),
    ("healed_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) was healed for (?P<value>\d+) hitpoints\.(?: \((?P<tag>.+)\))?$")),
    ("heal_self_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) healed (?:himself|herself|itself) for (?P<value>\d+) hitpoints\.(?: \((?P<tag>.+)\))?$")),
    ("mana_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) gained (?P<value>\d+) mana\.$")),
    ("mana_restore_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) was restored for (?P<value>\d+) mana\.$")),
    ("xp_player", re.compile(r"^(?!You\b)(?P<actor>[A-Z][^.]*?) gained (?P<value>\d+) experience points(?: \((?P<tag>.+)\))?\.$")),
    ("damage_plain_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) loses (?P<value>\d+) hitpoints\.$")),
    ("mana_drain_player", re.compile(r"^(?!You\b)(?P<victim>[A-Z][^.]*?) loses (?P<value>\d+) mana due to an attack by an? (?P<actor>[a-z][^.]*?)\.$")),
    # suas condicoes / campo (sem atacante nomeado)
    ("damage_condition", re.compile(r"^You lose (?P<value>\d+) hitpoints\.$")),
    ("mana_drain", re.compile(r"^You lose (?P<value>\d+) mana due to an attack by an? (?P<actor>.+?)\.$")),
    ("condition", re.compile(r"^You are (?P<what>paralyzed|burned|poisoned|electrified|freezing|cursed|drowning|hasted|dazzled|bleeding)\.$")),
    ("heal_self", re.compile(r"^You heal yourself for (?P<value>\d+) hitpoints\.(?: \((?P<tag>.+)\))?$")),
    # 28/09: a cura que VOCÊ lança em outro (o sio no EK) caía em "raw" — 38 mensagens em 4 min de
    # pt. É o turno que o druida gasta com a pt, o sinal do auxiliador do Utamo Vita.
    ("heal_other", re.compile(r"^You heal (?P<target>[A-Z][^.]*?) for (?P<value>\d+) hitpoints\.(?: \((?P<tag>.+)\))?$")),
    ("healed", re.compile(r"^You were healed for (?P<value>\d+) hitpoints\.(?: \((?P<tag>.+)\))?$")),
    ("mana_gain", re.compile(r"^You gained (?P<value>\d+) mana\.$")),
    ("mana_restore", re.compile(r"^You were restored for (?P<value>\d+) mana\.$")),
    ("xp_gain", re.compile(r"^You gained (?P<value>\d+) experience points(?: \((?P<tag>.+)\))?\.$")),
    ("level_up", re.compile(r"^You advanced from Level (?P<from>\d+) to Level (?P<to>\d+)\.$")),
    ("loot", re.compile(r"^Loot of an? (?P<target>.+?): (?P<items>.+)$")),
    ("looted", re.compile(r"^You looted (?P<what>.+)$")),
    ("looted_partial", re.compile(r"^You only looted (?P<what>.+)$")),
    ("dodge", re.compile(r"^You dodged an attack(?: by an? (?P<actor>.+?))?\.(?: \((?P<tag>.+)\))?$")),
    ("proc", re.compile(r"^(?P<what>Momentum) was triggered\.$")),
    ("speech", re.compile(r"^(?P<actor>[^:]+?) \[(?P<level>\d+)\]: (?P<text>.*)$")),
    ("npc_say", re.compile(r"^(?P<actor>[A-Z][^:]{0,30}): (?P<text>.*)$")),
]


def classify(body):
    for kind, rx in PATTERNS:
        m = rx.match(body)
        if m:
            d = {k: v for k, v in m.groupdict().items() if v is not None}
            if "value" in d:
                d["value"] = int(d["value"])
            if "crit" in d:
                d["crit"] = True
            # O cliente põe o proc depois do ponto para você e antes dele
            # para outros jogadores. Não incorporar Onslaught ao nome.
            if kind == "damage_dealt_player":
                proc = re.search(r" \(([^()]+)\)$", d["actor"])
                if proc:
                    d["actor"] = d["actor"][:proc.start()]
                    d["tag"] = proc[1]
            if kind in ("damage_dealt", "damage_dealt_player"):
                d["fatal"] = d.get("tag", "").casefold() == "onslaught"
            if kind == "area":
                d["acao"] = "entrou" if d["acao"].startswith("ent") else "saiu"
                d["area"] = d["area"].replace("�", "?").strip()
            return kind, d
    return "raw", {}


def frame_messages(path, glyphs, gap):
    """Mensagens (ts, corpo) do frame; continuacoes de wrap juntadas; lixo fora."""
    msgs, started = [], False
    for line in ab.decode_frame(path, glyphs, gap, input_top=None):
        line = TRAIL_JUNK.sub("", line)
        m = TS.match(line)
        if m:
            started = True
            msgs.append([m.group(1), m.group(2)])
        elif started and msgs:
            msgs[-1][1] += " " + line
    # subarea: corta no 1o ponto — o resto ("Return to discover...") quebra em linhas diferentes
    # conforme a rolagem e o dedupe por sufixo perderia o encaixe
    return [(t, b.split(".", 1)[0] + "." if SUBAREA in b else b)
            for t, b in msgs if "�" not in b or SUBAREA in b]


def new_tail(prev, cur):
    for k in range(min(len(prev), len(cur)), 0, -1):
        if prev[-k:] == cur[:k]:
            return cur[k:]
    return cur


def build(session_dir):
    session = pathlib.Path(session_dir)
    glyphs, gap = ab.load_atlas()
    frames = sorted(session.glob("c_*.png"))
    events, prev = [], []
    last_ts = ""
    for f in frames:
        cur = frame_messages(f, glyphs, gap)
        if not cur:
            continue
        # ponytail: user rolou o chat p/ cima -> janela so com msgs antigas; pula
        if last_ts and all(t < last_ts for t, _ in cur):
            continue
        for ts, body in new_tail(prev, cur):
            kind, data = classify(body)
            events.append({"ts": ts, "kind": kind, "body": body, "frame": f.name, **data})
            last_ts = max(last_ts, ts)
        prev = cur
    return events


def summarize(events):
    kinds = collections.Counter(e["kind"] for e in events)
    print(f"{len(events)} eventos:")
    for kind, n in kinds.most_common():
        print(f"  {kind:14} {n}")
    dealt = [e for e in events if e["kind"] == "damage_dealt"]
    taken = [e for e in events if e["kind"] == "damage_taken"]
    if dealt:
        by_target = collections.Counter()
        for e in dealt:
            by_target[e["target"]] += e["value"]
        print(f"\ndano causado: {sum(e['value'] for e in dealt)} "
              f"(crit: {sum(e['value'] for e in dealt if e.get('crit'))})")
        for t, v in by_target.most_common():
            print(f"  {t:20} {v}")
    if taken:
        by_actor = collections.Counter()
        for e in taken:
            by_actor[e["actor"]] += e["value"]
        print(f"dano recebido: {sum(e['value'] for e in taken)}")
        for a, v in by_actor.most_common():
            print(f"  {a:20} {v}")
    raws = [e for e in events if e["kind"] == "raw"]
    if raws:
        print(f"\n{len(raws)} eventos nao classificados (kind=raw), ex.:")
        for e in raws[:8]:
            print(f"  {e['body'][:100]}")


def main():
    session_dir = sys.argv[1]
    events = build(session_dir)
    out = pathlib.Path(session_dir) / "events.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"gravado {out}\n")
    summarize(events)


if __name__ == "__main__":
    main()
