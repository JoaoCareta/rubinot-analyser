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
