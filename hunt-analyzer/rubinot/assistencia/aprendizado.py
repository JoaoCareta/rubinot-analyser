"""Políticas de aviso de escudo, avaliadas por sessão e contexto. Sem IO."""
import collections
import hashlib
import json

VERSAO = 'utamo-aprendizado-1'


def episodios(observacoes, horizonte=8):
    """Risco observado no futuro; intervenções censuram rótulos negativos."""
    grupos = collections.defaultdict(list)
    for r in observacoes:
        if r.get('tipo')=='observacao' and not r.get('qa') and not r.get('sintetico'):
            grupos[(r['sessao'], json.dumps(r['contexto'], sort_keys=True))].append(r)
    saida = []
    for rows in grupos.values():
        rows = sorted({r['id']:r for r in rows}.values(), key=lambda r:r['t'])
        ultimo = -1e9
        for i, r in enumerate(rows):
            if r['t']-ultimo<horizonte or not r.get('combate') or r.get('escudo') is not False or not r.get('certificado'):
                continue
            futuro = [s for s in rows[i+1:] if r['t']<s['t']<=r['t']+horizonte]
            seq = [r,*futuro]
            if not futuro or futuro[-1]['t']<r['t']+horizonte-2 or any(b['t']-a['t']>3 for a,b in zip(seq,seq[1:])):
                continue
            if any(s.get('vida') is None or not s.get('certificado') for s in seq):
                continue
            perigo = any(s['vida']<=.60 for s in futuro)
            interveio = any(s.get('escudo') is True or s.get('som_recente') for s in futuro)
            if not perigo and (interveio or min(s['vida'] for s in futuro)<.80):
                continue
            saida.append({**r, 'perigo_futuro':perigo, 'rotulo_origem':'vida_futura_observada',
                          'fim_instante':max(s['instante'] for s in futuro), 'provas_resultado':[s['id'] for s in futuro]})
            ultimo = r['t']
    return saida


def avaliar(rows, espera):
    positivos = negativos = acertos = omissoes = avisos = 0
    for r in rows:
        # A política aprende somente o atraso de confirmação de queda.
        # Prontidão desconhecida continua observável, mas não certifica ação.
        avisar = r.get('pronta') is True and (r.get('caido_s') or 0)>=espera and r.get('dano',0)>0
        perigo = r['perigo_futuro']; positivos += perigo; negativos += not perigo
        avisos += avisar; acertos += avisar and perigo; omissoes += perigo and not avisar
    return {'positivos':positivos, 'negativos':negativos, 'acertos':acertos,
            'omissoes':omissoes, 'avisos':avisos, 'perda':omissoes*10+avisos-acertos}


def treinar(observacoes, contexto, base, antes_de, sessao_atual):
    rows = [r for r in episodios(observacoes) if r['contexto']==contexto
            and contexto.get('hunt') and r['sessao']!=sessao_atual and r['fim_instante']<antes_de]
    grupos = collections.defaultdict(list)
    for r in rows:
        grupos[r['sessao']].append(r)
    ordem = sorted(grupos, key=lambda s:min(r['instante'] for r in grupos[s]))
    out = {'versao':VERSAO, 'estado':'coletando', 'promover':False, 'contexto':contexto,
           'base_s':base, 'escudo_s':base, 'sessoes':len(ordem), 'episodios':len(rows),
           'semantica':'antecedencia_de_risco_observado_nao_efeito_causal_do_som'}
    if len(ordem)<6:
        return out
    treino = [r for s in ordem[:-3] for r in grupos[s]]
    selecao = grupos[ordem[-3]]
    teste = [r for s in ordem[-2:] for r in grupos[s]]
    if max(r['instante'] for r in treino)>=min(r['instante'] for r in selecao) or max(r['instante'] for r in selecao)>=min(r['instante'] for r in teste):
        return {**out, 'estado':'sessoes_sobrepostas'}
    if any(min(avaliar(rs,base)[k] for k in ('positivos','negativos'))<3 for rs in (treino,selecao,teste)):
        return out
    candidato = min((4,8,12,16), key=lambda n:avaliar(treino,n)['perda'])
    a, b = avaliar(selecao,base), avaliar(selecao,candidato)
    if b['omissoes']>a['omissoes'] or b['perda']>=a['perda']:
        return {**out, 'estado':'sem_melhoria_na_selecao'}
    a, b = avaliar(teste,base), avaliar(teste,candidato)
    # Exigir melhora também em cada sessão posterior; não esconder uma piora
    # na média. Nunca mudar o limiar de vida nem o intervalo global de sons.
    aceita = b['omissoes']==0 and b['perda']<a['perda'] and all(
        avaliar(grupos[s],candidato)['perda']<avaliar(grupos[s],base)['perda'] for s in ordem[-2:])
    out.update(estado='validado_no_contexto' if aceita else 'sem_melhoria_no_teste', promover=aceita,
               escudo_s=candidato if aceita else base, teste_base=a, teste_candidato=b,
               treino_sessoes=ordem[:-3], selecao_sessoes=ordem[-3:-2], teste_sessoes=ordem[-2:],
               avaliado_ate=max(r['instante'] for r in teste), origens=[r['id'] for r in rows])
    out['id'] = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    return out
