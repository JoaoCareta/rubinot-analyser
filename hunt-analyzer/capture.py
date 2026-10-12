"""Harness de captura: grava a janela do RubinOT enquanto voce caca.

Cadencias:
  - recorte do chat (Server Log) a cada 0.5s  -> c_HHMMSS_mmm.png
  - recorte da Battle List a cada 0.5s        -> b_HHMMSS_mmm.png
  - janela inteira a cada 4s                  -> f_HHMMSS_mmm.png
  - buffer completo sincronizado (60s)        -> q_HHMMSS_mmm.png
Todos os recortes saem da mesma captura; KS preserva o quadro exato antes do buffer expirar.

Uso:  python capture.py [pasta_da_sessao]   (Ctrl+C para parar)
Saida: capture/session_YYYYMMDD_HHMMSS/ (ou a pasta dada, que continua sendo gravada)
Recortes: layout.atual() (calibracao.json; sem ela, os fixos de antes), gravados em
layout.json da sessao para os leitores.
"""
import ctypes
import collections
import contextlib
import ctypes.wintypes as wt
from rubinot.adapters.historico import reservar_sessao
import datetime as dt
import json
import pathlib
import re
import shutil
import sys
import time

import mss
import mss.tools
from PIL import Image

import layout
import fontes
import stream_twitch

ctypes.windll.user32.SetProcessDPIAware()

TICK_S = 0.5
FULL_EVERY_TICKS = 8  # 4s
KS_BUFFER_TICKS = 120  # últimos 60 s completos, enquanto o detector lê o console
MAX_HOURS = 3  # ponytail: auto-stop 3h para nao encher o disco se esquecerem ligado
MIN_LIVRE_GB = 10  # 21/09: ~3 GB por hora de hunt; para antes de encher o disco (ao_vivo avisa)
TITLE_MARK = "RubinOT Client"
# Recortes relativos a janela: layout da calibracao (21/09); o historico dos fixos
# de antes esta em layout.LEGADO. ue_alerta e calib_snap importam estes nomes.
LAYOUT = layout.atual()
CHAT_REL = LAYOUT["chat"]
SPELL_REL = LAYOUT.get("spell")  # a calibracao nao marca Spells -> sem lane s_
BATTLE_REL = LAYOUT["battle"]
MAP_REL = LAYOUT["map"]
MAP_EVERY_TICKS = 2  # 1s


def find_game_rect():
    user32 = ctypes.windll.user32
    found = {}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if TITLE_MARK in buf.value:
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w > 200 and h > 200:  # ignora janela minimizada
                found["rect"] = {"left": r.left, "top": r.top, "width": w, "height": h}
                found["title"] = buf.value
                found["hwnd"] = hwnd
                return False
        return True

    user32.EnumWindows(cb, 0)
    return found


def rel_rect(win, rel):
    return {
        "left": win["left"] + rel["left"],
        "top": win["top"] + rel["top"],
        "width": rel["width"],
        "height": rel["height"],
    }


def pouco_disco(pasta=pathlib.Path(__file__).parent):
    return shutil.disk_usage(pasta).free < MIN_LIVRE_GB * 1e9


def salva_quadro(img, destino):
    """Publica somente PNG completo, para os leitores não pegarem escrita parcial."""
    tmp = destino.with_suffix('.tmp')
    img.save(tmp, format='PNG', compress_level=1)
    tmp.replace(destino)


def recorta(img, rel):
    x, y = rel['left'], rel['top']
    return img.crop((x, y, x + rel['width'], y + rel['height']))


def carimbo(agora, dia):
    """HHMMSS_mmm com a hora contada desde a meia-noite do dia da sessao (00:00:05 do dia
    seguinte = 240005_...): nome e ordem alfabetica continuam crescendo."""
    h = (agora.date() - dia.date()).days * 24 + agora.hour
    return f"{h:02d}" + agora.strftime("%M%S_%f")[:-3]


