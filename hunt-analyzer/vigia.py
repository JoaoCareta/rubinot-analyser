"""Vigia da hunt: estados + volta por checkpoint + box ao vivo.

Sucessor do lap_watch para hunts com `referencias.json`. Resolve o que o user
pediu em 27/07:

  1. ESTADOS reconhecidos e contabilizados (estados.jsonl):
     VIAJANDO -> CACANDO -> INDO_REFILL -> NO_REFILL -> VOLTANDO -> CACANDO
  2. VOLTA com mais de uma referencia: checkpoints fixos do anel (cada um e um
     quarto do percurso) + a pilha ter caido ("regiao limpa"), em vez do raio
     unico — que fazia o inicio da volta escorregar pelo anel inteiro.
  3. NARRACAO: imprime o que esta reconhecendo (1/4, 2/4, estado, box) para o
     orquestrador publicar sem o user pedir.
  4. Marca PREPARAR_COACH na volta 4 para o coach sair pronto no fim da 5.
  5. BOX ao vivo: parado >=8s com pilha >=6 -> imprime BOX na hora.

Uso ao vivo:  python vigia.py capture\\session_X ingol
Replay:       python vigia.py capture\\session_X ingol --replay
"""
import json
import math
import pathlib
import sys
import time

import numpy as np

import lap_watch as lw
import map_live
import mapa_ingol as mi

PILHA_HUNT = 3          # bichos na battle para contar como caca
FRAC_COMBATE = 0.35     # fracao da janela com pilha -> caçando
FRAC_PARADO = 0.15      # abaixo disso -> saiu da hunt
JANELA_S = 90
TILES_ANDOU = 25
PARADO_REFILL_S = 20    # quieto tanto tempo fora da hunt = esta no depot
BOX_PARADO_S = 8
BOX_PILHA = 6
COACH_NA_VOLTA = 4      # comeca a preparar aqui para sair no fim da 5


def carregar_ref(hunt):
    p = pathlib.Path("hunt_data") / hunt / "referencias.json"
    ref = json.loads(p.read_text(encoding="utf-8"))
    if not ref.get("checkpoints"):
        raise SystemExit(f"{p} ainda nao tem checkpoints — medir uma sessao primeiro")
    return ref


