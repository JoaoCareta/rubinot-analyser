# Campos que vamos ler em cada painel

Planejamento de 13/10/2026, atualizado pela correção do usuário. Esta relação define o escopo pretendido; não afirma que todos os leitores já funcionam. A numeração corresponde ao mapa visual. Campo oculto ou ilegível permanece sem dado.

**Economia:** Party Hunt é a fonte de supplies, loot e profit da PT; Hunt Analyser é a fonte individual. Supply e Loot Analyser são estimativas auxiliares. **Tempo da sessão:** exclusivamente Session do Party Hunt; sem leitura válida, fica como lacuna, sem substituir pelo Hunt Analyser. **XP:** exclusivamente XP Analyser. **Dano recebido:** Input Analyser. Consoles complementam com eventos e confirmação.

O usuário aprovou a captação dos itens desta relação, com a correção do tempo da sessão acima. A aprovação define o escopo do planejamento; a implementação continua fora desta etapa.

## 01 Hunt Analyser

| Campo | O que representa | Uso planejado |
|---|---|---|
| Session | Contador próprio do Hunt Analyser | Excluído da captação planejada como fonte de tempo da sessão; não usar como substituto do Party Hunt |
| Loot | Valor acumulado do loot pessoal | Fonte econômica individual |
| Supplies | Valor acumulado dos gastos pessoais | Fonte econômica individual |
| Balance | Loot menos supplies; pode ser negativo | Profit/prejuízo individual |
| Damage | Dano pessoal acumulado no painel | Dano em solo; em PT, prevalece a leitura por membro do Party |
| Damage/h | Taxa de dano por hora | Ritmo pessoal, preservando período e precisão |
| Healing | Cura pessoal acumulada no painel | Cura em solo; em PT, prevalece o Party. Não presumir que mede cura útil |
| Healing/h | Taxa de cura por hora, quando exposta | Ritmo pessoal; campo fora da tela continua pendente |
| Killed Monsters | Lista/contagem por espécie, quando exposta | Abates por espécie, após validação da lista completa |
| Seção de loot detalhado | Itens e quantidades, quando exposta | Detalhe da sessão; não pressupor sua presença no print atual |

Raw XP Gain, XP Gain, Raw XP/h e XP/h repetidos aqui não alimentam as métricas de XP: a fonte é o painel 02.

## 02 XP Analyser

| Campo | O que representa |
|---|---|
| Raw XP Gain | Experiência acumulada sem os bônus da XP exibida |
| XP Gain | Experiência acumulada com os bônus considerados pelo cliente |
| Raw XP/h | Ritmo de experiência raw por hora |
| XP/h | Ritmo de experiência com bônus por hora |
| Next Level | Tempo estimado pelo cliente para o próximo nível |
| Barras e gráfico | Evolução visual e contexto; preservar modo/eixos antes de interpretar |

Os quatro números de XP vêm exclusivamente deste painel. A barra não substitui o número; gráfico não fornece série exata sem validação própria.

## 03 Party Hunt com os totais da PT

| Campo | O que representa |
|---|---|
| Session | Fonte exclusiva do tempo da sessão considerado pelo analyser |
| Loot Type | Base de preços, como Market ou Leader |
| Loot | Valor acumulado do loot da PT |
| Supplies | Valor acumulado dos supplies da PT |
| Balance | Profit/prejuízo acumulado da PT |

O botão Split Loot não é métrica. Dados do grupo não são somados aos dados individuais, pois isso duplicaria valores. Mudanças na base de preços precisam de registro.

Session ausente, oculto ou ilegível permanece sem dado; não usar Session do Hunt Analyser, inclusive em solo. O relógio das capturas continua identificando horários de eventos e intervalos de observação, sem substituir o tempo de sessão do Party. Taxas lidas diretamente de outros painéis conservam seus períodos próprios; não recalculá-las com duração incompatível.

## 04 Party Hunt por integrante

| Campo | O que representa |
|---|---|
| Nome | Identidade do integrante; normalizar espaços sem inventar nomes cortados |
| Escudo/indicação de líder | Vínculo e papel observados; combinar com nome no Party |
| Linha econômica com ícone | Balance individual; não confundir com loot individual bruto |
| Linha de espadas | Dano acumulado do integrante |
| Linha de cruz | Cura acumulada do integrante |
| Participação | Percentual calculado sobre dano dos integrantes, com cobertura compatível |

Loot e supplies separados por integrante só entram se forem realmente expostos em uma apresentação observada do cliente. As três linhas deste print mostram balance, dano e cura. Não obter loot e supplies individuais a partir de balance sozinho. Parte da lista fora do recorte não transforma PT x4 em PT x3.

## 05 Input Analyser com total e pico

| Campo | O que representa |
|---|---|
| Received Damage | Identificação da seção de dano recebido |
| Total | Dano recebido no período/modo do painel |
| Max-DPS | Maior dano recebido em um segundo; não é maior golpe isolado |
| Gráfico | Evolução visual do dano recebido; leitura aproximada |
| Modo/período | Diferenciar sessão de período recente, quando identificável |

O valor não separa automaticamente perda de vida e absorção pelo escudo. Para isso, cruzar observações de HP, mana, Utamo e eventos atribuíveis, preservando lacunas.

## 06 Input Analyser por tipo e fonte

