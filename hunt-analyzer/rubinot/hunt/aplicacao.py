"""Motor ao vivo da tela de hunt (/hunt): grava, acha o lugar no mapa, segue a trilha e monta as voltas.

21/09 (user): depois da calibração o programa grava sozinho, percebe o início da hunt, fecha as
voltas e a tela atualiza a cada volta. Roda dentro do app.py, em duas threads:
  supervisor (5 s): relança na MESMA sessão a captura e o lap_watch que morreram;
  análise (5 s): posição pelo minimapa do cliente (mapa_mundo, qualquer hunt), cards das voltas
  (pt_card), bichos, nome da hunt pelo catálogo e fundo dos andares. Erro vira estado.mensagem.
json_hunt() = o JSON de /api/hunt: formato do ui/mock_hunt.json + "estado".

22/09 (user), em cima das decisões do lap_watch/sinais.py:
  refis      cada ida ao depot com início, fim e duração, e as estatísticas da sessão (item 4);
  trechos    linha do tempo (cidade, espera, hunt, refil) e as entradas (hunt, cave) (item 2);
  espécies   bicho de outra hunt sai da conta (item 3);
  histórico  hunt_data/<hunt>/sessoes/<AAAAMMDD_HHMM>/ a cada volta e no fim, sem prints (item 5);
  analise.log  uma linha por decisão e por evento, com os números (item 6), em /api/log;
  reiniciar()  fecha a sessão e começa outra sem derrubar o programa (item 7).
"""
import base64
import copy
import io
import bisect
import collections
import datetime as dt
import json
import math
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import traceback

import atlas_build as ab
import capture
import catalogo
import lap_watch as lw
import layout
import fontes
import locais
import mapa_local as ml
import mapa_mundo as mm
import pt_card
import ks
import sinais as sg
import runtime
import configuracoes
from rubinot.adapters.historico import reservar_sessao

AQUI = pathlib.Path(__file__).resolve().parents[2]
CALIB = fontes.caminhos()[0]
LOCAIS_PLAYER = AQUI / "locais_player.json"


def house_player(char):
    try:
        dados = json.loads(LOCAIS_PLAYER.read_text(encoding='utf-8'))
        return dados.get((char or '').casefold(), {}).get('house')
    except (OSError, ValueError):
        return None


CAPTURAS = pathlib.Path(os.environ.get("HUNT_CAPTURAS_RAIZ") or AQUI / "capture")
HUNT_DATA = pathlib.Path(os.environ.get("HUNT_DATA") or AQUI / "hunt_data")  # histórico (o teste aponta para outra)
# caminho completo na linha de comando: é por ele que o controle.py encerra os processos
SCRIPTS = {"capture": AQUI / "capture.py", "lap_watch": AQUI / "lap_watch.py", "ks": AQUI / "ks.py"}
SEM_JANELA = 0x08000000   # CREATE_NO_WINDOW
TICK_S = 5
PASSO_S = 2               # um ponto da trilha a cada 2 s
BATTLE_S = 2              # b_ mais distante que isso do m_ não vale para o ponto
BUSCA_S = 30              # perdido (refill, templo): busca no mundo inteiro no máximo a cada 30 s de jogo
# 23/09 (user): cave que o cliente ainda não gravou no minimapa (.otmm) fica sem mapa a hunt inteira
# — na Unhallowed Crypt o mapa_mundo devolveu None nos 1340 quadros e a tela ficou sem mapa até o
# jogador sair. Aí o mapa sai dos próprios m_ (mapa_local.py), em coordenada RELATIVA, e vira o do
# mundo assim que o ancorar() casar o mosaico com os .otmm.
LOCAL_BUSCAS = 2          # buscas no mundo falhadas (uma a cada BUSCA_S) antes de montar o local
LOCAL_GAP = 60            # s de jogo sem nenhuma posição do mundo
LOCAL_COLA = 0.8          # 2ª confirmação: fração dos m_ que o mosaico local conseguiu colar
LOCAL_MASCARA = 0.75      # máscara de px fixos maior que isso = jogador parado: cola sem máscara
LOCAL_MAX = 400           # quadros relidos ao ligar o local (13 min; o normal é ligar em ~1 min)
LOCAL_RECUSAS = 3         # mosaico que não cola 3 vezes: desiste (Map View fora do lugar)
LOCAL_MIN_QUADROS = 30    # plano com menos quadros que isso não tem forma para procurar no mundo
MAX_ANCORA = 2            # planos procurados no mundo por vez (~4 s cada): o resto fica para depois
# tenta trocar o local pelo do mundo a cada 10 min de jogo: é o mm.RECARGA_S, e antes disso o índice
# do mundo está em cache — a resposta seria a mesma, só que 4 s mais cara
ANCORA_S = 600
FOLGA = 160               # região de rastreio = área visitada + 160 tiles (o m_ tem 97x88)
PERTO = 300               # pontos a mais que isso da posição são de outro lugar (cidade do refill)
MARGEM = 6                # tiles em volta da área visitada no fundo dos andares
MIN_PTS_ANDAR = 8         # andar com menos pontos que isso na hunt é passagem: fica sem mapa
GRADE = 8                 # fundo em múltiplos de 8 tiles: não troca a imagem a cada passo
PARADO_S = 20             # sem quadro novo há mais que isso = captura em espera
# auto-stop de 3 h da captura: emenda se uma volta fechou na última hora. 22/09: era 15 min, e um
# refill/pausa longa na marca das 3 h perdia o resto da hunt; 1 h = a mesma regra da retomada
EMENDA_S = 3600
RETOMA_S = 3600           # 21/09 (user): religar com a última hunt parada há menos de 1 h continua nela
REDE_S = 300              # catálogo sem internet: pergunta de novo em 5 min
# 21/09: o card em cache (cards.jsonl) é do pt_card + as espécies do ao_vivo; leitor novo = recalcula
VERSAO = f"{pt_card.VERSAO}.1"
# nome do wiki -> apelido do user, raw XP por bicho pelo tamanho da pt (CLAUDE.md, 21/09) e a
# pasta do histórico em hunt_data (as pastas já existem desde julho)
# a tabela das hunts (nome, pasta, raw por bicho) mora no locais.py: o pt_card usa a mesma
PARCIAL = ("sessao parou", "gravacao parou")
# 22/09 (user item 3): espécie de outra hunt sai da conta com DUAS confirmações — o CATÁLOGO (os
# locais fixos dela não incluem o local desta hunt) e a PRESENÇA (aparece em poucas voltas).
# Medido na sessão de 22/09: as da Livraria de Gelo (icecold book, squid warden) e as de passagem
# (knowledge elemental, dog, animated feather) ficaram em 2 a 3 das 36 voltas (<= 8%); as da Fogo,
# em 10 a 36 voltas (28% a 100%) — inclusive flying book, que é a mais rara delas.
FORA_PRESENCA = 0.25
FORA_MIN_VOLTAS = 4       # com menos voltas fechadas a presença ainda não separa: não filtra nada
GLYPHS, GAP = ab.load_atlas()
_MONSTROS = {}            # nome -> (entrada | None = o wiki não conhece | False = sem resposta, quando)


def monstro(nome):
    """Entrada do catálogo ou None (player/NPC da Battle List). Sem internet: None e tenta em REDE_S."""
    e, quando = _MONSTROS.get(nome, (False, 0.0))
    if e is False and time.time() - quando >= REDE_S:
        try:
            e = catalogo.buscar(nome)
        except (OSError, ValueError, LookupError):
            e = False
        _MONSTROS[nome] = (e, time.time())
    return e or None


