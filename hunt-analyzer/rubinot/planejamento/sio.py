"""Aprendizado descritivo de sio por destino; sem fabricar HP ou cura base."""
import bisect
import hashlib
import json
import statistics

from rubinot.hunt.metricas import balanco_cura

VERSAO = 'sio-ek-1'
DANOS = {'damage_taken', 'damage_condition', 'damage_taken_player', 'damage_plain_player'}
CURAS = {'heal_other', 'healed_player', 'heal_self_player', 'healed', 'heal_self'}


def identidade(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False).encode('utf8')).hexdigest()


def estudar(eventos, recursos, contexto, party, configuracao=None, max_gap_s=12):
    """Console é amostra parcial. Identidade/vocação vêm da party confirmada."""
    configuracao = configuracao or {}
    char = contexto.get('char'); sessao = contexto.get('sessao')
    eventos = sorted({e.get('id') or identidade(e):e for e in eventos
                      if isinstance(e.get('t'), (int, float)) and not e.get('qa') and not e.get('sintetico')}.values(), key=lambda e:e['t'])
    casts = [e for e in eventos if e.get('kind')=='cast' and e.get('ator')==char
             and e.get('qualidade')=='identificada' and e.get('magia_id') in ('heal_friend','nature_s_embrace','mass_healing')]
    tempos_casts = [e['t'] for e in casts]
    membros = []
    for aliado in party:
        if aliado.get('vocacao')!='EK' or not aliado.get('identidade_confirmada') or not aliado.get('nome'):
            continue
        nome = aliado['nome']
        proprias = [e for e in eventos if e.get('alvo')==nome and e.get('kind')=='heal_other' and e.get('ator')==char]
        associadas = {}
        for e in proprias:
            perto = [c for c in casts[bisect.bisect_left(tempos_casts,e['t']-1):bisect.bisect_right(tempos_casts,e['t'])]
                     if c.get('alvo')==nome or c.get('magia_id')=='mass_healing']
            if len(perto)==1:
                associadas[e['id']] = perto[0]
        sios = [c for c in casts if c.get('magia_id')=='heal_friend' and c.get('alvo')==nome]
        dados = [e for e in eventos if e.get('alvo')==nome and e.get('kind') in DANOS | CURAS]
        tempos = [e['t'] for e in dados]
        barras = []
        for q in recursos:
            v = q.get('aliados',{}).get(nome, {})
            # Nome integral e party confirmada identificam o destino. Uma
            # barra antiga/truncada ou nome OCR com '?' não ganha identidade.
            identificada = v.get('identidade_confirmada') or v.get('origem')=='barra_nameplate_integral'
            if identificada and v.get('percentual') is not None and 0<=v['percentual']<=100:
                barras.append({'t':q['t'], 'percentual':v['percentual'], 'prova':q.get('prova') or q.get('origem'),
                               'revisao':q.get('revisao')})
        barras.sort(key=lambda b:b['t'])
        janelas = []
        for a,b in zip(sios,sios[1:]):
            dt = b['t']-a['t']
            if not 0<dt<=max_gap_s or a.get('fase_id')!=b.get('fase_id') or a.get('vigencia_inconclusiva') or b.get('vigencia_inconclusiva'):
                continue
            rows = dados[bisect.bisect_left(tempos,a['t']):bisect.bisect_left(tempos,b['t'])]
            danos = [e for e in rows if e['kind'] in DANOS]
            curas = [e for e in rows if e['kind'] in CURAS]
            # Representações explícita e genérica da MESMA cura não são somadas.
            explicitas = {(e['t'],e.get('value')) for e in curas if e['kind']!='healed_player'}
            curas = [e for e in curas if e['kind']!='healed_player' or (e['t'],e.get('value')) not in explicitas]
            sio = [e for e in curas if associadas.get(e['id'],{}).get('magia_id')=='heal_friend']
            outras = [e for e in curas if e not in sio]
            perto = [v for v in barras if a['t']-1<=v['t']<=b['t']+1]
            j = {'id':identidade([VERSAO,sessao,nome,a['id'],b['id']]), 'inicio':a['t'],'fim':b['t'],
                 'fase_id':a.get('fase_id'),'dano_hp':sum(e['value'] for e in danos) if danos else None,
                 'sio_hp':sum(e['value'] for e in sio) if sio else None,
                 'outras_hp':sum(e['value'] for e in outras) if outras else None,
                 'cobertura_completa':False,'origem':'console_parcial','sio_eventos':[e['id'] for e in sio],
                 'dano_eventos':[e['id'] for e in danos], 'vida_minima':min((v['percentual'] for v in perto),default=None),
                 'provas':list(dict.fromkeys([a.get('origem'),b.get('origem'),*[e.get('origem') for e in rows],*[v['prova'] for v in perto]]))}
            janelas.append(j)
        balanco = balanco_cura(janelas)
        treino = balanco['janelas'][:len(balanco['janelas'])*2//3]
        teste = balanco['janelas'][len(treino):]
        modelo = {'estado':'coletando','unidade':'HP_por_segundo_de_console_parcial','treino':len(treino),'teste':len(teste),
                  'beneficio_real_validado':False,'ajuste_automatico':False}
        # Perfis por fase: misturar alterações do RTC não certifica rendimento.
        perfis = []
        for fase in sorted({j['fase_id'] or '' for j in balanco['janelas']}):
            rows = [j for j in balanco['janelas'] if (j['fase_id'] or '')==fase]
            corte = len(rows)*2//3
            ts, vs = rows[:corte], rows[corte:]
            if len(ts)<12 or len(vs)<4:
                continue
            perfil = {'fase_id':fase or None,'treino_ids':[j['id'] for j in ts], 'teste_ids':[j['id'] for j in vs],
                      'treino_ate':ts[-1]['fim'],'teste_desde':vs[0]['inicio'],'metricas':{}}
            for campo in ('dano_hp_s','sio_hp_s'):
                med = statistics.median(j[campo] for j in ts)
                erro = statistics.mean(abs(j[campo]-med) for j in vs)
                perfil['metricas'][campo] = {'previsto':med,'observado_medio':statistics.mean(j[campo] for j in vs),
                    'erro_absoluto_medio':erro,'erro_relativo':erro/max(1,abs(med)),
                    'validado':erro/max(1,abs(med))<=.30}
            perfil['estado'] = 'validado_descritivo_parcial' if all(m['validado'] for m in perfil['metricas'].values()) else 'rejeitado_por_erro'
            perfis.append(perfil)
        modelo['perfis'] = perfis
        modelo['estado'] = 'validado_descritivo_parcial' if any(p['estado']=='validado_descritivo_parcial' for p in perfis) else 'coletando'
        limiar = configuracao.get(nome,{}).get('sio_percent')
        evidencias = [j for j in balanco['janelas'] if j['saldo_sio_hp']<0 and j['vida_minima'] is not None
                      and isinstance(limiar,int) and j['vida_minima']<limiar]
        membros.append({'nome':nome,'vocacao':'EK','balanco':balanco,'modelo':modelo,'vida_amostras':len(barras),
            'vida_minima':min((b['percentual'] for b in barras),default=None), 'pressao_com_deficit':len(evidencias),
            'sio_percent_observado':limiar, 'provas_pressao':list(dict.fromkeys(p for j in evidencias for p in j['provas'] if p))})
    sugestoes = []
    for m in membros:
        limiar = m['sio_percent_observado']
        if m['pressao_com_deficit'] and isinstance(limiar,int) and limiar<90:
            sugestoes.append({'origem':'aprendizado_sio_parcial','sessao':sessao,'hazard':contexto.get('hazard'),
                'id':'heal_friend','vocacao_destino':'EK','alvo':m['nome'],'anterior':limiar,'vida_percent':90,
                'provas':m['provas_pressao'],'beneficio_real_validado':False,
                'motivo':f"{m['pressao_com_deficit']} intervalos com cura do sio abaixo do dano observado e vida abaixo de {limiar}%. Testar 90%; cobertura parcial, sem ganho real certificado."})
    return {'versao':VERSAO,'sessao':sessao,'contexto':contexto,'membros':membros,'sugestoes':sugestoes[:1],
            'estado':'estudo_parcial' if membros else 'identidade_ek_pendente',
            'limites':['Console não fornece o total da hunt; quedas de HP não são convertidas em dano.',
                       'Cura aplicada observada não calibra cura base nem excesso; críticos não sustentam segurança garantida.',
                       'Gatilho de 90% é candidato de teste; gran sio e demais campos são preservados.']}
