# Aprendizado

## Interface e histórico de cura — 14/10/2026

Estudos, amostras de treinamento, seleção/teste, diagnósticos de ML e cenários internos de simulação não são apresentados ao usuário. Continuam preservados e consumidos internamente. O RTC mostra configuração e sugestões concretas para a próxima hunt; a roda mantém a comparação dos benefícios dos pontos, sem tabelas de simulação. Auxiliares não mostram estado/contagens do aprendizado.

No histórico, “Curas da party” fica visível logo abaixo do dano e antes das voltas. A tabela traz apenas jogadores com Sio ou Gran sio registrado, quantidades parciais por destinatário exato e ícones locais das magias. Quem tem zero em ambas as magias não aparece na tabela nem no seletor. A consulta `/api/historico/<id>/curas` conserva todos os membros e os trechos anteriores para compatibilidade, separando capturas agrupadas; a interface mostra faixas de vida, sem divisão por horários. Faixas: [0,30), [30,50), [50,70), [70,90), [90,100], com tempo estimado, Sio e Gran sio. Vida zero é válida.

A permanência usa pares consecutivos de leituras válidas separados por até 6 s; atribui o intervalo à faixa da leitura inicial, sem interpolar transições. Leitura inválida/identidade ausente interrompe a continuidade. Não extrapola antes da primeira leitura ou após a última. Todo o tempo restante fica em “Sem leitura suficiente”; sem nenhum intervalo utilizável, o tempo de cada faixa é indisponível (—), não zero. Barras comparam somente o tempo identificado. A faixa de cada cast usa a última vida válida até 1,5 s antes da magia; casts sem essa referência ficam na linha sem leitura, conservando as contagens totais. Isso não prova vida exata no disparo nem recuperação causada pelo sio. São estimativas observacionais parciais, não diagnósticos de estudos/ML.

Dados vêm dos eventos e recursos existentes, com prioridade às releituras de cura para o mesmo instante; originais não são reescritos. Exige ator da sessão, magia identificada e nome exato do destinatário. Vocação vem da declaração por sessão ou look de participante confirmado, nunca da ordem das regras ou do recebimento de cura. Sem intervalo de voltas conhecido, não atribui toda a captura à hunt. A consulta não executa treinamento. Métricas `resumo_vida`/`permanencia_vida` e espelhos `resumoVida`/`permanenciaVida` têm testes de paridade, incluindo limites das faixas, lacunas, identidade, duplicatas e conservação do tempo.

## Feedback de disputa entre autocura e sio — 14/10/2026

Uma redução emergencial informada pelo usuário é evidência de risco na política anterior, não um percentual ótimo aprendido. O registro `feedback_cura` conserva personagem, hunt, modalidade, sessão, contexto conhecido, configuração antes/depois, provas, relato, lacunas e resultado ainda não confirmado. A projeção em `modelo.json.feedback_cura` é consumida pelo planejamento. Originais, fases e previsões anteriores não são reescritos.

Na sugestão da sessão correspondente, até dois gatilhos de autocura podem usar os valores corretivos confirmados pelo usuário. A busca temporal parte dessa referência e não eleva os gatilhos limitados pelo feedback. Reduções adicionais continuam exigindo treino/seleção/teste e segurança por integrante, inclusive do próprio ED; emergências de autocura continuam elegíveis. Esse limite é uma restrição por risco relatado, não uma política com benefício validado. Fora da sessão, exige mesmo personagem, hunt, PT, Hazard e postura conhecidos e iguais. Contexto incompleto não autoriza transferir os percentuais para outra hunt.

O replay compartilha o relógio de cura de mas res/sio, respeita cobertura real do mas res e preserva autocura emergencial. Sem casts/HP suficientes no trecho anterior não há estimativa causal de atraso evitado, mortes evitadas ou melhoria posterior. O relato não preenche essas lacunas.

Caso de 14/10: mas res 95%→75%, exura vita 80%→70%, Restoration (exura max vita) preservada em 60%. Primeira imagem do conjunto final às 06:58:05; isso não identifica o início exato da alteração. A leitura antiga confundia os ícones de Mass Healing/Ultimate Healing/Restoration. Referências corrigidas e releituras versionadas preservam os registros e as provas originais. Percentuais são lidos no próprio campo, independentemente dos textos nas outras colunas.

