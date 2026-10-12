"""Comandos dos subprocessos no desenvolvimento e no programa compilado."""
import pathlib
import sys

COMPILADO = "__compiled__" in globals()
AQUI = pathlib.Path(__file__).resolve().parent


def comando(processo, *args):
    if processo not in {"app", "capture", "lap_watch", "ks"}:
        raise ValueError(f"Processo desconhecido: {processo}")
    if COMPILADO:
        # No standalone do Nuitka, sys.executable aponta para um python.exe
        # que não é distribuído. argv[0] é o nosso executável de verdade.
        return [str(AQUI / pathlib.Path(sys.argv[0]).name), "--processo", processo, *map(str, args)]
    exe = pathlib.Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    return [str(exe), str(AQUI / f"{processo}.py"), *map(str, args)]