class Vigia:
    def __init__(self, session, hunt, replay=False, prefixo=""):
        self.session = pathlib.Path(session)
        self.ref = carregar_ref(hunt)
        self.replay = replay
        self.cps = self.ref["checkpoints"]
        self.ordem = self.ref["sentido"]
        b = self.ref.get("bbox")
        self.area = (b[0], b[1], b[2], b[3], self.ref["z"]) if b else (mi.X0, mi.X1, mi.Y0, mi.Y1, mi.Z)
        self.estado = "VIAJANDO"
        self.t_estado = None
        self.tempos = {}
        self.volta = 1
        self.lap_ini = None
        self.cp_ini = None
        self.batidos = []
        self.pilha_min = 99
        self.box_aberto = None
        self.pos = []          # [(t, x, y)]
        self.bat = {}          # t -> pilha
        self.estados_p = self.session / f"estados{prefixo}.jsonl"
        self.laps_p = self.session / f"voltas{prefixo}.jsonl"

    # ---------- entrada de dados ----------
    def atualizar(self):
        novos = map_live.walked_update(self.session, *self.area)
        self.pos = [tuple(p) for p in novos]
        cache = self.session / "battle_cache.json"
        if not self.bat and cache.exists():
            self.bat = {int(k): v for k, v in json.loads(cache.read_text()).items()}
        antes = len(self.bat)
        for f in sorted(self.session.glob("b_*.png")):
            t = lw.fsec(f.name)
            if t % 2 == 0 and t not in self.bat:
                self.bat[t] = lw.battle_count(f)
        if len(self.bat) != antes:
            cache.write_text(json.dumps(self.bat))

    def _no_anel(self, t, folga=45):
        """(esta na area da hunt?, ha quanto tempo sem posicao valida)"""
        xs = [c["xy"][0] for c in self.cps]
        ys = [c["yx"][1] if "yx" in c else c["xy"][1] for c in self.cps]
        x0, x1 = min(xs) - folga, max(xs) + folga
        y0, y1 = min(ys) - folga, max(ys) + folga
        recentes = [p for p in self.pos if t - 20 <= p[0] <= t]
        if not recentes:
            return False, 999
        px, py = recentes[-1][1], recentes[-1][2]
        return (x0 <= px <= x1 and y0 <= py <= y1), t - recentes[-1][0]

    def _janela(self, t):
        t0 = t - JANELA_S
        pil = [n for tt, n in self.bat.items() if t0 <= tt <= t]
        pts = [p for p in self.pos if t0 <= p[0] <= t]
        andou = sum(math.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2])
                    for i in range(1, len(pts)))
        frac = (sum(1 for n in pil if n >= PILHA_HUNT) / len(pil)) if pil else 0.0
        return frac, andou, len(pil)

    # ---------- estados ----------
    def _troca(self, novo, t, motivo):
        if self.t_estado is not None:
            self.tempos[self.estado] = self.tempos.get(self.estado, 0) + (t - self.t_estado)
        with self.estados_p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"de": self.estado, "para": novo, "em": lw.fmt(t),
                                 "motivo": motivo}, ensure_ascii=False) + "\n")
        print(f"ESTADO {self.estado} -> {novo} as {lw.fmt(t)} ({motivo})", flush=True)
        self.estado, self.t_estado = novo, t

    def passo_estado(self, t):
        frac, andou, n = self._janela(t)
        if n < 20:
            return
        if self.estado in ("VIAJANDO", "VOLTANDO"):
            no_anel, _ = self._no_anel(t)
            if no_anel and frac >= FRAC_COMBATE and andou >= TILES_ANDOU:
                self._troca("CACANDO", t, f"pilha {PILHA_HUNT}+ em {frac:.0%} da janela e {andou:.0f} tiles")
                self.lap_ini, self.batidos, self.pilha_min = t, [], 99
                self.cp_ini = None
        elif self.estado == "CACANDO":
            no_anel, atraso = self._no_anel(t)
            if (not no_anel) or atraso >= 30:
                motivo = ("saiu da area da hunt" if not no_anel and atraso < 30
                          else f"rastreio sem posicao no anel ha {atraso}s")
                self._troca("INDO_REFILL", t, motivo)
                if self.cp_ini:
                    print(f"  volta {self.volta} descartada: saiu da hunt no meio "
                          f"({len(set(self.batidos))}/{len(self.cps)} do circuito)", flush=True)
                self.lap_ini, self.cp_ini, self.batidos = None, None, []
        elif self.estado == "INDO_REFILL":
            pts = [p for p in self.pos if t - PARADO_REFILL_S <= p[0] <= t]
            desl = sum(math.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2])
                       for i in range(1, len(pts)))
            no_anel, atraso = self._no_anel(t)
            if atraso >= 60 or (len(pts) >= 5 and desl <= 4):
                self._troca("NO_REFILL", t, f"parado/fora do anel ({atraso}s sem posicao no anel)")
        elif self.estado == "NO_REFILL":
            no_anel, atraso = self._no_anel(t)
            if no_anel and atraso <= 10:
                self._troca("VOLTANDO", t, "reapareceu na area da hunt")

    # ---------- volta por checkpoint ----------
    def _cp_em(self, x, y):
        for c in self.cps:
            if math.hypot(x - c["xy"][0], y - c["xy"][1]) <= c["raio"]:
                return c
        return None

    def passo_volta(self, t, x, y):
        if self.estado != "CACANDO":
            return
        pil = max([n for tt, n in self.bat.items() if t - 4 <= tt <= t] or [99])
        self.pilha_min = min(self.pilha_min, pil)
        c = self._cp_em(x, y)
        if not c:
            return
        if self.cp_ini is None:
            self.cp_ini = c["nome"]
            self.batidos = [c["nome"]]
            self.lap_ini = t
            print(f"VOLTA {self.volta} abriu em {c['nome']} as {lw.fmt(t)} "
                  f"(fecha ao voltar em {c['nome']} tendo passado pelos outros 3)", flush=True)
            return
        if c["nome"] == self.batidos[-1]:
            return
        if c["nome"] == self.cp_ini:
            if len(set(self.batidos)) >= len(self.cps):
                self.fechar(t)
            else:
                falta = [x["nome"] for x in self.cps if x["nome"] not in self.batidos]
                print(f"  volta {self.volta}: voltou em {c['nome']} as {lw.fmt(t)} SEM fechar o "
                      f"circuito (falta {', '.join(falta)}) — nao conta volta", flush=True)
            return
        else:
            self.batidos.append(c["nome"])
            q = len(set(self.batidos))
            print(f"  {q}/{len(self.cps)} da volta {self.volta} — passou em {c['nome']} "
                  f"as {lw.fmt(t)} (pilha {pil})", flush=True)

    def fechar(self, t):
        limpou = self.pilha_min <= self.ref["volta"]["pilha_limpa_quando"]
        dur = t - self.lap_ini
        out = {"volta": self.volta, "inicio": lw.fmt(self.lap_ini), "fim": lw.fmt(t),
               "dur_s": dur, "checkpoints": self.batidos, "abriu_em": self.cp_ini,
               "pilha_min": self.pilha_min, "regiao_limpa": limpou}
        with self.laps_p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"VOLTA {self.volta} FECHADA {lw.fmt(self.lap_ini)}-{lw.fmt(t)} ({dur}s) "
              f"por {self.cp_ini} · pilha minima {self.pilha_min} · "
              f"{'regiao limpa' if limpou else 'REGIAO NAO LIMPOU'}", flush=True)
        if self.volta == COACH_NA_VOLTA:
            print(f"PREPARAR_COACH volta {self.volta} — juntar frames e box agora para o coach "
                  f"sair pronto no fim da volta {COACH_NA_VOLTA + 1}", flush=True)
        self.volta += 1
        self.lap_ini, self.cp_ini, self.batidos, self.pilha_min = t, None, [], 99

    # ---------- box ao vivo ----------
    def passo_box(self, t):
        if self.estado != "CACANDO":
            return
        pts = [p for p in self.pos if t - BOX_PARADO_S <= p[0] <= t]
        if len(pts) < 4:
            return
        desl = sum(math.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2])
                   for i in range(1, len(pts)))
        pil = max([n for tt, n in self.bat.items() if t - BOX_PARADO_S <= tt <= t] or [0])
        if desl <= 2.0 and pil >= BOX_PILHA:
            if self.box_aberto is None:
                self.box_aberto = t
                print(f"BOX comecou {lw.fmt(t)} em ({pts[-1][1]:.0f},{pts[-1][2]:.0f}) "
                      f"pilha {pil} — analise sai ao fim da volta", flush=True)
        elif self.box_aberto is not None:
            print(f"BOX terminou {lw.fmt(t)} (durou {t - self.box_aberto}s)", flush=True)
            self.box_aberto = None

    # ---------- laco ----------
    def rodar(self):
        vistos = set()
        while True:
            self.atualizar()
            porpos = {p[0]: (p[1], p[2]) for p in self.pos}
            base = sorted(set(self.bat) | set(porpos))     # tempo, nao posicao
            for t in [t for t in base if t not in vistos]:
                vistos.add(t)
                self.passo_estado(t)
                xy = porpos.get(t)
                if xy:
                    self.passo_volta(t, xy[0], xy[1])
                    self.passo_box(t)
            if self.replay:
                break
            time.sleep(5)
        if self.t_estado is not None and self.pos:
            self.tempos[self.estado] = self.tempos.get(self.estado, 0) + (self.pos[-1][0] - self.t_estado)
        print("\nTEMPO POR ESTADO:", {k: f"{v // 60}min{v % 60:02d}" for k, v in self.tempos.items()}, flush=True)


if __name__ == "__main__":
    rep = "--replay" in sys.argv
    v = Vigia(sys.argv[1], sys.argv[2], rep, "_replay" if rep else "")
    v.rodar()
