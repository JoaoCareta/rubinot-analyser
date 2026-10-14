# Plano de aprendizado e confirmação de uso do RTC

**Execução autorizada e retomada em 12/10/2026:** implementação técnica, limites de observabilidade e evidências de verificação/instalação estão no [relatório da implementação](rtc-aprendizado-implementacao-20261012.md). O texto abaixo preserva os critérios do plano; testes de software não substituem benefício pessoal em hunts posteriores.

Planejamento de 12/10/2026. O próximo avanço é ligar a confirmação do usuário à configuração efetivamente detectada na calibração e usar essa configuração para explicar e melhorar ataque, runas, autocura e cura da party. O aprendizado deve primeiro reproduzir a execução atual; depois comparar alternativas e verificar o resultado em hunts posteriores.

Este plano complementa os [insights da execução](rtc-aprendizado-insights-20261012.md) e o [plano de aprendizado integral](../output/planejamento/rtc-roda/plano-aprendizado-hunt-rtc-roda.md). O escopo desta entrega é planejamento. As etapas abaixo ainda precisam ser implementadas e validadas.

## Resultado esperado para o usuário

Na calibração, o programa mostra o personagem, a configuração detectada, o horário da leitura e os campos que conseguiu reconhecer. A confirmação de uso nasce dessa leitura. O usuário pode confirmar o conjunto detectado ou informar que não o está usando. Confirmar o RTC também apresenta a Cura correspondente, mantendo explícito quando essa aba ainda não foi lida.

O sistema aprende tanto com uma configuração própria do usuário quanto com uma sugestão adotada. Concordância com a sugestão é uma informação separada. A sugestão continua pronta desde o início; dados insuficientes limitam a personalização, sem retirar os valores iniciais recomendados.

As recomendações mostram uma justificativa curta, os números disponíveis e até dois ajustes para a próxima hunt. A investigação detalhada dos turnos permanece interna, com provas consultáveis na calibração. Não acrescentar painel de treinamento, sequência visual de turnos ou alertas novos.

## Base existente e mudanças necessárias

O diagnóstico considera as fontes presentes no workspace, incluindo alterações locais já existentes. Não certifica a versão instalada.

| Base atual | Mudança planejada |
|---|---|
| `configuracao_combate/estado.py` guarda leituras, provas e campos parciais | Acrescentar declaração de uso vinculada às revisões observadas e ao intervalo de vigência |
| `confirmar(char, ident)` confirma o ID da sugestão e grava `aplicado_lido: False` | Distinguir confirmar uso de uma leitura e declarar adoção de uma sugestão |
| `ui/features/planejamento/painel.js` só oferece confirmação após calcular RTC e roda | Levar a ação à calibração, independente de haver sugestão ou roda calculada |
| Snapshots começam com `aplicado_confirmado: False`; `Registro.fase` depende desse campo | Resolver vigência e elegibilidade por componente sem transformar declaração em leitura de aplicação |
| `observacao/execucao.py` exige RTC, Cura e Roda aplicados para atualizar parte dos modelos | Substituir o bloqueio global por dependências explícitas de cada aprendizado |
| `planejamento/modelos.py` aprende intervalos entre casts; `ui/integracao.js` pode usá-los como `cd` | Separar cadência observada, cooldown visual, espera por condições e disputa; não promover intervalo entre casts a cooldown |
| O monitor de configurações consome `q_`/`f_`; recursos da execução ainda recebem `f_` | Medir a cadência real por fonte e compartilhar os quadros necessários com os novos leitores |
| Há registro SQLite, fases, cobertura, replay de cura e busca RTC/roda | Evoluir esses componentes, preservando fachadas, APIs, histórico e modelos anteriores |

## Confirmação baseada na calibração

### Fluxo de uso

1. Reconhecer automaticamente a aba ativa e o personagem. A barra compartilhada com os nomes Cura e RTCaster não basta para identificar a aba.
2. Mostrar a leitura com magias, runas, ordem, prioridades, mana, criaturas e opções do RTC. Mostrar autocura e destinatários/percentuais da Cura em bloco próprio. Cada campo tem origem, horário e qualidade.
3. Oferecer **Estou usando o que foi detectado** e **Não estou usando esta configuração**. Sem leitura do RTC, mostrar **Abra o RTC para identificar a configuração** e manter a coleta geral.
4. Ao confirmar, vincular a resposta ao conteúdo exato apresentado e ao personagem/sessão. Uma atualização concorrente da leitura exige reapresentar o conteúdo antes de aceitar a confirmação.
5. Na resposta negativa, distinguir **Uso outro RTC** de **RTC desligado**. Não usar a mesma negativa para significar rejeição da sugestão, leitura incorreta e ausência de RTC.
6. Em Magias e elementos, exibir o estado vindo da calibração e o acesso **Conferir configuração detectada**. Evitar uma segunda confirmação independente do mesmo fato.

Quando a leitura for parcial, a ação declara o uso da configuração mostrada, com a lista das lacunas visível. A confirmação não preenche os campos ausentes. Cura e Roda só ficam confirmadas se suas revisões também foram apresentadas e incluídas explicitamente na resposta. A falta de leitura de Cura não bloqueia a declaração sobre o RTC ofensivo.

### Estados que precisam continuar separados

| Dimensão | Estados previstos | Consequência |
|---|---|---|
| Leitura | Não detectado, parcial, suficiente para determinado uso | Diz o que a tela permite conhecer |
| Declaração | Sem resposta, uso confirmado, uso negado, RTC desligado informado | Registra a resposta do usuário |
| Concordância | Confere, diverge, inconclusiva | Compara observado e sugerido, por componente |
| Execução | Compatível, divergente, inconclusiva | Compara previsões com lançamentos e condições observáveis |
| Aprendizado | Coletando, candidato, validado no escopo, benefício posterior observado | Determina o que pode influenciar recomendações |

Não detectar o editor não significa RTC desligado. Fechar o editor não comprova aplicação. Identificar um cast não comprova que foi disparado pelo RTC, pois pode haver hotkey manual. A confirmação é evidência declarada de uso; detecção e execução conservam suas origens próprias.

Uma configuração diferente da sugerida pode ser confirmada e usada como referência de aprendizado. Uma sugestão recalculada não invalida o fato histórico de que o usuário confirmou outra configuração; apenas muda sua concordância com a nova proposta.

### Identidade e validade temporal

