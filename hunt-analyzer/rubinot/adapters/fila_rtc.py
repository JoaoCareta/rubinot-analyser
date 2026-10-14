"""Recibos duráveis de leitura; nunca remove quadros da gravação."""
import sqlite3
import time

from rubinot.adapters.arquivos import gravar_json


def consumir(sessao, char, leitor, quadros, limite=12, parar=None):
    if not char:
        return 0
    con = sqlite3.connect(sessao / 'fila_rtc.sqlite3', timeout=30)
    try:
        con.execute('CREATE TABLE IF NOT EXISTS lidos (char TEXT, quadro TEXT, PRIMARY KEY(char,quadro))')
        vistos = {r[0] for r in con.execute('SELECT quadro FROM lidos WHERE char=?', (char,))}
        fila = [p for p in quadros if p.name not in vistos]
        feitos = 0
        for p in fila[:limite]:
            if parar and parar.is_set():
                break
            try:
                leitor.processar(p, char, sessao.name)
                # Falha mantém a cabeça pendente; repetição é idempotente no leitor.
                with con:
                    con.execute('INSERT OR IGNORE INTO lidos VALUES (?,?)', (char, p.name))
                feitos += 1
            except Exception as erro:
                gravar_json(sessao / 'coleta_rtc.json', {'estado':'falha de leitura',
                    'quadro':p.name, 'erro':str(erro), 'pendentes':len(fila)-feitos})
                raise
        gravar_json(sessao / 'coleta_rtc.json', {'estado':'pendente' if len(fila)>feitos else 'em dia',
            'pendentes':len(fila)-feitos, 'processado_em':time.time(),
            'primeiro_pendente':fila[feitos].name if len(fila)>feitos else None,
            'atraso_s':max(0,time.time()-fila[feitos].stat().st_mtime) if len(fila)>feitos else 0,
            'cadencia_captura_alvo_s':0.5,
            'limite':'Aberturas entre capturas podem não ser observadas.'})
        return feitos
    finally:
        con.close()
