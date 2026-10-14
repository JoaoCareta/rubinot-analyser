# Arquitetura

Monólito modular local. Captura e workers continuam separados por processo; o HTTP e a interface continuam no PC do jogador. Contextos representam significados distintos dos dados, sem exigir implantação independente.

| Contexto | Dono do contrato | Código |
|---|---|---|
| Observação | Quadro, leitura, qualidade, evento observado | `rubinot/observacao/configuracao.py`, `execucao.py`; captura e atlas nas fachadas legadas |
| Hunt | Volta limpa, taxa, cobertura, histórico e ciclo de vida | `rubinot/hunt/metricas.py`, `aplicacao.py` |
| Configuração de combate | Snapshot, confirmação, concordância | `rubinot/configuracao_combate/estado.py`, `concordancia.py` |
| Planejamento e aprendizado | Registro, fase, exemplo, avaliação temporal e modelo | `rubinot/planejamento/registro.py`, `avaliacao.py`, `modelos.py` |
| Conflitos | Aliados, episódio de KS e prova | `rubinot/conflitos/detector.py` |
| Assistência | Escudo, perigo, silêncio e arbitragem do apito | `rubinot/assistencia/utamo.py` |

Arquivos/HTTP/gerações do histórico ficam em `rubinot/adapters`. `rubinot/bootstrap/monitor.py` compõe leitores e observadores. Catálogo e localização mantêm módulos existentes, com os consumidores registrados no manifesto.

`metricas.py`, `avaliacao.py` e `concordancia.py` são regras puras. SQLite não é o dono da avaliação de segurança. O aprendizado importa métricas sem carregar o motor da hunt. Modelos usam o armazenamento público, sem importar configuração visual. Configuração não inicia o monitor.

As fachadas `ao_vivo`, `configuracoes`, `aprendizado_hunt`, `rtc_ml`, `observacao_execucao`, `ks`, `auxiliares` e `app` preservam identidade de módulo, atributos e CLIs. Isso mantém consumidores e testes que substituem raízes de armazenamento funcionando. Novos consumidores preferem o contexto proprietário.

O pacote fica diretamente em `hunt-analyzer/rubinot/`, para funcionar com as CLIs e o dispatcher compilado sem instalar fontes na máquina do usuário. Não há camadas vazias nem `BaseService`. A extração de serviços internos continua possível atrás das mesmas fachadas.

Interface: `ui/app/hunt.js` coordena a página em escopo fechado e publica `HuntApp`. Planejamento consulta essa API, sem usar variáveis internas da página. Cards e grade são módulos testáveis; histórico renderiza dados prontos. Apresentação comum vive em `HuntUI`. Os motores RTC/Temporal/Roda conservam os contratos existentes.

Atualizações da interface preservam conteúdo durante consultas assíncronas. O resumo da calibração atualiza textos nos mesmos cards e publica a resposta completa, sem esvaziar a grade antes da consulta. Planejamento separa a assinatura das categorias de magias da assinatura do contexto de cálculo; horários/provas de releituras não invalidam conteúdo equivalente. RTC e roda mantêm seus containers, expansão e controles entre consultas. O lote de rodas só redesenha a combinação selecionada quando ela muda; resultados anteriores durante recálculo ficam identificados e indisponíveis para interação até a conclusão. Tempos dos estudos/modelos continuam significativos e não entram no filtro de metadados das leituras.

O teste de arquitetura percorre imports tardios e pacotes; nenhum ciclo é aceito. Testes negativos provam que o verificador detecta ciclos e imports proibidos. APIs HTTP e formatos antigos continuam legíveis; gerações novas são aditivas.