| Campo | O que representa |
|---|---|
| Ícone em Damage Types | Tipo/elemento de dano, após reconhecimento validado |
| Valor | Dano daquele tipo |
| Percentual | Participação daquele tipo no total do painel |
| Damage Sources | Fontes/agressores apresentados, quando a seção estiver visível |

Não atribuir elemento somente pela ordem das linhas ou converter ícone desconhecido em nome suposto. Fontes fora de uma lista limitada não significam dano zero.

## 07 Supply Analyser como estimativa auxiliar

| Campo | O que vamos aproveitar |
|---|---|
| Ícone do item | Identificar a composição observável de supplies |
| Contagem do item | Apoiar estimativa de consumo por item, respeitando janela, abreviação e cobertura |
| Gold Value | Estimativa auxiliar do custo exibido |
| Per Hour | Tendência estimada de gasto por hora |
| Target | Meta configurada; não é consumo realizado |
| Gráfico | Evolução aproximada do gasto |

**Não define nem corrige os supplies oficiais da análise.** Esses vêm do Hunt/Party. Não dividir gold total pelo preço de uma potion para inventar quantidade. Em janela móvel, diferença entre contagens não equivale automaticamente ao consumo ocorrido entre quadros.

## 08 Loot Analyser como estimativa auxiliar

| Campo | O que vamos aproveitar |
|---|---|
| Ícone do item | Identificar composição observável do loot |
| Contagem do item | Apoiar estimativa de frequência/quantidade por item |
| Gold Value | Estimativa auxiliar de valor |
| Per Hour | Tendência estimada de loot por hora |
| Target | Meta configurada |
| Gráfico | Evolução aproximada do loot |

**Não define nem corrige loot ou profit oficiais.** Esses vêm do Hunt/Party. Item fora da área visível não recebe contagem zero.

## 09 Battle List

Nomes e ícones identificam criaturas ou jogadores listados; barras mostram vida visível; seleção indica alvo; contagem de linhas ajuda a medir população observada. Filtros e rolagem limitam cobertura. A lista não comprova mortes, criaturas atingidas por magia ou todos os monstros da box.

## 10 Map View

Pin, posição relativa, andar e escala sustentam localização e trajetória. A sequência temporal permite identificar deslocamentos, boxes e voltas. Primeiro confirmar que o mapa acompanha o jogador; movimentar o mapa manualmente não pode deslocar sua posição estimada.

## 11 Vida e mana

Valores atual/máximo e barras do HUD fornecem reserva, percentuais, quedas e recuperação. O ícone de Utamo, quando presente e reconhecido, fornece estado de proteção. Barra parcialmente encoberta é lacuna. Se o HUD mostrar apenas o máximo completo ou houver dúvida de identidade, não inferir perda zero.

## 12 Skills e atributos do personagem

Level e Magic fornecem nível e magic level; XP Gain Rate e Store Boost contextualizam bônus; Stamina contextualiza experiência. HP/mana podem corroborar o HUD. Demais atributos de combate, como crítico e leech, só entram quando seus campos estiverem expostos e identificados. Speed, capacidade e outros rótulos visíveis são contexto disponível, sem prioridade para a primeira entrega. XP acumulada de Skills não substitui o XP Analyser.

## 13 Personagens e cenário

Nomes, barras integrais de HP, escudos de party, Hazard, posição e distância relativa dão contexto de saúde e combate por personagem. Guardar identidade, cobertura e oclusão por observação. Cura recebida ou cor do nome sozinhas não comprovam vínculo de party. Elementos visuais não identificados permanecem desconhecidos.

## 14 Hotkeys e cooldowns

Ícones identificam magias/itens; contadores mostram estoque; temporizadores e estado visual indicam prontidão quando reconhecidos. Estoque não é consumo: compra, transferência e refil alteram a quantidade. Não afirmar cooldown completo a partir de uma amostra isolada. Esta região complementa observação de execução e de recursos.

## 15 Spells

Horário, autor, fala da magia e destinatário, quando escrito, permitem identificar casts e cadência. Distinguir o jogador dos aliados e outras pessoas. Linhas quebradas e repetidas precisam ser reconstruídas/deduplicadas. Runa sem fala depende de outras provas; ausência no console parcial não comprova ausência de uso.

## 16 Server Log

Horário, origem, alvo, valor e tipo do evento permitem confirmar dano, cura, críticos, fatais, mortes, mensagens de área e possíveis agressores. São detalhes parciais: não substituem acumulados dos painéis nem fornecem XP oficial. Eventos de dano/cura podem ter valor direto observado, mas sua soma continua com a cobertura do console.

## Marcações e limites da imagem

O mapa usa ciano para fontes principais, amarelo para estimativas de Supply/Loot e violeta para contexto/confirmação. Esses estados indicam o papel da fonte, não certificação de um leitor já implementado. As dezesseis regiões dividem alguns dos onze painéis de calibração em partes e incluem HUD, Skills e hotkeys.

O mapa gerado é uma ilustração de planejamento, não uma prova dos números da hunt. A geração pode redesenhar pequenos textos/valores. O print original está preservado em `output/planejamento/paineis-adaptativos-20261013/referencia-campos-usuario.png`; somente originais e leituras conferidas servem de evidência quantitativa. A numeração e esta relação textual definem os campos; a XP duplicada no Hunt não é fonte mesmo estando dentro do contorno do painel.

A legenda 01 da imagem v1 antecede a correção do usuário: seu item Session fica desconsiderado. O tempo da sessão pertence somente à região 03, Party Hunt. A imagem anterior permanece preservada como versão do planejamento.
