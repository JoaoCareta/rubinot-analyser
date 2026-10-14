# Plano de implementação do RTC e dos experimentos da Twin por XP

Data: 14/10/2026. Estado: planejado, sem implementação por esta tarefa.

Completar o ciclo reconhecer o RTC → identificar o período de uso → medir XP e dano → comparar com a referência → sugerir o próximo teste. Aproveitar os registros existentes de sugestões, adoção e resultados posteriores.

## 1 Prioridade de XP

- Principal: raw XP/h em condições comparáveis.
- Secundário: dano da PT/h; dano próprio ajuda a explicar o resultado.
- Restrição: preservar sustentação e segurança dos integrantes.

Calcular deltas do XP Analyser divididos pelo tempo observado. A leitura é do personagem e será identificada como indicador da produção da hunt em PT, sem inventar a soma de XP dos quatro jogadores. Dano maior não compensa perda comprovada de XP. Diferenças dentro da variação normal ficam inconclusivas e mantêm a referência.

## 2 Leitura automática do RTC

O monitor atual escolhe o quadro mais recente e compartilha processamento com análises de combate, podendo perder uma abertura breve da janela.

- Processar quadros capturados em ordem, com controle persistente de pendências.
- Separar a leitura do RTC do processamento pesado de combate.
- Guardar imagem, horário da captura, personagem, sessão e campos reconhecidos.
- Atualizar a última leitura sem criar nova configuração quando nada mudou.
- Preservar leituras intermediárias e impedir que quadros antigos substituam o estado atual.
- Mostrar atraso ou falha de leitura quando houver.

Aceite: uma abertura presente em quadro legível da gravação produz leitura recuperável, mesmo se processada após o fechamento da janela. Aberturas entre capturas continuam sendo uma limitação mensurada. Integrar e testar a retenção permanente de gravações já entregue, sem recriar essa funcionalidade nem apagar quadros.

## 3 Confirmação automática do ajuste observado

Desvincular a comparação do RTC do resultado da roda e da confirmação manual na calibração. Comparar por campo e componente; roda incompleta não impede confirmar Twin em 5+.

Exemplos de apresentação:

- Twin sugerida: 5+ · Última leitura: 5+ · Confere · Observada às 06:25:37.
- Twin sugerida: 5+ · Última leitura: 2+ · Configuração diferente da sugerida.

Distinguir configuração visível de uso automático ativo. Se a tela não comprovar ativação, informar a lacuna. Manter declarações do usuário para correções históricas, com origem identificada.

Aceite: nova leitura atualiza automaticamente o comparativo, sem visita à calibração, sem depender de recomendação de roda e sem confirmar campos ilegíveis.

## 4 Períodos de configuração e comparação

Abrir fase a cada mudança relevante de Twin, roda, cura, composição da PT ou Hazard.

- Usar somente medidas cujos intervalos pertençam à fase correspondente.
- Separar voltas que atravessem mudanças, sem repartir XP ou dano por estimativa.
- Distinguir horário observado, horário informado e intervalo incerto.
- Comparar personagem, hunt, PT, Hazard, roda, rota e interferências conhecidas compatíveis.
- Exibir tempo, cobertura e quantidade de voltas utilizadas.

Aceite: nenhuma taxa da hunt inteira pode ser atribuída ao 2+ apenas porque ele estava configurado no final. A classificação da comparação deve respeitar a qualidade da evidência de adoção.

## 5 Incorporação do histórico de 13 e 14 de outubro

Contexto inicial: Hetero afeminado, ED, Monster Graveyard, PT x4, roda pt-dammage após a troca informada.

| Configuração | Papel no aprendizado |
| --- | --- |
| 5+ | Referência escolhida pelo usuário para o contexto estudado |
| 2+ | Experiência observada, com resultados e limitações preservados |
| 4+ | Candidato ainda sem resultado |
| 6+ | Candidato ainda sem resultado |

Reproduzir os recortes e as métricas já calculados:

| Trecho | Raw XP/h | Dano próprio/h |
| --- | --- | --- |
| 13/10, 06:45:13,801 até 08:48:59,534, bloco 5+ | 19,157 kk | 11,156 kk |
| 14/10, após a troca da roda, 06:50:02,967 até 07:55:58,556, bloco analítico 5+ | 20,243 kk | 11,793 kk |
| 14/10, 07:55:58,556 até 08:59:20,073, bloco analítico 2+ | 19,870 kk | 11,374 kk |
| União ponderada dos dois blocos 5+ | 19,534 kk | 11,378 kk |

Preservar 07:56 como corte analítico informado pelo usuário, não instante recuperado da mudança. A leitura intermediária de 9+ às 07:45:16 continua como ressalva; não reclassificar ou apagar a prova. O início após a troca da roda foi delimitado pelo retorno observado, não pelo instante exato do clique.

