# Sessões locais e previsto × observado — 12/10/2026

Reaproveitamento autorizado pelo usuário, com continuidade nas novas hunts a partir de 13/10. Nenhuma captura foi iniciada nesta execução.

## Dados recuperados

- 44 sessões distintas, 793 voltas no inventário e 82 cópias deduplicadas. Uma cópia não conta como uma sessão independente.
- 70.897 registros existentes lidos na importação de eventos/recursos, com persistência por identidade. Essa contagem não representa necessariamente registros novos.
- 13.398 quadros de console reprocessados: 54 eventos adicionais e nenhuma falha final.
- 130 leituras adicionais de recursos recuperadas. Nenhum contador de Supply por item foi aceito nesses quadros; esse consumo continua desconhecido.
- 6.480 estudos por medida/volta, dos quais 3.676 têm previsto e observado comparáveis. Campos sem leitura permanecem desconhecidos.
- Cadência: 561 exemplos históricos, 113 comparações em teste posterior. Rendimento: 570 exemplos históricos, 110 comparações em teste posterior; nenhum perfil aprovado. Os diagnósticos históricos não foram promovidos como configuração aplicada ou ganho pessoal comprovado.

## Como a previsão se ajusta

Cada estudo guarda previsto, observado, erro, unidade, versão, origem e IDs das observações anteriores usadas. O previsto original permanece imutável. Nos replays, é uma reconstrução cronológica, sem usar dados posteriores ao começo da volta. A referência descritiva usa mediana; uma janela recente só substitui a referência se melhorar os erros anteriores. As próximas voltas avaliam a escolha feita. Isso aproxima previsões da experiência observada sem prometer erro zero.

As previsões por volta são distintas da previsão de execução do RTC. Não alteram cooldown, regras do jogo ou a configuração no cliente. Modelos de cadência e rendimento registram suas próprias comparações na avaliação temporal; candidatos rejeitados permanecem documentados. As novas sessões continuam submetidas às confirmações e critérios de validação de RTC, Cura e Roda.

Ao vivo, a publicação das voltas registra previsões para as próximas duas voltas, preservando horizonte e horário. Uma previsão só é prospectiva quando emitida antes do início do trecho alvo. Dano/cura parcial não vira total; zero observado e falta de leitura continuam distintos. Contextos conhecidos usam personagem, hunt, modalidade e origem da medida; contexto desconhecido fica restrito à sessão.

## Evidências locais

Resultados e diagnósticos em `output/aprendizado/20261012-previsto`, incluindo `resultado.json`, `estudos.json`, estudos por sessão, diagnósticos de cadência/rendimento e backups SQLite de antes/depois. Os backups foram conferidos por integridade; 156 provas adicionais foram copiadas e conferidas por hash, com manifesto próprio. A primeira tentativa de recuperação de recursos e consolidação teve erros internos; as correções foram testadas, os recursos foram recuperados novamente e todas as 44 sessões foram consolidadas. As tentativas anteriores continuam preservadas para auditoria.

Os dados estão no registro de aprendizado da instalação existente, sem apagar histórico, modelos ou provas.

## Verificação e atualização

Perfil rápido aprovado. Perfil completo da revisão final em `output/harness/previsto-completo-instalacao`: 142 testes Python e suites JavaScript, paridade, arquitetura, trackers e navegador aprovados, sem falhas ou ignorados. O teste de navegador verifica os valores previsto/observado e a tabela em tela estreita. Runtime da QA: `6fb272f8e3dad28807c1a3a048a5ac6a9366a0ab2dccbc2ae09d9952138a451d`; 205 assets do compilado conferidos com a lista de distribuição.

Compilado de `output/atualizacoes/20261012_previsto/build_final` aprovado em autoteste e smoke de 11 rotas. Atualização concluída em `C:/Users/User/AppData/Local/HuntAnalyzer`: 3 arquivos de produto substituídos, 28.614 pessoais preservados por hash e reversão autotestada. Manifesto em `output/atualizacoes/20261012_previsto/instalacao`. Nenhum Setup.exe, push ou captura real.

O smoke do instalado teve timeout na primeira tentativa de leitura HTTP. A repetição completa, sem alteração de código, passou nas 11 rotas, confirmação parcial, idempotência, rejeição de revisão obsoleta e encerramento pela API. Evidência final em `output/atualizacoes/20261012_previsto/smoke-instalado-final`; a tentativa anterior permanece preservada.
