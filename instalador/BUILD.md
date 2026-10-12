# Instalador Windows

Desde 09/10/2026, alterações no programa pessoal são atualizadas diretamente na
instalação existente. Não gerar Setup nem copiar instalador para a Área de Trabalho
sem novo pedido de distribuição. Use `--apenas-compilar` para produzir e validar
somente o aplicativo. A atualização copia os arquivos do build, preservando os
arquivos pessoais da instalação e guardando uma cópia dos arquivos substituídos.

Distribuição para amigos: `saida/HuntAnalyzer-Setup.exe`. O ZIP antigo é legado.

O motor e os módulos locais são compilados pelo Nuitka em um executável nativo.
Python, bibliotecas e dados públicos acompanham o instalador; os amigos não
precisam instalar Python. HTML/JavaScript e dados do catálogo continuam visíveis.
Compilação dificulta engenharia reversa, mas não é criptografia nem garantia
contra cópia. O instalador ainda não tem assinatura digital do autor.

## Remontar

De `D:\Documentos\rubinot\hunt-analyzer`, execute:

```powershell
& '..\instalador\ferramentas\build312\Scripts\python.exe' ..\instalador\montar_wizard.py --versao 1.0.0
```

O ambiente de build usa Python 3.12, Nuitka e as dependências do programa.
As versões usadas ficam em `requirements-build.txt` (instalar com `pip install -r`).
O Inno Setup portátil fica em `ferramentas/inno`; `--iscc` permite outro caminho.
O Nuitka baixa seu compilador MinGW na primeira execução e guarda seu cache em
`ferramentas/nuitka-cache`.
As ferramentas e as pastas `build` não devem ser enviadas aos amigos.

`montar_wizard.py` usa a lista aprovada e o fecho de imports de `montar_pacote.py`,
recusa dados pessoais/fontes Python no resultado, inclui licenças de terceiros,
executa o autoteste compilado e gera `saida/manifesto.json` com SHA-256 e versões.
`--sem-compilar` apenas reempacota um build existente: não incorpora alterações
posteriores no código.

## Funcionamento

`hunt_launcher.py` despacha os subprocessos com `--processo app/capture/lap_watch/ks`.
`runtime.comando` mantém os comandos Python no desenvolvimento e usa o próprio
executável na distribuição. O supervisor reconhece ambos e continua salvando
a hunt ao fechar a interface. O instalador fica no perfil do usuário, onde o
programa pode escrever os dados. Atualizações e desinstalação não removem
arquivos de calibração e histórico criados pelo usuário.

## Validação de 08/10/2026

Setup de 51,5 MB. Autoteste nativo, importação do motor, subprocesso KS,
servidor sem gravação, sete páginas/APIs, encerramento, instalação, atualização
e desinstalação passaram. O teste removeu Python do PATH do executável e usou
calibração/histórico fictícios para confirmar a preservação. O resultado está
em `build/qa-resultado.json` e no manifesto da distribuição. Não substitui o
teste de captura de uma hunt real em outro PC, com calibração própria.