- Separar a identidade do conteúdo da identidade de cada observação. O conteúdo inclui slots vazios, opções, valores, destinatários e campos desconhecidos; timestamps e caminho da prova não criam uma nova configuração.
- Guardar `capturado_em`, `processado_em`, `visto_por_ultimo_em` e `confirmado_em`. Reprocessar um quadro antigo não produz uma leitura atual.
- Atualizar a última observação mesmo quando o conteúdo não muda; manter as provas originais e o início da configuração.
- A confirmação vale a partir do momento da resposta, por padrão. Uma declaração posterior sobre horário anterior fica registrada como relato, sem rotular retroativamente toda a hunt como comprovada.
- Calibração anterior à hunt pode ser referência. Para uso na sessão seguinte, revalidar a associação à sessão e apresentar uma confirmação simples; não transportar automaticamente o intervalo anterior.
- Mudança comprovada em campo relevante, personagem, preset ou declaração de uso abre nova fase. Ler novamente o mesmo conteúdo não abre fase nem repete perguntas.
- Se uma alteração só for descoberta depois, guardar a fronteira como intervalo entre a última evidência compatível e a primeira divergente. Esse trecho fica inconclusivo. Uma leitura perdida não significa alteração, mas sua ausência limita a continuidade que pode ser afirmada.
- Voltas que atravessam mudança ficam mistas. Preservar totais originais; não ratear XP, profit ou supplies. Eventos com horário conhecido podem ser analisados nos respectivos trechos.
- Correções e revogações acrescentam registros. Reprocessamentos geram uma interpretação versionada, preservando fatos e associações anteriores para auditoria.

## Contratos e limites de aprendizado

Os nomes abaixo são contratos propostos; a implementação pode adaptar a forma ao armazenamento existente sem mudar sua semântica.

| Registro | Conteúdo mínimo |
|---|---|
| Leitura de configuração | Personagem, sessão, tipo, revisão, assinatura do conteúdo, prova, tempos de captura/processamento, campos e qualidade por campo |
| Declaração de uso | Resposta, personagem/sessão, revisões incluídas, instante, início declarado, origem, revisão substituída e ID opcional da sugestão |
| Fase efetiva | Revisões por componente, intervalo de vigência ou fronteira incerta, declaração, contexto de hunt e versões das regras/leitores |
| Oportunidade de ação | Intervalo temporal, relógios de ataque/cura, candidatos, condições conhecidas/desconhecidas, escolha observada e provas |
| Exemplo de aprendizado | Fase, fontes, alvo ou membro, cobertura, variáveis conhecidas, rótulo permitido e motivo de inclusão/exclusão |
| Avaliação de modelo | Dados de treino/seleção/teste, versões, métricas, incerteza, domínio de uso, modelo anterior e motivo de promoção/rejeição |

`null`, campo inaplicável e slot vazio confirmado precisam ser distintos. Por exemplo, não exigir um campo de criaturas inexistente para a runa single nem convertê-lo em zero. Também conferir opções, slots extras e itens removidos: a igualdade das linhas sugeridas isoladamente não garante igualdade da composição inteira.

### Dependências por tipo de aprendizado

| Aprendizado | Evidência necessária | Com lacunas |
|---|---|---|
| Frequência e intervalos observados | Cast próprio identificado, tempo e cobertura da fonte | Guardar contagens positivas e cadência parcial; não atribuir origem automática |
| Disputa e seleção do RTC | RTC detectado e uso confirmado, opções relevantes, condições/cooldowns/competidores no intervalo | Investigar hipóteses; marcar decisão inconclusiva onde faltar condição |
| Cooldown efetivo | Transições visuais de prontidão, execução associável e contexto compatível | Intervalos entre casts continuam descritivos; não substituem cooldown |
| Percentuais de cura | Cura detectada e confirmada, identidade do destino, HP/cura e relógios com resolução suficiente | Manter sugestão inicial; não aprender HP máximo pelo percentual nem segurança por ausência de morte |
| Efeitos da roda e gemas | Efeito relevante conhecido e vigente, requisitos ativos e configuração comparável | Não atribuir ganho à casa/gema desconhecida nem transferir coeficientes entre estágios |
| Resultado da sugestão adotada | Concordância da alteração avaliada, fase estável e sessões posteriores comparáveis | Descrever associação ou resultado misto; não declarar ganho comprovado |

Uma roda incompleta permite descrever casts e investigar seleção quando as condições necessárias forem conhecidas. Se a lacuna afeta cooldown, potência ou proteção da ação avaliada, aquele aprendizado continua limitado. Confirmar RTC sozinho não libera automaticamente todos os modelos.

## Observação sincronizada e explicação dos turnos

Reutilizar a captura existente. Primeiro medir intervalo entre quadros, precisão dos horários, latência de leitura, perda e legibilidade de cada fonte. O intervalo de um segundo do monitor não prova resolução suficiente para reconstruir cada decisão. Recursos espaçados em quatro segundos não descrevem todos os picos de cura.

| Fonte | Informação a extrair | Limite |
|---|---|---|
| Editor RTC e Cura | Composição, valores, opções, destinatários | Configuração visível não prova mecanismo interno nem aplicação |
| Barra inferior | Ícone, prontidão, contagem regressiva, transição após uso e quantidade de runas | Um quadro isolado não reconstitui turnos; alteração de quantidade pode ter outras causas |
| Spells e fala do personagem | Identidade e tempo do lançamento próprio | Deduplicar o mesmo cast entre fontes, preservando casts distintos próximos |
| Recursos e Battle List | Mana, HP e população visível | População não comprova alcance, orientação ou alvos atingidos |
| Console de dano e cura | Efeitos associáveis e valores observados | Ambiguidade permanece; não fabricar total por magia |
| Supplies e consumo por item | Gasto pessoal/coletivo e quantidade de potions por tipo quando legível | Gold agregado não identifica quantidade nem tipo de potion |
| Contexto da hunt | Andar, composição, levas, party, postura e pausas | Mudanças de contexto não são efeito automático do RTC |

Para cada oportunidade, classificar cada candidata: condição de mana/criaturas/vida não atendida; cooldown individual ou de grupo bloqueado; geometria incompatível quando verificável; elegível e preterida; escolhida; ou inconclusiva. Registrar as condições individualmente, permitindo múltiplos bloqueios.

Comparar hipóteses de prioridades entre magias e runas, desempate, combo em ordem e interferência de hotkey. Quando hipóteses produzirem a mesma sequência, manter a ambiguidade. Não forçar uma conclusão pela posição do slot. Não tratar ataque e cura como relógios independentes ou compartilhados por conveniência: aplicar os grupos normativos e os vínculos comprovados.

