"""Previsões sequenciais: o resultado de um trecho só ajusta o próximo."""
import math
import statistics

VERSAO = 'previsto-observado-1'


def prever(valores):
    valores = [float(v) for v in valores if isinstance(v, (int, float))
               and not isinstance(v, bool) and math.isfinite(v)]
    if not valores:
        return {'previsto': None, 'modelo': VERSAO, 'amostras': 0,
                'estado': 'sem_referencia', 'incerteza': None}
    # Escolha usando somente erros de previsões anteriores ao trecho alvo.
    perdas = {'mediana_historica': [], 'mediana_recente': []}
    for i in range(max(5, len(valores)-30), len(valores)):
        perdas['mediana_historica'].append(abs(valores[i]-statistics.median(valores[:i])))
        perdas['mediana_recente'].append(abs(valores[i]-statistics.median(valores[max(0, i-5):i])))
    modelo = 'mediana_historica'
    if len(perdas[modelo]) >= 8 and sum(perdas['mediana_recente']) < sum(perdas[modelo])*.95:
        modelo = 'mediana_recente'
    treino = valores[-5:] if modelo == 'mediana_recente' else valores
    erros = perdas[modelo]
    return {'previsto': statistics.median(treino), 'modelo': VERSAO+':'+modelo,
            'amostras': len(valores), 'estado': 'previsao_descritiva',
            'incerteza': statistics.mean(erros) if erros else None,
            'erro_anterior_medio': statistics.mean(perdas['mediana_historica']) if erros else None,
            'erro_modelo_medio': statistics.mean(erros) if erros else None,
            'incerteza_unidade': 'erro_absoluto_medio_anterior',
            'beneficio_rtc_comprovado': False}


def comparar(previsao, observado):
    previsto = previsao.get('previsto')
    valido = isinstance(observado, (int, float)) and not isinstance(observado, bool) and math.isfinite(observado)
    erro = observado-previsto if valido and previsto is not None else None
    return {**previsao, 'observado': observado if valido else None,
            'erro': erro, 'erro_absoluto': abs(erro) if erro is not None else None,
            'erro_percentual': erro/abs(observado)*100 if erro is not None and observado else None}
