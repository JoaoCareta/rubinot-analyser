# Insights para planejar o aprendizado da execução do RTC

Registro da conversa de 12/10/2026, horário de Brasília. Este documento consolida requisitos e evidências para planejamento; não declara a função implementada nem autoriza alterações no cliente durante a hunt.

## Objetivo do usuário

Entender conclusivamente como o RTC configurado funciona na prática e usar esse aprendizado para afinar sugestões. A composição inteira deve ser otimizada: quantidade e escolha de magias, com ou sem runa, uma ou duas forks, waves, UE, mínimos de criaturas e prioridades. Preencher todos os slots não é objetivo nem garantia de uma rotação útil.

O usuário rejeitou o 2+ uniforme: opções habilitadas nas mesmas levas disputam os mesmos turnos. Os limites de criaturas e prioridades devem ser aprendidos em conjunto com cooldowns e oportunidades de ataque; aumentar o mínimo apenas para silenciar uma magia não resolve a otimização.

## Evidências e escopo da fase de hoje

- Personagem: Hetero afeminado; sessão `session_20261012_142757`; Book World, área ativa andar 11, Crusader/Headwalker.
- O usuário confirmou ter aplicado o RTC por volta de 15:11. A leitura do editor foi feita às 15:11:42, preset `tests-analyser`. Essa leitura comprova os campos visíveis; não comprova, isoladamente, cada decisão do motor do jogo.
- Slots de magia lidos: Eternal Winter 8+; Strong Ice Wave, Forked Thorns, Terra Wave e Forked Glacier 2+. Todos com mana 5% e prioridade 1, nessa ordem.
- Runas: Avalanche 1+, prioridade 2; Sudden Death prioridade 1, campo de criaturas não disponível na leitura. Não preencher esse campo ausente como configuração observada.
- Opções lidas: virar para o alvo ligado; combo em ordem de prioridade desligado; hotkey tem prioridade ligado. O comportamento de desempate entre prioridades iguais e a interferência das hotkeys precisam ser medidos, não presumidos pela posição dos slots.
- Antes da aplicação havia outra composição: por exemplo, Ice Burst aparece nas voltas 7 e 8. Não usar essas voltas como validação do novo RTC.
- A volta 9 (15:10:52–15:15:20) atravessou a aplicação; a primeira volta completa da nova fase foi a 10.

| Lançamentos próprios identificados | Volta 10: 15:15:20–15:19:44 | Volta 11: 15:19:44–15:24:24 |
|---|---:|---:|
| Forked Thorns | 32 | 40 |
| Strong Ice Wave | 22 | 30 |
| Forked Glacier | 7 | 11 |
| Eternal Winter | 2 | 2 |
| Terra Wave | Nenhum identificado | Nenhum identificado |

Cobertura temporal registrada pelo observador: 142,9 s de 264 s na volta 10 e 280 s de 280 s na volta 11. Cobertura temporal integral não equivale automaticamente a todos os lançamentos legíveis: console cortado, sobreposição e leituras inválidas precisam de critérios próprios. Contagens identificadas são evidência positiva, não total garantido.

Em um recorte anterior da fase nova, o modelo registrava 33 Strong Ice Waves, 37 Forked Thorns, 17 Forked Glaciers e 3 UEs, sem Terra Wave identificada. São contagens cumulativas de outro instante; não somar aos números das voltas acima.

Previsões consultadas durante a conversa oscilaram com o contexto: uma simulação previa zero Forked Glacier apesar de 17 lançamentos identificados; outra previa 10 Terra Waves apesar da ausência observada nas duas voltas completas. Essa divergência evidencia inadequação da previsão à execução observada, não mede o ganho de uma composição alternativa.

O estado do aprendizado consultado ainda indicava `configuracao_aplicada_desconhecida`, sem intervalos efetivos aprovados nessa fase. Há observações coletadas, mas não uma otimização conjunta pessoal validada.

## Correção central feita pelo usuário

Uma magia em slot posterior não recebe necessariamente o quarto ou quinto turno. A cada oportunidade, opções anteriores podem voltar a ficar prontas e ganhar novamente. A pergunta relevante é: **existe algum turno em que Terra Wave está pronta, atende às condições e não é preterida?**

O usuário relatou ausência em dez voltas. Registrar esse relato sem convertê-lo em dez voltas auditadas com a configuração das 15:11. Exigir mais voltas não substitui explicar a disputa dos turnos quando já existem evidências para investigá-la.

O critério solicitado de três voltas completas com configuração estável continua útil como alerta operacional de ausência de uso. Para a fase das 15:11, as voltas elegíveis são 10, 11 e 12; a volta 12 não foi auditada nesta consolidação. Não usar esse limiar como pré-requisito para investigar a causa nem como prova de ausência absoluta com fontes incompletas.

### Demonstração no simulador atual

Teste ilustrativo, não reconstrução comprovada do cliente: 2+ criaturas constantes, todos os alvos disponíveis, turno compartilhado de 2 s, ordem Strong Ice Wave → Forked Thorns → Terra Wave → Forked Glacier, sem UE/runa/interferência manual.

- Frigo Hur com cooldown de 4 s e fork de 6 s: sequência inicial Frigo → fork → Frigo → Terra; 3 Terra Waves em 30 s.
- Frigo Hur e fork com cooldown de 4 s: alternância Frigo → fork repetida; zero Terra Wave em 30 s. Não há um número finito de turnos que garanta sua vez nesse cenário estável.

O teste demonstra que a saturação pode existir e que o cooldown efetivo altera a conclusão. Não estabelece o cooldown real da Forked Thorns nessa hunt nem valida a regra de prioridade/desempate do cliente.

## Fontes visuais indicadas pelo usuário