def _le_json(p, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # não existe ou pego no meio da escrita
        return padrao


def _jsonl(p):
    """Linhas de um .jsonl da sessão; a última pode estar pela metade (o lap_watch escrevendo)."""
    if not p.exists():
        return []
    out = []
    for linha in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        try:
            out.append(json.loads(linha))
        except ValueError:
            continue
    return out


def _texto_decisao(d):
    """Linha do decisoes.jsonl (lap_watch) em uma frase com os números que a sustentam."""
    q, dec, num = d.get("quando", ""), d.get("decisao", ""), d.get("numeros", "")
    if dec == "hunt comecou":
        return f"{q} hunt começou às {d.get('inicio')} — {num}"
    if dec == "refil comecou":
        return f"{q} refil começou às {d.get('inicio')} — {num}"
    if dec == "refil acabou":
        return f"{q} refil acabou · {d.get('dur_s')} s"
    if dec.startswith("volta"):
        return (f"{q} {dec} ({d.get('fechada_por')}) · {d.get('kills')} bichos · raio "
                f"{d.get('raio')} · percurso {d.get('percurso')}" + (f" · {d['porque']}" if d.get("porque") else ""))
    return f"{q} {dec}{' — ' + num if num else ''}"


def _vazio():
    return {"sessao": {}, "andares": {}, "voltas": [], "amostras": [], "refis": [], "refil": {},
            "trechos": [], "entradas": [], "especies_fora": {}}


def _agora_s():
    n = dt.datetime.now()
    return n.hour * 3600 + n.minute * 60 + n.second


def _char_da_sessao(s):
    log = s / "capture.log"
    m = re.search(r"RubinOT Client - ([^']+)'", log.read_text(encoding="utf-8", errors="replace")) if log.exists() else None
    return m[1].strip() if m else None


QUADRO = re.compile(r"^[bcmfsq]_\d+_\d+\.png$")


def limpa_quadros(manter=None, raiz=None):
    """Apaga os QUADROS das sessões já encerradas (user, 28/09: "o que me interessa são os números,
    porém os vídeos não"). Os números — laps.jsonl, cards.jsonl, trilha.jsonl, logs — ficam onde
    estão, e o histórico em hunt_data nem é tocado. A sessão passada em `manter` fica inteira: é
    dela que o retomavel() continua se você religar em menos de 1 h.

    Sem isso a pasta capture ia a 3 GB por hora de hunt e o disco enchia sozinho.
    """
    manter = str(manter) if manter else ""
    apagados = bytes_ = 0
    for s in sorted((raiz or CAPTURAS).glob("session_*")):
        if str(s) == manter or not s.is_dir():
            continue
        estado_aprendizado = _le_json(s / 'aprendizado_estado.json') or {}
        if estado_aprendizado.get('estado') in ('coletando', 'pendente', 'falhou'):
            continue  # Extração incompleta é recuperável; quadros ainda são evidência.
        for p in s.iterdir():
            if p.is_file() and QUADRO.match(p.name):
                try:
                    bytes_ += p.stat().st_size
                    p.unlink()
                    apagados += 1
                except OSError:      # quadro preso por outro processo: fica para a próxima
                    pass
    return apagados, bytes_


def retomavel(char=None, raiz=None):
    """Sessão para continuar (user, 21/09): a hunt mais recente (lap_state = a hunt começou nela), se o
    último m_ tem menos de 1 h, a calibração é a mesma e o personagem também. Pasta sem hunt não conta."""
    for s in sorted((raiz or CAPTURAS).glob("session_*"), reverse=True):
        if not (s / "lap_state.json").exists():
            continue
        ultimo = max((e.stat().st_mtime for e in os.scandir(s) if e.name.startswith("m_")), default=0)
        outro = _char_da_sessao(s)
        ok = (time.time() - ultimo < RETOMA_S and (not char or not outro or outro == char)
              and layout.da_sessao(s) == json.loads(json.dumps(layout.atual()))
              and fontes.da_sessao(s) == fontes.atual())
        return s if ok else None
    return None


class Gravacao:
    def __init__(self):
        self.sessao = None
        self.parar = threading.Event()
        self.trava = threading.Lock()
        self.procs = {}
        self.erros = {}
        self.dados = _vazio()
        self.info = {}
        self.mapa, self.planos, self.t_local = None, [], None   # mapa local: só nasce no _comeca
        self.local = (None, (None, ""))
        self.decisoes, self.n_decisoes = [], 0
        self.n_hist, self.marcos_vistos, self.fora_vistas = -1, set(), set()

    # ------------------------------------------------------------ ciclo de vida

    def ativo(self):
        return self.sessao is not None and not self.parar.is_set()

    def ligar(self, char=None, nova=False):
        """Grava: retoma a hunt de menos de 1 h ou abre sessão nova. A pasta nova só nasce quando a
        captura sobe (jogo aberto): abrir o programa com o jogo fechado não cria sessão vazia.

        nova=True (botão "Iniciar hunt" da tela, 24/09): sessão nova sempre — quem pediu para
        começar a hunt não quer voltar para a que acabou de encerrar.
        """
        if not self.ativo():
            fonte = fontes.atual()
            janela = capture.find_game_rect().get("title", "") if fonte['tipo'] == 'janela' else ''
            char_agora = janela.split(" - ", 1)[1].strip() if " - " in janela else char
            sessao = (None if nova else retomavel(char_agora)) or \
                reservar_sessao(CAPTURAS, dt.datetime.now())
            if fonte['tipo'] == 'twitch':
                char = fonte['char']
            fontes.grava_json(sessao / 'fonte.json', fonte)
            self._comeca(sessao, char, grava=True)
        return self.sessao

    def anexar(self, sessao, char=None):
        """Teste/retomada numa pasta que já existe: sem captura; lap_watch só se chegar m_ novo."""
        if not self.ativo():
            sessao = pathlib.Path(sessao)
            sessao = (sessao if sessao.is_absolute() else AQUI / sessao).resolve()
            sessao.mkdir(parents=True, exist_ok=True)
            self._comeca(sessao, char, grava=False)
        return self.sessao

    def desligar(self):
        with self.trava:
            self.parar.set()
            for p in self.procs.values():
                if p is self.procs.get('ks'):
                    continue
                if p.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                                   creationflags=SEM_JANELA)
            detector = self.procs.get('ks')
            if detector and detector.poll() is None:
                (self.sessao / 'ks_encerrar').touch()
                try:
                    detector.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    # Leitura em atraso: interromper captura não fabrica um fim de KS.
                    detector.terminate()
        try:
            self._fecha_mapa()        # 23/09 (user item 2): o mundo pode ter gravado a região agora
        except Exception as e:        # fechar a sessão nunca pode falhar por causa do mapa
            self.registra(f"erro ao refazer o mapa no fim: {type(e).__name__}: {e}")
        try:
            import observacao_execucao
            if self.sessao and self.char:
                observador=observacao_execucao.Observador()
                limite=time.monotonic()+20
                quadros=sorted(self.sessao.glob('f_*.png'))
                while time.monotonic()<limite:
                    observador.processar(self.sessao,self.char,quadros[-1] if quadros else None)
                    estado=_le_json(self.sessao/'aprendizado_estado.json') or {}
                    if estado.get('estado')=='numeros_persistidos':break
        except Exception as erro:
            configuracoes._grava(self.sessao/'aprendizado_estado.json',{'estado':'falhou','erro':str(erro)})
            self.registra(f'extração de execução pendente: {erro}')
        self._historico(final=True)   # 22/09 (user item 5): a sessão fecha guardada
        n, b = limpa_quadros(manter=self.sessao)   # 28/09 (user): os quadros das sessões velhas vão
        if n:
            self.registra(f"limpeza: {n} quadros de sessões encerradas apagados ({b/1e9:.1f} GB); "
                          "os números de todas elas continuam na pasta")

    def reiniciar(self):
        """Recomeça a análise do zero (user, 22/09 item 7): fecha a sessão de agora (salvando o
        histórico), abre uma sessão nova e volta a esperar a hunt. O servidor não cai e o supervisor
        religa a captura no próximo tique (5 s)."""
        if not self.ativo():
            return None
        char, grava = self.char, self.grava
        self.registra("reinício pedido: esta sessão fecha aqui")
        self.desligar()   # já guarda o histórico da sessão que fecha
        self._comeca(reservar_sessao(CAPTURAS, dt.datetime.now()), char, grava)
        return self.sessao

    # ------------------------------------------------------------ log interno (item 6)

    def registra(self, texto):
        """Uma linha por decisão e por evento, com hora e números (user, 22/09 item 6).

        Não cria a pasta da sessão: ela só nasce quando a captura sobe (jogo aberto).
        """
        if not self.sessao or not self.sessao.is_dir():
            return
        try:
            with (self.sessao / "analise.log").open("a", encoding="utf-8") as fh:
                fh.write(f"{dt.datetime.now():%H:%M:%S} {texto}\n")
        except OSError:  # log nunca derruba a análise
            pass

    def ler_log(self, n=200):
        """Últimas n linhas do analise.log (rota /api/log)."""
        if not self.sessao:
            return []
        try:
            return (self.sessao / "analise.log").read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        except OSError:
            return []

    def _espelha_decisoes(self):
        """decisoes.jsonl do lap_watch (com os sinais e os números) em pt-BR no analise.log."""
        self.decisoes = _jsonl(self.sessao / "decisoes.jsonl")
        for d in self.decisoes[self.n_decisoes:]:
            self.registra(_texto_decisao(d))
        self.n_decisoes = len(self.decisoes)

    def _conta_m(self):
        return sum(1 for e in os.scandir(self.sessao) if e.name.startswith("m_")) if self.sessao.is_dir() else 0

    def _comeca(self, sessao, char, grava):
        self.sessao, self.char, self.grava = sessao, char, grava
        self.parar, self.procs, self.erros, self.info = threading.Event(), {}, {}, {}
        # o que já está na pasta (retomada, anexar) não conta como "crescendo"
        self.n_m = self._conta_m()
        self.visto = None       # time.time() da última vez que chegou m_ novo
        self.t0 = time.time()   # sem quadro ainda: a espera conta daqui (jogo nunca veio para a frente)
        self.pos, self.reg, self.t_busca = None, None, -10 ** 9   # rastreio no minimapa
        # mapa local (23/09): self.mapa = None enquanto o minimapa do cliente dá conta
        self.mapa, self.mapa_pre, self.planos = None, {}, []
        self.buscas_falhas, self.local_recusas, self.local_quer = 0, 0, False
        self.t_local, self.t_ancora = None, -10 ** 9
        self.fundo, self.local = (None, {}), (None, (None, ""))
        self.hunt_comecou = None
        # 22/09: reiniciar abre uma sessão cuja pasta só nasce com a captura, e até lá o _analisa
        # volta na porta — sem limpar aqui, a tela (e o "emenda" do supervisor) seguiam com as
        # voltas da sessão anterior depois do botão Reiniciar
        self.dados = _vazio()
        tr = sessao / "trilha.jsonl"  # retomada: continua de onde parou; sem trilha, refaz dos m_
        self.amostras = [[d["t"], d["z"], d["x"], d["y"], d["battle"]] for d in
                         map(json.loads, tr.read_text(encoding="utf-8").splitlines() if tr.exists() else [])]
        ajuste = (_le_json(AQUI / 'ui' / 'mapa_ajustes.json') or {}).get('sessoes', {}).get(sessao.name, {})
        if ajuste.get('char') == char:
            por_tempo = {c['t']: c for c in ajuste.get('correcoes', [])}
            for a in self.amostras:
                c = por_tempo.get(a[0])
                if c and a[1:4] == c['antes']:
                    a[1:4] = c['depois']
        # 23/09 (user): sessão gravada antes do mapa local ficava com uma trilha de 2 pontos para
        # 45 min de hunt, e o histórico dela abria sem mapa nenhum. Trilha muito menor que os
        # quadros = não dá para continuar dela: refaz dos m_.
        quadros = sum(1 for _ in sessao.glob("m_*.png"))
        if self.amostras and len(self.amostras) * 4 * PASSO_S < quadros:
            self.amostras = []
            tr.unlink(missing_ok=True)
        # 23/09: a parte RELATIVA da trilha não sobrevive ao relance — o mosaico novo tem outra
        # origem, e os dois pedaços juntos dariam um mapa dobrado. O que veio do mundo continua.
        lm = _le_json(sessao / "mapa_local.json") if tr.exists() else None
        if lm and any(a[0] > lm.get("t_local", 0) for a in self.amostras):
            self.amostras = [a for a in self.amostras if a[0] <= lm.get("t_local", 0) or a[2] > 10000 and a[3] > 10000]
            tr.write_text("".join(json.dumps(dict(zip(("t", "z", "x", "y", "battle"), a))) + "\n"
                                  for a in self.amostras), encoding="utf-8")
        self.t_trilha = self.amostras[-1][0] if self.amostras else -PASSO_S
        cs = sessao / "cards.jsonl"
        self.cards = {c["chave"]: c for c in
                      map(json.loads, cs.read_text(encoding="utf-8").splitlines() if cs.exists() else [])}
        # sessão retomada: o que já foi espelhado no analise.log não entra de novo
        self.decisoes = _jsonl(sessao / "decisoes.jsonl")
        self.n_decisoes = len(self.decisoes) if (sessao / "analise.log").exists() else 0
        self.n_hist, self.marcos_vistos, self.fora_vistas = -1, set(), set()
        self.leitor_configuracoes = configuracoes.Leitor()
        for passo in (self._supervisiona, self._analisa):
            threading.Thread(target=self._laco, args=(passo, self.parar), daemon=True).start()

    def _configuracoes(self, parar):
        quadros = sorted(self.sessao.glob('f_*.png'))
        if quadros and not parar.is_set():
            self.leitor_configuracoes.processar(quadros[-1], self.char, self.sessao.name)

    def _laco(self, passo, parar):
        # 22/09: o Event vai por parâmetro — reiniciar() troca o self.parar, e uma thread que lesse
        # o novo Event (nunca marcado) continuaria viva ao lado das threads da sessão nova (e a
        # antiga podia subir uma segunda captura na sessão nova, gravando quadro repetido)
        while not parar.is_set():
            try:
                passo(parar)
                self.erros.pop(passo.__name__, None)
            except Exception as e:  # nunca derruba o programa: detalhe no app.log, tela em pt-BR simples
                msg = f"{type(e).__name__}: {e}"
                if self.erros.get(passo.__name__) != msg:
                    print(f"{passo.__name__}: {traceback.format_exc()}", flush=True)
                    self.registra(f"erro de leitura em {passo.__name__}: {msg}")
                self.erros[passo.__name__] = msg
            parar.wait(TICK_S)

    def _sobe(self, nome, *args):
        self.sessao.mkdir(parents=True, exist_ok=True)
        if nome == 'ks':
            (self.sessao / 'ks_encerrar').unlink(missing_ok=True)
        self.registra(f"{nome} {'relançado' if nome in self.procs else 'iniciado'}")
        with open(self.sessao / f"{nome}.log", "a", encoding="utf-8") as log:
            self.procs[nome] = subprocess.Popen(
                runtime.comando(nome, self.sessao, *args), cwd=AQUI, stdout=log,
                stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, creationflags=SEM_JANELA)

    def _vivo(self, nome):
        p = self.procs.get(nome)
        return p is not None and p.poll() is None

    def _supervisiona(self, parar):
        n = self._conta_m()
        cresceu, self.n_m = n > self.n_m, n
        if cresceu:
            self.visto = time.time()
        with self.trava:
            if parar.is_set() or self.parar is not parar:   # desligado/reiniciado no meio do passo
                return
            cap = self.procs.get("capture")
            if self.grava and not self._vivo("capture") and (fontes.da_sessao(self.sessao)['tipo'] == 'twitch' or capture.find_game_rect()) and not capture.pouco_disco():
                # saída 0 = auto-stop de 3 h: emenda só com a hunt rolando (CLAUDE.md: hunt > 3 h emenda)
                ultima = (self.dados["voltas"] or [{}])[-1].get("fim")
                if cap is None or cap.returncode != 0 or (ultima and _agora_s() - ultima < EMENDA_S):
                    self._sobe("capture")
            # lap_watch sai sozinho após 180 s sem quadro ("sessao parou") e retoma pelo lap_state.json
            if cresceu and not self._vivo("lap_watch"):
                self._sobe("lap_watch", *([self.char] if self.char else []))
            if cresceu and not self._vivo("ks"):
                self._sobe("ks", *([self.char] if self.char else []))

    # ------------------------------------------------------------ análise

    def _analisa(self, parar):
        if parar.is_set() or not self.sessao.is_dir():  # sessão nova: a pasta nasce com a captura
            return
        self.erros.pop("volta", None)
        nomes = sorted(os.listdir(self.sessao))  # ~60k nomes numa hunt de 2 h: dezenas de ms
        ms = [n for n in nomes if n.startswith("m_")][:-1]  # o mais novo pode estar sendo gravado
        bs = [n for n in nomes if n.startswith("b_")][:-1]
        self._trilha(ms, bs)
        self.planos = self.mapa.estado() if self.mapa is not None else []   # limites por plano: a tela rotula
        self._espelha_decisoes()
        laps = self._laps()
        cards = [(L, self._card(L, laps)) for L in laps]
        cards = [(L, c) for L, c in cards if c]

        if not self.hunt_comecou:
            log = self.sessao / "lap_watch.log"
            m = re.search(r"HUNT COMECOU as (\d\d:\d\d:\d\d)",
                          log.read_text(encoding="utf-8", errors="replace")) if log.exists() else None
            self.hunt_comecou = m[1] if m else (laps[0]["inicio"] if laps else None)
        st = _le_json(self.sessao / "lap_state.json")
        nome = re.search(r"(\d{4})(\d\d)(\d\d)_(\d\d)(\d\d)(\d\d)", self.sessao.name)
        self.info = {
            # sem lap_state (pasta sem lap_watch rodando): a seguinte à última fechada
            "volta_atual": ((st or {}).get("lap") or (laps[-1]["volta"] + 1 if laps else 1)) if self.hunt_comecou else None,
            "pausa": bool(st) and st.get("lap_start") is None,
            # 1º quadro: o programa pode abrir bem antes do jogo vir para a frente
            "desde": lw.fmt(lw.fsec(ms[0])) if ms else (":".join(nome.groups()[3:]) if nome else None),
            "data": "/".join(nome.groups()[2::-1]) if nome else dt.date.today().strftime("%d/%m/%Y"),
        }
        # espécies da hunt (chat + Battle List); player e NPC o catálogo não conhece e saem
        vistas = collections.Counter()
        for L, c in cards:
            vistas.update(c["especies"])
        local, hunt = self._local(vistas)
        fora = self._fora(cards, local)
        voltas = [self._volta(L, c, local, fora) for L, c in cards]

        # janelas de hunt: voltas fechadas + a aberta (refill entre voltas fica fora do fundo)
        janelas = [(pt_card.sec(L["inicio"]), pt_card.sec(L["fim"])) for L in laps]
        if st and st.get("lap_start") is not None:
            janelas.append((st["lap_start"], 10 ** 9))
        t0 = pt_card.sec(self.hunt_comecou) if self.hunt_comecou else 0
        ultimo = cards[-1][1] if cards else None
        agora = lw.fsec(ms[-1]) if ms else _agora_s()   # "agora" do jogo = o último quadro gravado
        refis, refil = self._refis(t0, agora)
        lt = self._linha_do_tempo(t0, janelas)
        self.dados = {
            "sessao": {"hunt": hunt, "char": self.char or "",
                       # a tela escreve "gravação desde <inicio>"; o início da hunt vai no estado
                       "data": self.info["data"], "inicio": self.info["desde"] or "",
                       "fim": laps[-1]["fim"] if laps else "",
                       "pt": modalidade_party(_le_json(self.sessao / 'ks.json', {}),
                           ("solo" if ultimo["solo"] else f"pt x{ultimo['membros']}" if ultimo["membros"] else "") if ultimo else "")},
            "andares": self._andares(janelas),
            "voltas": voltas,
            "amostras": [a for a in self.amostras if a[0] >= t0],
            "refis": refis, "refil": refil,
            "trechos": lt["trechos"], "entradas": lt["marcos"],
            "especies_fora": fora,
        }
        self._historico()

    def _trilha(self, ms, bs):
        """Posição dos m_ novos + battle da b_ mais próxima -> trilha.jsonl. Rastreio no minimapa do
        cliente (mapa_mundo) enquanto ele conhece a região; onde ele não gravou nada, mapa local."""
        if self.local_quer:
            self._ativa_local(ms)
        bt = [lw.fsec(n) for n in bs]
        novos = []
        for i, n in enumerate(ms):
            t = lw.fsec(n)
            if t - self.t_trilha < PASSO_S:
                continue
            self.t_trilha = t
            p = self._onde(ms, i, t)
            if self.local_quer:   # mapa local no próximo ciclo: daqui para a frente os quadros
                break             # entram por ele, e a trilha volta para onde o mundo parou
            j = bisect.bisect_left(bt, t)
            j = min((j for j in (j - 1, j) if 0 <= j < len(bt)), key=lambda j: abs(bt[j] - t), default=None)
            if p is None or j is None or abs(bt[j] - t) > BATTLE_S:
                continue
            novos.append([t, p["z"], round(p["x"], 1), round(p["y"], 1), lw.battle_count(self.sessao / bs[j])])
            self.amostras.append(novos[-1])  # a região refeita logo adiante já conta este ponto
        if novos:
            with (self.sessao / "trilha.jsonl").open("a", encoding="utf-8") as fh:
                fh.writelines(json.dumps(dict(zip(("t", "z", "x", "y", "battle"), a))) + "\n" for a in novos)
        if self.mapa is not None and novos and novos[-1][0] - self.t_ancora >= ANCORA_S:
            self.t_ancora = novos[-1][0]
            self._reancorar()

    def _onde(self, ms, i, t):
        """Posição de um m_. Mapa do mundo (minimapa do cliente) ou, depois do _ativa_local, o local."""
        png = self.sessao / ms[i]
        if self.mapa is not None:
            return self.mapa_pre.pop(t) if t in self.mapa_pre else self.mapa.passo(png)
        p = mm.rastrear(png, self.reg, self.pos) if self.reg else None
        if p is None and t - self.t_busca >= BUSCA_S:
            self.t_busca = t
            p = mm.localizar([self.sessao / m for m in ms[max(0, i - 2):i + 1]])
            if p:
                self._regiao(p)
            else:
                self.buscas_falhas += 1
                # 1ª confirmação do mapa local: o mundo não tem esta área (a 2ª é o mosaico colar).
                # Sai no próximo ciclo, com a lista de quadros inteira na mão.
                self.local_quer = (self.local_recusas < LOCAL_RECUSAS and self.buscas_falhas >= LOCAL_BUSCAS
                                   and t - (self.amostras[-1][0] if self.amostras else lw.fsec(ms[0])) >= LOCAL_GAP)
        self.pos = p
        return p

    def _ativa_local(self, ms):
        """Monta o mapa dos próprios m_ (user, 23/09) quando o cliente não gravou o minimapa da área.

        DUAS confirmações, as duas com o número no log: o mundo falhou em LOCAL_BUSCAS buscas
        globais e está há LOCAL_GAP s sem posição; e o mosaico dos m_ cola LOCAL_COLA dos quadros.
        Os quadros relidos entram em self.mapa_pre e a trilha volta para o 1º deles: assim o mapa
        começa onde o mundo parou, sem misturar coordenada do mundo com coordenada relativa.
        """
        self.local_quer = False
        desde = self.amostras[-1][0] if self.amostras else -10 ** 9
        sel, t_ant = [], desde
        for n in ms:   # só até onde a análise chegou: o resto entra pelo passo() daqui para a frente
            if t_ant + PASSO_S <= lw.fsec(n) <= self.t_trilha:
                sel.append(n)
                t_ant = lw.fsec(n)
        sel = sel[-LOCAL_MAX:]
        if len(sel) < 8:
            return
        am = [self.sessao / n for n in sel[::max(len(sel) // 16, 1)][:16]]
        fixa = ml.mascara_fixa(am)
        pct = float(fixa.mean())
        mapa = ml.MapaLocal(fixa if pct <= LOCAL_MASCARA else None)   # parado: quase tudo "fixo"
        pre = {lw.fsec(n): r for n in sel for r in [mapa.passo(self.sessao / n)] if r}
        colados = sum(1 for r in pre.values() if r["fonte"] in ("inicio", "mosaico", "dr"))
        if colados < LOCAL_COLA * len(sel):
            self.local_recusas += 1
            self.registra(f"mapa local recusado ({self.local_recusas} de {LOCAL_RECUSAS}): o mosaico "
                          f"colou só {colados} de {len(sel)} quadros (mínimo {LOCAL_COLA:.0%})")
            return
        self.mapa, self.mapa_pre = mapa, pre
        self.t_local = self.t_trilha = lw.fsec(sel[0]) - PASSO_S
        self.t_ancora = lw.fsec(sel[-1])
        # marca onde a trilha deixou de ser do mundo: se o programa for relançado nesta sessão, o
        # _comeca corta daqui para a frente em vez de emendar dois mosaicos de origens diferentes
        (self.sessao / "mapa_local.json").write_text(json.dumps({"t_local": self.t_local}), encoding="utf-8")
        self.registra(f"mapa local ligado às {lw.fmt(lw.fsec(sel[-1]))}: o minimapa do cliente não tem "
                      f"esta área ({self.buscas_falhas} buscas no mundo sem achar) e o mosaico dos m_ "
                      f"colou {colados} de {len(sel)} quadros ({pct:.0%} de px fixos "
                      f"{'mascarados' if pct <= LOCAL_MASCARA else 'ignorados'}). "
                      "Coordenada RELATIVA até o mundo gravar a região")

    def _reancorar(self):
        """Troca o mapa local pelo do mundo quando o cliente finalmente grava os .otmm da área (ele
        grava ao sair dela). Só os planos da hunt (os de mais quadros) e no máximo MAX_ANCORA por
        vez: ancorar custa ~4 s por plano, e os planos de 10 quadros são o caminho do refil — os
        que sobrarem entram no ciclo seguinte. True = a trilha virou coordenada do mundo."""
        alvos = sorted((p for p in self.mapa.planos if p.anc is None and p.quadros >= LOCAL_MIN_QUADROS),
                       key=lambda p: -p.quadros)[:MAX_ANCORA]
        mudou = 0
        for p in alvos:
            antes = p.z
            laudo = self.mapa.ancorar(antes, registra=self.registra)
            if not laudo or p.anc is None:   # dois planos com o mesmo número: quem ancorou foi o outro
                continue
            dx, dy = p.anc
            n = 0
            for a in self.amostras:   # só os pontos do mapa local: os do mundo já estão no lugar
                if a[1] == antes and a[0] >= (self.t_local or 0):
                    a[1], a[2], a[3] = p.z, round(a[2] + dx / ml.ZOOM, 1), round(a[3] + dy / ml.ZOOM, 1)
                    n += 1
            mudou += n
            self.registra(f"trilha refeita no mundo: {n} pontos do plano {antes} viraram o andar "
                          f"{p.z} em ({laudo['x']}, {laudo['y']})")
        if not mudou:
            return False
        (self.sessao / "trilha.jsonl").write_text(
            "".join(json.dumps(dict(zip(("t", "z", "x", "y", "battle"), a))) + "\n" for a in self.amostras),
            encoding="utf-8")
        self.fundo = (None, {})
        return True

    def _regiao(self, p):
        """Região de rastreio: o que já foi visitado perto de p + FOLGA, andares visitados +- 2."""
        pts = [(a[2], a[3], a[1]) for a in self.amostras
               if abs(a[2] - p["x"]) <= PERTO and abs(a[3] - p["y"]) <= PERTO] + [(p["x"], p["y"], p["z"])]
        xs, ys, zs = zip(*pts)
        self.reg = mm.regiao(min(xs) - FOLGA, max(xs) + FOLGA, min(ys) - FOLGA, max(ys) + FOLGA,
                             range(min(zs) - 2, max(zs) + 3))

    def _laps(self):
        p = self.sessao / "laps.jsonl"
        if not p.exists():
            return []
        por_n = {}
        for linha in p.read_text(encoding="utf-8-sig").split("\n")[:-1]:  # a última pode estar pela metade
            if linha.strip():
                L = json.loads(linha)
                # 22/09: o lap_watch já manda deslocamento para trechos.jsonl; se um escapar para cá
                # (sessão antiga, relance), ele não é volta e não entra na conta
                if L.get("tipo", "volta") == "volta":
                    por_n[L["volta"]] = L  # relançado, fecha de novo a mesma volta: vale a última
        return [por_n[n] for n in sorted(por_n)]

    def _card(self, L, laps):
        """Card do pt_card + espécies, calculado uma vez e guardado em cards.jsonl (chave com a versão)."""
        chave = f"{VERSAO}|{L['volta']}|{L['fim']}"
        if chave not in self.cards:
            try:
                c = {"chave": chave, **pt_card.volta(self.sessao, GLYPHS, GAP, L, laps)}
                # volta gravada pelo lap_watch de antes de 21/09 não tem espécies: lê a Battle List
                c["especies"] = L["especies"] if "especies" in L else lw.battle_especies(
                    self.sessao, pt_card.sec(L["inicio"]), pt_card.sec(L["fim"]), GLYPHS, lw.nomes_conhecidos())
            except Exception as e:  # f_ pela metade ou painel ilegível: tenta de novo no próximo ciclo
                self.erros["volta"] = f"volta {L['volta']}: {type(e).__name__}: {e}"
                return None
            with (self.sessao / "cards.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
            self.cards[chave] = c
            self.registra(f"card da volta {L['volta']} ({L['inicio']}-{L['fim']}, {c['dur_s']} s): "
                          f"raw {c['xp_raw_painel']} · profit {c['balance_atual']} · "
                          f"{len(c['especies'])} espécies")
        return self.cards[chave]

    def _local(self, vistas):
        """(local do wiki, nome da hunt): o local mais comum das espécies (ex. Book World); sem local,
        "Hunt de <espécie mais vista>". Recalcula só quando aparece espécie nova."""
        conhecidas = [n for n, _ in vistas.most_common() if monstro(n)]
        if self.local[0] != conhecidas:
            local = catalogo.local_da_hunt(conhecidas) if conhecidas else None
            hunt = (locais.nome(local) or local
                    or (f"Hunt de {monstro(conhecidas[0])['nome']}" if conhecidas else ""))
            if (local, hunt) != self.local[1]:
                self.registra(f"local da hunt: {hunt or '?'} ({local or 'sem local fixo no wiki'}) "
                              f"por {', '.join(conhecidas[:3])}")
            self.local = (conhecidas, (local, hunt))
        return self.local[1]

    def _fora(self, cards, local):
        """Espécies que não são desta hunt (user, 22/09 item 3), com DUAS confirmações:
        CATÁLOGO (os locais fixos dela não incluem o local da hunt) e PRESENÇA (aparece em no
        máximo FORA_PRESENCA das voltas). Espécie sem local no wiki nunca sai: o catálogo se cala.
        Fica {nome: {n, voltas, local}} para a tela poder mostrar "vistos no caminho"."""
        if not local or len(cards) < FORA_MIN_VOLTAS:
            return {}
        tot, em = collections.Counter(), collections.Counter()
        for _, c in cards:
            tot.update(c["especies"])
            em.update(c["especies"].keys())   # em quantas VOLTAS a espécie apareceu
        fora = {}
        for nome, n in tot.items():
            e = monstro(nome)
            if e and e.get("local") and local not in e["local"] and em[nome] <= FORA_PRESENCA * len(cards):
                fora[nome] = {"n": n, "voltas": em[nome], "local": e["local"][:3]}
                if nome not in self.fora_vistas:
                    self.fora_vistas.add(nome)
                    self.registra(f"{nome} fora da conta: local fixo {', '.join(e['local'][:2])} "
                                  f"(a hunt é {local}) e só em {em[nome]} de {len(cards)} voltas")
        return fora

    def _refis(self, t0, agora):
        """Refis da sessão (user, 22/09 item 4). Cada um vai do "refil comecou" do lap_watch (que
        data no último kill) até o "refil acabou"/"hunt comecou" seguinte; o que ainda não fechou
        conta até agora. Estatísticas: quantos, total, média e quanto isso é da hunt."""
        lista = []
        for d in self.decisoes:
            quando = pt_card.sec(d.get("inicio") or d.get("quando") or "00:00:00")
            if d.get("decisao") == "refil comecou":
                lista.append({"inicio": quando, "fim": None, "dur_s": None, "aberto": True,
                              "sinais": [k for k, v in (d.get("sinais") or {}).items() if v]})
            elif lista and lista[-1]["aberto"] and d.get("decisao") in ("refil acabou", "hunt comecou"):
                lista[-1].update(fim=quando, dur_s=max(quando - lista[-1]["inicio"], 0), aberto=False)
        for r in lista:
            if r["aberto"]:
                r["dur_s"] = max(agora - r["inicio"], 0)
        total = sum(r["dur_s"] for r in lista)
        hunt_s = max(agora - t0, 1) if t0 else 0
        return lista, {"n": len(lista), "total_s": total,
                       "media_s": round(total / len(lista)) if lista else 0,
                       "fracao": round(total / hunt_s, 3) if hunt_s else 0}

    def _linha_do_tempo(self, t0, janelas):
        """Trechos e entradas (user, 22/09 item 2): cidade do caminho, espera, hunt e refil, mais
        os marcos de entrada da hunt e da cave. As subáreas do cliente vêm do areas.jsonl."""
        pontos = [dict(zip(("t", "z", "x", "y", "battle"), a)) for a in self.amostras]
        lt = sg.linha_do_tempo(pontos, _jsonl(self.sessao / "areas.jsonl"),
                               inicio_hunt=t0 or None, janelas=janelas)
        lt['trechos'] = sg.identifica_house(lt['trechos'], pontos, house_player(self.char))
        for m in lt["marcos"] if janelas else ():   # a área da hunt só fecha com a 1ª volta; antes
            if m["tipo"] not in self.marcos_vistos:  # disso o marco ainda troca de lugar
                self.marcos_vistos.add(m["tipo"])
                self.registra(f"{m['tipo'].replace('_', ' ')} às {lw.fmt(m['t'])}"
                              + (f" (andar {m['z']})" if m.get("z") is not None else ""))
        return lt

    def _volta(self, L, c, local, fora=()):
        """Volta no formato do contrato."""
        esp = {n: k for n, k in c["especies"].items() if monstro(n) and n not in fora}
        xp = c["xp_raw_painel"]
        return {"n": L["volta"], "tipo": L.get("tipo", "volta"),
                "ini": pt_card.sec(L["inicio"]), "fim": pt_card.sec(L["fim"]), "dur": c["dur_s"],
                "xp_raw": xp, "xp_raw_15min": c.get("xp_raw_15min"), "estabilizando": c.get("estabilizando"),
                "profit": c["balance_atual"], "sup_pt": c.get("supplies_pt"), "sup_eu": c.get("supplies_eu"),
                "bichos": self._bichos(c, L, esp, local), "base": c.get("base"),
                "solo": c["solo"], "reset": bool(c.get("reset")),
                "parcial": bool(L.get("parcial")) or L.get("fechada_por") in PARCIAL,
                "especies": esp,
                "loots": {k: n for k, n in (L.get("loots") or {}).items() if isinstance(n, (int, float))}}

    @staticmethod
    def _bichos(c, L, esp, local):
        """pt: raw ÷ fator medido da cave; solo: raw ÷ XP média das espécies da volta (catálogo), com a
        contagem do chat de piso (o chat subconta); sem nada disso, a contagem do chat."""
        xp, chat = c["xp_raw_painel"], L.get("kills_total")
        if not c["solo"]:
            fator = locais.raw_por_bicho(local, c.get("membros"))
            return round(xp / fator) if xp and fator else chat
        peso = {n: (k, monstro(n)["xp"]) for n, k in esp.items() if monstro(n).get("xp")}
        if not xp or not peso:
            return chat
        media = sum(k * x for k, x in peso.values()) / sum(k for k, _ in peso.values())
        return max(round(xp / media), chat or 0)

    # ------------------------------------------------------------ histórico (item 5)

    def _fecha_mapa(self):
        """Última tentativa de trocar o mapa local pelo do mundo ao fechar a sessão (user, 23/09): o
        cliente grava os .otmm quando o jogador sai da área, então na hora de encerrar a região já
        costuma existir. Deu certo: refaz amostras e fundos do resumo antes de guardar."""
        d = self.dados
        if self.mapa is not None and self._reancorar():
            t0 = pt_card.sec(self.hunt_comecou) if self.hunt_comecou else 0
            d["amostras"] = [a for a in self.amostras if a[0] >= t0]
            self.planos = self.mapa.estado()
        # 24/09 (user): reenquadra com as voltas FECHADAS. Enquanto a hunt corre, a janela da volta
        # aberta vai até o infinito para o mapa acompanhar você — e no fim isso põe o caminho de
        # volta para a cidade dentro do fundo (552x328 tiles numa hunt que ocupa 120x120, e mapa
        # dos andares 7 e 10 que a hunt nem usou).
        if d["voltas"]:
            d["andares"] = self._andares([(v["ini"], v["fim"]) for v in d["voltas"]])

    def _historico(self, final=False):
        """Guarda a sessão em hunt_data/<hunt>/sessoes/<AAAAMMDD_HHMM>/ (user, 22/09 item 5): a cada
        volta e ao fechar. resumo.json (com a trilha e a geometria dos andares, para a tela de
        histórico remontar o painel) + laps.jsonl + o mapa de cada andar em PNG; print nenhum.
        A pasta é a da sessão, então releitura atualiza a mesma e nunca pisa em sessão antiga."""
        d = self.dados
        # 23/09: também regrava quando o MAPA muda (apareceu, ou virou coordenada do mundo) — senão
        # o mapa que chega depois da última volta não entrava no histórico
        mp = self._mapa_estado()
        marca = (len(d["voltas"]), bool(d["andares"]), mp["fonte"], mp["ancorado"])
        if not d["voltas"] or not d["sessao"].get("hunt") or (not final and marca == self.n_hist):
            return
        from rubinot.adapters.historico import chave_sessao, publicar
        ident = chave_sessao(self.sessao.name, d["sessao"].get("char") or "")
        local, hunt = self.local[1]
        pasta = (HUNT_DATA / (locais.pasta(local) or catalogo.slug(hunt)) / "sessoes"
                 / ident)
        pasta.mkdir(parents=True, exist_ok=True)
        soma = lambda k: sum(v[k] or 0 for v in d["voltas"])  # noqa: E731 - uma linha, seis usos
        # andar principal: onde a hunt passou mais tempo. É o mapa que ilustra a sessão na lista e o
        # que a tela abre primeiro — o PNG maior costuma ser o do caminho de volta, não o da hunt
        janelas = [(v["ini"], v["fim"]) for v in d["voltas"]]
        n_z = collections.Counter(str(a[1]) for a in d["amostras"] if any(i <= a[0] <= f for i, f in janelas))
        principal = next((z for z, _ in n_z.most_common() if z in d["andares"]), None)
        resumo = {"salvo_em": dt.datetime.now().isoformat(timespec="seconds"), "versao": VERSAO,
                  "fonte": fontes.da_sessao(self.sessao),
                  "pasta": self.sessao.name, "hunt_comecou": self.hunt_comecou, "fechada": final,
                  "sessao": d["sessao"],
                  "totais": {"voltas": len(d["voltas"]), "dur_s": soma("dur"), "xp_raw": soma("xp_raw"),
                             "profit": soma("profit"), "sup_pt": soma("sup_pt"), "sup_eu": soma("sup_eu"),
                             "bichos": soma("bichos")},
                  "voltas": d["voltas"], "refis": d["refis"], "refil": d["refil"],
                  "trechos": d["trechos"], "entradas": d["entradas"],
                  "especies": especies(d["voltas"]), "especies_fora": d["especies_fora"],
                  # 23/09 (user): o que a tela de histórico precisa para remontar o painel sozinha.
                  # O fundo de cada andar fica no PNG ao lado (o resumo já é grande); aqui vai só a
                  # geometria, e "mapa" diz se a coordenada é a do mundo ou a relativa do mapa local.
                  "mapa": mp, "amostras": d["amostras"], "andar": principal,
                  "andares": {z: {c: a[c] for c in ("x0", "y0", "w", "h")} for z, a in d["andares"].items()}}
        arquivos = {f'mapa_z{z}.png': base64.b64decode(a['fundo'].split(',', 1)[1])
                    for z, a in d['andares'].items()}
        if (self.sessao / 'laps.jsonl').exists():
            arquivos['laps.jsonl'] = (self.sessao / 'laps.jsonl').read_bytes()
        publicar(pasta, resumo, arquivos)
        self.n_hist = marca  # só marca depois da publicação completa
        if final:
            try:
                import aprendizado_hunt
                registro = aprendizado_hunt.Registro(HUNT_DATA / '_aprendizado')
                resultado = registro.consolidar(self.sessao.name, resumo)
                configuracoes._grava(pasta / 'aprendizado.json', resultado)
            except Exception as erro:
                configuracoes._grava(self.sessao / 'aprendizado_estado.json', {'estado':'falhou','erro':str(erro)})
                self.registra(f'aprendizado numérico pendente: {erro}')
        self.registra(f"histórico salvo em {pasta} · {len(d['voltas'])} voltas · "
                      f"{len(d['amostras'])} pontos de trilha · {len(d['andares'])} andar(es) · mapa "
                      f"{mp['fonte']}{'' if mp['ancorado'] else ' (coordenada relativa)'}"
                      + (" · sessão fechada" if final else ""))

    def _mapa_estado(self):
        """Qual mapa está valendo (user, 23/09 item 1): o do mundo (minimapa do cliente, coordenada
        absoluta) ou o local, colado dos m_ — e neste caso se ele já foi ancorado no mundo."""
        if self.mapa is None:
            return {"fonte": "mundo", "ancorado": True, "planos": []}
        return {"fonte": "local", "ancorado": any(p.anc is not None for p in self.mapa.planos),
                "planos": self.planos}

    def _andares(self, janelas):
        """Fundo de cada andar visitado na hunt (1 px por tile, cores do minimapa) na área visitada + MARGEM."""
        pts = [a for a in self.amostras if any(i <= a[0] <= f for i, f in janelas)]
        if not pts:
            return {}
        # 21/09: a volta 1 abre com o char ainda na cidade (andou até o teleporte): ponto longe do
        # miolo da hunt não entra, senão o fundo vira a cidade inteira e ganha o andar dela
        mx, my = statistics.median(a[2] for a in pts), statistics.median(a[3] for a in pts)
        pts = [a for a in pts if abs(a[2] - mx) <= PERTO and abs(a[3] - my) <= PERTO]
        if not pts:  # 22/09: meio a meio cidade/hunt, a mediana cai no caminho: fica o fundo de antes
            return self.fundo[1]
        xs, ys = [a[2] for a in pts], [a[3] for a in pts]
        bbox = ((int(min(xs)) - MARGEM) // GRADE * GRADE, -(-(int(max(xs)) + 1 + MARGEM) // GRADE) * GRADE,
                (int(min(ys)) - MARGEM) // GRADE * GRADE, -(-(int(max(ys)) + 1 + MARGEM) // GRADE) * GRADE)
        # andar com meia dúzia de pontos é escada de passagem (ou, no mapa local, plano que nasceu
        # de um quadro solto): não vira mapa na tela nem PNG no histórico
        n_z = collections.Counter(a[1] for a in pts)
        zs = sorted(z for z, n in n_z.items() if n >= MIN_PTS_ANDAR) or [n_z.most_common(1)[0][0]]
        fonte = self.mapa if self.mapa is not None else mm   # mesma assinatura nos dois (23/09)
        if self.fundo[0] != (bbox, zs):
            self.fundo = ((bbox, zs), {str(z): {"x0": bbox[0], "y0": bbox[2], "w": bbox[1] - bbox[0],
                                                "h": bbox[3] - bbox[2], "fundo": fonte.fundo(z, bbox)} for z in zs})
        return self.fundo[1]

    # ------------------------------------------------------------ rota

    def json_hunt(self):
        calib = _le_json(fontes.caminhos()[0])
        ativo = self.ativo()
        ult = round(time.time() - (self.visto or self.t0)) if ativo else None
        # anexar (sem captura nossa): "gravando" = a pasta está crescendo (replay ou capture.py na mão)
        gravando = ativo and (self._vivo("capture") if self.grava else bool(self.visto) and ult <= PARADO_S)
        g, cj = capture.find_game_rect(), (calib or {}).get("janela") or {}
        # 21/09: recortes relativos à janela; outro tamanho = tudo lido no lugar errado
        mudou = bool(g and cj.get("largura") and (g["rect"]["width"], g["rect"]["height"]) != (cj["largura"], cj.get("altura")))
        e = {"calibrado": layout.calibrada(calib), "jogo": bool(g), "janela_mudou": mudou, "ativo": ativo,
             "char": (self.char if ativo else None) or (calib or {}).get("char"),
             "gravando": gravando, "sessao": self.sessao.name if ativo else None,
             "hunt_comecou": self.hunt_comecou if ativo else None,
             "volta_atual": self.info.get("volta_atual") if ativo else None,
             "pausa": bool(ativo and self.hunt_comecou and self.info.get("pausa")),
             "desde": self.info.get("desde") if ativo else None,
             "local": self.local[1][0] if ativo else None, "ultimo_quadro_s": ult,
             # 23/09 (user item 1): qual mapa está valendo. fonte "local" e ancorado False = o z é
             # NÚMERO DE PLANO e a coordenada é relativa (o cliente não gravou o minimapa desta área)
             "mapa": self._mapa_estado() if ativo else {"fonte": "mundo", "ancorado": True, "planos": []}}
        e["mensagem"] = self._mensagem(e)
        house = house_player(e.get('char')) if e['mapa']['ancorado'] else None
        if ativo and house and self.amostras:
            t, z, x, y, *_ = self.amostras[-1]
            if z == house['z'] and abs(x-house['x']) <= house.get('raio', 3) and abs(y-house['y']) <= house.get('raio', 3):
                e['local'] = 'House do player'
                e['mensagem'] = 'Na house do player · aguardando a próxima hunt'
        fonte = fontes.da_sessao(self.sessao) if ativo else fontes.atual()
        e['fonte'] = fonte
        if fonte['tipo'] == 'twitch':
            st = _le_json(self.sessao / 'stream_estado.json', {}) if ativo else {}
            recente = time.time() - st.get('atualizado_em', 0) < 5
            e.update(jogo=bool(recente and st.get('conectado')), janela_mudou=False, stream=st)
            e['mensagem'] = (st.get('mensagem', 'Conectando à Twitch…') if ativo else e['mensagem']) + ' Mapas dependem da base local; alertas têm o atraso da live.'
        return {"estado": e, **(self.dados if ativo else _vazio()),
                "ks": _le_json(self.sessao / "ks.json", {}) if self.sessao else {}}

    def _mensagem(self, e):
        if not e["calibrado"]:
            return "Faça a calibração: depois dela o programa grava sozinho."
        if not self.ativo():
            return "Gravação parada. Clique em Iniciar hunt aqui em cima quando quiser gravar a próxima."
        if self.grava and not e["jogo"]:
            return "Abra o RubinOT e entre com o personagem: a gravação começa sozinha."
        if self.grava and e["janela_mudou"]:
            return "A janela do jogo mudou de tamanho desde a calibração: maximize o jogo ou refaça a calibração."
        if self.grava and not e["gravando"]:  # caiu: o supervisor relança; o detalhe fica no capture.log
            if capture.pouco_disco():
                return (f"Disco quase cheio (menos de {capture.MIN_LIVRE_GB} GB livres): a gravação parou. "
                        "Apague as sessões antigas da pasta capture e religue.")
            if getattr(self.procs.get("capture"), "returncode", None) == 0:
                return "Gravação encerrada no limite de 3 h, sem volta na última hora. Para continuar: Desligar e Ligar."
            return "A captura parou, religando."
        if self.grava and (e["ultimo_quadro_s"] is None or e["ultimo_quadro_s"] > PARADO_S):
            return "Gravação em espera: ela só grava com o jogo em primeiro plano."
        if self.erros:  # o detalhe vai para o app.log
            return "Um quadro não leu direito; a análise tenta de novo sozinha."
        # 24/09 (user): na hunt da cripta o Hunt Analyser saiu da tela por 14 min e 4 voltas fecharam
        # sem XP raw — só apareceu dias depois, no gráfico. Enquanto durar, a tela avisa.
        fechadas = self.dados["voltas"]
        if fechadas and fechadas[-1].get("xp_raw") is None and not fechadas[-1].get("parcial"):
            cegas = sum(1 for v in fechadas if v.get("xp_raw") is None)
            return (f"A volta {fechadas[-1]['n']} fechou sem ler o Hunt Analyser"
                    + (f" (já são {cegas})" if cegas > 1 else "") +
                    ": deixe o painel visível na tela, senão a volta fica sem XP raw.")
        if not e["hunt_comecou"]:
            # 22/09: o gatilho agora é matar de verdade + uma 2ª confirmação (sinais.py)
            return ("Gravando." if self.grava else f"Lendo {self.sessao.name}.") + \
                " A hunt começa sozinha quando você começar a matar; o caminho até lá fica de fora."
        if not self.dados["andares"]:
            sem_mapa = " · mapa ainda não encontrado"
        elif self.mapa is not None and not e["mapa"]["ancorado"]:
            sem_mapa = " · mapa montado dos seus quadros (o cliente não gravou o minimapa daqui)"
        else:
            sem_mapa = ""
        if e["pausa"]:
            r = next((r for r in self.dados["refis"] if r.get("aberto")), None)
            tempo = f" há {r['dur_s'] // 60}m{r['dur_s'] % 60:02d}" if r else ""
            return f"Pausa ou refill{tempo}: a volta {e['volta_atual']} recomeça quando a hunt voltar{sem_mapa}."
        vs = self.dados["voltas"]
        if not vs:
            return f"Hunt começou às {e['hunt_comecou']}. Volta 1 em andamento{sem_mapa}."
        return f"Volta {e['volta_atual']} em andamento · a volta {vs[-1]['n']} fechou às {lw.fmt(vs[-1]['fim'])}{sem_mapa}."


# ------------------------------------------------------------------ histórico guardado (23/09)
# O user quis abrir a hunt depois de encerrada ("depois da hunt quis fazer a análise dela e não
# consegui"): a sessão já era guardada em hunt_data/<hunt>/sessoes/<AAAAMMDD_HHMM>/, mas não havia
# rota para lê-la. Estas funções leem SÓ o disco — servem com a gravação desligada.
ID_HIST = re.compile(r"[a-z0-9_.\-]{1,60}/\d{8}_\d{4}(?:\d{2}(?:_[a-f0-9]{8})?)?")   # id estável, sem caminho de arquivo


def _pasta_hist(ident):
    """Pasta de uma sessão guardada pelo id "hunt/AAAAMMDD_HHMM"; None = id inválido ou sem resumo.
    Nada fora do hunt_data, por mais criativo que seja o id."""
    if not ID_HIST.fullmatch(ident or ""):
        return None
    p = HUNT_DATA / ident.split("/")[0] / "sessoes" / ident.split("/")[1]
    return p if p.resolve().is_relative_to(HUNT_DATA.resolve()) and (p / "resumo.json").is_file() else None


def _fechada(r):
    """Sessão fechada (user, 24/09): pelo Encerrar hunt, ou sozinha pela idade — passada mais de
    RETOMA_S sem dado novo nem o retomavel() volta para ela, então ela está fechada de fato. Sessão
    que o programa perdeu no meio (queda, PC desligado) parava com "não fechada" para sempre."""
    if r.get("fechada"):
        return True
    try:
        return (dt.datetime.now() - dt.datetime.fromisoformat(r["salvo_em"])).total_seconds() > RETOMA_S
    except (KeyError, TypeError, ValueError):   # resumo velho, sem salvo_em
        return False


from rubinot.hunt.metricas import PAUSA_S, especies, taxas


def _pico_xph(r):
    """Melhor XP raw/h de uma volta da sessão (o selo da capa na lista). Mesmas voltas limpas do
    `taxas` e a mesma regra por volta do card da tela: 15 min × 4 e, sem ela, a raw da volta."""
    vs = [v for v in (r.get("voltas") or []) if not v.get("parcial") and (v.get("dur") or 0) < PAUSA_S]
    picos = [v["xp_raw_15min"] * 4 if v.get("xp_raw_15min") else v["xp_raw"] * 3600 / v["dur"]
             for v in vs if v.get("xp_raw_15min") or v.get("xp_raw")]
    return round(max(picos)) if picos else None


def _grupos_historico():
    """Mesmo dia, hunt, personagem e modalidade; intervalo < 1 h. Originais intactos."""
    registros = []
    for p in HUNT_DATA.glob('*/sessoes/*/resumo.json'):
        r = _le_json(p)
        if isinstance(r, dict):
            registros.append((p, r))
    grupos, ultimos = [], {}
    for p, r in sorted(registros, key=lambda item: item[0].parent.name):
        s = r.get('sessao') or {}
        chave = (p.parent.parent.parent.name, s.get('data'), s.get('char'), s.get('pt'))
        grupo = ultimos.get(chave)
        junta = False
        if grupo and all(chave):
            anterior = grupo[-1][1].get('sessao') or {}
            try:
                intervalo = pt_card.sec(s['inicio']) - pt_card.sec(anterior['fim'])
                junta = 0 <= intervalo < 3600
            except (ValueError, KeyError, TypeError):
                pass
        if junta:
            grupo.append((p, r))
        else:
            grupo = [(p, r)]
            grupos.append(grupo)
        ultimos[chave] = grupo
    return grupos


def _ident_hist(p):
    return f'{p.parent.parent.parent.name}/{p.parent.name}'


def _mescla_historico(grupo):
    r = copy.deepcopy(grupo[0][1])
    r['sessoes_origem'] = [_ident_hist(p) for p, _ in grupo]
    if len(grupo) == 1:
        return r
    r['sessao']['fim'] = grupo[-1][1]['sessao'].get('fim')
    r['fechada'] = all(_fechada(d) for _, d in grupo)
    r['salvo_em'] = max(d.get('salvo_em', '') for _, d in grupo)
    for campo in ('voltas', 'amostras', 'refis', 'trechos', 'entradas'):
        r[campo] = []
        for p, d in grupo:
            for item in d.get(campo) or []:
                novo = copy.deepcopy(item)
                if campo == 'voltas':
                    novo['n_origem'], novo['sessao_origem'] = novo.get('n'), _ident_hist(p)
                    novo['n'] = len(r[campo]) + 1
                r[campo].append(novo)
    r['totais'] = {k: sum((d.get('totais') or {}).get(k, 0) or 0 for _, d in grupo)
                   for k in ('voltas', 'dur_s', 'xp_raw', 'profit', 'sup_pt', 'sup_eu', 'bichos')}
    r['especies'] = especies(r['voltas'])
    r['refil'] = grupo[-1][1].get('refil') or {}
    # Intervalos entre gravações ficam explícitos, fora do tempo das voltas e das taxas.
    r['intervalos_gravacao'] = [{'inicio': a['sessao'].get('fim'), 'fim': b['sessao'].get('inicio')}
                               for (_, a), (_, b) in zip(grupo, grupo[1:])]
    # Coordenadas locais de sessões diferentes não têm a mesma origem.
    if any(not (d.get('mapa') or {}).get('ancorado', True) for _, d in grupo):
        ultimo = grupo[-1][1]
        for campo in ('andares', 'andar', 'mapa', 'amostras'):
            r[campo] = copy.deepcopy(ultimo.get(campo))
        r['mapa_sessao_origem'] = _ident_hist(grupo[-1][0])
    return r


def _grupo_hist(ident):
    return next((g for g in _grupos_historico() if any(_ident_hist(p) == ident for p, _ in g)), None)


def _fundos_hist(grupo, r):
    from PIL import Image
    from rubinot.adapters.historico import arquivo_publicado
    escolhidos = [(p, d) for p, d in grupo
                  if not r.get('mapa_sessao_origem') or _ident_hist(p) == r['mapa_sessao_origem']]
    saida = {}
    for z in {z for _, d in escolhidos for z in d.get('andares') or {}}:
        itens = [(arquivo_publicado(p.parent, d, f'mapa_z{z}.png'), d['andares'][z]) for p, d in escolhidos
                 if z in (d.get('andares') or {}) and (arquivo_publicado(p.parent, d, f'mapa_z{z}.png')).exists()]
        if not itens:
            continue
        x0, y0 = min(a['x0'] for _, a in itens), min(a['y0'] for _, a in itens)
        w = max(a['x0'] + a['w'] for _, a in itens) - x0
        h = max(a['y0'] + a['h'] for _, a in itens) - y0
        if w * h > 16_000_000:
            itens = itens[-1:]
            x0, y0, w, h = (itens[0][1][k] for k in ('x0', 'y0', 'w', 'h'))
        img = Image.new('RGB', (w, h), '#11141b')
        for png, a in itens:
            with Image.open(png) as fundo:
                img.paste(fundo.convert('RGB'), (a['x0'] - x0, a['y0'] - y0))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        saida[z] = {'x0': x0, 'y0': y0, 'w': w, 'h': h,
                    'fundo': 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()}
    return saida


def _ks_hist(grupo):
    relatorios = []
    for _, r in grupo:
        nome = r.get('pasta', '')
        if re.fullmatch(r'session_\d{8}_\d{6}(?:_[a-f0-9]{8})?', nome):
            k = _le_json(CAPTURAS / nome / 'ks.json')
            if not k:
                arquivos = list(ks.RAIZ.glob('session_*/logs/' + nome + '_relatorio.json'))
                k = _le_json(arquivos[0]) if arquivos else _le_json(ks.RAIZ / nome / 'relatorio.json')
            if k:
                if _fechada(r):
                    for ep in k.get('episodios') or []:
                        if ep.get('aberto'):
                            ep['fim'] = (ep.get('ultimo_evento') or {}).get('ts') or f"{int(ep['ultimo_t']) // 3600:02d}:{int(ep['ultimo_t']) // 60 % 60:02d}:{int(ep['ultimo_t']) % 60:02d}"
                            ep['aberto'] = False
                            ep['motivo_fim'] = 'gravacao_encerrada'
                            ep['prova_fim'] = ep.get('prova_ultimo') or {}
                relatorios.append(k)
    return {'episodios': [e for k in relatorios for e in k.get('episodios') or []],
            'estatisticas_party': ks.estatisticas_party(relatorios),
            'limite': relatorios[0].get('limite') if relatorios else None,
            'sessoes': relatorios}


def modalidade_party(k, anterior=''):
    relatorios = k.get('sessoes') or [k]
    nomes = {ks.nome_key(n) for r in relatorios for n in r.get('party') or []}
    return f'pt x{len(nomes)}' if len(nomes) >= 2 else anterior


def historico(limite=200):
    """Sessões guardadas, da mais nova para a mais velha. Só pasta com resumo.json — os summary
    soltos de julho ficam de fora."""
    out = []
    for grupo in _grupos_historico():
        arq = grupo[0][0]
        r = _mescla_historico(grupo)
        if not isinstance(r, dict):
            continue
        s, t = r.get("sessao") or {}, r.get("totais") or {}
        esp = next(iter(r.get("especies") or {}), None)   # bicho mais visto = a cara da hunt
        # 24/09 (user): a capa da sessão é o bicho da hunt, não o desenho do mapa. Até 3, os mais
        # mortos primeiro, e só os que têm gif no catálogo (sem gif a imagem quebraria na tela).
        icones = [sl for n in list(r.get("especies") or {})[:3]   # sl, não s: o walrus vaza da lista
                  if (sl := catalogo.slug(n)) and catalogo.imagem(sl)]
        out.append({"id": f"{arq.parent.parent.parent.name}/{arq.parent.name}",
                    "hunt": s.get("hunt") or arq.parent.parent.parent.name.replace("_", " "),
                    "data": s.get("data"), "inicio": s.get("inicio"), "fim": s.get("fim"),
                    "char": s.get("char"), "pt": modalidade_party(_ks_hist(grupo), s.get('pt')), "voltas": t.get("voltas", 0),
                    "sessoes_origem": r['sessoes_origem'],
                    "dur_s": t.get("dur_s", 0), "xp_raw": t.get("xp_raw", 0),
                    "profit": t.get("profit", 0), "bichos": t.get("bichos", 0),
                    # 24/09: a aba de evolução usa as TAXAS (por hora, só do que foi lido); os
                    # totais aqui são a soma do que deu para medir e podem ter buraco
                    "sup_pt": t.get("sup_pt", 0), "sup_eu": t.get("sup_eu", 0),
                    "taxas": taxas(r.get("voltas") or []),
                    # ilustração da hunt: o desenho do mapa (/api/historico/<id>/mapa.png) e o gif
                    # do bicho mais visto (/monstros/<icone>.gif)
                    # "mapa" = o painel vai ter mapa: resumo de antes de 23/09 não guardava os
                    # andares nem a trilha, então a hunt abre só com as voltas e os cards
                    # ancorado: mapa do mundo (o local, colado dos quadros, tem outra cara — a lista
                    # prefere um ancorado para ilustrar TODAS as sessões da mesma hunt, 24/09)
                    "mapa": bool(r.get("andares")), "andar": r.get("andar"),
                    "ancorado": bool((r.get("mapa") or {}).get("ancorado", True)),
                    "especie": esp, "icone": catalogo.slug(esp) if esp else None, "icones": icones,
                    "pico_xph": _pico_xph(r),
                    "fechada": _fechada(r), "salvo_em": r.get("salvo_em")})
    return sorted(out, key=lambda s: s["id"].split("/")[1] + s["id"], reverse=True)[:limite]


def historico_um(ident):
    """Uma sessão guardada no MESMO formato do /api/hunt, montada do disco: a tela reusa o painel."""
    grupo = _grupo_hist(ident)
    r = _mescla_historico(grupo) if grupo else None
    if not isinstance(r, dict):
        return None
    andares = _fundos_hist(grupo, r)
    s, t = r.get("sessao") or {}, r.get("totais") or {}
    k = _ks_hist(grupo)
    s = dict(s, pt=modalidade_party(k, s.get('pt')))
    pontos = [dict(zip(('t','z','x','y','battle'), a)) for a in r.get('amostras', [])]
    trechos = sg.identifica_house(r.get('trechos') or [], pontos,
                                house_player(s.get('char')) if (r.get('mapa') or {}).get('ancorado', True) else None)
    return {"estado": {"historico": True, "id": ident, "calibrado": True, "jogo": False,
                       "janela_mudou": False, "gravando": False, "sessao": r.get("pasta"),
                       "char": s.get("char"), "hunt_comecou": r.get("hunt_comecou"),
                       "volta_atual": None, "pausa": False, "desde": s.get("inicio"), "local": None,
                       "ultimo_quadro_s": None, "totais": t, "salvo_em": r.get("salvo_em"),
                       "mapa": r.get("mapa") or {"fonte": "mundo", "ancorado": True, "planos": []},
                       "mensagem": f"Hunt guardada · {s.get('data') or ''} {s.get('inicio') or ''}"
                                   f" · {t.get('voltas', 0)} voltas"
                                   + ("" if _fechada(r) else " · sessão não fechada")},
            "sessao": s, "andares": andares, "voltas": r.get("voltas") or [],
            "ks": k, "sessoes_origem": r['sessoes_origem'],
            "intervalos_gravacao": r.get('intervalos_gravacao', []),
            "amostras": r.get("amostras") or [], "refis": r.get("refis") or [],
            "refil": r.get("refil") or {}, "trechos": trechos,
            "entradas": r.get("entradas") or [], "especies_fora": r.get("especies_fora") or {}}


def historico_mapa(ident):
    """PNG do mapa da sessão guardada — o andar principal da hunt, para a lista ilustrar a sessão."""
    grupo = _grupo_hist(ident)
    if not grupo:
        return None
    r = _mescla_historico(grupo)
    fundos = _fundos_hist(grupo, r)
    a = fundos.get(r.get('andar')) or next(iter(fundos.values()), None)
    return base64.b64decode(a['fundo'].split(',', 1)[1]) if a else None


_G = Gravacao()  # singleton do módulo: um programa, uma gravação
ligar, anexar, desligar, ativo, json_hunt = _G.ligar, _G.anexar, _G.desligar, _G.ativo, _G.json_hunt
reiniciar, ler_log = _G.reiniciar, _G.ler_log


def sessao_atual():
    """Pasta da sessão gravando agora, ou None — o auxiliador lê o console dela (28/09)."""
    return _G.sessao if _G.ativo() else None


def hunt_atual():
    """Nome da hunt de agora, ou None — o auxiliador carrega as boxes dela (28/09)."""
    return (_G.local[1][1] or None) if _G.ativo() else None


def _demo_taxas():
    """A tela e o programa têm que dar o MESMO número (user, 24/09). Roda o ui/taxas.js no node com
    as voltas de cada sessão guardada e compara com o taxas() daqui. Sem node, só confere o Python
    contra os números medidos na hunt de 24/09 (4 voltas sem leitura do painel)."""
    guardadas = sorted(HUNT_DATA.glob("*/sessoes/*/resumo.json"))
    js = AQUI / "ui" / "taxas.js"
    for arq in guardadas:
        vs = (_le_json(arq) or {}).get("voltas") or []
        aqui = {"taxas": taxas(vs), "especies": especies(vs)}
        if not shutil.which("node"):
            continue
        prog = (f"const c = require({json.dumps(str(js))});const v = JSON.parse(process.argv[1]);"
                f"console.log(JSON.stringify({{taxas: c.taxasDe(v), especies: c.especiesDe(v)}}));")
        saida = subprocess.run(["node", "-e", prog, json.dumps(vs)], capture_output=True, text=True,
                               encoding="utf-8", creationflags=SEM_JANELA)
        assert saida.returncode == 0, f"node falhou em {arq.parent.name}: {saida.stderr[:300]}"
        la = json.loads(saida.stdout)
        assert la == aqui, (f"ui/taxas.js e o ao_vivo discordam em {arq.parent.name}:\n"
                            f"  tela:     {la}\n  programa: {aqui}")
    print(f"contas: taxas e espécies batem entre o programa e a tela em {len(guardadas)} sessões"
          if shutil.which("node") else "contas: sem node, comparação com a tela pulada")
    # espécies: a lista da tela, a do resumo e a da capa saem daqui — inclusive a queda para o loot
    vs = [{"especies": {"crypt fiend": 3, "creepy crawler": 1}, "loots": {"gold coin": 9}},
          {"especies": {"creepy crawler": 4}, "loots": {"gold coin": 2}}]
    assert list(especies(vs)) == ["creepy crawler", "crypt fiend"], especies(vs)
    assert especies(vs)["creepy crawler"] == 5, especies(vs)
    assert list(especies([{"especies": {}, "loots": {"rat": 2}}])) == ["rat"], "sessão antiga cai para o loot"
    # regressão da hunt de 24/09: raw pela mediana dos 15 min, e a volta sem leitura não vira zero
    vs = [{"n": 1, "dur": 300, "xp_raw": 1_000_000, "xp_raw_15min": 3_500_000, "profit": 300_000, "bichos": 30},
          {"n": 2, "dur": 300, "xp_raw": None, "xp_raw_15min": None, "profit": None, "bichos": 28},
          {"n": 3, "dur": 300, "xp_raw": 1_200_000, "xp_raw_15min": 3_400_000, "profit": 200_000, "bichos": 32},
          {"n": 4, "dur": 480, "xp_raw": 500_000, "xp_raw_15min": None, "profit": 10_000, "bichos": 10}]
    t = taxas(vs)
    assert (t["voltas"], t["total"], t["refil"], t["voltas_raw"]) == (3, 4, 1, 2), t
    # mediana de 13,6 e 14,0: com número par de voltas fica o de cima, como a tela sempre fez
    assert t["raw_h"] == 14_000_000 and t["raw_de"] == "15min", t
    assert t["taxa"]["profit_h"] == 3_000_000, t     # 500k em 600 s, sem a volta que não leu
    assert t["media"]["profit"] == 250_000, t
    assert t["taxa"]["bichos_h"] == 360, t           # 90 bichos em 900 s: bichos leu nas três
    print("taxas: regra da raw (mediana 15 min), lacuna e volta de refill conferidas")


def _demo():
    """Confere o filtro de espécie e a conta dos refis com os números medidos (22/09). Sem rede:
    o catálogo entra no cache na mão."""
    fogo, gelo = "Secret Library Fire Section", "Secret Library Ice Section"
    for nome, locais in {"rage squid": [fogo], "burning book": [fogo], "guardian of tales": [fogo],
                         "ink blob": ["Secret Library Earth Section", fogo, gelo],
                         "flying book": ["Secret Library Energy Section", fogo, gelo],
                         "icecold book": [gelo], "squid warden": [gelo], "animated feather": [gelo],
                         "knowledge elemental": ["Secret Library Energy Section"],
                         "dog": ["Carlin", "Edron Castle"], "traps the cat": None}.items():
        _MONSTROS[nome] = ({"nome": nome, "xp": 1000, "local": locais} if locais else None, time.time())
    g = Gravacao()
    # 22/09 (36 voltas): as da Fogo apareceram em 10 a 36 voltas; as de fora, em 2 a 3
    em = {"rage squid": 36, "burning book": 36, "guardian of tales": 34, "ink blob": 34,
          "flying book": 10, "squid warden": 3, "icecold book": 3, "knowledge elemental": 3,
          "animated feather": 2, "dog": 2, "traps the cat": 5}
    cards = [(None, {"especies": {n: 5 for n, k in em.items() if v < k}}) for v in range(36)]
    fora = g._fora(cards, fogo)
    assert set(fora) == {"squid warden", "icecold book", "knowledge elemental", "animated feather", "dog"}, fora
    assert fora["squid warden"]["voltas"] == 3, fora
    assert g._fora(cards[:3], fogo) == {}, "com menos de 4 voltas a presenca ainda nao separa"
    assert g._fora(cards, None) == {}, "sem local da hunt o catalogo nao fala"
    esp = {n: 5 for n in em}
    assert set(g._volta({"volta": 1, "inicio": "06:00:00", "fim": "06:01:00", "loots": {}},
                        {"especies": esp, "xp_raw_painel": 1, "xp_raw_15min": None, "balance_atual": 0,
                         "dur_s": 60, "solo": False, "membros": 3, "kills_total": 1},
                        fogo, fora)["especies"]) == {"rage squid", "burning book", "guardian of tales",
                                                     "ink blob", "flying book"}
    # refil de 22/09: comecou 08:01:03 (ultimo kill), a hunt voltou 08:09:13 -> 490 s
    g.decisoes = [{"quando": "06:36:48", "decisao": "hunt comecou", "inicio": "06:35:44"},
                  {"quando": "08:02:51", "decisao": "refil comecou", "inicio": "08:01:03",
                   "sinais": {"sem_kill": True, "lista_vazia": True, "longe": False}},
                  {"quando": "08:09:13", "decisao": "refil acabou", "dur_s": 490}]
    lista, st = g._refis(sg.seg("06:35:44"), sg.seg("08:32:51"))
    assert [(r["inicio"], r["fim"], r["dur_s"]) for r in lista] == [(sg.seg("08:01:03"), sg.seg("08:09:13"), 490)], lista
    assert lista[0]["sinais"] == ["sem_kill", "lista_vazia"] and not lista[0]["aberto"]
    assert st == {"n": 1, "total_s": 490, "media_s": 490, "fracao": 0.07}, st
    g.decisoes = g.decisoes[:2]   # refil ainda aberto: conta ate agora
    lista, st = g._refis(sg.seg("06:35:44"), sg.seg("08:05:03"))
    assert lista[0]["aberto"] and lista[0]["dur_s"] == 240 and st["n"] == 1, lista
    print("ao_vivo: filtro de especie e refis batem com a sessao de 22/09")
    _demo_historico()
    _demo_taxas()


def _demo_historico():
    """Ida e volta do historico (user, 23/09): o que e guardado remonta o painel da tela."""
    global HUNT_DATA
    import tempfile
    guarda = HUNT_DATA
    try:
        with tempfile.TemporaryDirectory() as d:
            HUNT_DATA = pathlib.Path(d) / "hunt_data"
            g = Gravacao()
            g.sessao = pathlib.Path(d) / "session_20260923_082428"
            g.sessao.mkdir()
            g.char, g.hunt_comecou, g.mapa, g.planos = "Traps the cat", "08:24:29", None, []
            g.local = (None, ("Unhallowed Crypt", "Unhallowed Crypt"))
            volta = {"n": 1, "ini": 30269, "fim": 30504, "dur": 235, "xp_raw": 904645, "profit": 386928,
                     "sup_pt": 79572, "sup_eu": 24592, "bichos": 33, "especies": {"crypt fiend": 35}}
            g.dados = {**_vazio(), "voltas": [volta],
                       "sessao": {"hunt": "Unhallowed Crypt", "char": "Traps the cat",
                                  "data": "23/09/2026", "inicio": "08:24:29", "fim": "09:05:19"},
                       "amostras": [[30269, 0, 363.0, 382.0, 9], [30271, 0, 364.0, 383.0, 8]],
                       # fundo de 2x2 tiles: sai do proprio mapa_mundo, sem bloco do cliente
                       "andares": {"0": {"x0": 320, "y0": 344, "w": 2, "h": 2,
                                         "fundo": mm.fundo(0, (0, 2, 0, 2))}}}
            g._historico(final=True)
            lista = historico()
            assert [s["id"] for s in lista] == ["unhallowed_crypt/20260923_0824"], lista
            assert (lista[0]["voltas"], lista[0]["bichos"], lista[0]["mapa"], lista[0]["icone"]) \
                == (1, 33, True, "crypt_fiend"), lista
            h = historico_um(lista[0]["id"])
            assert h["voltas"] == [volta] and h["amostras"] == g.dados["amostras"], h["voltas"]
            assert h["andares"]["0"] == {"x0": 320, "y0": 344, "w": 2, "h": 2,
                                         "fundo": g.dados["andares"]["0"]["fundo"]}, "fundo voltou diferente"
            assert h["estado"]["historico"] and h["estado"]["mapa"]["fonte"] == "mundo"
            assert len(historico_mapa(lista[0]["id"]) or b"") > 0, "sem PNG do mapa"
            # id que sai do hunt_data nao abre nada
            for mau in ("../../capture/20260923_0824", "x/20260101_0000", "unhallowed_crypt/nao"):
                assert historico_um(mau) is None and historico_mapa(mau) is None, mau
            print("ao_vivo: historico guardado e remontado (1 volta, 2 pontos de trilha, 1 andar)")
    finally:
        HUNT_DATA = guarda


if __name__ == "__main__":
    _demo()
