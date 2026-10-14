# Implementação do aprendizado RTC — 12/10/2026

O pedido de implementação supera o escopo anterior de somente planejamento. A retomada solicitada após os outros agentes encerrarem as alterações acrescentou os leitores conservadores, validação reservada, busca de pacotes e acompanhamento posterior. A conclusão técnica e a atualização local são registradas abaixo; benefício pessoal continua dependendo de observações futuras, não dos testes de software.

## Retomada: implementação das etapas restantes

| Etapa | Ligação implementada |
|---|---|
| 1–3 | Revisões → declaração → fases → elegibilidade de RTC, Cura e Roda, sem confirmação retroativa |
| 4 | `observacao/telemetria.py` integrado aos mesmos q_/f_: identidade de ícone, contagem visual em segundos, contador de uso por item com unidade/série/reset, provas próprias e transições censuradas do escudo |
| 5 | `planejamento/oportunidades.py`: cooldown individual, grupo e grupo secundário, prontidão visual, mana, criaturas, geometria e bloqueios simultâneos; origem manual permanece distinguível |
| 6 | `planejamento/validacao.py` e `Registro.validar_execucao`: reserva anterior à avaliação, origens independentes, hipóteses escolhidas na seleção, baseline/modelo anterior, teste final selado e política de pressão auditada por integrante |
| 7 | `ui/personalizacao.js` e integração: subconjuntos, troca de magia/runa, prioridades, criaturas, limiares de cura e redistribuição válida da roda; no máximo dois campos; replay conjunto com aquecimento e treino/seleção/teste independentes |
| 8 | Sugestão registrada antes da adoção; comparação do pacote detectado e declaração exata; resultado de hunts posteriores ligado automaticamente ao registro; incerteza entre sessões, perfis por contexto e uso dos bônus por magia sem repartir dano total entre perks |
| 9 | Documentação, testes de limites/arquitetura, paridade, navegador, compilado, backup/restauração e atualização preservando dados |

### Condições para personalizar

O aplicativo coleta e treina os modelos pertinentes automaticamente depois de confirmar a leitura na calibração. Não inicia captura para testar a entrega e não muda o RTC no jogo. A sugestão inicial continua disponível.

A busca personalizada exige validação da execução no mesmo personagem, sessão, declaração e configuração, prontidão conhecida, alvos observados, mana e cobertura de saúde dos integrantes. Rejeição, leitura parcial ou ambiguidade mantêm a referência. Cada candidata conserva os limites do RTC, os desbloqueios e a distribuição válida da roda. Nenhum intervalo entre casts altera o cooldown normativo.

A auditoria interna de episódios usa `episodios_auditados.json` na pasta de configuração do personagem: origem, início/fim, personagem/sessão/escopo, provas e oportunidades ou rótulos independentes de pressão. O próprio classificador não fabrica esses rótulos. Ausência dessa evidência deixa a validação em coleta; não exige um painel de treinamento para o usuário.

O contador de Supply exige título, identidade textual do item e quantidade explicitamente associada a uso; gold e inventário não são convertidos em potions. Layout sem esses campos permanece desconhecido. Ausência do escudo exige uma referência certificada com duas âncoras visíveis (`estados_referencia.json`); sem ela, apenas presença é afirmada. Extremos e gaps preservam censura da duração. Esses limites de observabilidade não equivalem a zero uso, cooldown medido ou segurança.

Resultados posteriores só alimentam perfis quando exposição, contexto, política anterior, segurança, vigência e incerteza permitem a comparação. Hunts mistas não recebem atribuição integral nem rateio de totais. Benefícios simultâneos pertencem ao pacote; uma perk isolada exige contraste próprio. A personalização não promete ganho antes de novas hunts comparáveis.

## Comportamento entregue

- Calibração apresenta o RTC lido e permite confirmar uso, informar outro RTC ou RTC desligado. Cura e Roda são incluídas explicitamente, com leituras e lacunas apresentadas. Não depende de calcular uma sugestão ou informar pontos.
- API aditiva `declarar_uso` recebe personagem, sessão, revisões e resposta. Rejeita revisão obsoleta e sessão incompatível. Respostas idênticas são idempotentes; substituições preservam os registros anteriores. A confirmação legada continua sendo intenção de adotar uma sugestão.
- Leituras têm assinatura de conteúdo, revisão, identidade da observação, captura, processamento e última observação. Quadros antigos são preservados e não substituem a referência vigente. SD não exige um campo de criaturas inaplicável.
- Aprendizado ofensivo depende do RTC declarado; rendimento ligado à roda depende de RTC e Roda. Falta de Cura não bloqueia ambos. Eventos anteriores à declaração não entram nos novos exemplos. Calibração anterior pode ser associada explicitamente à sessão, sem mudar sua origem.
- Fases incluem declaração e revisões. Mudanças descobertas depois registram fronteira incerta. A interpretação das voltas identifica mudança/mistura sem ratear os totais originais.
- Monitor compartilha `q_`/`f_` existentes, sem segunda captura. Avaliação registra cadência efetiva e latência por fonte, sem inventar perda ou cobertura integral.
- Intervalo observado entre casts não muda cooldown. A escala de referência do modelo de rendimento usa somente treino; a cura separa treino, seleção e teste cronológicos.
- Oportunidades com casts observados registram bloqueios simultâneos e variáveis desconhecidas. Geometria, prontidão inicial e origem manual não são presumidas.
- Métricas canônicas descrevem episódios de queda, persistência por faixas e cobertura do escudo. Contadores por item exigem identidade, unidade, série e continuidade; resets, inventário e lacunas não viram consumo válido. Espelho e paridade em JavaScript.
- Contratos puros de efetividade registram objetivo, expectativa, adoção, resultado, incerteza e limites de atribuição. O registro SQLite preserva avaliações versionadas. Casts, usos elegíveis e contribuição incremental são distintos; dano total não vira ganho da perk.

