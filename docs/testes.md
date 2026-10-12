# Harness

Entrada: `tools/verificar.ps1`; implementação portátil do runner em `tools/verificar.py`. Executar Python com cwd em `hunt-analyzer/`. Dependências diretas em `requirements-dev.txt` e resolução completa do ambiente validado em `requirements-lock.txt`.

| Perfil | Verificações |
|---|---|
| rápido | Sintaxe, lint de nomes/sintaxe, Python com branches, contratos/arquitetura/replay, JavaScript curto, trackers e snapshots |
| completo | Rápido + matriz completa da roda + navegador |
| Windows | Completo, exige Windows; supervisão real deve ser conferida na atualização |
| compilado | Suites + `--autoteste` do executável indicado por `-Executavel` |

O relatório grava versões, hash das fontes, estado por suíte, duração e código de saída. Estados: passou, falhou, inconclusivo por timeout. Teste ignorado faz a suíte Python reprovar; não é silenciosamente aprovado. Logs e relatórios ficam em `output/harness`, fora do Git.

Dados, fontes, configurações, captura, KS e auxiliador são redirecionados para temporários. Fixtures visuais incluem somente janelas/campos/barras, sem jogo, chat ou nomes; a hunt é inteiramente sintética. Não usar sessões pessoais como fixtures do clone.

Navegador usa HTTP real em porta efêmera, backend controlado e rede externa bloqueada. Cobre espera, voltas, raw estabilizada, seleção, histórico, evolução, altura real das barras, tela estreita, encerramento e recuperação após POST inválido. No Windows, usa Edge instalado se Chromium do Playwright estiver ausente. CI instala Chromium.

Cobertura de branches é publicada por módulo em `coverage.json`. Não impor percentual global como substituto das fronteiras de risco. Novas regras exigem testes de fronteira/falha e não podem reduzir a cobertura pertinente. Supervisão de uma janela Windows e benefício de aprendizado em hunts reais têm evidências próprias; navegador headless não os certifica.
