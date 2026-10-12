"""Cria e popula solo.db (tracker SOLO — grupo 'Johanes Characters').

Fonte: D:/Documentos/rubinot/hunt-analyzer/hunt_data (nada de rede, nada do
tracker publico). Rodar: python scripts/build_db.py
"""
import json, pathlib, sqlite3

RAIZ = pathlib.Path(__file__).resolve().parents[1]
HD = RAIZ.parent / "hunt-analyzer" / "hunt_data"
DB = RAIZ / "solo.db"

# Sessoes dos summaries (hunt_data/<hunt>/sessoes/<stem>.json), em ordem cronologica.
# kills_de: "xp" = soma de especies_por_xp (chat, subconta) | "voltas" = soma das
# voltas (chat bom) | None = sem contagem confiavel (fica NULL).
SUMARIOS = {
    ("falcon_bastion", "20260725_0635"): ("xp", None),
    ("falcon_bastion", "20260725_0703"): ("xp", None),
    ("falcon_bastion", "20260725_0726"): ("xp", None),
    ("ingol", "20260725_1452"): ("xp", None),
    ("ingol", "20260725_1519"): ("xp", None),
    ("infernatil_hell", "20260725_2129"): (None, "kills por volta não registrados no chat"),
    ("dragolisk", "20260725_2225"): ("voltas", None),
    ("falcon_bastion", "20260726_1135"): (None, "chat do console em 3 linhas: kills por volta não confiáveis"),
    ("falcon_bastion", "20260726_1419"): (None, "chat do console em 3 linhas: kills por volta não confiáveis"),
    ("falcon_bastion", "20260726_1531"): (None, "chat do console em 3 linhas: kills por volta não confiáveis"),
    ("infernatil_hell", "20260727_0533"): ("voltas", None),
    ("gnomprona_carrinho2", "20260727_2111"): (None,
        "pt com loot Leader: lucro pessoal so depois do split; kills do chat sao piso (console 3 linhas)"),
    ("falcon_bastion", "20260728_0511"): ("voltas",
        "kills por volta = painel (delta Raw XP / 6.516 por bicho); coach RP aplicado da volta 11+"),
}

def fmt_hora(s):
    return s if ":" in s else f"{s[:2]}:{s[2:4]}:{s[4:6]}"

def grava_mix(c, sessao_id, mix, fonte):
    total = sum(mix.values()) or 1
    for esp, n in sorted(mix.items(), key=lambda kv: -kv[1]):
        c.execute("INSERT INTO abate_especie (sessao_id, especie, abates, pct, fonte)"
                  " VALUES (?,?,?,?,?)", (sessao_id, esp, n, round(100 * n / total, 1), fonte))

DDL = """
CREATE TABLE grupo (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
CREATE TABLE personagem (
  id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, vocacao TEXT,
  nivel INTEGER, rate_pct INTEGER, grupo_id INTEGER REFERENCES grupo(id));
CREATE TABLE hunt (
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, nome TEXT, andar INTEGER,
  bbox TEXT, referencias_json TEXT);
CREATE TABLE sessao (
  id INTEGER PRIMARY KEY, personagem_id INTEGER REFERENCES personagem(id),
  hunt_id INTEGER REFERENCES hunt(id), data TEXT, janela TEXT, minutos REAL,
  voltas INTEGER, profit INTEGER, profit_h INTEGER, loot INTEGER, supplies INTEGER,
  balance INTEGER, kills INTEGER, kills_h INTEGER,
  xp_raw_h_mediana INTEGER, supplies_h INTEGER, dano_por_bicho INTEGER,
  ks_pct REAL, nivel_ini INTEGER, nivel_fim INTEGER, obs TEXT, nota TEXT);
CREATE TABLE volta (
  id INTEGER PRIMARY KEY, sessao_id INTEGER REFERENCES sessao(id), numero INTEGER,
  inicio TEXT, fim TEXT, dur_s INTEGER, kills INTEGER, profit INTEGER,
  xp_raw INTEGER, xp_chat INTEGER, dano_tomado INTEGER, battle_medio REAL,
  rotacao TEXT, descartada INTEGER DEFAULT 0);
CREATE TABLE abate_especie (
  id INTEGER PRIMARY KEY, sessao_id INTEGER NOT NULL REFERENCES sessao(id),
  especie TEXT NOT NULL, abates INTEGER NOT NULL, pct REAL NOT NULL,
  fonte TEXT NOT NULL);
CREATE TABLE zona (
  id INTEGER PRIMARY KEY, sessao_id INTEGER REFERENCES sessao(id), rank INTEGER,
  x INTEGER, y INTEGER, trecho TEXT, kills INTEGER, bichos_volta REAL,
  xp INTEGER, profit INTEGER, hp_por_bicho INTEGER, dwell_s INTEGER);
CREATE TABLE box_travada (
  id INTEGER PRIMARY KEY, sessao_id INTEGER REFERENCES sessao(id), n INTEGER,
  volta INTEGER, inicio TEXT, dur_s INTEGER, dano INTEGER, pilha INTEGER,
  abertura INTEGER, x INTEGER, y INTEGER, causa TEXT,
  historia_1 TEXT, historia_2 TEXT, historia_3 TEXT, imagem TEXT);
"""

