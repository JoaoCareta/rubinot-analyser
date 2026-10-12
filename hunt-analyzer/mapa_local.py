"""Mapa da hunt colado dos próprios m_, sem depender do minimapa do cliente (user, 23/09).

Na Unhallowed Crypt de 23/09 o cliente não gravou os .otmm da área: o `mapa_mundo` devolveu None a
hunt inteira (medido: 0 casamento acima de 0,82 no mundo todo) e a tela ficou sem mapa. Aqui o mapa
sai do que a captura já tem — os recortes m_ do Map View — colados um no outro:

  MapaLocal.passo(png)       posição em TILES, relativa ao 1º quadro (< 50 ms), e cola o m_ no plano
  MapaLocal.fundo(z, bbox)   PNG 1 px por tile como data URL: MESMA assinatura do mapa_mundo.fundo
  MapaLocal.ancorar(...)     casa o plano com o mundo quando os .otmm aparecem -> coordenada de verdade
  refazer_trilha(sessao)     refaz a trilha de uma sessão inteira dos m_ (histórico), ancorada ou não

O plano guarda ÍNDICE de paleta (1 byte por px, 255 = vazio), o mesmo dado dos .otmm: 2,4 MB por
andar, não cresce com as horas de hunt e casa direto contra o mundo.

Posição = {"x", "y", "z", "score", "fonte"}. z = número do plano enquanto o mapa é relativo e o andar
de verdade depois do ancorar(). Medido em 23/09 contra a trilha absoluta das mesmas sessões, depois
de ancorar: Livraria de Fogo z12 escala 1,0001 e rotação 0,001°, erro mediano 0,03 tile em 1.814
pontos (z13: 1,0002 / 0,03° / 0,06 tile); Book World 0,9998 / 0,004° / 0,04 tile. Na cripta, onde não
há mapa nenhum do cliente, as 10 voltas fecham a 19,3 tiles (o lap_watch mede 18-20 pelo caminho dele)
e a deriva de ponta a ponta em 41 min é de 23,7 tiles.
"""
import base64
import io
import os
import pathlib

import cv2
import numpy as np
from PIL import Image

import dead_reckon as dr
import mapa_mundo as mm
from anchor_map import PAL
from pin_detect import PIN_TIP_PX

ZOOM = 2             # Map View: 2 px por tile
LADO = 1536          # px de cada plano: 768 tiles de lado, 2,4 MB — hunt de 3 h não estoura
VAZIO = 255          # índice reservado: 0 é preto de verdade (tile que o cliente não mostrou)
RAIO = 24            # px em volta da posição prevista onde o quadro novo é procurado
COB = 0.45           # cobertura mínima do plano na janela para valer a pena casar
LIM = 0.72           # score mínimo do casamento contra o próprio mosaico
MARGEM = 8           # tiles de folga em volta da área colada, no fundo
ERRO_MAX = 0.05      # erro do casamento no mundo (medido em 23/09: 0,003 a 0,026 no lugar certo)
FINO = 48            # tiles de folga na conferência fina: a busca grossa (4 tiles/px) erra mais que
                     # os 8 tiles de antes quando o mosaico é grande e cheio de buraco
AMOSTRAS = 6         # quadros guardados por plano para conferir a âncora
TOL = 6.0            # tiles: o quanto o quadro solto pode discordar do mapa local e ainda ancorar
MIN_TILES = 1000     # mosaico menor que isso não tem forma para casar no mundo
MAX_PLANOS = 8       # teto de memória: 8 x 2,4 MB. Viagem pula de cidade em cidade e cria plano

# a PAL só tem as 216 cores do cubo: o resto, VAZIO inclusive, já sai preto — igual ao não explorado
PAL_BGR = np.ascontiguousarray(PAL[:, ::-1])


def _seg(nome):
    return int(nome[2:4]) * 3600 + int(nome[4:6]) * 60 + int(nome[6:8])