## Comparação da roda com a configuração atual

Desde 13/10, `comparacao_atual` usa a roda equipada como referência, incluindo graus/modificadores de gemas lidos e bônus visíveis do painel. Bônus visível não identifica gema/domínio nem completa casas desconhecidas. Dano/cura fixos, bônus base, área, alvos e cooldown são dimensões separadas. Um cenário sem gemas não apaga as gemas da referência. A gema observada resolve o nome da magia pelo catálogo, sem depender de uma lista redundante de IDs.

Para ED em PT, sio II e cura crítica são requisitos das candidatas, inclusive no foco Dano. Modalidade desconhecida conserva essa proteção. Vantagem ofensiva não autoriza piorar a segurança de qualquer aliado. Sem roda/gemas completas, geometria candidata comprovada e comparação de HP mínimo/tempo crítico/cura útil, mostrar a candidata como cenário e manter a roda atual; não oferecer adoção como melhoria certificada. Personalização exige referência suficiente e no máximo dois ajustes.

A comparação separa quatro braços: RTC atual + roda atual, RTC otimizado + roda atual, RTC atual + roda candidata e RTC otimizado + roda candidata. A mesma política otimizada é usada nos dois braços correspondentes para isolar a interação, mantendo os limiares de cura. Quando há potência calibrada e janelas coincidentes, o replay conjunto compartilha mana/relógios e avalia segurança sem depender de críticos. Índice ofensivo previsto não é HP/kk por hora; ganho real de dano/cura permanece nulo até avaliação posterior à adoção. Falta de cura comparável não vira zero.

Solo e PT, hunt e Hazard têm perfis cronológicos separados em `combate_ml.contextos`; exemplos antigos sem contexto continuam preservados, sem transferência para contextos conhecidos. A coleta acrescenta a modalidade declarada no contexto da hunt. Resistência favorável ao gelo não justifica retirar Frigo II: comparar cobertura, alvos efetivamente atingidos, frequência e turnos perdidos por posicionamento com as forks e com o benefício comprado pelos pontos. Não presumir que toda criatura no battle foi atingida, nem reutilizar a geometria observada de uma roda para certificar outra.

A extensão de 12/10 está no [plano integrado](aprendizado-integrado-plano-20261012.md): combinações Revelation, residual por sessões e diário de Utamo com validação futura. Supplies separa estoque estimado, contador de uso e gasto total. XP exclusivamente do XP Analyser; dano recebido total do Input Analyser. Histórico sem origem de XP certificada fica preservado no arquivo original e fora das novas comparações. Testes sintéticos não comprovam benefício pessoal.

Fluxo: evidência → registro SQLite → fase válida no instante → consolidação pelas métricas canônicas → exemplos com aplicação comprovada → avaliação temporal → sugestão para a próxima hunt.

Coleta independe de confirmar uma sugestão. Retomada drena o atraso em lotes e deduplica eventos. Encerramento espera consumidores antes de consolidar. Estado coletando, pendente ou falhou impede a limpeza dos quadros ainda necessários.

`Registro` é o adaptador transacional. Ele fecha conexões em sucesso e exceção e oferece `backup(destino)` pela API SQLite. `avaliacao.py` descreve cobertura/segurança por integrante; ausencia de leitura não fabrica segurança. `modelos.py` preserva a validação cronológica e mantém perfis separados por configuração e estágio.

O refactor preserva as capacidades existentes; testes de software não comprovam melhora personalizada. Identidade/HP máximo de aliados, buffs/gemas, contadores por item e oportunidades ilegíveis permanecem desconhecidos quando as fontes não os comprovam. O monitor de aprendizado compartilha os quadros completos `q_` existentes; mede a cadência efetiva e mantém `f_` como alternativa. Isso não garante observação de cada turno.

