# Contratos

## Hunt e métricas

`taxas(voltas)` e `especies(voltas)` são a fonte canônica. O espelho JavaScript tem testes de paridade em 102 conjuntos sintéticos com zero, lacuna, parcial, duração limite, refill e espécies. Os formatos atuais de `/api/hunt` e `/api/historico` continuam compatíveis.

Volta: `n`, `ini`, `fim`, `dur`, `tipo`, `parcial`, medidas anuláveis e espécies. `xp_raw_15min` é raw consolidada da janela de 15 min; multiplicar por quatro dá a taxa daquela janela. Nunca usar total observado dividido por todo o tempo para responder o rendimento da hunt.

Resultado: `voltas`, `total`, `parciais`, `refil`, `dur_s`, `dur_media`, `raw_h`, `raw_de`, `voltas_raw`, `voltas_15min`, `media`, `taxa`. `sup_pt` e `sup_eu` permanecem separados.

## Histórico v2

IDs novos: `hunt/AAAAMMDD_HHMMSS_<hash8>`. IDs antigos `hunt/AAAAMMDD_HHMM` continuam aceitos. Capturas com o mesmo segundo reservam uma pasta nova com sufixo; retomada explícita conserva a pasta original.

`resumo.json` recebe `historico_schema: 2` e `geracao: _geracoes/<uuid>`. Uma geração inclui mapas, laps e resumo completos. Só depois o resumo da raiz é substituído atomicamente. O leitor resolve arquivos pela geração indicada; interrupção não expõe mapas de outra publicação. Arquivos com nomes antigos são mantidos para CLIs legadas.

## Evidência e fases

Evento/recurso: identidade, sessão, personagem, origem, instante absoluto, offset `t`, precisão, leitor e fase. O registro não atribui configuração futura a evento antigo. Duplicatas usam chave `(sessao,tipo,id)`; cópias não são somadas no treino.

Fase: revisão por RTC/cura/roda, estado aplicado/observado sem aplicação/desconhecido, versões e instante. Confirmação não substitui evidência de aplicação. Eventos sem fase permanecem desconhecidos.

## HTTP

POST exige origem local e JSON objeto. Corpo inválido ou incompleto recebe 400; acima de 4.000.000 bytes recebe 413. Uma requisição inválida não derruba o servidor. Paths de assets e IDs são restritos por contrato; não aceitam travessia de diretórios.

## Trackers

Solo preserva a mediana canônica quando o banco já a fornece. Importações em `coladas.db` são idempotentes e independentes da reconstrução do banco derivado. Party mantém esquema/API próprios, com token de escrita e ETag conforme [trackers](../trackers.md).