def indices(png):
    """m_ -> índices da paleta de 216 cores (a mesma dos .otmm); 97% dos px já caem no cubo de 51."""
    a = np.asarray(Image.open(png).convert("RGB"), dtype=np.int16)   # PIL: caminho com acento
    q = (a + 25) // 51
    return (q[:, :, 0] * 36 + q[:, :, 1] * 6 + q[:, :, 2]).astype(np.uint8)


def mascara_fixa(pngs):
    """Px que o cliente desenha por cima e não andam com o mapa (pin, bússola, borda do painel):
    ficam iguais em quadros distantes. Sem tirar isso, a bússola borra o mosaico inteiro."""
    a = np.stack([indices(p) for p in pngs])
    return (a == a[0]).all(axis=0)


class _Plano:
    """Um andar colado: índices de paleta num canvas fixo + onde ficou o último quadro."""

    def __init__(self, z):
        self.z = z                 # número do plano, ou o andar de verdade depois do ancorar()
        self.g = np.full((LADO, LADO), VAZIO, np.uint8)
        self.o = None              # origem do último recorte, em px do canvas
        self.v = np.zeros(2)       # px por quadro: prevê onde o próximo cai
        self.anc = None            # (dx, dy) px: canvas -> mundo, depois de ancorar
        self.visto = 0             # nº do último quadro que caiu aqui (ordem de busca)
        self.quadros = 0           # quantos quadros caíram aqui: a hunt tem centenas, a viagem tem 1
        self.bb = None             # [x0, y0, x1, y1] do que já foi colado (varrer o canvas custa 15 ms)
        self.amostras = []         # (png, origem) espalhadas: a conferência do ancorar() sai daqui
        self.passo_am = 4          # dobra quando a lista enche: amostra espalhada sem guardar tudo


