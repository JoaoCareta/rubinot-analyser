"""Catálogo de monstros, separado pelas classes do Bestiary do Tibia (user, 21/09).

Cada monstro fica em monstros/<classe>/<nome>.json + <nome>.gif. O que ainda não está no catálogo é buscado
no TibiaWiki BR pela API (a página comum fica atrás do Cloudflare, a API responde): vida, xp, quanto ele toma
de cada elemento, com que elementos ele bate, o loot por raridade, o gif e os locais fixos (21/09).

Uso: python catalogo.py                 confere o leitor do wiki, sem internet
     python catalogo.py "rage squid"    cataloga os nomes dados
"""
import collections
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "monstros"
API = "https://www.tibiawiki.com.br/api.php?"
UA = {"User-Agent": "HuntAnalyzer/0.1 (analisador local de hunt de Tibia)"}
TOMA = [("physical", "físico"), ("earth", "terra"), ("fire", "fogo"), ("death", "morte"),   # mesma ordem da
        ("energy", "energia"), ("holy", "sagrado"), ("ice", "gelo"), ("heal", "cura")]      # grade do wiki
BATE = [("physical", "físico"), ("earth", "terra"), ("fire", "fogo"), ("death", "morte"), ("energy", "energia"),
        ("holy", "sagrado"), ("ice", "gelo"), ("lifedrain", "dreno de vida"), ("manadrain", "dreno de mana"),
        ("drowning", "afogamento")]
LOOT = [("lootcomum", "comum"), ("lootincomum", "incomum"), ("lootsemiraro", "semi-raro"),
        ("lootraro", "raro"), ("lootmuitoraro", "muito raro")]
_trava = threading.Lock()   # ponytail: uma busca no wiki por vez; sobra para os 3 a 6 monstros de uma hunt


def slug(nome):
    return re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_")


def texto(v):
    """Wikitexto em texto: [[a|b]] vira b, [[a]] vira a; somem predefinição, tag e negrito."""
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\{\{[^{}]*\}\}|<[^>]*>|'{2,}", "", v)
    return v.strip().rstrip(".").strip()


def numero(v):
    m = re.search(r"\d+", v.replace(".", ""))
    return int(m[0]) if m else None


def lista(v, sep):   # separador dentro de parênteses não conta: "(0-705; causa poison)" é um item só
    return [p.strip() for p in re.split(re.escape(sep) + r"(?![^()]*\))", texto(v)) if p.strip()]


def ler_infobox(wikitexto):
    """Campos da Infobox_Criatura do TibiaWiki BR, já no formato do catálogo."""
    f = dict(re.findall(r"^\|[ \t]*(\w+)[ \t]*=[ \t]*(.*?)[ \t]*$", wikitexto, re.M))
    return {
        "nome": texto(f.get("name", "")),
        "categoria": texto(f.get("creatureclass", "")) or "Sem classe",
        "hp": numero(f.get("hp", "")),
        "xp": numero(f.get("exp", "")),
        "toma": {pt: numero(f.get(f"{en}DmgMod", "")) for en, pt in TOMA},
        "bate": {pt: lista(f[f"hab_{en}"], ";") for en, pt in BATE if texto(f.get(f"hab_{en}", ""))},
        "loot": {pt: lista(f[k], ",") for k, pt in LOOT if texto(f.get(k, ""))},
    }


def _api(**params):
    url = API + urllib.parse.urlencode(dict(params, format="json", formatversion=2))
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
        return json.load(r)


def _no_disco(s):
    achado = next(PASTA.glob(f"*/{s}.json"), None)
    return json.loads(achado.read_text(encoding="utf-8")) if achado else None


