"""Grafo AST, incluindo imports locais dentro de funções e pacotes."""
import ast
import pathlib


def modulos(raiz):
    raiz = pathlib.Path(raiz)
    arquivos = list(raiz.glob('*.py')) + list((raiz / 'rubinot').rglob('*.py'))
    return {'.'.join(p.relative_to(raiz).with_suffix('').parts).removesuffix('.__init__'): p
            for p in arquivos if not p.name.startswith('test_')}


def dependencias(nome, caminho, conhecidos):
    saida = set()
    pacote = nome if caminho.name == '__init__.py' else nome.rpartition('.')[0]
    for n in ast.walk(ast.parse(caminho.read_text(encoding='utf8'))):
        alvos = []
        if isinstance(n, ast.Import):
            alvos = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ''
            if n.level:
                partes = pacote.split('.')
                base = '.'.join(partes[:len(partes) - n.level + 1] + ([base] if base else []))
            alvos = [base] + [base + '.' + a.name for a in n.names]
        for alvo in alvos:
            if alvo in conhecidos:
                saida.add(alvo)
    return saida


def grafo(raiz):
    arquivos = modulos(raiz)
    return {m: dependencias(m, p, arquivos) for m, p in arquivos.items()}


def ciclos(g):
    indice = {}; baixos = {}; pilha = []; ativos = set(); grupos = []
    def visitar(v):
        indice[v] = baixos[v] = len(indice)
        pilha.append(v); ativos.add(v)
        for w in g.get(v, ()):
            if w not in indice:
                visitar(w); baixos[v] = min(baixos[v], baixos[w])
            elif w in ativos:
                baixos[v] = min(baixos[v], indice[w])
        if baixos[v] == indice[v]:
            grupo = []
            while True:
                w = pilha.pop(); ativos.remove(w); grupo.append(w)
                if w == v:
                    break
            if len(grupo) > 1 or v in g.get(v, ()):
                grupos.append(sorted(grupo))
    for v in g:
        if v not in indice:
            visitar(v)
    return sorted(grupos)


def violacoes_dominio(texto):
    permitidos = {'collections', 'math', 'hashlib', 'json', 'datetime', 'dataclasses', 'typing', 'enum', 'statistics', 'bisect'}
    regras_puras = {'rubinot.planejamento.efetividade', 'rubinot.hunt.metricas'}
    violacoes = []
    for n in ast.walk(ast.parse(texto)):
        nomes = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ''] if isinstance(n, ast.ImportFrom) else []
        violacoes += [nome for nome in nomes if nome.split('.')[0] not in permitidos and nome not in regras_puras]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {'open', '__import__', 'eval', 'exec'}:
            violacoes.append(n.func.id)
    return violacoes
