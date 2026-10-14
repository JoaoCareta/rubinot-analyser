# RubinOT

Escrever em pt-BR. Números em kk, nunca M; vírgula decimal.

- Ler a memória deste workspace em `C:/Users/User/.claude/projects/D--Documentos-rubinot/memory/MEMORY.md` quando existir, incluindo feedbacks. Não aplicar memórias da ZoneSoft.
- Todos os comandos Python devem ter cwd em `hunt-analyzer/`.
- Métricas: `rubinot.hunt.metricas`; fachada `ao_vivo.taxas/especies`; espelho `ui/taxas.js`. Alterar os dois e executar a paridade. Lacuna é diferente de zero.
- Não alterar o RTC no jogo durante uma hunt. Sugestões são para a próxima hunt e exigem números, no máximo dois ajustes.
- Estudos, treinamento, diagnósticos e modelos de ML ficam internos, sem exposição na interface. Histórico de sio/vida mostra somente registros da hunt e suas lacunas.
- Nunca apagar histórico, aprendizado, configurações ou provas. Limpeza de quadros deve respeitar consumidores pendentes e o estado de coleta.
- Gravações e quadros completos não expiram: excluir somente após solicitação explícita do usuário para a gravação em questão. Consumo concluído e disco baixo não autorizam limpeza automática.
- Atualizar a instalação do atalho preservando dados. Não gerar Setup.exe sem pedido de distribuição.
- Manter APIs e CLIs compatíveis. Classificar ferramentas pelo `runtime-manifest.json`; arquivo fora do grafo não comprova código morto.
- Não introduzir ciclos nem imports de adaptadores nas regras puras. Testes usam dados temporários e rede simulada.
- Verificação: `tools/verificar.ps1 -Perfil rapido`; antes de atualizar, perfil completo e autoteste do compilado. Falha, timeout ou teste ignorado impedem aprovação geral.
- Aceite pertence ao snapshot: fontes e testes estáveis do início ao fim, proveniência do pacote e hashes instalados correspondentes. Usar a trava de `tools/atualizar_local.py`; não copiar uma revisão concorrente sobre a entrega validada. Procedimento em [docs/atualizacao.md](docs/atualizacao.md).
- Antes de atribuir perda à coleta, rastrear prova → persistência → API → carregador/worker → tela. Incidentes relevantes entram em `tools/incidentes.json` com regressão comportamental; UI exige dimensões efetivas e fluxo real.
- Distinguir implementado, testado, instalado, conferido na tela e benefício observado. Configuração informada, candidata e melhoria validada são estados distintos; não retroagir adoção nem inferir objetivo pelo nome de preset.
- Priorizar produção de XP, depois dano, com segurança como restrição. Feedback e rejeição respeitam personagem, objetivo, contexto e vigência.
- Memórias novas devem indicar decisão vigente e o que substituem, preservando o histórico. Detalhes ficam nos contratos/documentação, sem duplicar narrativas no AGENTS.md.
- Preservar o Git independente do tracker da party. Não fazer push em main: ele dispara deploy na VPS.
- Alterações de comportamento atualizam documentação e testes. Detalhes em [docs/README.md](docs/README.md).

As decisões vigentes acima complementam as instruções fornecidas pelo usuário; estas têm precedência. `CLAUDE.md` preserva o histórico das decisões do workspace e não é copiado para o repositório.