Desde a implementação de 12/10, a calibração declara uso do conteúdo exato detectado, independentemente da sugestão e dos pontos da roda. RTC, Cura e Roda têm revisões e elegibilidade próprias; negativas distinguem outro RTC e RTC desligado. A declaração vale desde a resposta, sem aplicação visual fabricada nem confirmação retroativa do histórico. Releitura atualiza frescor sem abrir fase; quadro atrasado fica preservado sem substituir a leitura vigente.

Cadência entre casts permanece diagnóstica e nunca substitui cooldown do catálogo. Cura separa cronologicamente treino, seleção e teste. Métricas descritivas de vida/escudo e contadores por item têm paridade Python/JavaScript; ausência de contadores legíveis continua sendo lacuna. O contrato de efetividade avalia um pacote de alterações sem dividir artificialmente seu ganho entre perks.

O [estado da entrega](rtc-aprendizado-implementacao-20261012.md) distingue a ligação funcional de confirmação/aprendizado dos leitores, políticas e benefícios que ainda precisam de evidência.

Leitores de telemetria preservam provas e séries de contadores. A reserva de avaliação precede o teste final, que permanece selado no escopo da declaração; outra configuração abre outra reserva. Políticas de pressão usam episódios auditados independentes, com cobertura por integrante. A busca conjunta reavalia RTC, Cura e roda, mantém aquecimento dos relógios/recursos e limita a proposta personalizada a dois campos. Resultados posteriores da adoção confirmada geram avaliações versionadas e perfis por contexto, incluindo rejeições e resultados inconclusivos. Origem manual, geometria ou prontidão desconhecidas bloqueiam a certificação pertinente, sem interromper a coleta.

QA sintético não entra no inventário de treino. Fixtures carregam `qa` e `sintetico`. Cópias de uma sessão não podem ocupar treino e validação como sessões independentes. Na falta de suporte suficiente, manter a referência e a incerteza.

Estudos de previsto × observado preservam a previsão original, o modelo, unidade, contexto, fontes, IDs do treino e erro. Replays históricos são reconstruções cronológicas, não previsões emitidas no passado. Só observações anteriores ao início do trecho entram no treino. A referência descritiva por volta usa mediana histórica; uma mediana recente só substitui essa referência se melhorar os erros sequenciais anteriores, e sua avaliação ocorre nas voltas seguintes. Duração, raw, profit e supplies usam as métricas canônicas; dano/cura de console têm unidade explicitamente parcial. Lacuna não vira zero, configuração desconhecida não ganha atribuição e resultado previsto não comprova benefício do RTC.

Ao publicar cada volta, o programa registra previsões imutáveis para as próximas duas voltas, com o horizonte identificado. Isso permite uma previsão anterior ao início mesmo quando a detecção do fechamento chega depois que a próxima volta começou. Só considera uma previsão prospectiva se ela tiver sido emitida antes do início da volta avaliada. Previsões emitidas depois do início são replay; os erros não reescrevem previsões anteriores. Os estudos aparecem no planejamento com previsto, observado e erro. Modelos de cadência e rendimento também conservam esses campos em sua avaliação temporal, incluindo candidatos rejeitados. A coleta real continua nas novas hunts, sem alterar o RTC no jogo.

Desde 13/10, a roda Dano em ED/party prefere sio maior quando a potência ofensiva é equivalente, após a segurança medida. A busca inclui redistribuições completas com ressonância mais barata, preservando estágios, perks, ressonâncias, vida/mana/mitigação e reserva de 3. Essa preferência é do usuário; não certifica ganho pessoal nem autoriza perda ofensiva arbitrária. Redistribuições de vários campos continuam sendo várias mudanças, sem ocultá-las no limite de dois ajustes personalizados.

O estudo de sio compara cura aplicada e dano recebido do EK nos mesmos intervalos entre sios identificados, com identidade/vocação confirmadas. Associa cura a cast próprio somente quando não há ambiguidade com mas res/gran sio. Outras recuperações ficam separadas; representações duplicadas não são somadas. Console é parcial: silêncio não vira zero, redução de HP não vira dano e cura crítica não garante segurança. Métricas canônicas `balanco_cura`/`balancoCura` têm paridade. Modelos descritivos por fase usam treino anterior e teste posterior, com IDs/erros, sem fabricar cura base, HP máximo ou efeito causal de perk.

