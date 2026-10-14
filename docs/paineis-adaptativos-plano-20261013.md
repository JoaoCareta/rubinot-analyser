# Planejamento da leitura adaptativa dos painéis

Atualização posterior: o usuário autorizou a implementação e encerrou o aplicativo. O planejamento abaixo preserva a evidência e as decisões daquela etapa; o comportamento entregue e seus limites estão em [Implementação de 13/10](paineis-adaptativos-implementacao-20261013.md).

Data: 13/10/2026. Estado: planejamento com verificação inicial na hunt real de hoje. A implementação e a atualização do aplicativo não fazem parte desta etapa.

O analyser deve reconhecer os limites e o conteúdo de cada painel, acompanhar mudanças de posição e tamanho e usar o painel específico como fonte principal de cada informação. Reconhecer o título ou parte dos rótulos não comprova leitura completa. A calibração inicial deve servir de referência recuperável, sem prender toda a sessão a retângulos imutáveis.

Decisão reforçada pelo usuário: uma informação repetida pertence prioritariamente ao painel específico. XP vem exclusivamente do XP Analyser, mesmo quando também aparece no Hunt Analyser. Uma falha de leitura não autoriza substituir silenciosamente a fonte. Para comparar fontes, identidade, período, unidade, modo e base de preço precisam ser compatíveis.

Correção do usuário nesta continuação: **Supply Analyser e Loot Analyser são fontes de estimativa auxiliar. Supplies, loot e profit oficiais da análise vêm do Party Hunt para a PT e do Hunt Analyser para o individual.** Essa decisão prevalece sobre qualquer leitura anterior da regra de especialização que tratasse Supply/Loot como fonte econômica principal. Ícones e contagens podem orientar composição e tendências, sem substituir, corrigir ou invalidar os acumulados econômicos principais. Relação detalhada e numeração visual em [Campos por painel](paineis-campos-20261013.md).

## Evidências confirmadas em 13 de outubro

Decisão posterior à relação visual: usuário aprovou a captação dos itens e determinou **tempo da sessão exclusivamente pelo Party Hunt**. Session do Hunt Analyser não integra a fonte de tempo nem serve de fallback. Sem leitura válida do Party, o campo fica como lacuna, inclusive em solo. Horários de quadros/eventos e duração dos trechos observados são medidas distintas. Esta aprovação do escopo não autoriza implementação nesta etapa.

Base principal: `session_20261013_062400`, Monster Graveyard, PT x4, Hazard 5 confirmado anteriormente pelo usuário. Foram reprocessados três quadros completos preservados, às 07:05:11, 07:42:51 e 09:02:20. Também foi inspecionada a releitura anterior com 1.445 registros de Party Hunt entre 07:05:11 e 09:02:20: todos com quatro membros e nenhuma redução nos acumulados de dano por membro entre registros consecutivos. Isso não representa cobertura contínua nem valida todos os tamanhos de painel.

O quadro de 09:02:20 já mostra End Of Days, depois das 35 voltas registradas da hunt. Seus valores são o último acumulado preservado dos painéis desta sessão, não uma medição isolada de Monster Graveyard. Para resultado por área, usar fronteiras e deltas compatíveis.

Um quadro das 16:10:08, com Market aberto, foi usado como controle fora de combate. Ele contém XP acumulada e Party Hunt vazio: aplicativo ativo ou painel não zerado não comprovam hunt. A sessão das 12:22 foi inventariada, mas não usada como referência quantitativa deste estudo; não misturar personagens, áreas ou períodos apenas por serem do mesmo dia.

### Problemas reproduzidos