O diagnóstico da Terra Wave deve indicar quem ocupou as oportunidades, sob quais condições e com quais provas. Três voltas completas com configuração estável permitem registrar ausência de uso observado; a investigação começa antes desse limiar. Cobertura temporal e legibilidade dos casts são medidas diferentes.

Se a cadência atual for insuficiente, propor recortes mais frequentes no produtor compartilhado, após medir custo. Não iniciar captura duplicada. Leitores novos devem registrar seus consumidores e preservar quadros pendentes; provas selecionadas ficam fora da limpeza transitória.

## Reconhecimento de hunts tranquilas e pressionadas

Ampliação solicitada em 12/10: reconhecer a pressão pela profundidade e frequência das quedas de vida, duração do Utamo, proporção do tempo com e sem escudo e consumo de potions de mana por minuto. A classificação deve orientar o aprendizado de ataque, cura e roda, por personagem e contexto, preservando os episódios que a média da hunt esconderia.

Separar três dimensões: **pressão recebida**, **esforço para sustentar a hunt** e **risco observado**. Vida alta com muita cura e renovação de escudo pode caracterizar pressão controlada. Vida baixa isolada pode ser um episódio pontual. Tempo sem Utamo só é indicador de exposição quando relacionado à estratégia em uso e ao combate; jogar de Vida não constitui falha de proteção.

### Sinais de vida e recuperação

| Sinal | Medida planejada | Interpretação |
|---|---|---|
| Profundidade | Menor percentual observado e distribuição da vida ao longo do tempo | O mínimo lido não garante capturar o menor valor real entre quadros |
| Frequência | Episódios de queda por minuto de combate observável, por profundidade e amplitude | Um episódio contínuo conta uma vez, não uma vez por quadro |
| Persistência | Tempo e proporção abaixo de faixas de vida | Distinguir um susto rápido de permanência prolongada com pouca margem |
| Velocidade de queda | Pontos percentuais perdidos por segundo no intervalo observado | Medida líquida entre leituras; dano recebido e cura simultânea exigem fontes próprias |
| Recuperação | Tempo até recuperar uma faixa estável e novas quedas antes da recuperação | Recuperação lenta ou incompleta indica pouca folga |
| Sustentação | Curas/minuto, cura útil atribuível, cura externa e uso de recursos de emergência | Frequência alta não prova necessidade; cruzar com vida faltante e condições |
| Saúde da party | Mesmas medidas por integrante identificado e crises simultâneas | Personagem estável não prova que EK/RP ou toda a party estão estáveis |

Como faixas descritivas iniciais para estudo, comparar tempo abaixo de 70%, 50% e 30% de vida; esses valores são propostas de análise, não limiares universais de segurança nem sugestões de cura. Calibrar e versionar faixas, amplitude mínima de queda, recuperação e exposição necessária por contexto antes da validação final.

Detectar o início de um episódio pelo cruzamento de faixa ou queda relevante; encerrá-lo após recuperação sustentada com uma margem que evite contar oscilações do leitor como novas crises. Um episódio pode alcançar várias faixas, mas não multiplica a contagem total. Episódios já em curso no início, cortados por lacuna ou sem recuperação observada ficam marcados como incompletos.

### Sinais do Utamo Vita

| Sinal | Medida planejada | Interpretação |
|---|---|---|
| Presença do escudo | Tempo com escudo, sem escudo e desconhecido | Ícone não localizado em região ilegível não prova ausência |
| Cobertura em combate | `100 × tempo com escudo / tempo com estado conhecido`, no mesmo recorte de combate | Informar também a cobertura da leitura sobre o combate total; lacunas não entram como tempo protegido ou exposto |
| Duração de cada ativação | Intervalo entre ativação identificada e desaparecimento verificado | Escudo já ativo no começo tem idade desconhecida; não contar como ativação nova |
| Resistência dentro da box | Tempo entre entrada na box e desaparecimento | É tempo restante dentro da box, diferente da duração total desde o cast |
| Frequência de perdas | Perdas observadas por minuto de combate e por minuto protegido | Preservar denominadores; não confundir com frequência de avisos sonoros |
| Renovação | Tempo sem escudo até reaparecer e frequência de recasts | Cruzar com prontidão e uso observado; não presumir atraso voluntário nem cooldown |
| Exposição com perigo | Tempo sem escudo enquanto recebe dano, vida cai ou há pressão verificável | Chegar sem escudo a uma box e ficar sem escudo entre levas têm significados diferentes |

Separar perda do ícone, esgotamento, expiração e remoção voluntária quando houver evidência; causa não identificável fica desconhecida. Dano no HP sozinho não prova queda do Utamo. Uma recarga que renova o escudo sem intervalo visível exige cast ou outra transição identificada, sem inventar uma quebra entre quadros.

Ao comparar durações, incluir ativações que terminam ainda protegidas como durações mínimas conhecidas. Calcular a média apenas das ativações que quebraram enviesaria o resultado para escudos curtos. Guardar limites temporais das transições e distinguir duração de efeito, duração sob combate e tempo na box.

### Potions de mana e supplies

A leitura de supplies existente será reutilizada. No fluxo conferido em `pt_card.py` e nas métricas canônicas, `supplies_eu`/`supplies_pt` representam o gasto agregado lido nos painéis; isso não certifica uma contagem por tipo de potion. A implementação deve conferir os campos disponíveis no leitor e nas provas e acrescentar leitura por item somente onde ainda faltar.

| Indicador | Cálculo ou fonte | Uso |
|---|---|---|
| Potions de mana por minuto | `60 × quantidade consumida / duração em segundos`, por tipo, em intervalos válidos | Quantificar a intensidade de reposição |
| Consumo recente e por volta | Deltas das contagens acumuladas por item em janelas com limites conhecidos | Comparar picos e tendência sem diluí-los na média de toda a hunt |
| Gasto pessoal e da party | Deltas já lidos de supplies e suas taxas canônicas | Contexto econômico separado da contagem de itens |
| Reserva de mana | Mínimo observado, tempo em faixas baixas e velocidade de recuperação | Identificar consumo alto que mantém reserva ou que não consegue repô-la |
| Interferência na execução | Oportunidades com mana insuficiente para atacar, curar ou renovar proteção, quando verificáveis | Diferenciar custo alto de limitação efetiva da build |
| Eficiência comparável | Potions por criatura abatida ou pelo resultado medido no mesmo intervalo | Comparar configurações sem atribuir todo aumento de consumo à pressão |

