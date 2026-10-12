"""Monta o instalador do Hunt Analyzer para a pt: pasta HuntAnalyzer/ + zip, só com o que o programa usa.

Uso: python montar_pacote.py [pasta_de_saida]     (padrão: pacote/ ao lado deste script)

Código = fecho dos imports locais (AST: pega import dentro de função e try/except) a partir das
entradas. Dados = lista DADOS abaixo (whitelist): tudo o mais da pasta do projeto fica de fora.
Aborta se faltar módulo, se algum arquivo do projeto citado no código ou nas páginas ficar de fora
sem estar em PESSOAIS, ou se algo pessoal escapar para o pacote.
"""
import ast
import pathlib
import re
import shutil
import sys
import zipfile

PROJETO = pathlib.Path(__file__).resolve().parent.parent / "hunt-analyzer"
AQUI = pathlib.Path(__file__).resolve().parent
SAIDA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / "pacote"
PASTA = SAIDA / "HuntAnalyzer"
ZIP = SAIDA / "Hunt Analyzer - instalador.zip"
LEIA_ME = AQUI / "LEIA-ME.txt"

# controle = atalho; app = servidor; capture e lap_watch = subprocessos que o ao_vivo sobe
ENTRADAS = ["controle", "app", "capture", "lap_watch", "ao_vivo"]
DADOS = [
    "atlas.json",            # atlas de glifos: todo leitor de texto (atlas_build.load_atlas)
    "botao_x.png",           # molde do × dos cabeçalhos (app.detectar)
    "pin_template.png",      # molde do pin do Map View (pin_detect)
    "monstros_nomes.txt",    # nomes de bicho: separa player de monstro na Battle List (lap_watch)
    "requirements.txt", "instalar.bat", "abrir.bat",
    "ui/index.html", "ui/hunt.html", "ui/evolucao.html", "ui/auxiliadores.html",
    "ui/taxas.js",   # taxas.js = a conta da tela
    "ui/navegacao.js",  # menu lateral e cabeçalho compartilhados
    "ui/tutorial.js", "ui/rtc.js", "ui/magias.json",
    "ui/rtc_worker.js", "ui/temporal.js", "ui/integracao.js", "ui/janelas_referencias.json", "ui/recursos_glifos.json", "ui/roda_motor.js", "ui/fflate.js", "ui/fflate-LICENSE.txt", "ui/roda_catalogo.json",
    "ui/configuracoes.html", "ui/voc_ed.png", "ui/voc_ms.png", "ui/roda_visual.js",
    "ui/configuracoes_glifos.json", "ui/rtc_referencias.json", "ui/roda_referencias.json",
    "ui/gato_scuba.png", "ui/gato_som.mp3",
]
DADOS += ['ui/magia_apprentice_s_strike.png', 'ui/magia_buzz.png', 'ui/magia_chill_out.png', 'ui/magia_death_strike.png', 'ui/magia_energy_beam.png', 'ui/magia_energy_strike.png', 'ui/magia_energy_wave.png', 'ui/magia_eternal_winter.png', 'ui/magia_fire_wave.png', 'ui/magia_flame_strike.png', 'ui/magia_great_energy_beam.png', 'ui/magia_hell_s_core.png', 'ui/magia_ice_strike.png', 'ui/magia_lightning.png', 'ui/magia_great_fire_wave.png', 'ui/magia_ice_burst.png', 'ui/magia_great_death_beam.png', 'ui/magia_forked_glacier.png', 'ui/magia_forked_thorns.png', 'ui/magia_physical_strike.png', 'ui/magia_rage_of_the_skies.png', 'ui/magia_strong_energy_strike.png', 'ui/magia_strong_flame_strike.png', 'ui/magia_strong_ice_strike.png', 'ui/magia_strong_ice_wave.png', 'ui/magia_strong_terra_strike.png', 'ui/magia_scorch.png', 'ui/magia_mud_attack.png', 'ui/magia_terra_strike.png', 'ui/magia_terra_wave.png', 'ui/magia_wrath_of_nature.png', 'ui/magia_ultimate_energy_strike.png', 'ui/magia_ultimate_ice_strike.png', 'ui/magia_ultimate_terra_strike.png', 'ui/magia_ultimate_flame_strike.png', 'ui/magia_terra_burst.png', 'ui/magia_avalanche_rune.png', 'ui/magia_great_fireball_rune.png', 'ui/magia_stone_shower_rune.png', 'ui/magia_thunderstorm_rune.png', 'ui/magia_sudden_death_rune.png']
DADOS += ['ui/roda_icone_5.png', 'ui/roda_icone_6.png', 'ui/roda_icone_23.png', 'ui/roda_icone_24.png', 'ui/roda_icone_25.png', 'ui/roda_icone_26.png', 'ui/roda_icone_27.png', 'ui/roda_icone_28.png', 'ui/roda_icone_29.png', 'ui/roda_icone_30.png', 'ui/roda_icone_31.png', 'ui/roda_icone_32.png', 'ui/roda_icone_33.png', 'ui/roda_icone_34.png', 'ui/roda_icone_35.png', 'ui/roda_icone_36.png', 'ui/roda_icone_37.png', 'ui/roda_icone_38.png', 'ui/roda_icone_39.png', 'ui/roda_icone_40.png']
DADOS += ['ui/magia_intense_healing.png', 'ui/magia_ultimate_healing.png', 'ui/magia_heal_friend.png', 'ui/magia_mass_healing.png', 'ui/magia_restoration.png', 'ui/magia_nature_s_embrace.png']
DADOS += ['ui/elemento_fisico.png', 'ui/elemento_fogo.png', 'ui/elemento_terra.png', 'ui/elemento_energia.png', 'ui/elemento_gelo.png', 'ui/elemento_sagrado.png', 'ui/elemento_morte.png']
DADOS += [p.relative_to(PROJETO).as_posix() for d in ("app", "features", "shared") for p in (PROJETO / "ui" / d).rglob("*") if p.is_file() and p.relative_to(PROJETO).as_posix() not in DADOS and p.name != "mock_hunt.json"]
DADOS_PASTAS = ["monstros"]  # catálogo já baixado do TibiaWiki (o resto baixa sozinho)
# citados no código mas são do dono (ou gerados em uso): nunca vão
PESSOAIS = {"calibracao.json", "calibracao_print.png", "app.log", "app_anterior.log", "z_ue_calib.png", "mock_hunt.json",
            "fonte.json", "fontes", "stream_estado.json",
            "auxiliares.json", "locais_player.json", "rtc_player.json", "mapa_ajustes.json",   # configurações e reparos pessoais
            ".tela_perfil", "capture", "KS", "configuracoes_player",
            "cache_mundo.npz",   # 24/09: índice do minimapa DESTA máquina; nasce no 1º uso (26 MB)
            "hunt_data"}   # 22/09: o ao_vivo guarda o histórico aqui; a pasta nasce no 1º uso de cada um
