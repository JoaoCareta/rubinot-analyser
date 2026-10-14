"""Diário numérico append-only; modelo fixado antes da primeira decisão."""
import json
import hashlib
import pathlib
from rubinot.adapters.arquivos import gravar_json
from rubinot.assistencia.aprendizado import treinar


class Diario:
    def __init__(self, raiz, sessao, contexto, base, instante):
        self.raiz = pathlib.Path(raiz); self.raiz.mkdir(parents=True, exist_ok=True)
        self.arquivo = self.raiz/(sessao+'.jsonl')
        self.sessao = sessao; self.contexto = contexto
        self.ids = set(); anteriores = []
        for p in self.raiz.glob('*.jsonl'):
            with p.open(encoding='utf8') as f:
                for linha in f:
                    try:
                        r = json.loads(linha)
                    except ValueError:
                        continue
                    if p==self.arquivo:
                        self.ids.add(r['id'])
                    else:
                        anteriores.append(r)
        # Retomada reutiliza a decisão congelada; não escolhe novamente no teste.
        chave = hashlib.sha256(json.dumps(contexto,sort_keys=True).encode()).hexdigest()[:20]
        congelada = self.raiz/(sessao+'-'+chave+'-politica.json')
        if congelada.exists():
            self.politica = json.loads(congelada.read_text(encoding='utf8'))
        else:
            self.politica = treinar(anteriores, contexto, base, instante, sessao)
            gravar_json(congelada, self.politica)

    def guardar(self, r):
        if r['id'] in self.ids:
            return
        r = {**r, 'sessao':self.sessao, 'contexto':self.contexto,
             'politica':self.politica.get('id', self.politica['versao'])}
        incompleta = False
        if self.arquivo.exists() and self.arquivo.stat().st_size:
            with self.arquivo.open('rb') as f:
                f.seek(-1, 2); incompleta = f.read(1) != b'\n'
        with self.arquivo.open('a', encoding='utf8') as f:
            if incompleta:
                f.write('\n')
            f.write(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n')
        self.ids.add(r['id'])
