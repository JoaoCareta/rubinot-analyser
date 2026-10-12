"""Abre diretamente a interface e supervisiona seu fechamento, sem painel intermediário.
Fechar a janela ou usar Desligar salva a hunt e encerra os processos do analisador.
O navegador usa perfil próprio; outras janelas do usuário ficam fora do encerramento.
Uso: pythonw controle.py (atalho Hunt Analyzer).
"""
import ctypes
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import runtime

AQUI = pathlib.Path(__file__).resolve().parent
URL = f"http://127.0.0.1:{os.environ.get('HUNT_PORTA') or 3312}"   # mesma porta do app.py
PERFIL = AQUI / ".tela_perfil"   # perfil próprio do navegador: a janela da tela vira processo nosso
LOG = AQUI / "app.log"
SEM_JANELA = 0x08000000          # CREATE_NO_WINDOW: nenhum console piscando


def python_do_analisador():
    """python.exe do mesmo ambiente do painel (o .venv do instalador)."""
    exe = pathlib.Path(sys.executable)
    return str(exe.with_name("python.exe")) if exe.name.lower() == "pythonw.exe" else str(exe)


def navegador():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            if base and (p := pathlib.Path(base) / rel).exists():
                return str(p)
    return None


TOLERA_QUEDAS = 3   # leituras seguidas sem resposta antes de dar o servidor por morto (~6 s)


def servidor_ligado(timeout=2.5):
    """28/09 (user, "a janela do analisador está fechando do nada"): o timeout era de 0,8 s e o
    servidor às vezes demora mais (remontar o índice do minimapa leva segundos). Uma consulta
    lenta virava "caiu" e o painel matava a janela da tela com o programa inteiro vivo."""
    try:
        with urllib.request.urlopen(URL + "/api/status", timeout=timeout) as r:
            return r.status == 200
    except OSError:
        return False


def processos():
    """[(pid, linha de comando)] do analisador: python com o caminho desta pasta ou navegador com o
    perfil da tela (21/09: Edge aberto num arquivo desta pasta é da pessoa e não pode ser fechado).
    Os painéis de controle (controle.py) ficam de fora: cada um se fecha sozinho."""
    ps = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-CimInstance Win32_Process | "
          "Where-Object { $_.Name -match '^(python|pythonw|HuntAnalyzer|msedge|chrome)\\.exe$' } | "
          "ForEach-Object { \"$($_.ProcessId)`t$($_.Name)`t$($_.CommandLine)\" }")
    saida = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                           encoding="utf-8", errors="replace", creationflags=SEM_JANELA).stdout
    achados = []
    for linha in saida.splitlines():
        pid, nome, cmd = (linha.split("\t", 2) + ["", ""])[:3]
        cmd_n = cmd.lower().replace("/", "\\")
        alvo = str(PERFIL if nome.lower() in ("msedge.exe", "chrome.exe") else AQUI).lower()
        supervisor = nome.lower() == "huntanalyzer.exe" and "--processo" not in cmd_n
        if pid.strip().isdigit() and alvo in cmd_n and "controle.py" not in cmd_n and not supervisor and int(pid) != os.getpid():
            achados.append((int(pid), cmd.strip()))
    return achados


def encerrar(so_tela=False):
    """Fecha a tela e encerra os processos do analisador (ou só a janela da tela). Devolve quantos."""
    pids = [pid for pid, cmd in processos() if not so_tela or str(PERFIL).lower() in cmd.lower()]
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=SEM_JANELA)
    return len(pids)


def abrir_tela():
    # já calibrado: abre direto na tela de hunt (user, 21/09); sem calibração, na de calibração
    url = URL + "/hunt" if (AQUI / "calibracao.json").exists() else URL
    exe = navegador()
    if not exe:  # sem Edge/Chrome: abre no navegador padrão (aí a aba não fecha sozinha)
        webbrowser.open(url)
        return
    subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={PERFIL}", "--no-first-run",
                      "--no-default-browser-check", "--window-size=1440,920"], creationflags=SEM_JANELA)


def ligar():
    """Sobe o servidor (se ainda não estiver no ar) e abre a tela. False se não subiu em 15 s."""
    if not servidor_ligado():
        # 28/09 (user, "o programa fechou 2x"): guarda o log da vez anterior antes de reescrever —
        # com "w" a prova de qualquer queda sumia no Ligar seguinte
        try:
            if LOG.exists():
                LOG.replace(AQUI / "app_anterior.log")
        except OSError:
            pass
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(f"\n===== ligado em {time.strftime('%d/%m %H:%M:%S')} =====\n")
            log.flush()
            subprocess.Popen(runtime.comando("app", "--sem-navegador"), cwd=AQUI,
                             stdout=log, stderr=subprocess.STDOUT, creationflags=SEM_JANELA)
        for _ in range(30):
            if servidor_ligado():
                break
            threading.Event().wait(0.5)
        else:
            return False
    abrir_tela()
    return True


# O supervisor não tem janela: acompanha somente a interface com perfil próprio.
def janelas_da_tela():
    pids = {pid for pid, cmd in processos() if str(PERFIL).lower() in cmd.lower()}
    u = ctypes.windll.user32
    achadas = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(hwnd):
            achadas.append(hwnd)
        return True
    u.EnumWindows(cb, 0)
    return achadas


def trazer_para_frente():
    janelas = janelas_da_tela()
    if not janelas:
        return False
    u = ctypes.windll.user32
    u.ShowWindow(ctypes.c_void_p(janelas[0]), 9)
    u.SetForegroundWindow(ctypes.c_void_p(janelas[0]))
    return True


def desligar_com_calma():
    # Salva a hunt antes de limpar processos que eventualmente sobraram.
    try:
        req = urllib.request.Request(URL + '/api/desligar', data=b'{}',
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5):
            pass
        for _ in range(60):
            if not servidor_ligado(timeout=1):
                break
            time.sleep(1)
    except OSError:
        pass
    finally:
        encerrar()


def acompanhar():
    vista = False
    ausencias = quedas = 0
    limite = time.monotonic() + 40
    while True:
        visivel = bool(janelas_da_tela())
        vista = vista or visivel
        ausencias = 0 if visivel else ausencias + 1
        if (vista and ausencias >= 2) or (not vista and time.monotonic() >= limite):
            return
        quedas = 0 if servidor_ligado() else quedas + 1
        if quedas >= TOLERA_QUEDAS:
            return
        time.sleep(1)


def main():
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    mutex = kernel.CreateMutexW(None, False, 'HuntAnalyzerInterfaceDireta')
    if kernel.GetLastError() == 183:
        trazer_para_frente()
        kernel.CloseHandle(ctypes.c_void_p(mutex))
        return
    try:
        if not navegador():
            raise RuntimeError('Instale Microsoft Edge ou Google Chrome para abrir o Hunt Analyzer.')
        if not ligar():
            raise RuntimeError(f'O analisador não iniciou. Consulte {LOG}.')
        acompanhar()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(None, str(e), 'Hunt Analyzer', 0x10)
    finally:
        desligar_com_calma()
        kernel.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == '__main__':
    main()