Estudos, exemplos e revisões de barras são anexados ao registro (`estudo_sio`, `amostra_sio`, `recurso_sio_revisado`), preservando originais e aprendizado anterior. A sugestão de gatilho é um candidato de teste quando déficit observado coincide com vida abaixo do gatilho conhecido; não é política pessoal certificada. Na sessão de 13/10, o candidato sio EK 80%→90% pode aparecer na sugestão da própria hunt para uso futuro. Gran sio EK 50% informado pelo usuário é mantido como referência atual, sem retroagir seu horário desconhecido ao replay.
# Calibração atual e semelhança da roda — 13/10/2026

O planejamento para uma hunt histórica usa o RTC e a roda atuais do mesmo personagem. Quando a vocação não aparece no cabeçalho, benefícios exclusivos reconhecidos identificam ED/MS; evidência ambígua não troca a referência. As leituras históricas e a declaração de uso permanecem intactas. Um slot vazio confirmado e a ausência do limiar de criaturas da SD não tornam o RTC incompleto.

“Similar à sugestão” compara benefícios principais lidos na calibração: Frigo e sio no mesmo estágio; forks, Twin e Blessing ativos, com no máximo um estágio de diferença, registrado em `variacoes`. Campos ausentes ou divergência nesses requisitos retiram o selo. O selo não confirma igualdade de estágios/gemas/casas, uso ou vantagem medida. Gemas e bônus diretamente lidos continuam na comparação; bônus da roda conhecidos podem aparecer separados de gemas pendentes.

A leitura de Vessels isola a coluna a partir dos cabeçalhos para evitar interferência dos botões à esquerda, incluindo dano/cura fixos e Heal Friend. A comparação exibe as tabelas e o selo; os parágrafos de cobertura, metodologia e lacunas abaixo delas foram retirados a pedido do usuário. As restrições continuam no cálculo e na API do módulo.
# Feedback após a hunt na página do histórico

## Avaliação observacional de cura — 14/10/2026

`planejamento/cura.py` avalia gatilhos usando vida percentual sincronizada do próprio
personagem e dos aliados identificados. Não depende de inventar HP máximo do EK.
Conta condições concorrentes de autocura/cura da party e urgências observadas sem
gatilho: vida posterior abaixo de 30%, ou queda de pelo menos 15 pontos percentuais
terminando abaixo de 60%. São critérios operacionais explícitos, não limiares ótimos.
O estudo não chama essas condições de turnos perdidos nem calcula mortes evitadas.

A busca avalia mudanças de 5 ou 10 pontos percentuais na referência, preserva
Restoration/gran sio e entrega no máximo um ajuste observacional. Exige 30 episódios
com provas, espaçados em pelo menos 6 segundos, pares separados por até 1,5 segundo,
fase igual sem fronteira incerta e combate identificado próximo. Não soma fases
ou Hazard diferentes para validar. Metade dos episódios treina, um quarto seleciona,
o restante testa. Uma candidata precisa melhorar seleção e teste sem aumentar
urgências sem gatilho de nenhum integrante. A saída é uma sugestão para testar,
não uma previsão contrafactual de HP, política ótima ou benefício real certificado.
O replay calibrado já existente continua separado e pode avaliar até dois ajustes.

Os estados `dados_insuficientes`, `sem_melhoria_demonstrada` e `sugestao_para_testar`
aparecem na interface com cobertura, lacunas e comparação. A configuração própria
é preservada como referência. Estudos antigos não alteram uma referência divergente.
`Registro.estudar_cura` persiste estudos versionados por sessão; a consulta histórica
não depende do contexto da última sessão aberta. QA fica fora dos estudos reais.

O consumidor `Observador.coletar_cura` lê a fila de quadros completos em ordem,
com cadência-alvo explícita de 1 segundo, preservando prova e revisão temporal.
O cursor só avança após persistência. O buffer e a limpeza respeitam esse consumidor;
atrasos permanecem pendentes. Não há segunda captura. A leitura de HP não depende
exclusivamente da cor verde: o texto integral alinhado à mana também é usado em
vida baixa. Glifos aceitam variação de até um pixel apenas com identidade única
e margem de pelo menos três pixels para outro caractere. Nomes ilegíveis continuam
desconhecidos; nenhum nome aproximado ganha vocação por receber sio.

