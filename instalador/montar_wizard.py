"""Compila o motor com Nuitka e gera o assistente Windows com Inno Setup.

Execute de hunt-analyzer/: <python do ambiente de build> ../instalador/montar_wizard.py
As ferramentas de build não são distribuídas. Nenhum dado pessoal entra no pacote.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import pathlib
import shutil
import subprocess
import sys

import montar_pacote as pacote

AQUI = pathlib.Path(__file__).resolve().parent
PROJETO = AQUI.parent / "hunt-analyzer"
BUILD = AQUI / "build"
DIST = BUILD / "hunt_launcher.dist"
SAIDA = AQUI / "saida"


def valida_dados():
    pacote.PROJETO = PROJETO
    pacote.ENTRADAS = [*pacote.ENTRADAS, "hunt_launcher"]
    mods, arvores = pacote.fecho()
    dados = [p for p in pacote.DADOS if p not in {"requirements.txt", "instalar.bat", "abrir.bat"}]
    dados += [p.relative_to(PROJETO).as_posix() for d in pacote.DADOS_PASTAS
              for p in sorted((PROJETO / d).rglob("*")) if p.is_file() and not p.name.endswith(".tmp")]
    nomes = {pathlib.PurePosixPath(p).name for p in dados} | {f"{m}.py" for m in mods}
    fora = pacote.citados(arvores) - nomes - pacote.PESSOAIS - {"ui", "monstros"}
    if fora:
        raise RuntimeError(f"Dados citados e fora da lista: {sorted(fora)}")
    for p in dados:
        if pacote.PROIBIDO.search(p) or pathlib.Path(p).name in pacote.PESSOAIS or pathlib.Path(p).suffix in {".py", ".pyc", ".pyo"}:
            raise RuntimeError(f"Arquivo proibido: {p}")
    return mods, dados


def licencas():
    destino = DIST / "licencas"
    destino.mkdir(exist_ok=True)
    python_license = pathlib.Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Licença do Python não encontrada")
    shutil.copy2(python_license, destino / "Python-LICENSE.txt")
    for nome in ("numpy", "opencv-python-headless", "pillow", "mss", "streamlink", "truststore", "av"):
        meta = importlib.metadata.distribution(nome)
        arquivos = [p for p in meta.files or [] if
                    any(t in p.name.lower() for t in ("license", "licence", "copying", "notice"))]
        if not arquivos:
            raise RuntimeError(f"Licença não encontrada: {nome}")
        for n, p in enumerate(arquivos):
            fonte = pathlib.Path(meta.locate_file(p))
            if fonte.is_file():
                shutil.copy2(fonte, destino / f"{nome}-{n}-{p.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sem-compilar", action="store_true", help="empacota um build já compilado")
    parser.add_argument("--apenas-compilar", action="store_true", help="valida o aplicativo sem gerar instalador")
    parser.add_argument("--versao", default="1.0.0")
    parser.add_argument("--iscc", type=pathlib.Path, default=AQUI / "ferramentas/inno/ISCC.exe")
    args = parser.parse_args()
    if not args.apenas_compilar and not args.iscc.is_file():
        raise RuntimeError(f"Compilador do Inno Setup ausente: {args.iscc}")
    mods, dados = valida_dados()
    BUILD.mkdir(exist_ok=True)
    SAIDA.mkdir(exist_ok=True)
    if not args.sem_compilar:
        cmd = [sys.executable, "-m", "nuitka", "--mode=standalone", "--mingw64",
               # Caminhos 8.3 podem colidir com pastas virtualizadas do Windows.
               "--experimental=avoid-short-path",
               "--assume-yes-for-downloads", "--windows-console-mode=disable",
               "--output-filename=HuntAnalyzer.exe", f"--output-dir={BUILD}",
               f"--report={BUILD / 'compilacao.xml'}", "--company-name=Hunt Analyzer",
               "--product-name=Hunt Analyzer", f"--file-version={args.versao}",
               f"--product-version={args.versao}", "--jobs=4"]
        cmd += [f"--include-module={m}" for m in mods if m != "hunt_launcher"]
        if os.environ.get('HUNT_BUILD_SEM_CACHE') == '1':
            cmd.append('--disable-ccache')
        # PyAV 19 inclui .py e .pyd homônimos. --include-package duplica módulos
        # no Nuitka 4.2.2; incluir cada extensão nativa uma única vez evita isso.
        import av
        avroot = pathlib.Path(av.__file__).parent
        avmods = sorted({'av.' + '.'.join(p.relative_to(avroot).with_suffix('').parts)
                         for p in avroot.rglob('*.pyd')})
        cmd += [f'--include-module={m}' for m in avmods]
        cmd += ['--include-package-data=streamlink', '--include-distribution-metadata=streamlink', '--no-prefer-source-code']
        # Só arquivos da lista aprovada; não incluir pasta do projeto inteira.
        cmd += [f"--include-data-files={PROJETO / p}={p}" for p in dados]
        cmd += [str(PROJETO / "hunt_launcher.py")]
        subprocess.run(cmd, cwd=PROJETO, check=True, env={**os.environ,
                       "NUITKA_CACHE_DIR": str(AQUI / "ferramentas/nuitka-cache"),
                       "PYTHONIOENCODING": "utf-8"})
    exe = DIST / "HuntAnalyzer.exe"
    if not exe.is_file():
        raise RuntimeError("Executável compilado ausente")
    for p in dados:
        if not (DIST / p).is_file():
            raise RuntimeError(f"Dado faltando no build: {p}")
    licencas()
    shutil.copy2(AQUI / "LEIA-ME-wizard.txt", DIST / "LEIA-ME.txt")
    # Barreira final contra fonte aberta e arquivos pessoais.
    proibidos = [str(p.relative_to(DIST)) for p in DIST.rglob("*") if p.is_file() and
                 (p.suffix.lower() in {".py", ".pyc", ".pyo", ".pyw"} or
                  pacote.PROIBIDO.search(p.relative_to(DIST).as_posix()))]
    if proibidos:
        raise RuntimeError(f"Build contém arquivos proibidos: {proibidos}")
    resultado = BUILD / "autoteste.json"
    resultado.unlink(missing_ok=True)
    subprocess.run([str(exe), "--autoteste", "--resultado", str(resultado)], cwd=DIST,
                   timeout=90, check=True)
    teste = json.loads(resultado.read_text(encoding="utf-8"))
    if not teste.get("ok") or not teste.get("compilado"):
        raise RuntimeError(f"Executável não passou no autoteste: {teste}")
    if pathlib.Path(teste["comando"][0]) != exe:
        raise RuntimeError(f"Subprocesso não aponta para o executável distribuído: {teste}")
    if args.apenas_compilar:
        print(f'Aplicativo validado, sem instalador: {exe}')
        return
    subprocess.run([str(args.iscc), f"/DPayload={DIST}", f"/DReleaseDir={SAIDA}",
                    f"/DAppVersion={args.versao}", str(AQUI / "HuntAnalyzer.iss")], check=True)
    setup = SAIDA / "HuntAnalyzer-Setup.exe"
    manifesto = {"versao": args.versao, "sha256": hashlib.sha256(setup.read_bytes()).hexdigest(),
                 "bytes": setup.stat().st_size, "modulos_compilados": mods, "autoteste": teste,
                 "arquivos": [p.relative_to(DIST).as_posix() for p in sorted(DIST.rglob("*")) if p.is_file()],
                 "dependencias": {n: importlib.metadata.version(n) for n in
                                   ("nuitka", "numpy", "opencv-python-headless", "pillow", "mss")}}
    (SAIDA / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: {setup} ({setup.stat().st_size / 1024**2:.1f} MB)")


if __name__ == "__main__":
    main()
