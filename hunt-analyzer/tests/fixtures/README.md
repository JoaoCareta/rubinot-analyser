# Fixtures

`hunt.json`: dados inteiramente sintéticos, personagem QA, oito voltas, quatro lacunas de raw, mapa de teste e flag `sintetico/qa`. Nunca importar no treino.

`leitores/`: amostras sanitizadas para replay do atlas e reconhecimento. Somente os recortes das janelas necessárias são preservados sobre fundo preto, além das barras e campos numéricos do teste de recursos. Jogo, mapa, consoles, nomes de jogadores e demais painéis foram removidos. Destinos nominais de cura foram ocultados. Não são configuração de referência do usuário.

Cada resultado esperado fica no teste consumidor. Não aumentar esse conjunto com capturas integrais ou históricos pessoais.