Priorizar contador de uso por item no Supply Analyser quando disponível e legível. Preservar personagem, identidade do item, unidade, valor acumulado, instante, sessão/reset do painel e prova. Diferenciar mana, vida e potions híbridas; somar famílias apenas com definição explícita e listar sua composição. Tipos diferentes não representam necessariamente a mesma reposição por unidade.

Não dividir supplies em gold por um preço suposto para inventar potions/minuto. Contagem de inventário/barra é fonte secundária: reposição, movimentação e troca de pilha podem alterar a quantidade sem uso. Não duplicar consumo observado em contador e inventário.

Usar o tempo exato correspondente ao delta. Se duas leituras delimitarem cinco minutos, esse consumo pertence aos cinco minutos; não dividi-lo apenas pelos segundos em que o painel ficou visível nem distribuí-lo por picos internos desconhecidos. Só calcular consumo por minuto de combate quando for possível separar o consumo dentro e fora dele. Em todos os casos, rotular o denominador e a resolução temporal.

Reset, contador negativo, troca de personagem/item ou leitura incompatível abrem nova série. Contador igual só comprova zero uso daquele item no intervalo quando sua validade e continuidade estiverem estabelecidas. Sem resolução para uma janela curta, a taxa curta fica indisponível, mantendo a agregada comprovável. Não confundir refill com consumo negativo.

**Interpretação conjunta:** mais potions com mana estável, ataques frequentes e vida segura pode refletir ritmo ofensivo maior. Mais potions com mana baixa, recasts de Utamo e quedas recorrentes de vida reforça a hipótese de pressão com pouca margem. São hipóteses a validar, não regras causais baseadas somente em consumo.

### Classificação por trecho e pela hunt

| Estado proposto | Evidência esperada |
|---|---|
| Tranquila | Boa cobertura, vida com margem, recuperação consistente e esforço de sustentação baixo para aquele contexto |
| Pressionada mas controlada | Proteção/cura/reposição frequentes mantêm vida e mana com margem, apesar da pressão |
| Pressionada com pouca margem | Quedas profundas ou repetidas, recuperação lenta, exposição relevante sem proteção ou reserva insuficiente, conforme estratégia |
| Inconclusiva | Cobertura, duração ou contexto insuficientes para sustentar a classificação |

A hunt pode ser mista: conservar proporção do tempo classificável, trechos desconhecidos, pior episódio e diferenças por box/andar/volta. Não reduzir tudo a uma média nem esconder pressão sobre um membro. Sem leitura da party, limitar a conclusão ao personagem observado. Pausas, house, refill e deslocamento sem combate não devem diluir a pressão dos combates; deslocamento com dano continua elegível.

Comparar por personagem, solo/PT, objetivo, composição/andar, tamanho das levas, postura e configuração conhecida. Uma referência pessoal frequente não torna segura uma situação cronicamente perigosa: a comparação histórica complementa os critérios absolutos de risco. Usar estabilidade na transição de estados para evitar alternância causada por ruído, preservando episódios graves identificados.

Começar com regras explicáveis e calibradas nos replays; evoluir modelos somente quando melhorarem a avaliação em períodos posteriores. Não gerar rótulos com uma regra e depois apresentar a reprodução desses mesmos rótulos como validação independente. Avaliar contra episódios/provas reservados e resultados posteriores, com atenção especial a falsos diagnósticos de tranquilidade.

### Integração com o aprendizado existente

`planejamento/avaliacao.py` já calcula mínimo observado, cobertura e episódios por membro. `assistencia/utamo.py` já localiza o ícone e reúne medidas por box; `observacao/execucao.py` já consulta os leitores de recursos. Reutilizar essas evidências, evoluindo o contrato para presença/ausência/desconhecido e qualidade por fonte. A coleta para aprendizado deve funcionar mesmo com alertas desligados e não pode herdar supressões ou períodos de silêncio dos apitos.

Persistir episódios e avaliações versionadas com fase, intervalos, motivos, numeradores/denominadores, qualidade e provas. As medidas canônicas de vida, escudo e consumo ficam em `rubinot.hunt.metricas`, com espelho em `ui/taxas.js` e paridade; `planejamento/avaliacao.py` interpreta pressão e risco por política versionada. O restante da interface apenas apresenta os resultados pertinentes.

A pressão observada pode ser descrita sem confirmação do RTC. Atribuir a mudança de pressão a uma configuração exige a confirmação e os critérios de comparação do plano. Usar a classificação para avaliar dano sustentável, percentuais de cura e proteção na próxima hunt, sem reduzir cura automaticamente porque o trecho foi classificado como tranquilo. Mostrar apenas a justificativa curta das sugestões; manter a análise detalhada interna e sem novos apitos.

## Efetividade de cada atributo e ajuste sugerido

Ampliação solicitada em 12/10: avaliar granularmente se cada benefício sugerido valeu a pena na configuração adotada, considerando o foco escolhido pelo usuário. Mana Leech é um exemplo desse contrato geral, que também inclui Life Leech, modificadores de cura/dano, cooldowns, proteção, gemas, estágios e campos do RTC.

### Vincular intenção aplicação e resultado

Para cada recomendação, registrar o objetivo escolhido, a configuração de referência, o campo alterado e seu valor anterior/novo, benefício esperado, condições de ativação, custo de pontos/caminho e alternativa preterida. Guardar a versão da previsão antes da adoção; não reescrever a expectativa depois de conhecer o resultado.

A calibração precisa identificar o que foi efetivamente adotado. Selecionar foco Dano ou Cura não comprova aplicação da roda. Preservar objetivo declarado, sugestão e leitura como informações separadas; objetivo desconhecido permanece desconhecido. Uma adoção parcial avalia apenas as alterações conhecidas, sem atribuir o resultado à proposta inteira.

Cada avaliação vincula a mudança aos intervalos de uso confirmado, contexto, doses/estágios conhecidos, métricas esperadas e observadas, cobertura, incerteza e efeitos adversos. Manter chance, quantidade e condições de um efeito como campos separados quando existirem no catálogo. Um ponto adicional, uma casa completa e a ativação de um estágio são mudanças distintas.

### Medidas adequadas a cada benefício