class MapaLocal:
    """Cola os m_ e devolve a posição em tiles. Relativa ao 1º quadro até o ancorar() dar certo."""

    def __init__(self, fixa=None):
        self.fixa = fixa
        self.planos = [_Plano(0)]
        self.atual = 0
        self.prev = None           # quadro anterior em cinza, para o dead reckoning
        self.contas = {}
        self.n = 0                 # quadros lidos

    # ---------------------------------------------------------------- rastreio

    def passo(self, png):
        """Posição do m_ em tiles, colando-o no plano. None = não deu para situar o quadro."""
        try:
            idx = indices(png)
        except OSError:            # quadro ainda sendo gravado
            return None
        cinza = cv2.cvtColor(PAL_BGR[idx], cv2.COLOR_BGR2GRAY).astype(float) / 255.0
        p = self.planos[self.atual]
        ch, cw = idx.shape
        fonte, score = "inicio", 1.0
        self.n += 1

        if p.o is None:
            p.o = np.array([(LADO - cw) // 2, (LADO - ch) // 2], float)
        else:
            achado, score = self._casa(p, idx, p.o + p.v, RAIO)
            fonte = "mosaico"
            if achado is None:
                s = dr.shift_between(self.prev, cinza) if self.prev is not None else None
                achado, fonte = (p.o - np.array(s, float), "dr") if s is not None else (None, "")
            if achado is None:
                # o conteúdo trocou de uma vez: escada, teleporte ou refill. Procura o quadro nos
                # planos que já existem e, se não for de nenhum, abre um plano novo.
                achado, score, fonte = self._reencontra(idx)
            if achado is None:
                self._conta("perdido")
                self.prev, p.v = cinza, np.zeros(2)
                return None
            p = self.planos[self.atual]            # _reencontra pode ter trocado de plano
            p.v = achado - p.o if p.o is not None and fonte in ("mosaico", "dr") else np.zeros(2)
            p.o = achado
        self._conta(fonte)
        self.prev, p.visto = cinza, self.n
        self._cola(p, idx)
        if p.quadros == 1 or p.quadros % p.passo_am == 0:
            p.amostras.append((png, p.o.copy()))
            if len(p.amostras) > AMOSTRAS:            # enche: fica com uma sim, uma não
                p.amostras, p.passo_am = p.amostras[::2], p.passo_am * 2
        dx, dy = p.anc or (0, 0)
        return {"x": (p.o[0] + dx + PIN_TIP_PX[0]) / ZOOM, "y": (p.o[1] + dy + PIN_TIP_PX[1]) / ZOOM,
                "z": p.z, "score": round(float(score), 3), "fonte": fonte}

    def _conta(self, k):
        self.contas[k] = self.contas.get(k, 0) + 1

    def _casa(self, p, idx, alvo, raio, minimo=LIM, cob=COB):
        """Casa o m_ contra o próprio mosaico numa janela em volta de 'alvo'. (origem, score)."""
        ch, cw = idx.shape
        x0 = int(np.clip(round(alvo[0]) - raio, 0, LADO - cw))
        y0 = int(np.clip(round(alvo[1]) - raio, 0, LADO - ch))
        x1 = int(np.clip(round(alvo[0]) + cw + raio, x0 + cw, LADO))
        y1 = int(np.clip(round(alvo[1]) + ch + raio, y0 + ch, LADO))
        janela = p.g[y0:y1, x0:x1]
        if janela.shape[0] < ch or janela.shape[1] < cw or (janela != VAZIO).mean() < cob:
            return None, 0.0
        res = cv2.matchTemplate(PAL_BGR[janela], PAL_BGR[idx], cv2.TM_CCOEFF_NORMED)
        _, sc, _, loc = cv2.minMaxLoc(res)
        if sc < minimo:
            return None, float(sc)
        return np.array([x0 + loc[0], y0 + loc[1]], float), float(sc)

    def _reencontra(self, idx):
        """Quadro que não seguiu do anterior: procura no que já foi colado, plano atual primeiro.
        Exige score maior que o do rastreio normal — enganar aqui joga a rota para o outro lado.
        Só dentro do que cada plano tem colado (mais meio recorte de folga): varrer o canvas
        inteiro custava 200 ms por plano e não achava nada a mais."""
        for i in [self.atual] + sorted((j for j in range(len(self.planos)) if j != self.atual),
                                       key=lambda j: -self.planos[j].visto):
            q = self.planos[i]
            if q.o is None or q.bb is None:
                continue
            bx0, by0, bx1, by1 = q.bb
            meio = np.array([(bx0 + bx1 - idx.shape[1]) / 2, (by0 + by1 - idx.shape[0]) / 2])
            raio = int(max(bx1 - bx0, by1 - by0) / 2 + idx.shape[1] / 2)
            achado, sc = self._casa(q, idx, meio, raio, LIM + 0.08, cob=0.0)
            if achado is not None:
                self.atual = i
                return achado, sc, "salto"
        # planos demais (viagem pulando de cidade em cidade): recicla o que recebeu MENOS quadros,
        # nunca o atual. Por idade ou por área colada, a volta apagava o plano da hunt — e uma
        # cidade inteira entra num quadro só, enquanto a cave aparece aos pedaços.
        if len(self.planos) >= MAX_PLANOS:
            self.atual = min((j for j in range(len(self.planos)) if j != self.atual),
                             key=lambda j: self.planos[j].quadros)
            self.planos[self.atual] = _Plano(self.planos[self.atual].z)
        else:
            self.planos.append(_Plano(len(self.planos)))
            self.atual = len(self.planos) - 1
        return np.array([(LADO - idx.shape[1]) // 2, (LADO - idx.shape[0]) // 2], float), 1.0, "plano"

    def _cola(self, p, idx):
        ox, oy = int(round(p.o[0])), int(round(p.o[1]))
        ch, cw = idx.shape
        p.quadros += 1
        if not (0 <= ox <= LADO - cw and 0 <= oy <= LADO - ch):
            return                                 # ponytail: canvas cheio para de colar; 768 tiles
        blk = p.g[oy:oy + ch, ox:ox + cw]          # de lado cobrem qualquer hunt medida até aqui
        m = (idx != 0) & (blk == VAZIO)            # 0 = preto: tile que o cliente ainda não mostrou
        if self.fixa is not None:
            m &= ~self.fixa
        blk[m] = idx[m]
        p.bb = [min(p.bb[0], ox), min(p.bb[1], oy), max(p.bb[2], ox + cw), max(p.bb[3], oy + ch)] \
            if p.bb else [ox, oy, ox + cw, oy + ch]

    # ---------------------------------------------------------------- saída

    def _plano(self, z):
        # dois planos podem ancorar no mesmo andar (o jogador voltou): vale o que tem mais quadros
        return max((p for p in self.planos if p.z == z), key=lambda p: p.quadros, default=None)

    def limites(self, z):
        """(x0, x1, y0, y1) em tiles da área colada do plano, com MARGEM. None = plano vazio."""
        p = self._plano(z)
        nz = np.nonzero(p.g != VAZIO) if p is not None else (np.array([]),)
        if not len(nz[0]):
            return None
        dx, dy = p.anc or (0, 0)
        return (int((nz[1].min() + dx) // ZOOM) - MARGEM, int((nz[1].max() + dx) // ZOOM) + MARGEM + 1,
                int((nz[0].min() + dy) // ZOOM) - MARGEM, int((nz[0].max() + dy) // ZOOM) + MARGEM + 1)

    def estado(self):
        """Um resumo por plano, para quem monta a tela: [{z, ancorado, quadros, limites}]."""
        return [{"z": p.z, "ancorado": p.anc is not None, "quadros": p.quadros,
                 "limites": self.limites(p.z)} for p in self.planos if p.quadros]

    def fundo(self, z, bbox):
        """Fundo do plano, 1 px por tile, como data URL — igual ao mapa_mundo.fundo."""
        x0, x1, y0, y1 = (int(v) for v in bbox)
        saida = np.full((y1 - y0, x1 - x0), VAZIO, np.uint8)
        p = self._plano(z)
        planos = [p] if p is not None else []
        if p is not None and p.anc is not None:
            mundo = mm._cor(x0, x1, y0, y1, z)
            if mundo is not None:
                saida = mundo.copy()
            planos = sorted((q for q in self.planos if q.z == z and q.anc is not None), key=lambda q:q.quadros)
        for p in planos:
            dx, dy = p.anc or (0, 0)
            cols = x0 * ZOOM - dx + np.arange(x1 - x0) * ZOOM      # px do canvas de cada tile
            rows = y0 * ZOOM - dy + np.arange(y1 - y0) * ZOOM
            oc, orr = (cols >= 0) & (cols < LADO), (rows >= 0) & (rows < LADO)
            if oc.any() and orr.any():
                trecho = p.g[np.ix_(np.round(rows[orr]).astype(int), np.round(cols[oc]).astype(int))]
                anterior = saida[np.ix_(orr, oc)]
                # Mosaicos parciais não apagam regiões já conhecidas do mundo.
                saida[np.ix_(orr, oc)] = np.where((trecho != VAZIO) & (trecho != 0), trecho, anterior)
        buf = io.BytesIO()
        Image.fromarray(PAL[saida]).save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    # ---------------------------------------------------------------- mundo

    def ancorar(self, z, zs=None, registra=None):
        """Casa o mosaico do plano com os .otmm e passa a devolver coordenada de verdade.

        DUAS confirmações (regra do user, 22/09), as duas com o número no log:
          1. o mosaico casa no mundo com erro bem menor que o do 2º melhor lugar;
          2. pelo menos DOIS quadros soltos, espalhados pela sessão e situados só pelo mapa do
             cliente, caem onde o mapa local já dizia — até TOL tiles. Como o mapa local mediu a
             distância entre eles por dead reckoning, isso confere de uma vez o lugar e o percurso.
        Devolve o laudo, ou None quando o mundo ainda não tem a região (a cripta de 23/09).
        """
        diz = registra or (lambda _s: None)
        p = self._plano(z)
        if p is None or p.o is None or p.anc is not None:
            return None
        nz = np.nonzero(p.g != VAZIO)
        if len(nz[0]) < MIN_TILES * ZOOM * ZOOM:
            diz(f"ancorar: mosaico pequeno demais ({len(nz[0]) // (ZOOM * ZOOM)} tiles, "
                f"mínimo {MIN_TILES})")
            return None
        y0, y1, x0, x1 = nz[0].min(), nz[0].max() + 1, nz[1].min(), nz[1].max() + 1
        peq = p.g[y0:y1, x0:x1][::ZOOM, ::ZOOM]                 # 1 px por tile, como os .otmm
        alvo = PAL_BGR[peq].astype(np.float32) / 255.0
        msk = cv2.merge([(peq != VAZIO).astype(np.float32)] * 3)
        n = float(msk[:, :, 0].sum())
        # busca grossa MASCARADA: o mosaico de uma hunt longa é 20% preenchido, e reduzir os buracos
        # junto com o mapa (INTER_AREA puro) fazia o pico grosso cair longe do lugar certo
        gw, gh = max(peq.shape[1] // mm.GROSSO, 1), max(peq.shape[0] // mm.GROSSO, 1)
        grosso = cv2.resize(alvo, (gw, gh), interpolation=cv2.INTER_AREA)
        gmsk = cv2.resize(msk, (gw, gh), interpolation=cv2.INTER_AREA)
        gn = float(gmsk[:, :, 0].sum())

        picos = []
        for zi, X0, Y0, img in mm._indice():
            if (zs is not None and zi not in zs) or img.shape[0] < gh or img.shape[1] < gw:
                continue
            res = cv2.matchTemplate(img.astype(np.float32) / 255.0, grosso, cv2.TM_SQDIFF, mask=gmsk)
            d, _, loc, _ = cv2.minMaxLoc(res)
            picos.append((d / (3 * gn), zi, X0 + loc[0] * mm.GROSSO, Y0 + loc[1] * mm.GROSSO))
        if not picos:
            diz("ancorar: o cliente ainda não gravou bloco nenhum do minimapa")
            return None

        erros = []
        for _d, zi, X, Y in sorted(picos)[:mm.CANDIDATOS]:
            reg = mm.regiao(X - FINO, X + peq.shape[1] + FINO, Y - FINO, Y + peq.shape[0] + FINO, [zi])
            big = reg["big"].get(zi)
            if big is None or big.shape[0] < peq.shape[0] or big.shape[1] < peq.shape[1]:
                continue
            d, _, loc, _ = cv2.minMaxLoc(cv2.matchTemplate(big, alvo, cv2.TM_SQDIFF, mask=msk))
            erros.append((d / (3 * n), zi, reg["X0"] + loc[0], reg["Y0"] + loc[1]))
        if not erros:
            diz("ancorar: nenhum candidato do mundo cabe o mosaico")
            return self._por_quadros(p, z, zs, diz)
        erros.sort()
        erro, zi, X, Y = erros[0]
        segundo = min((e[0] for e in erros[1:]
                       if e[1] != zi or abs(e[2] - X) > 4 or abs(e[3] - Y) > 4), default=9.9)
        laudo = {"z": zi, "x": int(X), "y": int(Y), "tiles": int(n), "erro": round(erro, 4),
                 "segundo": round(segundo, 4), "confere": 0, "desvio": None}
        if erro > ERRO_MAX:                          # 1ª confirmação: o mosaico casou no mundo
            diz(f"ancorar: mosaico não casou — erro {erro:.4f} (limite {ERRO_MAX}), {int(n)} tiles "
                f"colados, 2º lugar a {segundo:.4f}")
            return self._por_quadros(p, z, zs, diz)

        # 2ª confirmação: quadros soltos, espalhados pela sessão, situados SÓ pelo mapa do cliente,
        # caem onde o mapa local (dead reckoning) já dizia — e o deslocamento entre eles bate.
        # O quadro escolhe o andar sozinho (zi-1..zi+1): andar empilhado de Livraria se parece,
        # e errar o andar é errar o mapa inteiro.
        dx, dy = X * ZOOM - int(x0), Y * ZOOM - int(y0)          # canvas px -> mundo px
        desvios, foras = [], []
        for png, o in list(p.amostras)[-AMOSTRAS:]:
            prev = {"x": (o[0] + dx + PIN_TIP_PX[0]) / ZOOM, "y": (o[1] + dy + PIN_TIP_PX[1]) / ZOOM}
            reg = mm.regiao(prev["x"] - 70, prev["x"] + 70, prev["y"] - 70, prev["y"] + 70,
                            range(zi - 1, zi + 2))
            achou = mm.rastrear(png, reg, {**prev, "z": zi})
            if achou is None or achou["z"] != zi:
                continue
            d = (achou["x"] - prev["x"], achou["y"] - prev["y"])
            foras.append(round(float(max(abs(d[0]), abs(d[1]))), 1))
            if max(abs(d[0]), abs(d[1])) <= TOL:
                desvios.append(d)
        laudo["confere"], laudo["desvio"] = len(desvios), foras[:6]
        if len(desvios) < 2:
            diz(f"ancorar: o mosaico casou (erro {erro:.4f}, 2º a {segundo:.4f}) mas só "
                f"{len(desvios)} de {len(p.amostras)} quadros soltos caíram onde o mapa local previa "
                f"(precisa 2; desvios medidos {foras[:6]} tiles, limite {TOL})")
            return self._por_quadros(p, z, zs, diz)
        # os quadros soltos mandam na coordenada do mundo: tira o ~1 tile de viés que a amostragem
        # do mosaico (meio tile de fase) deixa
        med = np.median(np.array(desvios), axis=0)
        p.anc, p.z = (dx + med[0] * ZOOM, dy + med[1] * ZOOM), zi
        diz(f"ancorar: plano {z} é o andar {zi} em ({int(X)}, {int(Y)}) — erro {erro:.4f} contra "
            f"{segundo:.4f} do 2º lugar com {int(n)} tiles colados, e {len(desvios)} de "
            f"{len(p.amostras)} quadros soltos a {foras[:6]} tiles do previsto (limite {TOL})")
        return laudo

    def _por_quadros(self, p, z, zs, diz):
        """Plano B: sem o mosaico, cada quadro solto se acha no mundo pelo mapa_mundo.localizar.
        Duas confirmações: cada quadro já entra com score >= mapa_mundo.MIN_SCORE, e DOIS quadros
        distantes têm de dar o MESMO deslocamento — a distância entre eles é a que o dead reckoning
        mediu, então bater no mundo confere o lugar e o percurso de uma vez."""
        achados = []
        for png, o in p.amostras:
            w = mm.localizar([png], zs)
            if w:
                achados.append((w["z"], w["x"] * ZOOM - o[0] - PIN_TIP_PX[0],
                                w["y"] * ZOOM - o[1] - PIN_TIP_PX[1], w["score"]))
        for zi, dx, dy, sc in achados:
            iguais = [a for a in achados if a[0] == zi and abs(a[1] - dx) <= TOL * ZOOM
                      and abs(a[2] - dy) <= TOL * ZOOM]
            if len(iguais) >= 2:
                d = np.median(np.array([[a[1], a[2]] for a in iguais]), axis=0)
                p.anc, p.z = (d[0], d[1]), zi
                diz(f"ancorar: plano {z} é o andar {zi} pelos quadros soltos — {len(iguais)} de "
                    f"{len(p.amostras)} se acharam no mundo no mesmo lugar (scores "
                    f"{[a[3] for a in iguais][:6]}), espalhamento "
                    f"{float(np.abs(np.array([[a[1], a[2]] for a in iguais]) - d).max()) / ZOOM:.1f} "
                    f"tile (limite {TOL})")
                return {"z": zi, "x": int((d[0] + p.o[0] + PIN_TIP_PX[0]) / ZOOM),
                        "y": int((d[1] + p.o[1] + PIN_TIP_PX[1]) / ZOOM), "tiles": 0,
                        "erro": None, "segundo": None, "confere": len(iguais), "desvio": [],
                        "fonte": "quadros"}
        diz(f"ancorar: RELATIVO — só {len(achados)} de {len(p.amostras)} quadros soltos se acharam "
            f"no mundo e não fecharam dois no mesmo lugar (o cliente não gravou o minimapa daqui)")
        return None


# -------------------------------------------------------------------- sessão inteira

def refazer_trilha(sessao, passo_s=2, zs=None, registra=None, ancorar=True):
    """Refaz a trilha de uma sessão inteira a partir dos m_ (histórico, user 23/09).

    Devolve {"pontos": [[t, z, x, y]], "ancorado", "planos": {z: bbox}, "mapa", "laudos", "contas"}.
    ancorado=False => coordenada RELATIVA: a forma da rota vale, o lugar no mundo não.
    """
    sessao = pathlib.Path(sessao)
    diz = registra or (lambda _s: None)
    ms, t_ant = [], -10 ** 9
    for nome in sorted(n for n in os.listdir(sessao) if n.startswith("m_") and n.endswith(".png")):
        if _seg(nome) - t_ant >= passo_s:
            ms.append((_seg(nome), sessao / nome))
            t_ant = _seg(nome)
    if len(ms) < 8:
        diz(f"trilha dos m_: só {len(ms)} quadros, sem mapa")
        return {"pontos": [], "ancorado": False, "planos": {}, "mapa": None, "laudos": [], "contas": {}}
    mapa = MapaLocal(mascara_fixa([p for _, p in ms[::max(len(ms) // 16, 1)]][:16]))
    pontos = []
    for t, png in ms:
        r = mapa.passo(png)
        if r:
            pontos.append([t, r["z"], round(r["x"], 1), round(r["y"], 1)])
    laudos = []
    for p in list(mapa.planos) if ancorar else []:
        antes = p.z
        laudo = mapa.ancorar(antes, zs, diz)
        if laudo:
            dx, dy = p.anc
            for q in pontos:
                if q[1] == antes:
                    q[1], q[2], q[3] = p.z, round(q[2] + dx / ZOOM, 1), round(q[3] + dy / ZOOM, 1)
            laudos.append({"plano": antes, **laudo})
    diz(f"trilha refeita dos m_: {len(pontos)} pontos, {len(mapa.planos)} plano(s), "
        f"{'ancorada no mundo' if laudos else 'RELATIVA (o cliente não tem o minimapa daqui)'}, "
        f"{mapa.contas}")
    return {"pontos": pontos, "ancorado": bool(laudos), "laudos": laudos, "mapa": mapa,
            "planos": {p.z: mapa.limites(p.z) for p in mapa.planos}, "contas": dict(mapa.contas)}


if __name__ == "__main__":
    import sys
    import tempfile
    import time

    if len(sys.argv) > 1:                 # sessão de verdade: python mapa_local.py capture/session_X
        t0 = time.time()
        r = refazer_trilha(pathlib.Path(sys.argv[1]), registra=lambda m: print(" ", m))
        n = max(len(r["pontos"]), 1)
        print(f"{len(r['pontos'])} pontos em {time.time() - t0:.0f} s "
              f"({1000 * (time.time() - t0) / n:.0f} ms/quadro), ancorado={r['ancorado']}")
        for e in r["mapa"].estado():
            print("  ", e)
        assert r["pontos"], "nenhum ponto: o mapa local não saiu"
        sys.exit()

    # autoteste sem sessão: m_ sintéticos tirados do próprio minimapa, andando um quadrado fechado
    # (o mesmo truque do mapa_mundo.py). Falha se o rastreio derivar, se o fundo sair torto ou se o
    # ancorar() perder o lugar de verdade.
    X, Y, Z, L = 32636, 32690, 12, 18     # Livraria de Fogo, quadrado de 18 tiles
    assert mm._bloco(X // 64 * 64, Y // 64 * 64, Z) is not None, "minimapa do cliente sem a Livraria"
    passos = ([(i, 0) for i in range(L)] + [(L, i) for i in range(L)] +
              [(L - i, L) for i in range(L)] + [(0, L - i) for i in range(L + 1)])
    with tempfile.TemporaryDirectory() as d:
        pngs = []
        for i, (ax, ay) in enumerate(passos):
            c = mm._cor(int(X + ax - PIN_TIP_PX[0] / ZOOM), int(X + ax - PIN_TIP_PX[0] / ZOOM) + 97,
                        int(Y + ay - PIN_TIP_PX[1] / ZOOM), int(Y + ay - PIN_TIP_PX[1] / ZOOM) + 88, Z)
            png = os.path.join(d, f"m_{i:06d}_000.png")
            Image.fromarray(PAL[np.kron(c, np.ones((ZOOM, ZOOM), np.uint8))][:176, :193]).save(png)
            pngs.append(png)
        mapa, achados, t0 = MapaLocal(), [], time.time()
        for png in pngs:
            r = mapa.passo(png)
            assert r, f"perdeu o quadro {png}"
            achados.append((r["x"], r["y"]))
        ms = 1000 * (time.time() - t0) / len(pngs)
        erro = max(max(abs(a[0] - achados[0][0] - p[0]), abs(a[1] - achados[0][1] - p[1]))
                   for a, p in zip(achados, passos))
        fecho = abs(achados[-1][0] - achados[0][0]) + abs(achados[-1][1] - achados[0][1])
        print(f"rastreio: {len(pngs)} quadros, {ms:.0f} ms/quadro, erro máximo {erro:.1f} tile, "
              f"fecho {fecho:.1f} tile, planos {len(mapa.planos)}")
        assert erro <= 1.0, f"rota local torta: {erro} tiles de erro"
        assert fecho <= 1.0, f"a volta não fechou: {fecho} tiles"
        assert ms < 50, f"{ms:.0f} ms por quadro: acima do teto de 50 ms"
        assert len(mapa.planos) == 1, "abriu plano à toa numa caminhada contínua"
        bbox = mapa.limites(0)
        assert mapa.fundo(0, bbox).startswith("data:image/png;base64,")
        laudo = mapa.ancorar(0, [Z], registra=lambda m: print(" ", m))
        assert laudo and laudo["z"] == Z, f"não ancorou no andar certo: {laudo}"
        p0 = mapa.planos[0]
        px = (p0.o[0] + p0.anc[0] + PIN_TIP_PX[0]) / ZOOM, (p0.o[1] + p0.anc[1] + PIN_TIP_PX[1]) / ZOOM
        assert abs(px[0] - X) <= 2 and abs(px[1] - Y) <= 2, f"ancorou fora do lugar: {px} != {(X, Y)}"
        depois = mapa.passo(pngs[-1])
        assert depois['z'] == Z and abs(depois['x'] - X) <= 2 and abs(depois['y'] - Y) <= 2, depois
        print(f"âncora: andar {laudo['z']}, última posição ({px[0]:.1f}, {px[1]:.1f}) contra "
              f"({X}, {Y}) de verdade")
    print("mapa_local ok")