Hoje, o bloco 2+ teve raw XP/h 1,84% menor, dano próprio/h 3,56% menor e dano da PT/h 1,98% menor que o bloco 5+. O agrupamento dos dois dias favoreceu levemente 2+ em XP, com Hazard 5 ontem e 6 hoje. Esses resultados orientam testes, sem demonstrar causalidade exclusiva ou superioridade universal de 5+.

Battle List é população disponível, não alvos atingidos. A média real de acertos e o dano total específico da Twin continuam indeterminados pelo console parcial. Não transformar danos de ataques concorrentes em dano da magia.

Aceite: reproduzir valores, fontes e intervalos; distinguir análise retrospectiva de teste prospectivo e preservar dados e previsões originais.

## 6 Testes progressivos com 4+ e 6+

Testar um candidato por hunt, mantendo os demais ajustes relevantes. Sequência inicial proposta:

1. Registrar referência recente em 5+.
2. Propor 4+ para a próxima hunt comparável.
3. Detectar a configuração aplicada e acompanhar o resultado.
4. Voltar a medir 5+ quando necessário para conferir a variação entre dias.
5. Avaliar 6+ pelo mesmo processo.

A ordem pode mudar se a análise de oportunidades justificar melhor outro candidato. Toda proposta explica o motivo, sem prometer percentual de ganho desconhecido. Simulação de dano pode ajudar a selecionar hipóteses, mas não certifica produção de XP.

Três voltas completas e estáveis são o mínimo para uma avaliação inicial, não garantia de superioridade. A promoção exige evidência suficiente e confirmação posterior, com critérios definidos antes de observar o resultado. Preservar separação cronológica entre seleção e avaliação, sem reutilizar o mesmo resultado repetidamente como confirmação independente.

Estados: proposto → configuração observada → em avaliação → promissor, pior ou inconclusivo → validado posteriormente.

Resultados negativos também ficam registrados. Pior ou inconclusivo mantém 5+; um candidato promissor requer confirmação antes de ser apresentado como melhoria validada. Sugestões são para a próxima hunt, no máximo dois ajustes; neste experimento, alterar somente o limiar da Twin. A aplicação no jogo continua sendo feita pelo usuário, sem automação de alterações durante a hunt.

## 7 Implementação e validação

Pontos principais de integração no diretório hunt-analyzer:

- `rubinot/bootstrap/monitor.py`: consumo de quadros e isolamento da leitura de configuração.
- `rubinot/configuracao_combate/estado.py`, `concordancia.py` e `vigencia.py`: leituras, comparação por componente e evidência temporal de uso.
- `rubinot/planejamento/registro.py`, `efetividade.py` e `validacao.py`: propostas, adoção, períodos comparáveis, resultados e promoção.
- `rubinot/planejamento/modelos.py`: aproveitamento contextual das experiências sem atribuição indevida.
- `ui/features/planejamento/painel.js`: última leitura, concordância independente da roda, acompanhamento e resultado dos testes.
- `rubinot/hunt/metricas.py`, fachadas `ao_vivo.taxas/especies` e `ui/taxas.js`: fonte canônica e paridade, se os cálculos precisarem de alteração.

Reutilizar os componentes existentes, manter APIs e CLIs compatíveis e impedir imports de adaptadores nas regras puras. Alterações de comportamento devem atualizar documentação e testes.

Casos obrigatórios de teste:

- RTC aberto brevemente, leitura parcial, quadro atrasado e retomada após reinício.
- Confirmação da Twin com roda indisponível ou reprovada.
- Configuração visível sem comprovação de ativação automática.
- Troca no meio de uma volta e intervalos de vigência incertos.
- Mais dano com menos XP: a opção não vence.
- Diferença pequena ou cobertura insuficiente: manter referência.
- Battle List numerosa sem prova de acerto: não produzir média de alvos atingidos.
- Reconstrução dos recortes históricos sem apagar leituras conflitantes.
- Preservação de históricos, imagens, previsões e configurações; processamento repetido sem duplicação.

Usar dados temporários e rede simulada nos testes. Executar `tools/verificar.ps1 -Perfil rapido` durante a implementação e perfil completo antes da atualização. Exigir autoteste do compilado e conferência do fluxo na aplicação instalada, com backup e reversão. Falha, timeout ou teste ignorado impedem aprovação geral.

O workspace contém alterações concorrentes. Identificar a revisão efetivamente entregue e validar seu conjunto, sem atribuir a esta tarefa alterações alheias. Atualizar a instalação do atalho preservando os dados, sem gerar Setup.exe e sem push em main.

## Ordem de execução

Primeiro coleta e confirmação; depois períodos e métricas; por último exploração de candidatos. O analyser só deve recomendar novos testes com acompanhamento quando conseguir identificar a configuração utilizada e o resultado correspondente.
