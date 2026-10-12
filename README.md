# RubinOT Hunt Analyzer

Aplicativo local para observar o jogo, analisar hunts e preparar configurações de combate. O programa usa imagens e logs como evidência; não aplica comandos ao cliente. Interface em pt-BR, valores em kk e vírgula decimal.

## Desenvolvimento no Windows

Requisitos: Python 3.12, Node 24 e Git. Todos os comandos Python rodam dentro de `hunt-analyzer/`.

```powershell
cd hunt-analyzer
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
cd ..
.\tools\verificar.ps1 -Python .\hunt-analyzer\.venv\Scripts\python.exe -Perfil rapido
```

O perfil completo inclui a matriz da roda e navegador:

```powershell
.\tools\verificar.ps1 -Python .\hunt-analyzer\.venv\Scripts\python.exe -Perfil completo
```

Para abrir o aplicativo em desenvolvimento: entre em `hunt-analyzer/` e execute `python hunt_launcher.py`. Para abrir apenas o servidor sem captura: `python app.py --sem-gravacao --sem-observacao --sem-navegador`. O atalho do usuário continua usando a instalação compilada.

## Estrutura

- `hunt-analyzer/rubinot/`: contextos de negócio, adaptadores e composição.
- `hunt-analyzer/ui/app`, `ui/features`, `ui/shared`: interface por funcionalidade.
- `hunt-analyzer/tests/`: contratos, arquitetura, integração e fixtures.
- `tools/`: harness, navegador e manutenção dos componentes compartilhados.
- `docs/`: arquitetura, linguagem, contratos, operação e decisões.
- `instalador/`: fontes do build; não contém a saída compilada no Git.
- `loe-hunt-tracker-solo/`: consumidor local, com testes sobre SQLite temporário.

`loe-hunt-tracker/` mantém Git próprio e não faz parte deste repositório. O contrato de sincronização de componentes está em [docs/trackers.md](docs/trackers.md).

Calibração, configurações, quadros, histórico, provas, bancos e modelos pessoais são excluídos do Git. Um clone inicia sem esses dados e os testes não precisam deles. Consulte [a documentação](docs/README.md).