| Evidência | Resultado da conferência | Consequência para a feature |
|---|---|---|
| XP com largura antiga de 158 px, em vez de 157 px | Nos três quadros, `Raw XP Gain` deixa de ser aceito; a borda/rolagem entra na leitura | Detectar área útil e scrollbar; não limpar caracteres desconhecidos de um número |
| Party Hunt terminando em y=900, em vez de y=916 | Nos três quadros, o leitor aceita somente Infortunio, Hetero afeminado e Sorcniel, omitindo Placeholder One | Três membros legíveis não comprovam lista completa; detectar bloco interrompido e continuação |
| Hunt e Supply com a borda direita atual | `Healing` do Hunt e `Gold Value` do Supply são perdidos nos três quadros | Qualidade deve ser por campo, com delimitação de bordas e ícones |
| Mesmos quadros, retirando 1 px à direita apenas no experimento | Recupera `Healing` e `Gold Value` nos três casos | Prova de sensibilidade geométrica; não é autorização para um corte fixo universal |
| Corte maior | Retirar 3 px adicionais da região atual de XP já elimina seus valores nas três amostras | A adaptação precisa preservar dígitos e avaliar geometria, não escolher qualquer recorte que produza número |
| Input Analyser | Total e Max-DPS foram lidos nos três quadros; valores por tipo aparecem, mas nomes ficam nulos e percentuais não são decodificados | Reconhecer ícones e separar `%`/parênteses/rolagem da área numérica |
| Calibração atual | `v_painel` aprova a partir de 60% dos rótulos; Party conta cinco rótulos gerais, sem medir completude dos membros | “5 de 5” não significa que todos os dados da PT foram coletados |

Três arquivos com prefixo `q_` preservados em uma atualização anterior são recortes ampliados do cenário, de 1160 × 640, e não quadros completos com o layout de 1936 × 1048. Foram excluídos da validação de painéis. O nome do arquivo não comprova sistema de coordenadas: dimensão, origem e transformação precisam fazer parte do contrato da prova.

### Valores conferidos nos pixels e nos leitores existentes

Valores abaixo em kk, salvo indicação de tempo. Casas adicionais são mantidas quando necessárias para comparar a leitura exata.

| Campo | 07:05:11 | 07:42:51 | 09:02:20 |
|---|---:|---:|---:|
| Raw XP Gain do XP Analyser | 6,298361 | 18,844571 | 43,628628 |
| Raw XP/h do XP Analyser | 18,961170 | 20,196545 | 11,769023 |
| Total recebido do Input | 0,495856 | 1,254505 | 2,960802 |
| Max-DPS do Input, em kk/s | 0,005316 | 0,005316 | 0,006186 |
| Supplies acumulados do Hunt | 0,188072 | 0,428952 | 0,710812 |
| Gold Value do Supply, após delimitação experimental | 0,188072 | 0,415341 | 0,174308 |

