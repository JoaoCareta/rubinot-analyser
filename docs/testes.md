# Harness

Retenção de gravações: testes verificam preservação após consumo concluído, pendência, falha e estado desconhecido; retomada conserva os quadros além do antigo buffer de 60 s. Replay testa agrupamento de sessões, deduplicação q/f, passagem da meia-noite, lacunas, sessão sem imagens e rejeição de caminhos externos. O navegador valida abertura do PNG real, avanço, reprodução e aviso de lacuna. O autoteste compilado exige retenção permanente e o asset de replay.

Entrada: `tools/verificar.ps1`; implementação portátil do runner em `tools/verificar.py`. Executar Python com cwd em `hunt-analyzer/`. Dependências diretas em `requirements-dev.txt` e resolução completa do ambiente validado em `requirements-lock.txt`.

| Perfil | Verificações |
|---|---|
| rápido | Sintaxe, lint de nomes/sintaxe, Python com branches, contratos/arquitetura/replay, JavaScript curto, trackers e snapshots |
| completo | Rápido + matriz completa da roda + navegador |
| Windows | Completo, exige Windows; supervisão real deve ser conferida na atualização |
| compilado | Suites + `--autoteste` do executável indicado por `-Executavel` |

O relatório grava versões, hash das fontes, estado por suíte, duração e código de saída. Estados: passou, falhou, inconclusivo por timeout. Teste ignorado faz a suíte Python reprovar; não é silenciosamente aprovado. Logs e relatórios ficam em `output/harness`, fora do Git.

## Rastreabilidade e incidentes

O relatório schema 2 identifica cada execução. `fontes-inicio.json` e `fontes-fim.json` registram os hashes dos arquivos rastreados e não ignorados pelo Git, incluindo testes, ferramentas e documentação. Alteração, inclusão ou remoção durante o QA reprova `integridade-fontes`, mesmo quando todas as suítes passam. O hash do runtime também é reconferido. A comparação de início/fim detecta mudanças persistentes; para isolamento de trabalhos concorrentes, executar um snapshot próprio e preservar a identificação da fonte entregue. Não alegar que esta checagem detecta uma alteração transitória revertida entre as duas leituras.

Reutilizar `-Saida` preserva a primeira tentativa e cria uma subpasta `tentativas/<id>`; o runner imprime o caminho efetivo. Não agregar aprovações de revisões diferentes. Testes ignorados e falhas esperadas não certificam aceite. `python-testes.json` relaciona os testes efetivamente executados e seus estados.

`tools/incidentes.json` liga cada incidente ao critério de aceite, IDs de testes Python, suítes JavaScript e marcos do navegador em `e2e-incidentes.json`. Um teste removido/renomeado ou marco não alcançado reprova o aceite no completo; atualizar a associação somente quando a regressão equivalente continuar existindo. O rápido registra aceites dependentes de navegador como parciais, sem certificar o fluxo visual. O perfil compilado não substitui o completo.

| Incidente | Proteção obrigatória |
|---|---|
| Feedback de cura perdido no histórico | Carregador e worker reais exibem 75/70/60; origem informada não vira ganho validado |
| Plunder filtrado | Espécie rara atravessa recorte e renderização; selo por sessão, sem inventar abates |
| XP e PT cortados | Scrollbar, quarta linha parcial e lacunas não produzem números/membros falsos |
| Rejeição da roda | Restrição contextual de Dano sem bloquear Cura |
| Barras invisíveis | Altura efetiva nas duas posições e igualdade de cores/larguras |
| Gravações apagadas | Preservação em todos os estados e replay com lacunas |
| Adoção presumida | Leitura parcial/obsoleta não confirma conjunto nem uso retroativo |

`tests/integration/test_rastreabilidade_entrega.py` usa pacotes fictícios e pastas temporárias: bloqueio de executável/asset alterado, arquivo extra, QA incompatível, mutação concorrente, exclusão mútua entre processos, reversão, preservação de dados e diagnóstico de timeout. Nenhum teste executa ou atualiza o aplicativo pessoal.

Antes de corrigir um dado ausente, seguir prova → persistência → API → carregador/worker → tela. Manter fontes específicas, contexto e lacunas em cada passagem. Testes sintéticos certificam comportamento, não benefício real de RTC/roda/cura.

Dados, fontes, configurações, captura, KS e auxiliador são redirecionados para temporários. Fixtures visuais incluem somente janelas/campos/barras, sem jogo, chat ou nomes; a hunt é inteiramente sintética. Não usar sessões pessoais como fixtures do clone.

Navegador usa HTTP real em porta efêmera, backend controlado e rede externa bloqueada. Cobre espera, voltas, raw estabilizada, seleção, histórico, evolução, altura real das barras, tela estreita, encerramento e recuperação após POST inválido. No Windows, usa Edge instalado se Chromium do Playwright estiver ausente. CI instala Chromium.

Regressão de estabilidade visual: na calibração, retém uma resposta de referências e confere identidade dos cards, altura da fonte, foco e texto em edição; simula falha e recuperação sem apagar os cards. Em Magias/RTC/Roda, confere que trocar categoria, atualizar só o horário da leitura e receber outras combinações do lote não substitui a roda exibida nem reinicia o cálculo do RTC.

Cobertura de branches é publicada por módulo em `coverage.json`. Não impor percentual global como substituto das fronteiras de risco. Novas regras exigem testes de fronteira/falha e não podem reduzir a cobertura pertinente. Supervisão de uma janela Windows e benefício de aprendizado em hunts reais têm evidências próprias; navegador headless não os certifica.

Cards de sugestões: conferência por campo com ícone acessível, incluindo leituras parciais, antigas, desativadas, destinos EK/RP e ausência de leitura. Ajustes mostram anterior → sugerido em uma linha, com indicação de próxima hunt. O selo da roda conserva o critério de semelhança existente e usa somente ícone. Semelhança não confirma uso nem ganho. Layout responsivo mantém valores e ícones dentro dos cards.

Histórico de sio: regressões de EK/RP, ator e destino exatos, deduplicação, prioridade de releitura, exclusão de QA, zero versus lacuna, limites do trecho e meia-noite. Paridade das faixas Python/JavaScript; navegador cobre API real, seleção do integrante/horário, tela estreita e ausência de diagnósticos internos no RTC.

Histórico de curas: todos os jogadores confirmados, destinatário exato, vocação desconhecida preservada, tabela visível após dano, ícones locais carregados e detalhes por horário em desktop/tela estreita.


Regressão de XP histórico: `test_fontes_paineis.py` verifica fallback antigo identificado, prioridade de releitura comprovada, zero válido, lacuna atual e preservação do resumo. `tools/e2e_evolucao.py`, integrado ao perfil completo, confere quebra de curva nas lacunas, zero medido, contagem de sessões medidas e painel próximo do fim separado da taxa típica.

Smoke nativo: arquivos HTTP usam conexão HTTP/1.1 persistente, como o navegador, com limite de 10 s, Content-Length e conteúdo exato. urllib força fechamento e pode cortar a cauda no Windows (limitação documentada no Handler); diagnósticos preservam transporte e bytes recebidos, inclusive falhas anteriores.

O hash de runtime inclui hunt_launcher e suas dependências tanto no harness quanto no build. Regressão: incluir explicitamente o launcher nas entradas do compilador não altera a identidade. A entrega de Sio usa snapshot congelado; nele, o fluxo de QA/atualização adota explicitamente as mesmas entradas nativas usadas na compilação.