Os nomes no mundo possuem formas de glifos diferentes das do console. O índice
inclui essas formas exatas; não completa letras ilegíveis por nomes da party.
Destinos identificados em casts próprios de sio continuam candidatos à leitura
da barra quando o nome está amarelo/vermelho. Isso não infere sua vocação.
Primeira/segunda regra de sio/gran sio só ganham EK/RP por associação explícita
em `cura_destinos.json`, sem confundir a lista compartilhada de nomes com regras.
Uma regra ativa sem integrante confirmado impede sugerir mudança parcial.
O estudo preserva a configuração completa, inclusive destinos não resolvidos,
e a consulta usa a data de processamento da revisão, separada da última amostra.
Percentual oculto numa regra posteriormente desabilitada pode usar o último valor
legível da mesma hunt como referência; isso não confirma uso nem reativa a regra.
O consumidor denso lê também o Hazard do próprio quadro, reutilizando os nomes
já decodificados, sem nova leitura completa do painel. Hazard desconhecido ou
divergente impede usar o par na comparação; a UI exige o mesmo Hazard do estudo.

O carregador do histórico transporta `feedback_cura` e `feedback_roda` da referência atual
do mesmo personagem, independentemente da disponibilidade de uma roda completa. O modelo
congelado da sessão permanece intacto; as correções posteriores são usadas na sugestão para
a próxima hunt e passam pelos filtros de personagem, sessão e contexto. Os testes de navegador
devem percorrer as duas consultas e o worker até os percentuais visíveis, além de testar o motor.

O relato de dano baixo e a troca de roda são intervenções do usuário. A configuração confirmada
após a troca substitui a referência atual, sem retroagir seus pontos, gemas ou efeitos para a
hunt inteira. Horário de adoção desconhecido permanece desconhecido. Relato negativo não treina
um ganho causal nem prova que a roda, isoladamente, causou o desempenho. O cache dos cenários
inclui os feedbacks; atualizar somente o modelo no disco não basta se a página descartar esses campos.

## Rejeição explícita de roda

O relato de desempenho insatisfatório deve alterar a seleção, e não apenas o texto da comparação. Uma rejeição vigente com prova e contexto identifica os benefícios da roda reprovada (estágios de conviction/revelation), independentemente do nome ou de pontos residuais. Essa combinação é excluída da busca e da personalização. O registro original permanece preservado.

O objetivo integra o contexto da rejeição: o feedback de 14/10 reprova Dano, independentemente do nome do preset testado. Registros legados sem objetivo valem para Dano; não excluem rodas de Cura. Os nomes pessoais dos presets não aparecem no painel de rodas.

A tela mostra a distribuição calculada e as variantes Sem gemas/Lesser/Regular/Greater, inclusive em Cura (Vida e Utamo). Após a rejeição em Dano, a proposta preserva os benefícios ofensivos e de suporte lidos na referência posterior, quando ela não é a própria roda reprovada. Os caminhos são reconstruídos com validação de conexões, ressonância e orçamento, reservando três pontos. Um caminho de ressonância superior também pode receber uma gema inferior; a busca não exige que a ressonância seja exatamente o tier escolhido.

Uma distribuição reconstruída não é a distribuição observada: a interface identifica os pontos calculados e mantém o ganho real não confirmado. O desenho e o código da candidata ficam disponíveis para comparação, mesmo sem evidência suficiente para recomendar a troca. A referência parcial e seus pontos/gemas ainda não lidos permanecem preservados como lacunas.

Feedback legado vale para a sessão de origem. Rejeição explicitamente marcada para próximas hunts também vale para o mesmo personagem, vocação, hunt, tamanho de party e Hazards registrados; lacuna ou diferença de contexto não autoriza transferência. A rejeição não atribui causalidade exclusiva à roda e não transforma a troca em resultado de treino positivo.

