# Refactor de 12/10/2026

Planejamento de origem: `output/arquitetura/2026-10-12/PLANO.md`. Evidências locais: `output/refactor/20261012/`; essas evidências e os backups não entram no Git.

| Entrega | Estado |
|---|---|
| Backup de fontes e SQLite consistente | Executado; snapshots recuperáveis fora do Git |
| Git principal e exclusões pessoais | Criado com marco anterior à migração; party permanece independente |
| Harness, dependências, fixtures e CI | Implementados; 94 testes Python, zero ignorados, sintaxe/lint, sete suites JS, trackers, arquitetura/paridade e E2E |
| Documentação e linguagem | README, instruções, contratos, donos, decisões e runbooks |
| Persistência e HTTP | IDs completos; reserva no mesmo segundo; gerações completas; JSON 400/413; temporários únicos |
| Regras da hunt | Métricas puras, fachada preservada; cobertura de linhas/branches de métricas em 100% |
| Observação/configuração/aprendizado | Leitores e concordância separados; composição fora de configuração; SQLite separado de avaliação; ciclo de cinco módulos eliminado |
| Conflitos e assistência | Contextos próprios com fachadas; retenção pendente e árbitro de apito protegidos por regressão |
| Interface | Aplicação em escopo fechado; módulos de cards, grade, histórico, planejamento e apresentação; API pública `HuntApp` |
| Trackers e limpeza | Seis funções comuns com SHA-256; check solo atual; fontes antigas sem consumidores retiradas com recuperação no marco Git |
| Party | Token e ETag testados em branch separada publicada no [PR rascunho #1](https://github.com/JoaoCareta/loe-hunt-tracker/pull/1); main/VPS preservadas |
| Aplicativo compilado | Build sem Setup e autoteste nativo aprovados; atualização usa QA da mesma revisão e conserva dados |
| Publicação principal | Aguardando nome/URL do remote privado; workflow preparado, execução remota ainda não comprovada |

O harness completo aprovado está em `qa-final/resultado.json`. A medição de cobertura não é uma nota global de qualidade: existem caminhos legados ainda sem cobertura suficiente, registrados por módulo. As fachadas preservam CLIs manuais; não houve exclusão em massa de ferramentas fora do grafo.

A migração estabeleceu fronteiras verificáveis, mas não declara concluídos os aceites futuros do aprendizado em hunts reais. Também não certifica a autenticação efetiva do proxy da VPS nem captura/supervisão de uma sessão de jogo real por E2E headless. Esses limites não são convertidos em aprovação automática.

Atualização local concluída na instalação do atalho: 12 arquivos de produto, 65.660 arquivos preexistentes fora do produto preservados por hash; autotestes do build, da instalação e da reversão aprovados. O binário instalado respondeu às 11 rotas verificadas em modo isolado, incluindo os novos assets e recuperação de JSON inválido. Encerramento pela API foi exercitado na distribuição de teste, com raízes temporárias. Nenhum Setup foi gerado.

Clone limpo do commit a4d0a62 validado em ambiente virtual novo, com dependências instaladas do arquivo de requisitos: 94 testes Python, sete suites JavaScript, sintaxe/lint, contratos, snapshots e navegador passaram sem banco, calibração ou configurações pessoais. Dependências de verificação também foram fixadas em `requirements-lock.txt`. O CI do tracker da party aprovou o commit ad88113. O repositório principal foi publicado como privado em [JoaoCareta/rubinot-analyser](https://github.com/JoaoCareta/rubinot-analyser), com pipeline de verificação a cada push.