| Atributo ou ajuste | Efeito direto a verificar quando observável | Resultado prático a comparar |
|---|---|---|
| Mana Leech | Recuperação de mana atribuível ao efeito e oportunidades de ativação | Potions de mana/minuto por tipo, reserva de mana, oportunidades perdidas por falta de mana e custo pessoal |
| Life Leech | Recuperação de HP atribuível ao efeito e parcela útil quando mensurável | Profundidade/frequência das quedas, recuperação, tempo com pouca vida, necessidade observada de autocura e potions de vida |
| Cura base e efeitos condicionais | Cura útil por execução, condições ativas, frequência e destinatários | Recuperação e risco por membro, consumo e capacidade de sustentar a party |
| Healing Link e efeitos de cura combinados | Contribuição associável ao personagem e aos aliados, sem dupla contagem | Autocura necessária, margem de vida e custo total da sustentação |
| Dano, crítico e bônus de magia | Dano e ativações observados no mesmo contexto, com cobertura | Ritmo de abates, duração das levas, raw, consumo e pressão resultante |
| Cooldown, prioridades e criaturas | Oportunidades úteis, espera, ações preteridas e frequência | Dano/cura sustentáveis e custo; liberar uma magia não comprova melhoria |
| Proteção, vida/mana máximas e Utamo | Efeito ativo, duração/exposição e recursos conhecidos | Episódios de risco, capacidade de recuperação e consumo para manter a proteção |
| Gemas, estágios e distribuição de pontos | Requisitos satisfeitos, efeitos ativos e caminho investido | Benefício marginal do pacote frente à melhor alternativa viável testada |

Somar apenas efeitos identificáveis. Uma subida da barra de mana/vida pode combinar potion, regeneração, leech, cura própria ou externa. Sem evidência para separar as fontes, registrar recuperação total e avaliar o resultado agregado da configuração; não inventar procs, recuperação por efeito ou economia diretamente causada por uma perk. HP cheio pode limitar a cura útil observada; mana cheia pode limitar a recuperação útil observável. Distinguir ausência de oportunidade de ausência de eficácia.

### Uso e impacto dos bônus de cada magia

O usuário também pediu avaliar quantas vezes uma magia beneficiada pela roda foi executada, quantas dessas execuções aproveitaram o bônus e qual foi seu impacto. Aplicar a Terra Hur, Frigo Hur, forks, mas res, sio/gran sio e demais magias elegíveis, com suas identidades normalizadas no catálogo. Não limitar a análise aos exemplos citados.

Manter um registro por magia, benefício e fase de configuração, separando estas medidas:

| Medida | Significado |
|---|---|
| Lançamentos identificados | Quantas execuções próprias foram reconhecidas, frequência no tempo observável e fontes/provas |
| Oportunidades do benefício | Em quantos usos seus requisitos estavam comprovadamente atendidos, não atendidos ou desconhecidos |
| Usos beneficiados | Quantas execuções receberam um bônus passivo comprovadamente vigente ou tiveram ativação condicional identificada |
| Efeito associado | Dano/cura e destinatários associáveis aos usos, com cobertura e ambiguidade preservadas |
| Contribuição incremental estimada | Diferença prevista com e sem o benefício sob as mesmas condições conhecidas, identificada como estimativa |
| Impacto no período | Contribuição acumulada estimável, mudança de frequência, consumo, duração das levas e risco |
| Valor do investimento | Benefício marginal frente ao custo de pontos/caminho e às alternativas viáveis no foco escolhido |

Um bônus passivo não exige um proc visual a cada cast: sua aplicação pode ser derivada da regra versionada, configuração vigente e elegibilidade conhecida, com origem explicitamente derivada. Um efeito condicional ou probabilístico exige suas próprias condições/evidências; não multiplicar todos os casts pelo bônus como se ele tivesse ativado sempre. Registrar elegibilidade e ativação separadamente.

Percentual nominal não basta para ranquear investimentos. Um bônus maior numa magia pouco utilizada pode contribuir menos que um bônus menor numa magia frequente. Para efeitos comparáveis de potência, estimar a contribuição somando o incremento dos usos elegíveis no período, respeitando base, resistências, modificadores conhecidos e alvos efetivamente sustentados pela evidência. Não aplicar automaticamente a fórmula percentual ao dano total quando a regra afeta somente a base ou interage com outros bônus.

Para efeitos em cooldown, alcance ou área, reavaliar oportunidades e alvos; não convertê-los em um percentual de dano por conveniência. Em cura, medir incremento útil limitado pela vida faltante e separar os destinos; bônus em mas res não multiplica casts pelo número de aliados. Sio e gran sio podem ter efeitos indiretos de proteção/autocura, preservando a atribuição e evitando somar o mesmo HP duas vezes.

O dano/cura total associado a uma magia não é o ganho causado pela perk. Distinguir o valor observado com bônus da diferença que seria esperada sem ele. Quando a observação não separar base, bônus, crítico ou outras fontes, conservar a contribuição como estimativa ou inconclusiva. Validar diferenças por contrastes compatíveis posteriores e considerar custo de oportunidade.

Se Terra Hur não tiver lançamentos identificados, o sistema deve investigar a disputa e a cobertura antes de concluir que seu bônus ficou sem uso. Zero execuções comprovável no recorte implica zero contribuição direta por execução nesse recorte; ausência de leitura implica desconhecimento. Isso não condena universalmente a magia: ela pode ser recurso condicional ou tornar-se relevante em uma candidata que altere composição/prioridades. A busca precisa recalcular frequência e benefício para essa candidata, preservando a frequência observada da configuração atual como fato separado.

Guardar `magia_id`, `beneficio_id`, estágio/valor, revisão e fase, casts identificados, usos elegíveis/inelegíveis/desconhecidos, ativações identificadas ou aplicações derivadas, efeito associado, contribuição estimada, duração, cobertura e provas. Alvos desconhecidos não viram um alvo fixo nem a população inteira da Battle List. Treino aproveita apenas os rótulos suportados; o restante continua útil como evidência parcial.

Nas sugestões, ponderar o ganho marginal pelo uso esperado no RTC candidato e pelo objetivo Dano/Cura, com validação em dados posteriores. O sistema deve conseguir justificar que um investimento foi mantido por uso frequente e contribuição sustentada, foi substituído por baixo aproveitamento comprovado ou permanece inconclusivo. Não usar apenas a porcentagem escrita na roda ou apenas a contagem de casts para escolher o vencedor.

### Exemplo de avaliação de Mana Leech

