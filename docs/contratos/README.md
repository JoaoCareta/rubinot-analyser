# Contratos

Fontes: `xp_origem: XP Analyser` certifica a origem das novas comparações históricas de XP. `dmg_in_painel` e `dmg_in_origem` distinguem Input Analyser do log parcial. `paineis_observados` e `supplies` ampliam a consulta sem remover campos anteriores. `variacoes_estoque`/`variacoesEstoque` têm paridade e não preenchem consumo confirmado por delta de inventário.

## Hunt e métricas

`sessao.tempo_sessao_s` é anulável e somente aceito com `tempo_sessao_origem: Party Hunt`. `tempo_sessao_resolucao_s: 60`, quadro e instante acompanham a leitura. `tempo_sessao`/`tempoSessao` têm paridade; `dur_s` das voltas continua medindo outro intervalo. Observações detalhadas versionadas ficam em `paineis/observacoes.jsonl`, e estimativas Supply/Loot não alimentam `contador_uso`.

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

## Reconhecimento da aba Cura

A barra compartilhada contém Cura e RTCaster mesmo quando uma das abas está
inativa. O leitor usa o texto de uma dessas abas como âncora e confirma Cura
pelos cabeçalhos “Cura por magia” e “Treino de mana” nas posições do painel.
Isso tolera mudanças no estado visual da barra e margens superiores na seleção
manual, sem aceitar a aba RTC como Cura. Ícones e percentuais continuam sendo
leituras independentes: reconhecer a janela não confirma campos ilegíveis nem
aplicação de sugestões.

Guardar janela aberta localiza automaticamente a única janela de configuração
visível, incluindo a aba ativa de Cura/RTC, sem seleção de tipo ou retângulo.
A região manual continua compatível. Rejeições e salvamentos ficam no app.log.
Durante a hunt, o monitor verifica a captura completa q_ já existente a cada
segundo, em vez de esperar os f_ espaçados e duas leituras consecutivas. As
provas aceitas são copiadas para o histórico de configurações antes de qualquer
descarte do buffer; o leitor não modifica a retenção nem o cliente do jogo.

## Declaração de uso detectado

`POST /api/configuracoes` com `acao: declarar_uso` recebe `char`, `sessao`,
`revisoes` (RTC obrigatório; Cura/Roda opcionais e explicitamente incluídas) e
`resposta`: `uso_confirmado`, `outro_rtc` ou `rtc_desligado`. A leitura atual
precisa corresponder exatamente a cada revisão apresentada. Revisão obsoleta
ou sessão incompatível retorna 400 sem gravar confirmação.

`declaracao_uso`, `uso_componentes` e `elegibilidade_aprendizado` são campos
aditivos de consulta. Confirmar uso não altera `aplicado_confirmado` nem
preenche campos ausentes. Intervalo inicia na resposta; revisão substituída e
lacunas ficam no histórico. `confirmar` mantém o contrato legado de intenção
de adotar a sugestão. Os cooldowns normativos não são substituídos por cadência.

## Avaliação reservada e resultado posterior

Registros aditivos: `contador_item`, `oportunidade`, `reserva_avaliacao`,
`episodio_auditado`, `validacao_execucao`, `politica_pressao`, `uso_bonus`,
`recomendacao`, `adocao`, `resultado_referencia`, `resultado_adotado` e
`efetividade`. IDs e INSERT OR IGNORE preservam versões e idempotência.
`perfis_efetividade` é uma consulta aditiva por contexto; resultados mistos não
viram ganho individual. A intenção legada não cria `adocao` sozinha.

Modelos validados têm escopo e declaração, origens de treino/seleção/teste,
baseline, erros, incerteza e razão de promoção/rejeição. O conjunto final não
escolhe hipóteses. Quantidade sem identidade/unidade/série ou continuidade não
produz consumo; ausência de ícone sem região certificada permanece desconhecida.
Recomendações personalizadas têm até dois campos em `alteracoes`, expectativa
numérica e avaliação posterior; candidatas que pioram segurança são rejeitadas.