Às 07:42:51, o Supply mostra 0,415341 kk e o Hunt 0,428952 kk; às 09:02:20, 0,174308 kk e 0,710812 kk. A diferença não permite invalidar automaticamente uma das fontes. O manual oficial descreve Supply e Loot como informações da última hora; o Hunt é de sessão. Modo, reset e preços também precisam ser registrados antes de reconciliação. [Manual oficial do cliente](https://www.tibia.com/gameguides/?section=interface&subtopic=manual).

Há uma interação concreta a corrigir no desenho: `painel_stream.ler_quadro` pode retirar Supplies/Loot/Balance do Hunt quando os valores divergem dos outros painéis. Nas três amostras a regra não disparou porque Gold Value não foi decodificado. Melhorar apenas o recorte ativaria essa comparação inadequada quando períodos diferentes fossem tratados como iguais.

O último Party Hunt preservado mostra dano total de **99,376420 kk**, loot de **28,652203 kk**, supplies de **4,479708 kk** e balance de **24,172495 kk**. A soma dos balances dos quatro membros confere exatamente com o total. Dano individual: Infortunio 22,611086 kk; Hetero afeminado 25,728034 kk; Sorcniel 23,899629 kk; Placeholder One 27,137671 kk.

O relatório anterior guarda **6,739266 kk** de dano observado no console para esses jogadores, equivalente a 6,78% daquele acumulado do painel. Essa razão é descritiva: início dos contadores e cobertura podem diferir; não é uma taxa medida de perda do OCR. Ainda assim, demonstra por que não usar o console como substituto do acumulado da PT.

Também há diferença de precisão: no último quadro, o Hunt exibe `25,728k`, enquanto o Party lê 25,728034 kk para o jogador. O texto abreviado do cliente precisa conservar sua resolução; convertê-lo para inteiro não o torna exato. A cura do Hunt e a cura do Party também divergem nos quadros; não presumir equivalência de escopo ou usar uma como conferência obrigatória da outra sem estabelecer o significado.

Provas locais, textos extraídos, variações de recorte e hashes: `output/planejamento/paineis-adaptativos-20261013/`. Nenhuma dessas releituras foi gravada no histórico ou no aprendizado do usuário.

## Inventário dos onze campos da calibração

O inventário distingue informação potencial do painel, leitura existente e trabalho proposto. Um conteúdo disponível no cliente, mas escondido por rolagem ou configuração, continua indisponível naquele quadro.

| Região | Conteúdo e uso | Situação observada e ampliação planejada |
|---|---|---|
| Tela do jogo | Identidade e posição dos personagens, barras de vida, escudos de party, criaturas visíveis, alvo, Hazard e contexto espacial | Há leitores de nomes, vida e Hazard. Localizar viewport, escala dos tiles e moldura integral das barras; separar sobreposição, personagem fora de alcance e leitura ausente. HP/mana numéricos e hotkeys ficam fora do viewport e precisam de regiões próprias no quadro completo |
| Server Log | Eventos com horário: dano, cura, efeitos, críticos, fatais, XP, mortes, mensagens de área e possíveis agressores | Fonte parcial de eventos. Reconstituir linhas quebradas e deduplicar sobreposição temporal. Não produzir totais oficiais de XP/dano da sessão a partir dele |
| Spells | Fala de magia, autor e horário; destinatário quando escrito; evidência de execução | Há coleta e parsing de casts. Adaptar altura, largura e linhas quebradas; distinguir aba ativa e falas alheias. Runa sem fala não pode receber cast inventado; pode precisar de contador de item/cooldown |
| Map View | Desenho do minimapa, pin, andar, zoom e trajetória | Há rastreio e relação com mapa conhecido. `recorte_mapa` ainda deriva um recorte fixo 193 × 176 com deslocamento do centro. Detectar área útil, pin, escala e andar, recusando mapa livre/ambíguo como posição do jogador |
| Battle List | Nomes, ícones, barras de vida, seleção e população visível | Já alimenta composição e pressão. Ler linhas pela área útil, filtros, posição de rolagem e abreviações. Lista vazia visível pode valer zero; lista escondida/cortada não. População listada não é quantidade atingida por magia nem número de abates |
| Hunt Analyser | Economia pessoal, dano/cura e taxas; seções de criaturas mortas e loot quando disponíveis | Hoje predominam os campos textuais superiores. XP é descartada em favor do XP Analyser; Session não é usado como tempo da sessão, exclusivo do Party Hunt. Planejar leitor de seções e contadores por espécie quando realmente expostos; nenhuma amostra atual confirma a leitura dessas listas inferiores |
| XP Analyser | Raw XP Gain, XP Gain, Raw XP/h, XP/h, Next Level, barras/gráfico e estado associado | Fonte exclusiva de XP. Quatro métricas numéricas são lidas; Next Level não é publicado pelo leitor numérico atual. Distinguir duração estimada, acumulado, taxa e bônus. Gráfico é apoio visual, não substitui número exato |
| Supply Analyser | Estimativas auxiliares de valor, taxa, composição de itens consumidos e gráfico; alvo configurado | A calibração verifica três rótulos, não o inventário. Planejar identidade dos itens, quantidade, abreviação, janela temporal e preços. Leitor atual de hotkeys mede estoque, não consumo. Gold agregado não permite deduzir potions/minuto. Supplies principais vêm do Hunt/Party |
| Party Hunt | Sessão e tipo de preço, totais econômicos, identidade dos membros, balance/dano/cura por membro | Leitor atual espera nome e três linhas numéricas consecutivas. Adaptar blocos e ícones; tolerar nomes longos, cores e ordenação; conservar membro confirmado quando sai de vista. A última leitura parcial não deve apagar valores anteriores nem ser apresentada como total atualizado de todos |
| Input Analyser | Dano recebido total, Max-DPS, gráfico, distribuição por tipo e principais fontes | Leitor já recupera total/pico e números por tipo, sem identificar elementos; fontes ainda não são estruturadas. Separar modo recente/sessão e abas/seções. Gráfico não fornece eventos exatos nem horário do pico sem eixo/calibração |
| Loot Analyser | Estimativas auxiliares de valor, taxa, composição de itens obtidos e gráfico; alvo configurado | Opcional. Evoluir de três rótulos para lista de itens e janela observada. Não confundir loot individual recente com loot da PT ou balance da sessão. Loot/profit principais vêm do Hunt/Party |

O Input oficial admite valores recentes ou de sessão, seções desligáveis e uma lista limitada às cinco maiores fontes. Ausência nessa lista não comprova ausência de dano de uma criatura. [Descrição oficial do Input](https://www.tibia.com/news/?id=5808&subtopic=newsarchive).

A base de preço do Party pode ser Market ou Leader; a comparação econômica precisa preservar essa escolha. [Descrição oficial do Party Hunt](https://www.tibia.com/news/?id=5259&subtopic=newsarchive). As regras seguem o Global conforme decisão do usuário; isso não dispensa observar o modo efetivamente selecionado na tela.

## Prioridade por informação

| Informação | Fonte principal | Papel das demais fontes |
|---|---|---|
| Tempo da sessão | Session do Party Hunt, exclusivamente | Session do Hunt Analyser não é usado. Sem leitura válida, lacuna; relógio das capturas permanece só como referência dos eventos/trechos observados |
| Qualquer métrica de XP | XP Analyser | Hunt/log somente comparação diagnóstica compatível; não preencher lacuna de XP |
| Dano recebido, pico e distribuição | Input Analyser, no modo identificado | Log fornece eventos parciais e horários; HP/Utamo medem consequências e proteção, não o mesmo total |
| Estimativa da composição e tendência do consumo | Supply Analyser, somente auxiliar | Não é fonte dos supplies oficiais; hotkey é estoque auxiliar; log confirma usos quando há evento identificável |
| Estimativa da composição e tendência do loot | Loot Analyser, somente auxiliar | Não é fonte do loot/profit oficial; log é evidência parcial; não somar duplicatas |
| Supplies, loot e profit pessoais da sessão | Hunt Analyser | Supply/Loot não substituem nem invalidam estes valores. Comparações auxiliares exigem janela, reset e preço compatíveis |
| Economia, dano e cura da PT por membro | Party Hunt | Hunt conserva observação pessoal separada; log conserva detalhes parciais. Falha no Party não transforma PT em solo |
| Dano/cura pessoal em solo | Hunt Analyser | Log complementar; Impact Analyser fica como possível expansão futura, fora dos onze painéis atuais |
| Criaturas mortas por espécie | Contador visível da seção Killed Monsters do Hunt, quando validado | Battle observa presença; log observa parte das mortes; estimativa por XP é explicitamente estimativa, nunca contador oficial |
| Localização e andar | Map View ancorado | Cenário e mensagens de área corroboram; não deslocar mapa com base em nome isolado |
| HP/mana, escudo e estado do personagem | Barras/valores/ícones correspondentes no quadro | Log contextualiza eventos; ausência de mensagem não comprova estado |
| Casts e sequência de combate | Spells, fala própria, prontidão e eventos atribuíveis | Consoles continuam necessários quando são a única fonte daquele evento; total acumulado não revela magia, alvo, horário ou crítico |

“Log para confirmação” vale para medidas já oferecidas pelo painel específico. Eventos exclusivos do console continuam como fonte de detalhe, separados dos acumulados. Se a prioridade exigir uma fonte indisponível, o estado é lacuna; a UI pode conservar a última leitura com seu horário, sem fingir atualização.

## Reconhecimento adaptável proposto

1. Identificar quadro e fonte: personagem, resolução, escala/DPI, origem local/stream, instante e área da janela. Rejeitar recortes com coordenadas incompatíveis antes de ler números.
2. Localizar candidatos por título, moldura, controles e conteúdo. Hoje `detectar` usa botão ×, largura aproximada fixa de 158 px e próximo cabeçalho na mesma coluna; substituir essas suposições por limites medidos. Título sozinho não distingue aba ativa ou painel sobreposto.
3. Separar cabeçalho, conteúdo, bordas, scrollbar, rodapé, gráficos e listas. Calcular escala da fonte e altura de linha. Não escalar toda a tela cegamente nem cortar largura fixa de todos os painéis.
4. Ler por âncoras de rótulo/ícone e blocos relativos: número à direita do rótulo, itens em grade, membros em blocos e séries em tabelas. Usar atlas existente quando a escala permitir; avaliar OCR alternativo somente em casos não cobertos, com rejeição de números ambíguos.
5. Registrar completude por campo e seção: observado, zero observado, abreviado, parcialmente visível, oculto, fora do recorte, ilegível, sobreposto ou desatualizado. Confiança no título não se transfere automaticamente aos valores.
6. Rastrear geometria em quadros seguintes. Mudança de borda/título ou queda de legibilidade provoca relocalização. Confirmar geometria ambígua em quadros subsequentes, sem exigir estabilidade de valores que naturalmente variam. Congelar emissão de medidas novas daquela região enquanto houver ambiguidade.
7. Publicar revisão de layout com vigência e transformação do quadro para o recorte. A captura e seus consumidores referenciam a mesma revisão; não substituir o layout histórico único por coordenadas novas e reinterpretar quadros antigos.
8. Quando o usuário mover, ampliar ou rolar um painel, aproveitar a nova área passivamente. Não automatizar cliques, rolagens ou alterações do jogo durante combate. Campo realmente escondido não é recuperável por aumentar artificialmente a imagem.

A captura local já obtém o quadro inteiro e depois cria recortes. Essa base permite relocalização sem uma segunda captura concorrente. Para stream, a mudança de resolução hoje suspende a leitura; preservar essa proteção até existir detecção e validação do novo layout. Depois, retomar somente regiões comprovadas e registrar a lacuna intermediária.

## Contratos e integração

Cada observação proposta deve guardar: sessão/personagem, painel/campo, valor e texto originais, unidade, precisão/abreviação, janela temporal ou modo desconhecido, base de preço, instante do quadro, revisão de layout, retângulo/escala, estado de visibilidade, qualidade, leitor/versão e prova com hash. Valor nulo é diferente de zero. Número abreviado guarda resolução ou intervalo; não alimentar treino como inteiro exato sem essa distinção.

Cada contador mantém sua própria época de reset. Queda legível pode ser reset, janela móvel, perda de XP, troca de modo/preço ou identidade; não classificar todo delta negativo como reset. Balance pode ser negativo. Per Hour e Max-DPS não são acumulados e não se somam. Gráfico é amostra visual aproximada. Target é meta configurada, não resultado.

Aceite específico de tempo: com durações diferentes nos dois painéis, selecionar apenas Session do Party; com Party ilegível/oculto/ausente, preservar lacuna sem fallback para Hunt. Testar também zero legível, reset do Party e cenário solo. Não reutilizar essa duração para recalcular taxas de fontes cujo intervalo não corresponda ao mesmo período.

Uma lista rolada pode acumular identidades conhecidas, mas valores de instantes diferentes não compõem um snapshot simultâneo. Conservar horários por membro/item e só reconciliar somas em observações compatíveis. Nenhum painel parcial fornece “total de todos os membros” por soma silenciosa de valores antigos.

Reconhecimento e interpretação pertencem a `rubinot.observacao`; arbitragem e deltas às regras puras de hunt; arquivos e persistência aos adaptadores; composição ao bootstrap. Reaproveitar fachadas, atlas e contratos existentes, sem ciclos. O manifesto de runtime deve registrar módulos e assets futuros. Manter APIs/CLIs e leitura de sessões legadas.

Consumidores a revisar: `capture.py`, `layout.py`, calibração em `rubinot/adapters/servidor.py`, `painel_stream.py`, `pt_card.py`, `lap_watch.py`, `rubinot/conflitos/detector.py`, `rubinot/observacao/execucao.py`, métricas e aprendizado. Mudanças nas métricas passam pela fonte canônica `rubinot.hunt.metricas`, fachadas e espelho `ui/taxas.js`, com paridade.

Retenção precisa preservar quadros aguardando leitores e provas de mudança/erro. Não ampliar a frequência e deixar consumidores perderem o buffer atual; planejar confirmação de consumo, limites de disco e métricas de atraso antes de mexer na limpeza. Reprocessamento produz revisão com proveniência, preservando originais, previsões e modelos. Dados pessoais permanecem fora do Git.

## Etapas e critérios para implementar depois

| Etapa | Entrega proposta | Critério de saída |
|---|---|---|
| 1. Corpus e semântica | Matriz de campos, modos, precisão e fonte prioritária; provas da hunt de hoje | Cada afirmação marcada como vista, documentada ou ainda não observada; fronteiras da hunt separadas dos contadores da sessão |
| 2. Geometria e qualidade | Localizador comum, áreas úteis, seções e revisão temporal do layout | Reproduzir XP 157/158 px e Party y=900/916; nenhum membro cortado aceito como lista completa |
| 3. Painéis prioritários | XP, Party, Input e campos pessoais do Hunt | Valores conferem com transcrição dos quadros; zero troca silenciosa de fonte; preservação de nulos, precisão e modos |
| 4. Itens e criaturas | Supply/Loot por item, tipos/fontes de Input e Killed Monsters | Identidades conferidas por ícone/texto e contador; abreviações e janelas móveis não geram consumo/mortes fictícios |
| 5. Integração temporal | Captura, voltas, KS, histórico e aprendizado usando observações versionadas | Replay determinístico; mesmos quadros e fontes; reset/saída da PT/rolagem não apagam acumulados válidos |
| 6. Validação e entrega | Comparação com leitor atual e relatório de ganhos/lacunas | Perfil rápido, completo e autoteste do compilado aprovados antes de atualizar a instalação; preservar dados, sem Setup.exe |

Antes de implementar, concluir os pontos não provados pelo material de hoje: variações reais de largura/altura/escala, painel movido de coluna, rolagem em listas, valores abreviados por item, Killed Monsters, Damage Sources e identificação completa dos tipos. Os três quadros completos confirmam defeitos e campos numéricos, mas não demonstram generalização automática a qualquer tamanho.

O conjunto de aceite deve cobrir: zero válido; painel vazio/fechado/oculto; mudança de resolução; Supply e Loot com rótulos idênticos; menu cobrindo conteúdo; nome longo em duas linhas; membro fora de alcance; quarto membro cortado; número negativo; `k` abreviado; scrollbar tocando dígito; fonte/percentual desconhecido; sessão acima de uma hora; resets independentes; morte/perda de XP; Market/Leader; troca de área; PT encerrada; reabertura da sessão e compatibilidade com histórico antigo. Transformações sintéticas só validam robustez técnica, nunca melhoria real da hunt.

Medir por campo: acerto contra transcrição manual, cobertura dos campos realmente visíveis, falsas aceitações, tempo para recuperar layout, atraso dos consumidores, CPU e disco. Nos casos críticos conhecidos, exigir zero valores errados aceitos como completos. Separar treino/ajuste e avaliação posterior por trecho/sessão; não usar os mesmos quadros para calibrar e anunciar generalização.

Na calibração, manter os cards existentes e apresentar estado compreensível: identificado, leitura parcial, lendo ou oculto. Detalhes mostram campos obtidos e faltantes; “5 de 5 rótulos” não será sinônimo de painel completo. Não adicionar diagnóstico técnico aos quadros de dano/RTC já simplificados.

## Pendências de confirmação

- Contagens por item: os ícones estão visíveis, mas não foram todos identificados nem reconciliados nesta rodada. Não publicar potions/minuto a partir dessas amostras.
- Campos abaixo da rolagem: sem prova não afirmar conteúdo zero, leitura completa ou número total de criaturas/itens.
- Janela e reset: registrar a semântica por campo e configuração; a documentação oficial não revela qual opção estava ativa em cada quadro.
- Cura: explicar a diferença entre acumulados pessoais e da PT antes de propor igualdade; nenhum total prova cura útil ou conforto do EK.
- Tipos do Input: os valores foram recuperados; a associação exata de cada ícone ao elemento e os percentuais precisam de validação própria. O Global corrigiu em agosto de 2026 a apresentação de todo dano como Mana Drain sob Magic Shield; não herdar esse pressuposto antigo. [Correção oficial](https://www.tibia.com/news/?id=8915&subtopic=newsarchive).

As páginas oficiais foram consultadas pelos resultados indexados; abertura direta retornou 403. As evidências do cliente são locais e independentes dessa limitação de acesso. A etapa atual entrega inventário, defeitos reproduzidos, prioridades e critérios; não declara a leitura adaptativa implementada ou integralmente validada.

## Verificação desta entrega

Somente documentação e evidências locais foram acrescentadas. Os sete arquivos de prova originais/cópias e as sete fontes usadas na auditoria foram conferidos por SHA-256, sem alteração. O perfil rápido passou no ambiente `.venv` do projeto: 175 testes Python, nenhuma falha/erro/omissão e demais suítes aprovadas. Relatório em `output/planejamento/paineis-adaptativos-20261013/verificacao-ambiente-projeto/`. A tentativa inicial com o Python padrão falhou por ausência de `ruff` e `coverage`; seu relatório foi preservado em `verificacao-rapida/`. Essa verificação não certifica a feature proposta; não houve build, instalação ou mudança de comportamento.