A pergunta será: com a alteração detectada e confirmada, houve redução de potions, melhoria da reserva de mana ou mais produção sustentável que compensasse o investimento?

Comparar potions/minuto por tipo e economia absoluta/relativa usando intervalos válidos. Custo em gold só entra quando houver atribuição por item/preço ou gasto diretamente medido; manter supplies total separado quando misturar runas e outros consumíveis. Uma redução percentual usa a referência anterior como denominador; referência zero impede essa divisão.

Mesmo consumo com mais dano e mana estável pode representar benefício. Menor consumo com menos ataques, levas menores ou pausas maiores não demonstra benefício do Mana Leech. Maior reserva sem economia de potions pode indicar margem adicional ou um limiar de potion que permaneceu alto. Registrar essas possibilidades e testar a hipótese em dados posteriores; não prometer economia automática nem mudar os limiares de potion sem leitura e campo configurável conhecido.

Para Life Leech, aplicar o mesmo raciocínio com HP e cura: não exigir redução de potions de vida quando o personagem nem as usa, nem concluir benefício só por HP alto. Considerar pressão, cura externa, oportunidades de dano e cura útil. O investimento pode melhorar sobrevivência, liberar oportunidades de ação ou ser redundante naquele contexto.

### Comparação e atribuição por campo

Comparar fases/hunts semelhantes em personagem, regras, área, composição, party, estratégia e condições iniciais, com exposição suficiente. Conservar dano, pressão, vida e consumo posteriores como resultados e possíveis mecanismos da mudança; filtrar apenas trechos que ficaram tranquilos depois da alteração eliminaria justamente parte do efeito a avaliar.

Quando várias alterações forem adotadas juntas, a conclusão inicial pertence ao conjunto. Não repartir arbitrariamente a economia entre Mana Leech, Life Leech, dano e cura, nem somar ganhos individuais como se fossem independentes. Para identificar contribuição isolada, aproveitar contrastes posteriores que variem aquele campo mantendo os demais comparáveis. Comparações simuladas que retiram um benefício ajudam a formular hipóteses, mas não comprovam seu ganho real.

Casas da roda exigem caminhos e redistribuições. Quando não existir contraste válido que altere só uma perk, registrar a unidade avaliada como pacote de investimentos e explicitar a limitação da conclusão por campo. Aumentos de dano podem mudar tanto o leech quanto a duração da leva; essas interações pertencem ao modelo conjunto.

Experimentos futuros, se propostos, são sugestões para próximas hunts, com no máximo dois ajustes concretos, confirmação do usuário e critérios de segurança. Não retirar proteção essencial para obter um contraste nem alterar o cliente durante a hunt.

### Conclusões que alimentam as próximas sugestões

Separar **benefício relevante**, **benefício moderado**, **sem ganho relevante detectável**, **resultado misto ou piora** e **inconclusivo**. Definir margens práticas antes da avaliação conforme objetivo e variabilidade pessoal. Uma estimativa próxima de zero com grande incerteza é inconclusiva; só exposição suficiente e uma faixa de incerteza estreita permitem concluir ausência de ganho relevante naquele contexto. Nenhuma dessas categorias vale universalmente para a perk.

No foco Dano, avaliar produção sustentável com limites de segurança; no foco Cura, sustentação e risco por integrante, incluindo custo e manutenção do ataque. Economia não justifica automaticamente perder desempenho ou proteção: comparar o ganho com o benefício abandonado ao investir os mesmos pontos em outra alternativa válida.

Guardar perfis por atributo/estágio e contexto, incluindo resultados negativos e inconclusivos. Atualizar o peso das alternativas somente após validação temporal pertinente, preservando versões anteriores. Uma perk sem oportunidade de ativação não recebe rótulo universal de inútil. A busca consulta os perfis para recomendar, manter ou substituir investimentos, apresentando até dois ajustes com justificativa curta e números; não cria um painel de treinamento adicional.

Estender os contratos de recomendação e avaliação com `alteracoes`, `objetivo_declarado`, `expectativa`, `adocao`, `unidade_avaliada`, `efeitos_observados`, `resultados`, `incerteza` e `limites_atribuicao`. O registro persistente guarda as ligações; regras puras de avaliação calculam a conclusão; modelos aprendem apenas no escopo suportado. Esse fechamento entre sugestão e resultado faz parte da etapa 8.

## Aprendizado e busca de sugestões

### Aprender o funcionamento antes de escolher alternativas

1. Manter o catálogo vigente do Global como referência versionada, com fontes por regra; RubinOT usa essas mesmas regras. Observação pessoal não sobrescreve silenciosamente a base normativa.
2. Reproduzir a configuração confirmada em um trecho posterior ao treino. Comparar seleção por oportunidade, ativações por magia, prontidão e consumo associável, sempre com cobertura.
3. Comparar o modelo novo com regras simples e com o modelo anterior. Um erro menor no total de casts não basta se a sequência ou a competição continuar incompatível.
4. Treinar seleção, cadência e efeitos como problemas distintos. Separar exemplos de RTC confirmado, uso manual informado e origem indeterminada. O usuário negar uso do RTC não produz exemplos de falha do RTC.
5. Preservar modelo anterior e restringir cada perfil ao personagem, configuração, estágio, contexto e versão em que foi validado. Detectar mudanças persistentes e suspender apenas a personalização afetada.

### Buscar composição e execução em conjunto

Comparar subconjuntos válidos: mais ou menos magias, uma ou duas forks, waves selecionadas, UE condicional, com ou sem runa e runa de apoio. Buscar composição, ordem/prioridades e mínimos de criaturas conjuntamente. Respeitar cinco magias, duas runas, single único, desbloqueios e campos existentes. Mana ofensiva sugerida permanece em 5%; isso não se aplica aos percentuais de vida da cura.

O limite de criaturas equilibra oportunidades, ativações e potência; não serve para esconder uma magia que deveria ter sido retirada ou repriorizada. Uma configuração menor pode vencer. Essa possibilidade supera a conservação obrigatória de todos os papéis após validação; a configuração inicial pronta continua disponível quando faltam dados.

Considerar dano base, resistências, ativações úteis, consumo e incerteza de alvos. Para cura, considerar base, frequência, vida faltante, cura externa, cooldowns, autocura, sio/gran sio e mas res, evitando contar um cast múltiplas vezes pelo número de beneficiados. Só atribuir efeitos de Link, crítico, postura ou gemas quando conhecidos.

