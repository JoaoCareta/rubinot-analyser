# Atualização local

Build do aplicativo, sem Setup.exe:

```powershell
cd hunt-analyzer
<python-do-build> ../instalador/montar_wizard.py --apenas-compilar
```

O empacotamento calcula imports de pacotes e entradas tardias por AST; assets vêm de whitelist. Não usa um caminho fixo do dono. Distribuição compilada não inclui fontes Python nem dados pessoais. HTML e JavaScript permanecem visíveis.

Antes de substituir: harness completo, autoteste do compilado, snapshot das fontes, backup consistente do banco, manifesto dos arquivos da instalação e hash dos pessoais. Não substituir executável durante uma hunt. Conferir o atalho para encontrar a instalação real.

Atualização copia somente os arquivos de produto validados. Arquivos pessoais ficam no lugar e seus hashes são comparados depois. O motor entra na próxima abertura. Testar abertura sem gravação, HTTP, encerramento, autoteste e reversão numa cópia de teste. Manter o backup da instalação anterior fora do Git.

Não executar Inno Setup nem copiar instaladores para a Área de Trabalho sem novo pedido de distribuição.

## Proveniência da entrega

`montar_wizard.py` compara fontes/testes e runtime antes e depois do build. Somente uma compilação estável e aprovada no autoteste gera `instalador/build/proveniencia.json`, fora do pacote distribuído. O documento vincula fontes, executável, assets e demais arquivos pelos hashes; versões anteriores permanecem em `build/proveniencias/`. `--sem-compilar` exige uma proveniência já existente e compatível, sem atribuir a um binário antigo as fontes atuais. Compilação legada sem esse documento precisa ser refeita para entrar no novo fluxo; não fabricar o manifesto a partir de um executável existente.

Ordem de entrega: estabilizar snapshot → compilar sem Setup → executar completo sobre as mesmas fontes/testes → smoke do pacote → atualizar → smoke instalado e conferência visual pertinente. Executar o completo antes da compilação também é válido se as fontes/testes permanecerem idênticos até a entrega. Todos os comandos Python partem de `hunt-analyzer/`.

```powershell
<python-do-build> ../tools/atualizar_local.py --build <pasta-do-pacote> --instalacao <instalacao-do-atalho> --qa <resultado-completo.json> --saida <evidencias-da-entrega>
```

Os argumentos anteriores continuam disponíveis; `--proveniencia <arquivo>` permite indicar outro local. Por padrão procura `proveniencia.json` na pasta mãe do pacote. Relatórios antigos sem hashes finais/schema 2 não aprovam novas entregas. O atualizador confere todas as suítes e a identidade das fontes/testes, além do runtime; um `ok` isolado não é suficiente.

O atualizador mantém uma trava do sistema operacional por instalação, liberada inclusive após queda do processo. Uma segunda atualização falha sem copiar arquivos. O pacote é copiado para preparação temporária, conferido contra a proveniência e usado como fonte estável. Antes da primeira substituição, reconferem-se QA, pacote e arquivos de produto existentes na instalação. A cópia verifica hashes individuais; o manifesto final compara todo o produto entregue, preserva QA/proveniência usados e registra a reversão. Aplicativo aberto continua bloqueando este fluxo. Saída de evidências deve ficar fora da instalação e do pacote.

Não usar o hash de arquivos voláteis de uma captura ativa para alegar preservação integral; banco exige backup consistente. Mudanças somente de interface em outra entrega devem conservar o executável existente e documentar sua compatibilidade e os assets exatos, sem apresentar uma fonte Python preparada como compilado instalado. Esta alteração do harness não atualiza automaticamente instalações nem recompila aplicações.

## Diagnóstico e linguagem do aceite

`nativo_smoke.py` grava `http.json` com URL, timeout, duração, fase de conexão/leitura, bytes, status HTTP e estado do processo. Mantém `nativo.log` e grava `nativo.json` também quando falha. Respostas 400 provocadas pelos cenários negativos aparecem no rastreio e são verificadas pelo cenário. Tentativas posteriores usam pasta própria; o caminho efetivo é impresso. O diagnóstico não aumenta timeouts nem repete silenciosamente uma rota após falhar, exceto a espera inicial já existente pela abertura do servidor.

Separar no relato: implementado, testado, instalado, conferido na tela e benefício observado. `conferido_na_tela` e `beneficio_observado` permanecem falsos no manifesto automático: autoteste e smoke não comprovam esses estados. Falha/timeout permanece como evidência, mesmo se uma repetição posterior passar. Alterações concorrentes fora do snapshot não recebem aprovação por associação.
