# Aprendizado

Fluxo: evidência → registro SQLite → fase válida no instante → consolidação pelas métricas canônicas → exemplos com aplicação comprovada → avaliação temporal → sugestão para a próxima hunt.

Coleta independe de confirmar uma sugestão. Retomada drena o atraso em lotes e deduplica eventos. Encerramento espera consumidores antes de consolidar. Estado coletando, pendente ou falhou impede a limpeza dos quadros ainda necessários.

`Registro` é o adaptador transacional. Ele fecha conexões em sucesso e exceção e oferece `backup(destino)` pela API SQLite. `avaliacao.py` descreve cobertura/segurança por integrante; ausencia de leitura não fabrica segurança. `modelos.py` preserva a validação cronológica e mantém perfis separados por configuração e estágio.

O refactor preserva as capacidades existentes; testes de software não comprovam melhora personalizada. Continuam pendentes os aceites reais de aplicar/cancelar, identidade e HP máximo de aliados, consumo por tipo, buffs/gemas, política de risco e benefício em sessões posteriores. A captura de quadro cheio permanece em 4 s.

QA sintético não entra no inventário de treino. Fixtures carregam `qa` e `sintetico`. Cópias de uma sessão não podem ocupar treino e validação como sessões independentes. Na falta de suporte suficiente, manter a referência e a incerteza.
