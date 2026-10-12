# Decisões arquiteturais

| ADR | Decisão aplicada | Motivo e consequência |
|---|---|---|
| 001 | Monólito modular local, seis contextos | Preserva execução no PC e limita dependências por significado |
| 002 | Evidência e fase temporal | Configuração futura não reescreve passado; desconhecido não é aplicado |
| 003 | Métricas canônicas com espelho verificado | Tela e consumidores usam os mesmos denominadores |
| 004 | Sessão completa e publicação por geração | Evita colisão por minuto e snapshot parcialmente visível; legado continua legível |
| 005 | Manifesto de runtime/CLIs | Não excluir ferramenta apenas por estar fora do grafo do aplicativo |
| 006 | Fixtures isoladas e atualização reversível | Testes sem histórico pessoal; hash/backup antes da instalação |
| 007 | Aprendizado com origem e QA separado | Teste de software não comprova ganho personalizado |
| 008 | Git privado e party independente | Dados fora do índice; main da party não recebe push automático |
| 009 | Pacote em `hunt-analyzer/rubinot` e fachadas | CLIs/Nuitka continuam funcionando sem instalação editable; pastas vazias não são arquitetura |
| 010 | Snapshots gerados dos trackers | Fonte comum com hashes; cada consumidor mantém diferenças de domínio |

Decisões futuras devem registrar contexto, alternativas relevantes, efeitos, contratos e reversão. Regras vigentes prevalecem sobre decisões históricas substituídas.