A roda atual é a semente. Candidatas de roda precisam de caminhos válidos, orçamento total menos três, estágio alcançável e bônus relevantes para o RTC candidato. Preservar controles independentes e reavaliar efeitos cruzados internamente. Comparar alternativas híbridas quando melhorarem sustentação e dano possível sem piorar a segurança.

Em PT tranquila, comparar dano mantendo margem de cura; em PT pressionada, cura/proteção e dano sustentável; em solo, abates, sobrevivência e consumo. Bestiary constitui contexto próprio. Nenhuma dessas classificações pode nascer apenas do total de cura ou da ausência de mortes.

### Validar sem reutilizar o teste para escolher a vencedora

Separar cronologicamente treino, seleção de hipóteses/candidatas e avaliação final. Agrupar episódios correlacionados; cópias da mesma sessão não são sessões independentes. O terço final usado hoje em partes do replay não pode escolher diversas candidatas e também certificá-las como teste intocado. Para ganho prático, reservar uma fase ou hunt posterior comparável.

Definir mínimos de exposição, tolerâncias de erro e margens de risco antes de abrir o conjunto final, usando precisão dos leitores e variabilidade histórica. Registrar também denominadores, duração observável e cobertura por membro. A calibração dessas margens é uma entrega da etapa de avaliação, sem inventar agora um percentual universal de melhoria.

Replay de composição alternativa é previsão: alterar dano também altera duração da leva e pressão. Apresentar sensibilidade e incerteza; verificar ganhos depois em contexto comparável. Mais raw ou dano não compensa automaticamente aumento de risco, mortes ou piora de um integrante.

A configuração atual, a recomendação inicial e a candidata são referências separadas. No máximo dois ajustes concretos por entrega, contados por alterações que o usuário precisa fazer; não embalar muitas trocas de campos como um único ajuste. Reavaliar o conjunto completo depois de selecionar o subconjunto de mudanças entregável.

## Etapas de implementação

| Etapa | Trabalho e componentes principais | Critério de conclusão |
|---|---|---|
| 1 | Contratos de leitura, declaração e vigência em `configuracao_combate`, `planejamento/registro.py` e `docs/contratos` | Estados separados; migração aditiva; legado não ganha confirmação retroativa |
| 2 | Confirmação na calibração, resumo em `ui/calibracoes_resumo.js`, `ui/configuracoes.html`, `ui/features/planejamento/painel.js` e API em `adapters/servidor.py` | Confirmar/negar leitura exata, inclusive parcial e diferente da sugestão; funcionar sem roda calculada |
| 3 | Resolver fases por declaração e revisão; elegibilidade por tarefa no observador e modelos | Uso confirmado alcança o aprendizado pertinente; mudanças, negativa e lacunas não contaminam outros intervalos |
| 4 | Medir cadência e integrar barra, fala, Spells, vida, Utamo, mana e consumo por item em `observacao`, `bootstrap/monitor.py` e produtor compartilhado quando necessário | Eventos deduplicados, horários de captura corretos, estados desconhecidos preservados, consumo com item/unidade e intervalos válidos; nenhuma segunda captura |
| 5 | Reconstruir oportunidades em regras de planejamento e adaptar `contexto_execucao.py`/`ui/temporal.js` | Explicar saturação ou apontar exatamente a variável desconhecida; não confundir intervalo com cooldown |
| 6 | Evoluir `planejamento/modelos.py`, métricas e avaliação de pressão/risco; validar previsão da configuração atual | Relatório reservado demonstra previsão, distinção entre pressão controlada e pouca margem, lacunas e paridade antes da busca personalizada |
| 7 | Busca conjunta e avaliação de cura em `ui/integracao.js`, `ui/rtc_worker.js` e motores existentes | Comparar subconjuntos, prioridades, criaturas e cura; ponderar bônus pelo uso elegível esperado de cada magia e pelo ganho marginal, com restrições de risco |
| 8 | Avaliação posterior por atributo/ajuste e pacote, justificativas curtas e integração da roda | Vincular objetivo, expectativa, adoção e resultado; avaliar benefício e custo de oportunidade sem atribuição artificial; entregar até dois ajustes e rastrear seu resultado |
| 9 | Documentação, harness, compilado e atualização local | Verificação completa da revisão, autoteste e preservação dos dados antes de atualizar o atalho |

Ordem de dependência: etapas 1–3 resolvem primeiro a ligação calibração → confirmação → aprendizado. Etapas 4–6 produzem evidência para entender a execução. Etapas 7–8 melhoram sugestões. A etapa 9 valida a entrega a ser instalada. Implementar tudo de uma vez não é requisito para começar a aproveitar a confirmação corretamente.

Manter regras puras sem imports de adaptadores e sem ciclos. Fachadas e chamadas antigas continuam compatíveis; a operação legada de confirmar sugestão permanece uma declaração de intenção e nunca se torna silenciosamente confirmação visual. Novos contratos devem ser aditivos e idempotentes, com rejeição de revisão obsoleta. Se uma regra precisar de implementação em Python e JavaScript, usar fixtures comuns de paridade. Métricas continuam em `rubinot.hunt.metricas` e `ui/taxas.js`.

## Casos obrigatórios de aceite