def preencher_damage_healing(c):
    """Dano/cura por sessao, lidos dos summaries (pareados por ordem cronologica —
    o nome do arquivo e a hora da janela conferem: 0635 <-> 06:35:04)."""
    import json as _json
    c.execute("ALTER TABLE sessao ADD COLUMN damage INTEGER")
    c.execute("ALTER TABLE sessao ADD COLUMN healing INTEGER")
    def acha(o, chaves):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in chaves and isinstance(v, (int, float)) and v > 1e5:
                    return int(v)
            for v in o.values():
                r = acha(v, chaves)
                if r: return r
        elif isinstance(o, list):
            for v in o:
                r = acha(v, chaves)
                if r: return r
        return None
    n = 0
    for (slug,) in c.execute("SELECT DISTINCT h.slug FROM sessao s JOIN hunt h ON h.id=s.hunt_id").fetchall():
        files = sorted((HD / slug / "sessoes").glob("*.json"))
        sess = c.execute("""SELECT s.id FROM sessao s JOIN hunt h ON h.id=s.hunt_id
                            WHERE h.slug=? ORDER BY s.data, s.janela""", (slug,)).fetchall()
        for (sid,), f in zip(sess, files):
            j = _json.loads(f.read_text(encoding="utf-8"))
            dmg = acha(j, {"damage", "damage_dado", "dano_dado", "damage_dealt"})
            heal = acha(j, {"healing", "cura"})
            c.execute("UPDATE sessao SET damage=?, healing=? WHERE id=?", (dmg, heal, sid))
            n += 1
    print(f"  damage/healing preenchidos em {n} sessoes")


def recuperar_totais_pelas_voltas(c):
    """Sessao com painel final envenenado (reset do analyser) mas com lucro POR
    VOLTA valido: o total honesto e a soma das voltas limpas (licao de 27/07 —
    a Infernatil do Traps tinha 5,14kk somaveis e aparecia como '—')."""
    n = 0
    for sid, soma, mins in c.execute("""
        SELECT s.id, SUM(CASE WHEN v.descartada=0 THEN v.profit END), s.minutos
        FROM sessao s JOIN volta v ON v.sessao_id = s.id
        WHERE s.profit IS NULL GROUP BY s.id HAVING SUM(CASE WHEN v.descartada=0 THEN v.profit END) IS NOT NULL""").fetchall():
        ph = round(soma * 60 / mins) if mins else None
        c.execute("UPDATE sessao SET profit=?, profit_h=? WHERE id=?", (soma, ph, sid))
        n += 1
    print(f"  sessoes com lucro recuperado pela soma das voltas: {n}")


LIMIAR_RESET = -1_000_000  # volta com delta gigante negativo = reset do analyser, nunca hunt real


def marcar_voltas_de_reset(c):
    """Ultima volta pos-reset do painel vira delta negativo gigante e envenena
    grafico e agregados (licao de 27/07: 'sempre descartar a volta em que o
    analyser foi resetado'). Marca como descartada em vez de apagar."""
    n = c.execute("UPDATE volta SET descartada=1 WHERE profit < ?", (LIMIAR_RESET,)).rowcount
    print(f"  voltas de reset do painel marcadas como descartadas: {n}")


