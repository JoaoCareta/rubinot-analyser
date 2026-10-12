"""Tabela das hunts conhecidas: nome em pt-BR, pasta do histórico e raw XP por bicho.

Fonte única (user, 24/09: "tudo deve vir da mesma fonte"). Antes o motor tinha a tabela e o
`pt_card` tinha um `FATOR_LOE = 6386` fixo com um comentário citando 7730 para a Livraria de Fogo
x3, onde a tabela (e o CLAUDE.md) dizem 8280 — três números para o mesmo bicho.

A chave é o "Local Fixo" do TibiaWiki, o mesmo que o catálogo devolve e que dá o nome da hunt; o
`fator` é por número de membros da pt. `raw_por_bicho` aceita tanto o local quanto o nome em pt-BR,
porque quem chama pela linha de comando conhece "Livraria de Fogo" e não o nome do wiki.
"""

HUNTS = {
    "Secret Library Fire Section": {"nome": "Livraria de Fogo", "pasta": "livraria_fogo",
                                    "fator": {3: 8280, 4: 7300}},
    "Secret Library Energy Section": {"nome": "Livraria de Energia", "pasta": "livraria_energy",
                                      "fator": {4: 6386}},
}


def _entrada(hunt):
    if hunt in HUNTS:
        return HUNTS[hunt]
    alvo = (hunt or "").strip().lower()
    return next((e for e in HUNTS.values() if e["nome"].lower() == alvo), {})


def raw_por_bicho(hunt, membros):
    """Raw XP por bicho da hunt com essa quantidade de membros, ou None (aí a contagem vem do chat).
    Quando a pt muda, conferir pela mensagem de XP e recalibrar aqui — em lugar nenhum mais."""
    return _entrada(hunt).get("fator", {}).get(membros)


def nome(hunt):
    return _entrada(hunt).get("nome")


def pasta(hunt):
    return _entrada(hunt).get("pasta")


if __name__ == "__main__":
    assert raw_por_bicho("Secret Library Fire Section", 3) == 8280
    assert raw_por_bicho("Livraria de Fogo", 4) == 7300          # pelo nome em pt-BR também
    assert raw_por_bicho("Livraria de Fogo", 2) is None          # pt que ninguém mediu
    assert raw_por_bicho("Unhallowed Crypt", 4) is None
    assert nome("Secret Library Energy Section") == "Livraria de Energia"
    print("locais: tabela de raw por bicho ok")