PROIBIDO = re.compile(r"(^|/)(calibracao|capture/|hunt_data|reports|\.venv|\.tela_perfil|__pycache__|z_|calib_|"
                      r"mock_hunt|walked_|zonas_|infernatil_|hunts_stats|cands_|dna_|clip_andares|arrows_series)"
                      r"|\.bak|\.log$|\.pyc$")


def caminhos_modulos():
    arquivos = list(PROJETO.glob('*.py')) + list((PROJETO / 'rubinot').rglob('*.py'))
    return {'.'.join(p.relative_to(PROJETO).with_suffix('').parts).removesuffix('.__init__'): p
            for p in arquivos}


def locais(mod):
    caminhos = caminhos_modulos()
    arv = ast.parse(caminhos[mod].read_text(encoding='utf-8'))
    nomes = set()
    pacote = mod if caminhos[mod].name == '__init__.py' else mod.rpartition('.')[0]
    for n in ast.walk(arv):
        alvos = []
        if isinstance(n, ast.Import):
            alvos = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ''
            if n.level:
                partes = pacote.split('.')
                base = '.'.join(partes[:len(partes)-n.level+1] + ([base] if base else []))
            alvos = [base] + [base+'.'+a.name for a in n.names]
        elif isinstance(n, ast.Call) and getattr(n.func, 'attr', getattr(n.func, 'id', '')) in ('import_module', '__import__'):
            sys.exit(f'import dinâmico em {mod}:{n.lineno}: conferir na mão')
        for alvo in alvos:
            if alvo in caminhos:
                nomes.add(alvo)
                partes = alvo.split('.')
                nomes.update('.'.join(partes[:i]) for i in range(1,len(partes)) if '.'.join(partes[:i]) in caminhos)
    return nomes, arv


def fecho():
    mods, fila, arvores = set(), list(ENTRADAS), {}
    while fila:
        m = fila.pop()
        if m not in mods:
            mods.add(m)
            deps, arvores[m] = locais(m)
            fila += deps
    return sorted(mods), arvores


def citados(arvores):
    """Arquivos da pasta do projeto (raiz e ui/) cujo nome aparece como string no código ou nas páginas."""
    existentes = {p.name for p in PROJETO.iterdir() if p.is_file()} | {p.name for p in (PROJETO / "ui").iterdir() if p.is_file()}
    achados = set()
    for arv in arvores.values():
        achados |= {n.value for n in ast.walk(arv) if isinstance(n, ast.Constant) and n.value in existentes}
    for html in ("ui/index.html", "ui/hunt.html"):
        achados |= set(re.findall(r"/ui/([\w.]+?\.\w+)", (PROJETO / html).read_text(encoding="utf-8"))) & existentes
    return achados


def main():
    mods, arvores = fecho()
    arquivos = [caminhos_modulos()[m].relative_to(PROJETO).as_posix() for m in mods] + DADOS
    arquivos += [p.relative_to(PROJETO).as_posix() for d in DADOS_PASTAS for p in sorted((PROJETO / d).rglob("*"))
                 if p.is_file() and not p.name.endswith(".tmp")]
    nomes = {pathlib.PurePosixPath(a).name for a in arquivos}
    fora = citados(arvores) - nomes - PESSOAIS - {"ui", "monstros"}
    if fora:
        sys.exit(f"citado no código e fora do pacote (pôr em DADOS ou PESSOAIS): {sorted(fora)}")
    vazou = [a for a in arquivos if PROIBIDO.search(a)]
    if vazou:
        sys.exit(f"pessoal no pacote: {vazou}")

    if PASTA.exists():
        shutil.rmtree(PASTA)
    for a in arquivos:
        (PASTA / a).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJETO / a, PASTA / a)
    # BOM + CRLF: o Bloco de Notas abre os acentos certos em qualquer Windows
    (PASTA / "LEIA-ME.txt").write_bytes(
        LEIA_ME.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig"))

    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(PASTA.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(SAIDA).as_posix())
    print(f"{len(mods)} módulos: {', '.join(mods)}")
    print(f"{sum(1 for p in PASTA.rglob('*') if p.is_file())} arquivos em {PASTA}")
    print(f"zip: {ZIP} ({ZIP.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