def main():
    out_root = pathlib.Path(__file__).parent / "capture"
    if pouco_disco():
        print(f"Disco quase cheio (menos de {MIN_LIVRE_GB} GB livres): gravacao nao iniciada.", flush=True)
        sys.exit(3)
    # 21/09: pasta dada = continua a mesma sessao (relance depois de cair/auto-stop)
    session = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1
               else reservar_sessao(out_root, dt.datetime.now()))
    session.mkdir(parents=True, exist_ok=True)
    fonte_p = session / 'fonte.json'
    if not fonte_p.exists():
        fontes.grava_json(fonte_p, fontes.atual())
    fonte = fontes.da_sessao(session)
    live = fonte['tipo'] == 'twitch'
    calib_p, _ = fontes.caminhos(fonte)
    if (session / 'calibracao.json').exists():
        calib_p = session / 'calibracao.json'
    calib = json.loads(calib_p.read_text(encoding='utf-8')) if calib_p.exists() else {}
    if live and not layout.calibrada(calib):
        print('Calibre a live antes de gravar.', flush=True)
        return
    dimensoes = (calib.get('janela', {}).get('largura'), calib.get('janela', {}).get('altura'))
    lay_p = session / "layout.json"
    # antes do 1o frame: os leitores leem a sessao por ele. Pasta com frames e sem ele = sessao
    # legada (LEGADO); nao gravar o layout de hoje por cima
    if not lay_p.exists() and not any(session.glob("f_*.png")):
        lay_p.write_text(json.dumps(layout.da_calibracao(calib) if calib else LAYOUT, ensure_ascii=False, indent=1), encoding="utf-8")
        fontes.grava_json(session / 'calibracao.json', calib)
    # 21/09: relance segue o layout da propria sessao (recalibrar no meio nao mistura recortes)
    lay = layout.da_sessao(session)
    chat_rel, battle_rel, map_rel, spell_rel = lay["chat"], lay["battle"], lay["map"], lay.get("spell")
    # 21/09: nome HHMMSS vira do avesso depois da meia-noite; a hora segue crescendo desde o dia
    # da sessao (24, 25...), como o lw.fsec ja le
    m = re.search(r"session_(\d{8})_", session.name)
    dia = dt.datetime.strptime(m[1], "%Y%m%d") if m else dt.datetime.combine(dt.date.today(), dt.time())

    game = find_game_rect() if not live else None
    if not game and not live:
        print("Janela 'RubinOT Client' nao encontrada. Abra o jogo e rode de novo.")
        sys.exit(1)
    print(f"Capturando {'Twitch / ' + fonte['canal'] if live else game['title']} -> {session}", flush=True)

    ticks = 0
    total_bytes = 0
    buffer_ks = collections.deque(sorted(session.glob('q_*.png')))
    with contextlib.ExitStack() as recursos:
        leitor = stream_twitch.Leitor(fonte['canal']) if live else None
        if leitor:
            recursos.callback(leitor.fechar)
        sct = None if live else recursos.enter_context(mss.MSS())
        sequencia = 0
        mudou_resolucao = False
        # 22/09: 3 h GRAVADAS (so conta tick com o jogo na frente); relogio de parede cortava a
        # hunt de quem da Ligar horas antes com o jogo atras de outra janela
        while ticks * TICK_S < MAX_HOURS * 3600:
            t0 = time.time()
            if live:
                inteiro, sequencia_nova = leitor.ultimo(sequencia)
                estado = leitor.estado()
                estado['atualizado_em'] = time.time()
                mudou_resolucao = mudou_resolucao or (inteiro is not None and inteiro.size != dimensoes)
                if mudou_resolucao:
                    estado.update(conectado=False, mensagem='A resolução da live mudou. Encerre a hunt e refaça a calibração.')
                    inteiro = None
                fontes.grava_json(session / 'stream_estado.json', estado)
                if inteiro is None:
                    time.sleep(TICK_S)
                    continue
                sequencia = sequencia_nova
            else:
                game = find_game_rect() or game  # acompanha se a janela mover
            # so captura com o jogo em primeiro plano (privacidade em alt-tab)
            fg = ctypes.windll.user32.GetForegroundWindow()
            if not live and game.get("hwnd") and fg != game["hwnd"]:
                time.sleep(1.0)
                continue
            stamp = carimbo(dt.datetime.now(), dia)

            # Uma única captura: o log e a prova completa têm os mesmos pixels.
            if not live:
                shot = sct.grab(game['rect'])
                inteiro = Image.frombytes('RGB', shot.size, shot.rgb)
            prova = session / f'q_{stamp}.png'
            salva_quadro(inteiro, prova)
            buffer_ks.append(prova)
            while len(buffer_ks) > KS_BUFFER_TICKS:
                antigo = buffer_ks[0]
                try:
                    antigo.unlink(missing_ok=True)
                except OSError:
                    break  # leitor usando o quadro: tentar no próximo tick
                buffer_ks.popleft()

            if ticks % FULL_EVERY_TICKS == 0:
                path = session / f'f_{stamp}.png'
                shutil.copyfile(prova, path.with_suffix('.tmp'))
                path.with_suffix('.tmp').replace(path)
                total_bytes += path.stat().st_size

            lanes = [("c", chat_rel), ("b", battle_rel)] + ([("s", spell_rel)] if spell_rel else [])
            if ticks % MAP_EVERY_TICKS == 0:
                lanes.append(("m", map_rel))
            for prefix, rel in lanes:
                path = session / f"{prefix}_{stamp}.png"
                salva_quadro(recorta(inteiro, rel), path)
                total_bytes += path.stat().st_size

            ticks += 1
            if ticks % 120 == 0:  # ~1 min
                print(f"{ticks} ticks, {total_bytes / 1e6:.0f} MB", flush=True)
                if pouco_disco(session):
                    print(f"Disco quase cheio (menos de {MIN_LIVRE_GB} GB livres): gravacao parada.", flush=True)
                    sys.exit(3)
            sleep = TICK_S - (time.time() - t0)
            if sleep > 0:
                time.sleep(sleep)
    print(f"Auto-stop apos {MAX_HOURS}h. {ticks} ticks.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Parado.", flush=True)