Imagem de referência: `C:/Users/User/AppData/Local/Temp/codex-clipboard-ebdc8ded-a844-4f6d-89e8-e5dfcfc61d60.png`. O caminho temporário pode desaparecer; preservar a imagem no conjunto de provas quando o planejamento organizar os anexos.

O usuário destacou a barra inferior com magias, cooldowns e runas. Informou que Spells fica aberto quase todo o tempo e que o personagem exibe as falas das magias liberadas. Essas fontes devem ser cruzadas, não tratadas como redundância dispensável:

- Editor RTC: composição, campos, opções e identidade da configuração.
- Barra: identificação dos ícones, contagem regressiva/prontidão e mudanças após uso; quantidades de runas quando visíveis.
- Spells e fala sobre o personagem: identificação e horário de lançamentos próprios. Deduplicar a mesma execução entre fontes.
- Recursos e Battle List: mana e população visível no mesmo instante. População não comprova alvos efetivamente atingidos ou condições geométricas de uma wave.
- Console de dano: associação parcial com lançamentos e efeitos; não inventar dano total por magia a partir de linhas incompletas.
- Tela do jogo: orientação, alcance e possíveis interferências manuais apenas quando observáveis.

A captura precisa ter resolução temporal suficiente para distinguir prontidão, seleção e lançamento entre turnos. Presença de cooldown numa imagem isolada não reconstrói todos os turnos. Medir cadência e perda das fontes existentes antes de propor novas capturas; não iniciar captura duplicada.

## O que o aprendizado deve conseguir explicar

Construir uma linha do tempo sincronizada de oportunidades, contendo configuração/fase, provas, magias candidatas e escolha observada. Classificar separadamente:

1. Condição de criaturas ou mana não atendida.
2. Cooldown próprio ou grupo compartilhado ainda bloqueado.
3. Geometria/alcance/orientação incompatíveis, se verificáveis.
4. Magia pronta e elegível, mas preterida por outra opção.
5. Decisão inconclusiva por lacuna, leitura ilegível ou variável oculta.

Aprender cooldowns efetivos, compartilhamento de grupos, desempate e influência de runas/hotkeys. Comparar hipóteses de seleção com a sequência real e guardar erros, inclusive quando a regra normativa não reproduz o cliente. Não transformar intervalo entre casts em cooldown: ausência de alvo, disputa ou movimento também alongam esse intervalo.

A conclusão desejada deve apontar quais opções ocupam os turnos da Terra Wave, em quais condições, por quanto tempo e com quais quadros de prova. Se não houver evidência suficiente para uma condição específica, explicitar essa condição desconhecida em vez de assumir elegibilidade completa.

## Busca de sugestões a planejar

Buscar conjuntamente composição, ordem/prioridade e mínimos de criaturas: mais ou menos magias, uma ou duas forks, waves selecionadas, com ou sem runa, runa como apoio e UE condicional. Respeitar desbloqueios, nível, roda efetivamente conhecida e campos realmente existentes no cliente.

Comparar aproveitamento de turnos, ativações, dano associado/previsto com sua incerteza, consumo e restrições de recursos. Fazer uma magia sair não comprova aumento do rendimento. Uma composição menor pode superar uma maior; a busca não deve conservar automaticamente todos os papéis apenas para preencher slots quando a validação indicar saturação ou redundância.

Separar treino e validação cronologicamente dentro de fases estáveis. Primeiro reproduzir a rotação atual em trecho posterior reservado; depois avaliar candidatas em replay. Replay de uma candidata é previsão, não melhoria comprovada. Confirmar ganhos em outra fase/hunt comparável, sem atribuir alterações de monstros, andar ou levas ao ajuste do RTC.

No máximo dois ajustes por entrega, para a próxima hunt, com números e objetivo verificável. A proposta anterior de mover Terra Wave acima de Forked Thorns foi apenas um teste hipotético; não é a combinação vencedora nem uma melhoria aprovada.

## Limites atuais e critérios para o futuro planejamento

- Hoje o analyser lê campos e casts e possui simulação temporal, mas não cruza todas essas fontes para explicar conclusivamente cada disputa.
- Não afirmar aprendizado pessoal aprovado, execução integral conhecida ou ganho de dano sem validação correspondente.
- Reutilizar provas e consumidores existentes; preservar histórico, configurações e aprendizado. Respeitar retenção de quadros necessários a consumidores pendentes.
- Mudanças de comportamento precisam de testes, documentação e harness completo/autoteste compilado antes de atualizar a instalação; não gerar Setup.exe sem pedido.
- Planejar aceites que distingam cooldown observado, elegibilidade comprovada, magia preterida e lacuna. Incluir replay de saturação, configuração que muda no meio da volta, prioridades iguais, competição com runa, deduplicação e fontes ilegíveis.
- Produzir explicação acessível na UI: por que cada opção entra na composição, quais oportunidades recebe e qual evidência sustenta a recomendação.

## Localização das provas da sessão

- Captura e fronteiras de voltas: `C:/Users/User/AppData/Local/HuntAnalyzer/capture/session_20261012_142757/`, especialmente `laps.jsonl`, `trilha.jsonl` e quadros existentes.
- Eventos próprios e cobertura: `C:/Users/User/AppData/Local/HuntAnalyzer/configuracoes_player/ad638a20075ee080a826f5b3/execucao/session_20261012_142757/observacao/`, especialmente `eventos.jsonl` e `posicao.json`.
- RTC fotografado: `C:/Users/User/AppData/Local/HuntAnalyzer/configuracoes_player/ad638a20075ee080a826f5b3/1791828702983166900_rtc.png` e seu JSON.

Os caminhos apontam para dados pessoais locais e não devem ser publicados com os arquivos. Esta consolidação não altera esses dados nem o cliente.