| Caso | Resultado exigido |
|---|---|
| Nenhum RTC detectado | Não oferecer confirmação de conteúdo inexistente; coleta continua |
| RTC parcialmente lido e usuário confirma | Guardar declaração e lacunas; não fabricar campos ou aplicação integral |
| Campo de criaturas inexistente na SD | Registrar inaplicabilidade, sem exigir valor artificial |
| Configuração própria divergente da sugestão | Permitir confirmar e aprender no escopo comprovado |
| Uso negado ou RTC desligado informado | Encerrar vigência declarada; preservar fatos e separar execução manual/indeterminada |
| Cura não lida ou roda parcial | Limitar os aprendizados dependentes, sem bloquear todos os demais |
| Revisão muda enquanto o usuário confirma | Rejeitar vínculo obsoleto e apresentar a leitura nova |
| Releitura idêntica, reinício e resposta repetida | Atualizar frescor, persistir resposta e evitar fases/eventos duplicados |
| Mesmo preset com valores diferentes | Abrir nova revisão; nome do preset não mascara a mudança |
| Slot extra, removido, vazio ou ilegível; opção alterada | Concordância considera todo o conteúdo, preservando lacunas |
| Mudança durante volta e descoberta tardia | Fronteira incerta/mista; sem atribuição retroativa ou rateio de totais |
| Troca de personagem, sessão, andar ou party | Isolamento da configuração e estratificação do contexto |
| Editor fechado ou apenas cabeçalho compartilhado visível | Não afirmar aplicação nem identificar incorretamente a aba |
| Prioridades iguais, runa concorrente e hotkey | Testar hipóteses; ambiguidade permanece quando não identificável |
| Saturação ilustrativa com cooldowns 4 s e 4 s versus 4 s e 6 s | Reproduzir alternância e oportunidade posterior sem chamar a fixture de prova do cliente |
| Spells mais fala, leitura repetida e casts próximos | Um evento por execução real, sem unir lançamentos distintos |
| Console cortado, barra oculta e quadro ausente | Cobertura por fonte; ausência de leitura nunca vira zero uso |
| Quantidade de runa cai, aumenta ou fica ilegível | Distinguir consumo associável, reposição e lacuna |
| HP máximo, identidade ou cura útil ausentes | Não promover limiares personalizados nem certificar segurança |
| Cura externa, Link e mas res para vários destinos | Evitar atribuição e contagem duplicadas |
| Mesma vida mínima, uma queda rápida versus várias quedas prolongadas | Distinguir frequência, persistência e recuperação, sem classificar só pelo mínimo |
| Oscilação junto a uma faixa de HP | Um episódio com recuperação sustentada, sem multiplicar eventos por quadro |
| Vida alta com cura e recasts frequentes | Permitir pressão controlada; não concluir tranquilidade somente pela vida |
| Utamo ausente por escolha de Vida ou durante intervalo sem combate | Não classificar pressão pela ausência isolada |
| Ícone oculto, janela ilegível e gap entre leituras | Estado desconhecido; não inventar queda, proteção ou duração |
| Escudo ativo no início ou no fim do trecho | Preservar duração incompleta; não confundir tempo na box com vida total do escudo |
| Mesmo tempo protegido com coberturas de leitura diferentes | Expor cobertura e denominadores; não atribuir confiança igual |
| Alertas desligados ou silenciados | Mesma coleta/classificação dos fatos; quantidade de apitos não altera episódios |
| Party sem dados de um membro | Limitar conclusão aos observados; média dos demais não certifica o ausente |
| Supplies em gold sem contagem por item | Manter custo; potions/minuto permanece desconhecido |
| Contador de potion lido em intervalos irregulares, reset ou refill | Usar duração correspondente; separar séries, sem negativos nem extrapolação de picos |
| Potions diferentes, híbridas, inventário e contador simultâneos | Preservar categorias/unidades e deduplicar consumo |
| Consumo alto com mana estável versus consumo alto com mana caindo | Considerar reserva e demanda antes de classificar pressão |
| Mana Leech adotado com menos potions e menor ritmo de combate | Não atribuir economia automaticamente à perk; comparar contexto e desempenho |
| Mesmo consumo de mana, mais produção e reserva estável | Permitir benefício de sustentação sem exigir economia de potions |
| Life Leech com HP cheio, cura externa ou sem oportunidade de ativação | Separar cura útil, outras fontes e falta de exposição; não inventar procs nem inutilidade |
| Mana Leech e dano alterados simultaneamente | Avaliar o pacote; não repartir artificialmente o ganho entre os dois campos |
| Perk com caminho obrigatório e redistribuição de pontos | Identificar pacote viável, benefício preterido e limites da atribuição individual |
| Estimativa de economia perto de zero com pouca amostra | Inconclusivo; não anunciar que a perk não funciona |
| Foco escolhido mas configuração sugerida não aplicada | Preservar intenção e avaliar apenas a configuração cujo uso estiver conhecido |
| Terra Hur com bônus, mas sem casts identificados e console parcial | Investigar disputa/cobertura; não concluir zero contribuição comprovada nem inutilidade universal |
| Bônus maior em magia rara versus menor em magia frequente | Comparar contribuição útil no mesmo período e custo de investimento, sem ranking só pelo percentual |
| Bônus passivo vigente versus bônus condicional/probabilístico | Separar aplicação derivada, oportunidade e ativação identificada; não atribuir bônus a todos os casts automaticamente |
| Dano da magia medido com várias fontes de bônus | Não chamar o dano inteiro de ganho da perk; contribuição incremental fica estimada ou inconclusiva |
| Bônus de mas res com múltiplos destinos e vida faltante diferente | Um cast; cura útil por destino, sem multiplicação de ativações ou dupla contagem |
| Candidata muda prioridade e torna uma magia antes preterida utilizável | Recalcular frequência e valor do bônus, sem transplantar zero uso da configuração anterior |
| Hunt com longa pausa e box pressionada | Pausa não dilui risco; conservar classificação por trecho e pior episódio |
| Resultado melhora no treino e piora depois | Rejeitar promoção e conservar referência anterior |
| Muitas candidatas e sessões copiadas | Nenhuma seleção no teste final nem duplicata entre treino e validação |
| Encerramento com leitor atrasado ou falha de escrita | Preservar provas/quadros pendentes e último estado consistente |

O replay real da sessão descrita nos insights deve tratar a volta 9 como mista, as voltas 10 e 11 conforme suas coberturas distintas, e a volta 12 como ainda não auditada naquele registro. A confirmação relatada às 15:11 não será convertida por migração em prova visual de todos os componentes. Dados reais permanecem locais; fixtures do repositório usam recortes sanitizados e dados temporários.

## Verificação e entrega

Cada etapa de comportamento atualiza documentação e testes de fronteira, contrato, replay e interface pertinentes. Executar `tools/verificar.ps1 -Perfil rapido`; antes de instalar, executar perfil completo e autoteste do compilado da mesma revisão. Falha, timeout ou teste ignorado impedem aprovação geral. Testes de software e demonstração de benefício pessoal terão conclusões separadas.

A atualização preserva calibração, histórico, modelos, números e provas. Fazer backup consistente do SQLite pela API existente, conferir restauração e hashes dos dados pessoais. Atualizar o aplicativo do atalho sem gerar Setup.exe. A ativação de motor novo respeita o encerramento normal da hunt. Não alterar RTC no jogo, iniciar captura, fazer push em main ou modificar o Git independente do tracker como parte deste planejamento.

**Primeira entrega funcional recomendada:** confirmação de uso na calibração com leitura exata, negativa explícita e fases válidas por componente. Ela corrige a ligação que falta hoje e estabelece a base para aprender a disputa de turnos com evidências confiáveis.
