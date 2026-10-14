# Hazard no contexto do aprendizado

O indicador fica junto ao personagem. O número só é aceito com o ícone real, glifos legíveis e associação única ao nome; jogadores de outra party e números de dano não definem o Hazard do personagem. Ausência de leitura permanece desconhecida, inclusive fora de uma região certificada. HZ 4 declarado para a próxima hunt não preenche o histórico.

## Mecânica e fontes

- Gnomprona inclui Carrinho 1 / Monster Graveyard, Carrinho 2 / Crystal Enigma e Carrinho 3 / Sparkling Pools.
- A qualificação máxima é desbloqueada com The Primal Menace; o nível ativo é selecionado com Gnomadness. São conceitos diferentes. Em party, vale o menor nível e o indicador mostra o efetivo. Não calcular o mínimo entre estranhos visíveis.
- Hazard afeta dano recebido, críticos de criaturas, esquiva, Primal Pods/Fungosaurus, experiência e encontro com Plunder Patriarch. Nada disso prova pressão pessoal sem medir vida, mana, cura e exposição.
- A CipSoft alterou dano/esquiva em 2022 e escalas em 2023; números antigos não são coeficientes vigentes. Em [29/07/2025](https://www.tibia.com/news/?id=8472&subtopic=newsarchive), reduziu o dano nos hazards menores que 12, preservou o nível 12 e aumentou acima dele; XP base das criaturas subiu 7,5%. Desde 01/09/2026 o bônus de loot por Hazard foi removido; XP não foi afetada por essa mudança. Coeficientes exatos de XP, dano, crítico, dodge e pods permanecem nulos nesta implementação, sem fórmulas presumidas.

Fontes consultadas em 12/10/2026: [CipSoft: lançamento](https://www.tibia.com/news/?id=6816&subtopic=newsarchive), [CipSoft: Hazardous Journey](https://www.tibia.com/news/?id=6735&subtopic=newsarchive), [CipSoft: ajustes de 2022](https://www.tibia.com/news/?id=6910&subtopic=newsarchive), [CipSoft: escalas de 2023](https://www.tibia.com/news/?id=7176&subtopic=newsarchive), [CipSoft: loot em 2026](https://www.tibia.com/news/?id=8945&subtopic=newsarchive), [regras da party e pods no anúncio traduzido](https://tibiawiki.com.br/wiki/Updates/12.90). O anúncio traduzido de 2022 mantém benefícios antigos; aplicar a mudança oficial de 2026.

## Implementação

O observador usa o mesmo quadro e o layout da sessão. Registra número efetivo, personagem, região, origem, horário e prova; preserva indicadores sem associação como inconclusivos. Uma leitura válida conserva a imagem em provas. Não inicia captura adicional nem altera o cliente.

Correção de 12/10: leituras de Hazard ficam restritas ao personagem próprio e aos nomes identificados no painel Party Hunt do mesmo quadro. Indicadores de estranhos ou sem associação única não entram nem na lista numérica de integrantes. Não usar a união histórica de aliados/KS como roster atual. Um integrante identificado pode fornecer o indicador efetivo quando o próprio está encoberto; divergência entre os indicadores da PT fica inconclusiva, sem calcular mínimo entre leituras inconsistentes. Sem painel legível, apenas o próprio personagem é elegível.

Com essa correção, a prova de 08/10 às 07:58:32 permite ler HZ 3 pelo integrante Sorcniel, identificado no painel da PT do mesmo quadro. Os indicadores 8 dos jogadores de fora foram excluídos. Essa referência pontual continua sem cobertura para rotular todas as voltas.

O estudo por volta exige ao menos 80% de cobertura temporal com intervalos de até 6 s e Hazard constante. Esse é um critério de qualidade de observação, não um limite de segurança da hunt. Troca de nível torna a volta mista; lacunas não são preenchidas pelo último print. O treino descritivo separa personagem/hunt/PT/área/Hazard/versão de regras/origem da métrica. Hazard desconhecido em Gnomprona fica restrito à sessão. Previsões originais permanecem preservadas; a coluna Hazard acompanha o previsto/observado. Perfis de rendimento de combate sem contexto correspondente não são transferidos para um Hazard conhecido.

O painel mostra a última leitura com esse rótulo; não promete que ela ainda seja atual. A configuração do RTC e cura permanece uma sugestão para a próxima hunt. O Hazard sozinho não muda limiares nem transforma classificação inconclusiva em suave.

## Evidência e limites

Uma prova de KS de 08/10 no Monster Graveyard contém indicadores 8 e 3 em jogadores diferentes. O leitor identifica quatro ícones e associa com segurança apenas Sorcniel, HZ 3, nessa imagem. O nome do personagem próprio está sobreposto. Portanto essa prova não permite declarar o Hazard da sessão inteira nem reinterpretar os 18,19 kk/h como HZ 4. A imagem original permanece preservada; a referência pública extraída contém apenas o ícone e o teste contém apenas o indicador, sem nomes.

Nesta entrega o Hazard entra nas observações e no aprendizado descritivo de voltas. Reconhecimento visual de pods, esquivas e críticos especiais e modelos causais de diferença entre níveis continuam dependentes de novos leitores/evidências; não estão implementados. O modelo não estima um percentual de risco a partir do nível sozinho.

## Verificação

Perfil rápido final aprovado em `output/harness/hazard-rapido-final`; perfil completo da revisão final aprovado em `output/harness/hazard-revisao-final`, com 146 testes Python sem falhas/ignorados, suites JavaScript, paridade, arquitetura, trackers e navegador. O teste de interface inclui HZ 4 na tabela em tela estreita. Testes específicos cobrem ícone real, associação ambígua/estranho, números com dois dígitos, mudança de Hazard, gaps e separação de treino sem reescrever previsões.

Build final em `output/atualizacoes/20261012_hazard/build`, autoteste nativo aprovado e 124 assets da whitelist conferidos por hash sem divergência. Smoke do compilado aprovado nas 11 rotas, com dados temporários e encerramento via API em `smoke-build`. Backup SQLite do aprendizado conferido por integridade antes da atualização. A primeira tentativa do rápido usou Python sem ruff/coverage; a execução completa no ambiente configurado passou. A primeira preparação do build encontrou pasta pai ausente; a pasta foi criada e os builds posteriores passaram. Esses registros permanecem preservados.

Instalação do atalho atualizada: 5 arquivos de produto, 28.616 pessoais preservados por hash, autotestes e reversão aprovados. Manifesto em `output/atualizacoes/20261012_hazard/instalacao`. Nenhuma captura foi iniciada, nenhum Setup.exe foi gerado.

Smoke da instalação final aprovado nas 11 rotas, com dados temporários e encerramento via API: `output/atualizacoes/20261012_hazard/smoke-instalado/nativo.json`.

Revisão do filtro exclusivo da PT aprovada em `output/harness/hazard-pt-completo`: 146 testes Python, JavaScript, paridade, arquitetura, trackers e navegador. Compilado e instalação passaram no autoteste e nas 11 rotas do smoke nativo. Instalação atualizada em `output/atualizacoes/20261012_hazard_pt/instalacao`, com um arquivo de produto alterado, 28.616 arquivos pessoais preservados por hash e reversão testada. Backup do aprendizado conferido por integridade. Nenhuma captura foi iniciada.