def _grava(pasta, s, entrada):
    tmp = pasta / f"{s}.json.tmp"   # grava inteiro e troca: quem lê nunca pega o arquivo pela metade
    tmp.write_text(json.dumps(entrada, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pasta / f"{s}.json")


def ler_locais(wikitexto):
    """[[Book World]][[Categoria:Spawns/Book World/nc]]. -> ["Book World"]: a categoria de cada local sai."""
    return lista(re.sub(r"\[\[Categoria:[^\]]*\]\]", "", wikitexto), ",")


def _local(titulo):
    """Locais fixos do wiki ("Locais Fixos: Book World"). Não estão na Infobox: saem da predefinição
    Locations, um switch pelo nome da página."""
    return ler_locais(_api(action="expandtemplates", title=titulo, text="{{Locations}}",
                           prop="wikitext")["expandtemplates"]["wikitext"])


def buscar(nome):
    """Entrada do catálogo; o que ainda não tem é buscado no wiki e guardado. None = o wiki não conhece o nome.
    Sem internet sobe o erro de rede e nada fica gravado, para tentar de novo depois."""
    s = slug(nome)
    entrada = _no_disco(s)
    if entrada and "local" in entrada:
        return entrada
    with _trava:
        entrada = _no_disco(s)   # outro pedido pode ter catalogado enquanto este esperava
        if not entrada:
            return _catalogar(nome, s)
        if "local" not in entrada:   # entrada de antes de 21/09: completa o local, o resto (e o gif) fica
            titulo = urllib.parse.unquote(entrada.get("fonte", "").rpartition("/wiki/")[2]).replace("_", " ")
            try:
                entrada["local"] = _local(titulo or entrada["nome"])
            except (OSError, ValueError, KeyError):   # sem internet ou wiki fora: completa numa próxima busca
                return entrada
            _grava(next(PASTA.glob(f"*/{s}.json")).parent, s, entrada)
        return entrada


def local_da_hunt(nomes):
    """Local fixo mais comum entre as espécies dadas (ex. "Book World"), ou None. Nome que o wiki não
    conhece (player na Battle List) ou busca sem internet não conta."""
    conta = collections.Counter()
    for n in dict.fromkeys(nomes):
        try:
            e = buscar(n)
        except (OSError, ValueError, KeyError):
            continue
        conta.update((e or {}).get("local") or [])
    return conta.most_common(1)[0][0] if conta else None


def _catalogar(nome, s):
    titulo = next((t for t in _api(action="opensearch", search=nome, limit=5, namespace=0)[1] if slug(t) == s), None)
    if not titulo:
        return None
    pagina = _api(action="query", prop="revisions", rvprop="content", rvslots="main", titles=titulo,
                  redirects=1)["query"]["pages"][0]
    wikitexto = pagina["revisions"][0]["slots"]["main"]["content"]
    if not re.search(r"\{\{\s*Infobox[ _]Criatura", wikitexto):
        return None
    entrada = ler_infobox(wikitexto)
    entrada["nome"] = entrada["nome"] or pagina["title"]
    pasta = PASTA / (re.sub(r"[^\w -]", "", entrada["categoria"]).strip() or "Sem classe")
    pasta.mkdir(parents=True, exist_ok=True)
    imagens = _api(action="query", generator="images", gimlimit="max", prop="imageinfo", iiprop="url",
                   titles=pagina["title"]).get("query", {}).get("pages", [])
    for img in imagens:   # o gif do monstro é a imagem da página com o mesmo nome dele
        url = (img.get("imageinfo") or [{}])[0].get("url", "")
        if slug(img["title"].split(":", 1)[-1].rsplit(".", 1)[0]) == s and url.lower().endswith(".gif"):
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
                dados = r.read()
            if dados[:4] == b"GIF8":
                (pasta / f"{s}.gif").write_bytes(dados)
                entrada["gif"] = f"{s}.gif"
            break
    entrada["local"] = _local(pagina["title"])
    entrada["fonte"] = "https://www.tibiawiki.com.br/wiki/" + urllib.parse.quote(pagina["title"].replace(" ", "_"))
    entrada["catalogado"] = time.strftime("%Y-%m-%d")
    _grava(pasta, s, entrada)
    return entrada


def imagem(s):
    """Gif catalogado do monstro, para o servidor mandar à página."""
    return next(PASTA.glob(f"*/{slug(s)}.gif"), None)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for n in sys.argv[1:]:
            e = buscar(n)
            print(n, "->", e and f"{e['categoria']} · {e['hp']} HP · {e['xp']} XP · gif {'sim' if e.get('gif') else 'não'}"
                                f" · {', '.join(e['local']) or 'sem local fixo'}")
        print("local da hunt:", local_da_hunt(sys.argv[1:]))
    else:
        amostra = """{{Infobox_Criatura|List={{{1|}}}
| name             = Rage Squid
| hp               = 17000
| exp              = 16.300
| creatureclass    = Inkborn
| hab_physical     = [[Melee|Corpo a corpo]] (0-650; causa poison até 45/turno)
| hab_earth        =
| hab_fire         = [[Magias de Criaturas#Strike|Fire Strike]] (600-750); [[Magias de Criaturas#Beam|Beam]] (400-500)
| fireDmgMod       = 0%
| iceDmgMod        = 115%
| healDmgMod       = 100%?
| lootcomum        = 0-6 [[Platinum Coin]]s, 0-3 [[Ultimate Health Potion]]s.
| lootraro         = [[Devil Helmet]], [[Purple Tome]].
}}"""
        e = ler_infobox(amostra)
        assert (e["nome"], e["categoria"], e["hp"], e["xp"]) == ("Rage Squid", "Inkborn", 17000, 16300), e
        assert (e["toma"]["fogo"], e["toma"]["gelo"], e["toma"]["cura"], e["toma"]["morte"]) == (0, 115, 100, None), e["toma"]
        assert e["bate"] == {"físico": ["Corpo a corpo (0-650; causa poison até 45/turno)"],
                             "fogo": ["Fire Strike (600-750)", "Beam (400-500)"]}, e["bate"]
        assert e["loot"] == {"comum": ["0-6 Platinum Coins", "0-3 Ultimate Health Potions"],
                             "raro": ["Devil Helmet", "Purple Tome"]}, e["loot"]
        assert ler_locais("[[Book World]][[Categoria:Spawns/Book World/nc]].") == ["Book World"]
        assert ler_locais("[[Banuta]][[Categoria:Spawns/Banuta/-5]], [[Yalahar Alchemist Quarter]]"
                          "[[Categoria:Spawns/Yalahar Alchemist Quarter/0]].") == ["Banuta", "Yalahar Alchemist Quarter"]
        assert ler_locais("") == []
        print("leitor do wiki ok")