def main():
    if DB.exists():
        DB.unlink()
    c = sqlite3.connect(DB)
    c.executescript(DDL)
    c.execute("INSERT INTO grupo (id, nome) VALUES (1, 'Johanes Characters')")
    chars = {
        "Hetero afeminado": ("druid", 787, 1125),
        "Traps the cat": ("paladin", 941, 450),
    }
    for nome, (voc, lvl, rate) in chars.items():
        c.execute("INSERT INTO personagem (nome, vocacao, nivel, rate_pct, grupo_id)"
                  " VALUES (?,?,?,?,1)", (nome, voc, lvl, rate))
    pid = {r[1]: r[0] for r in c.execute("SELECT id, nome FROM personagem")}

    # hunts + referencias
    hid = {}
    for d in sorted(p for p in HD.iterdir() if p.is_dir() and not p.name.startswith("_")):
        ref = d / "referencias.json"
        j = json.loads(ref.read_text(encoding="utf-8")) if ref.exists() else {}
        c.execute("INSERT INTO hunt (slug, nome, andar, bbox, referencias_json) VALUES (?,?,?,?,?)",
                  (d.name, d.name.replace("_", " ").title(), (json.dumps(j.get("z")) if isinstance(j.get("z"), (list, dict)) else j.get("z")),  # andar pode ser lista (livraria z12+z13)
                   json.dumps(j.get("bbox")), json.dumps(j, ensure_ascii=False)))
        hid[d.name] = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    # sessao medida do Hetero em Ingol (a unica com volta a volta)
    s = json.loads((HD / "ingol" / "sessoes" / "20260727.json").read_text(encoding="utf-8"))
    r = s["resultado_por_volta"]
    # ks_pct fica NULL: a fonte so tem texto ("sem competidor no log ..."), sem
    # numero. Gravar 0.0 aqui virava "0,0% de bicho roubado" na tela, medicao que
    # nao existe. O texto vai em obs e a tela mostra "—" na coluna.
    painel1 = s["painel_final_0955"]
    c.execute("""INSERT INTO sessao (personagem_id, hunt_id, data, janela, minutos, voltas,
                 profit, profit_h, loot, supplies, balance, kills, kills_h,
                 xp_raw_h_mediana, supplies_h,
                 dano_por_bicho, ks_pct, nivel_ini, nivel_fim, obs, nota)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (pid["Hetero afeminado"], hid["ingol"], s["data"], s["janela"], 84.17,
               s["voltas"]["limpas"], r["profit_somado"], r["profit_h"],
               painel1["loot"], painel1["supplies"], painel1["balance"], r["kills"],
               r["kills_h"], r["raw_xp_h"]["mediana"], painel1["supplies_h"],
               r["dano_por_bicho"], None, s["nivel"]["inicio"], s["nivel"]["fim"],
               s["ks"], s.get("_nota")))
    sid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    descartada = s["voltas"]["descartada"]["volta"]
    laps = [json.loads(l) for l in (RAIZ.parent / "hunt-analyzer" / "capture" /
            "session_20260727_080502" / "laps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    for L in laps:
        c.execute("""INSERT INTO volta (sessao_id, numero, inicio, fim, dur_s, kills, profit,
                     xp_raw, dano_tomado, battle_medio, descartada) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (sid, L["volta"], L["inicio"], L["fim"], L["dur_s"], L.get("kills_total"),
                   L.get("profit"), L.get("xp_raw_painel"), L.get("dmg_in"),
                   L.get("battle_medio"), 1 if L["volta"] == descartada else 0))

    # Mix de especies da sessao de 27/07: dict `loots` (corpo saqueado) do laps.jsonl
    # e a unica atribuicao real — o dict `kills` e quase todo "compartilhado".
    mix1 = {}
    for L in laps:
        for esp, n in (L.get("loots") or {}).items():
            mix1[esp] = mix1.get(esp, 0) + n
    grava_mix(c, sid, mix1, "loot_corpo")

    # Rateio das zonas: valor MEDIDO por bicho x abates da zona. Antes havia uma
    # constante de XP colada no codigo que era a soma das voltas boas — mas a volta
    # sem leitura de XP entrava no divisor, entao toda zona saia ~5% baixa, e a
    # constante nao acompanhava mudanca nas voltas.
    boas = [L for L in laps if L["volta"] != descartada]
    com_xp = [L for L in boas if L.get("xp_raw_painel") is not None]
    kills_com_xp = sum(L.get("kills_total") or 0 for L in com_xp) or 1
    kills_boas = sum(L.get("kills_total") or 0 for L in boas) or 1
    xp_por_kill = sum(L["xp_raw_painel"] for L in com_xp) / kills_com_xp
    profit_por_kill = r["profit_somado"] / kills_boas

    boxes = json.loads((HD / "ingol" / "boxes_20260727.json").read_text(encoding="utf-8"))
    for i, b in enumerate(sorted(boxes, key=lambda b: -b["kills"]), 1):
        c.execute("""INSERT INTO zona (sessao_id, rank, x, y, trecho, kills, bichos_volta,
                     xp, profit, hp_por_bicho, dwell_s) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (sid, i, b["x"], b["y"], b["trecho"], b["kills"],
                   round(b["kills"] / max(1, b["voltas"]), 2),
                   round(xp_por_kill * b["kills"]), round(profit_por_kill * b["kills"]),
                   b["dano_por_bicho"], b["dwell_s"]))

    trav = json.loads((RAIZ.parent / "hunt-analyzer" / "reports" / "boxes_travadas" /
                       "boxes_travadas.json").read_text(encoding="utf-8"))
    for b in trav:
        h = b.get("historia") or ["", "", ""]
        c.execute("""INSERT INTO box_travada (sessao_id, n, volta, inicio, dur_s, dano, pilha,
                     abertura, x, y, causa, historia_1, historia_2, historia_3, imagem)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (sid, b["n"], b.get("volta"), None, b["trava"][1] - b["trava"][0],
                   b["trava"][4], b["trava"][5], b["abertura"], int(b["trava"][2]),
                   int(b["trava"][3]), (b.get("erro") or [None, None, None, "sem gatilho"])[3],
                   h[0], h[1], h[2], f"boxgrid_{b['n']:02d}.png"))

    # 11 sessoes dos summaries. Regra dura: campo sem medicao = NULL.
    for (slug, stem), (kills_de, nota_extra) in SUMARIOS.items():
        j = json.loads((HD / slug / "sessoes" / f"{stem}.json").read_text(encoding="utf-8"))
        painel = j.get("painel_final") or {}
        painel_ok = (painel.get("raw_xph") or 0) > 0  # painel zerado = nao capturado
        horas = j["dur_s"] / 3600
        loot = painel.get("loot") if painel_ok else None
        supplies = painel.get("supplies") if painel_ok else None
        balance = painel.get("balance") if painel_ok and painel.get("balance") else None
        profit = balance if balance is not None else (
            loot - supplies if painel_ok else None)
        # pt com loot no leader: quando o split foi pago, o profit real do char
        # e o share recebido, nao o balance pessoal (que fica so com supplies)
        if j.get("split_pago"):
            profit = j["split_pago"]["share"]
            balance = None
        voltas = j.get("voltas")
        if kills_de == "xp":
            kills = sum(j["especies_por_xp"].values())
        elif kills_de == "voltas":
            kills = sum(v["kills"] or 0 for v in voltas)
        else:
            kills = None
        ks = j.get("ks") or {"atores": [], "minutos_disputados": 0,
                             "minutos_totais": round(j["dur_s"] / 60),
                             "pct_dano_terceiros": 0}
        obs = None
        if ks["atores"]:
            top = max(ks["atores"], key=lambda a: a["dano"])
            outros = len(ks["atores"]) - 1
            obs = (f"KS: {top['nome']} ({ks['minutos_disputados']}/{ks['minutos_totais']}"
                   f" min disputados)" + (f" +{outros} outros" if outros else ""))
        notas = []
        if painel_ok:
            notas.append("XP/h do painel da sessão, não mediana por volta")
        else:
            notas.append("painel não capturado: profit, loot, supplies e XP/h sem medição")
        if kills_de == "xp":
            notas.append("kills somados do chat de XP (subconta)")
        if j.get("split_pago"):
            notas.append(j["split_pago"]["nota"])
        if nota_extra:
            notas.append(nota_extra)
        c.execute("""INSERT INTO sessao (personagem_id, hunt_id, data, janela, minutos, voltas,
                     profit, profit_h, loot, supplies, balance, kills, kills_h,
                     xp_raw_h_mediana, supplies_h, ks_pct, obs, nota)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (pid["Hetero afeminado" if slug == "ingol" else "Traps the cat"], hid[slug],
                   f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}",
                   f"{fmt_hora(j['inicio'])} - {fmt_hora(j['fim'])}",
                   round(j["dur_s"] / 60, 2), len(voltas) if voltas else None,
                   profit, round(profit / horas) if profit is not None else None,
                   loot, supplies, balance,
                   kills, round(kills / horas) if kills is not None else None,
                   painel.get("raw_xph") if painel_ok else None,
                   round(supplies / horas) if supplies is not None else None,
                   ks["pct_dano_terceiros"], obs, "; ".join(notas)))
        sid2 = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        if j.get("especies_por_xp"):
            grava_mix(c, sid2, j["especies_por_xp"], "xp_chat")
        for v in voltas or []:
            c.execute("""INSERT INTO volta (sessao_id, numero, inicio, fim, dur_s, kills,
                         profit, xp_chat, dano_tomado, battle_medio, rotacao, descartada)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
                      (sid2, v["volta"], v["inicio"], v["fim"], v["dur_s"], v.get("kills"),
                       v.get("profit"), v.get("xp"), v.get("dmg_in"),
                       v.get("battle_medio"), v.get("rotacao")))

    achados = {(p.parent.parent.name, p.stem) for p in HD.glob("*/sessoes/*.json")}
    fora = achados - set(SUMARIOS) - {("ingol", "20260727")}
    if fora:
        print("AVISO: sessoes fora do mapeamento (não carregadas):", sorted(fora))

    marcar_voltas_de_reset(c)
    recuperar_totais_pelas_voltas(c)
    preencher_damage_healing(c)
    c.commit()
    for t in ("grupo", "personagem", "hunt", "sessao", "volta", "zona",
              "box_travada", "abate_especie"):
        print(f"  {t}: {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    print("ok ->", DB)

if __name__ == "__main__":
    main()