## Pendências da primeira entrega — superadas pela retomada técnica

Na primeira execução, as etapas 1–3 constituíam a ligação funcional e as etapas 4–8 ainda não estavam integralmente integradas. A retomada acima implementou os mecanismos destas pendências. A certificação pessoal continua condicionada às provas e ao domínio de leitura disponível:

1. Leitores certificados de prontidão/contagem regressiva e contadores de Supply Analyser por item, com provas e fixtures; reconhecimento confiável de ausência do escudo e duração de ativações.
2. Calibração reservada das políticas de pressão/risco e validação da previsão da configuração atual. As faixas de vida são descritivas; nenhuma classificação de tranquilidade é certificada pela ausência de morte.
3. Busca personalizada de subconjuntos/prioridades/composição, pacote de roda e até dois ajustes, condicionada à validação da execução atual e a conjuntos cronológicos independentes. A busca inicial existente permanece disponível.
4. Ligação automática entre sugestão adotada e resultado de hunts posteriores para alimentar perfis de efetividade. O contrato persistente existe; promoção automática por perk não está habilitada.

É possível coletar e treinar os modelos existentes com o uso declarado depois de instalar a entrega. Sugestões iniciais continuam prontas. Melhoras personalizadas dependem de cobertura, exemplos pertinentes e validação posterior; os dados antigos não ganham confirmação retroativa.

## Verificação e instalação

### Conclusão da retomada

Em 12/10/2026, após o usuário informar que os outros agentes encerraram as alterações, a revisão estável foi validada e instalada no aplicativo do atalho em `C:/Users/User/AppData/Local/HuntAnalyzer`.

- Perfil rápido aprovado; perfil completo `output/harness/rtc-plano-integral-completo`: **134 testes Python**, suites JavaScript (incluindo personalização), arquitetura, paridade, trackers e navegador aprovados, sem falhas ou ignorados.
- Hash do runtime da verificação igual ao código final; assets do build conferidos byte a byte com a whitelist atual.
- Compilado de `output/atualizacoes/20261012_rtc_plano_integral/build` aprovado no autoteste e no smoke isolado de 11 rotas. Instalação e reversão passaram em autoteste; smoke do instalado também aprovado.
- Atualização trocou **6 arquivos de produto** e preservou **28.614 arquivos pessoais**, conferidos por hash. Manifesto e backup em `output/atualizacoes/20261012_rtc_plano_integral/instalacao`.
- Backups SQLite consistentes da instalação e do workspace restaurados em cópias e conferidos por integridade/contagens, em `output/atualizacoes/20261012_rtc_plano_integral/dados`.
- Nenhum Setup.exe, captura real ou alteração no RTC do jogo foi produzido. Nenhum push foi executado.

O aprendizado pode rodar na próxima abertura e hunt, depois de confirmar os componentes detectados. Os mecanismos de refinamento estão integrados; aceitar uma personalização exige a evidência e a validação descritas acima. Esta conclusão técnica não afirma que o histórico antigo ganhou aplicação confirmada ou que uma melhoria pessoal já foi demonstrada.

Usar o Python de `instalador/ferramentas/build312`; os ambientes padrão e `.venv` não tinham `ruff`/`coverage` na verificação inicial. Perfis rápidos/completos, navegador e autoteste compilado têm relatórios locais em `output/harness` e `output/atualizacoes`. A conclusão final da instalação deve ser registrada após essas verificações, com backup SQLite, restauração e hashes dos dados pessoais. Não gerar Setup.exe.

### Evidências da primeira execução — anteriores à retomada

- Perfil rápido aprovado; várias rodadas completas aprovadas, incluindo `output/harness/rtc-aprendizado-instalacao-v5` com 115 testes Python e testes JavaScript, paridade, trackers e navegador sem falhas/ignorados.
- Compilado `output/atualizacoes/20261012_rtc_aprendizado/build_v5/hunt_launcher.dist/HuntAnalyzer.exe` passou no autoteste e no smoke isolado de 11 rotas, confirmação parcial, idempotência, negativa e rejeição de revisão obsoleta. Nenhuma captura real foi iniciada.
- Backup consistente e restauração conferidos dos bancos da instalação e do workspace em `output/atualizacoes/20261012_rtc_aprendizado/dados`.
- **Instalação não atualizada:** alterações concorrentes de outros trabalhos mudaram o runtime durante sucessivas verificações/compilações. O atualizador rejeitou a diferença de hash antes de substituir arquivos. O último build não certifica a revisão posterior do código. Revalidar uma revisão estável e compilar/testar o correspondente antes de atualizar o atalho.
- O programa foi encerrado pelo usuário, que informou não estar caçando. Estado de gravação não foi interpretado como prova de combate.
