"""Diário de observações e provas; captura e histórico não reescrevem o passado."""
import hashlib
import json
from pathlib import Path
import shutil

from rubinot.observacao import paineis
from rubinot.hunt.metricas import tempo_sessao


def ler_json(arquivo):
    try:
        return json.loads(Path(arquivo).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {}


def gravar(arquivo, dados):
    tmp = arquivo.with_suffix('.tmp')
    tmp.write_text(json.dumps(dados,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    tmp.replace(arquivo)


def registrar(imagem, sessao, frame, t, refs_itens=None):
    sessao = Path(sessao); pasta = sessao/'paineis'; pasta.mkdir(exist_ok=True)
    pendentes = ler_json(pasta/'pendentes.json')
    pendentes[frame] = {'t':t}
    gravar(pasta/'pendentes.json',pendentes)
    obs = paineis.ler(imagem,sessao,frame,t,refs_itens)
    fonte = sessao/frame
    obs['sha256'] = hashlib.sha256(fonte.read_bytes()).hexdigest()
    # Conservar prova de cada geometria e estado de qualidade novos, fora da limpeza de quadros.
    assinatura = {'layout':obs['layout']['revisao'],
                  'estados':{k:v['estado'] for k,v in obs['paineis'].items()}}
    chave = hashlib.sha256(json.dumps(assinatura,sort_keys=True).encode()).hexdigest()[:20]
    prova = pasta/'provas'/f'{chave}.png'
    if not prova.exists():
        prova.parent.mkdir(exist_ok=True)
        shutil.copy2(fonte,prova)
    obs['prova_layout'] = prova.relative_to(sessao).as_posix()
    with (pasta/'observacoes.jsonl').open('a',encoding='utf8') as f:
        f.write(json.dumps(obs,ensure_ascii=False,separators=(',',':'))+'\n')
    gravar(pasta/'atual.json',obs)
    pendentes.pop(frame,None)
    gravar(pasta/'pendentes.json',pendentes)
    return obs


def resumo(sessao):
    obs = ler_json(Path(sessao)/'paineis'/'atual.json')
    return {'tempo_sessao_s':tempo_sessao(obs),
            'tempo_sessao_origem':'Party Hunt','tempo_sessao_resolucao_s':60,
            'tempo_sessao_quadro':obs.get('frame'),'tempo_sessao_t':obs.get('t'),
            'paineis_revisao':obs.get('layout',{}).get('revisao')}
