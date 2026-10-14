# Dados e recuperação

Extensão integrada: `contexto_hunt.json` publica contexto da sessão; recursos guardam `paineis.xp` e `paineis.input`; SQLite separa `estoque_item` de `contador_item`. `supplies_referencias.json` é pessoal por personagem, com identidade, ícone, glifos, prova e preço datado. `residual_exemplos.json`, `residual_modelos/` e `residual_vigente.json` preservam avaliações; `assistencia/*.jsonl` registra observações e avisos, congelando a política por sessão/contexto. Nada disso entra no pacote distribuível.

Git guarda fontes, documentação, assets de produto e fixtures sanitizadas. Não guarda `capture`, `hunt_data`, `KS`, `configuracoes_player`, bancos, modelos pessoais, calibração, prints, logs, perfil do navegador, ambientes, builds ou backups.

As pastas pessoais não foram movidas. O resolvedor atual permite raízes por ambiente: `HUNT_DATA`, `HUNT_CAPTURAS_RAIZ`, `HUNT_CONFIGURACOES_RAIZ`, `HUNT_APRENDIZADO_RAIZ`, `HUNT_FONTES_RAIZ`, `HUNT_KS_RAIZ` e `HUNT_AUXILIARES_CONFIG`. Sem overrides, os caminhos antigos continuam valendo.

Backup do aprendizado: usar `Registro(raiz).backup(destino)` enquanto o aplicativo pode escrever; copiar apenas o `.sqlite3` aberto não substitui a API de backup. O backup precisa passar `PRAGMA integrity_check`. O teste restaura o snapshot numa raiz temporária e compara registros.

Para recuperar a instalação: encerrar o aplicativo, restaurar os arquivos alterados listados no manifesto da atualização e executar o autoteste. Calibração, números, provas e aprendizado continuam na instalação; não restaurar dados antigos por cima de novas hunts. Reversão de schema exige uma cópia compatível e não autoriza apagar registros atuais.

Gerações incompletas do histórico não são publicadas. Gerações anteriores permanecem recuperáveis; nenhuma limpeza delas foi automatizada nesta mudança. Desde a decisão de 14/10/2026, gravações e quadros completos são permanentes: só podem ser excluídos após solicitação explícita do usuário para as gravações em questão. A política anterior de remover quadros após consumo está superada, inclusive para sessões antigas ainda existentes.

`capture/session_*/q_*.png` guarda cada quadro completo capturado, sem expiração de 60 s; `f_*.png` e recortes continuam compatíveis com os leitores. Não há corte automático em três horas. A reserva de 10 GB interrompe a coleta sem apagar dados. A captura mantém a privacidade do jogo em primeiro plano e a cadência alvo de 0,5 s; processamento, alt-tab, indisponibilidade da fonte ou disco baixo podem gerar lacunas. Não é um vídeo de alta frequência nem possui áudio.

O histórico oferece **Rever gravação da hunt**, com seleção de trecho, reprodução, avanço quadro a quadro, horário e acesso ao PNG original. A consulta reúne as sessões agrupadas da hunt, combina `q_` e `f_` sem duplicar instantes e sinaliza lacunas maiores que 1,5 s. Trechos sem quadros são explicitados; imagens já apagadas pela versão antiga não podem ser reconstruídas. As rotas de consulta são somente leitura e restritas à raiz de capturas. `limpa_quadros(manter, raiz)` permanece compatível, retornando `(0, 0)` sem remover arquivos. Nenhuma rotina nova de exclusão foi criada.

A modalidade é exibida como `solo` ou `pt xN`, sem usar o nome do personagem como substituto. Modalidade ausente aparece como `modalidade não lida`. Uma contagem de membros ilegível não comprova solo. Correções confirmadas pelo usuário preservam o resumo original em backup e não alteram medidas ou provas da hunt.

Dano e cura usam os acumulados do Hunt Analyser em solo e do Party Hunt em grupo. O Server Log permanece como evidência parcial separada de dano observado, golpes, críticos, fatais e maior golpe; nunca substitui nem é somado ao dano do painel. `estatisticas_party` mantém seu nome por compatibilidade e informa `fonte_dano`, inclusive `Hunt Analyser` em solo. Leitura ausente preserva a última medida válida do segmento; uma redução legível abre novo segmento de reset. Party Hunt vazio depois da saída da PT não substitui o acumulado de grupo. Nome confirmado independe de todos os dígitos estarem legíveis. Dano/h não é dano acumulado. Painéis antigos sem dano/cura não são preenchidos por estimativa retroativa.

## Espécies raras na área ativa

As espécies predominantes usadas para reconhecer uma mudança de área não formam uma lista
exclusiva. Voltas inteiramente posteriores à fronteira preservam todas as espécies reconhecidas,
inclusive aparições raras. A tela reúne essas observações com a composição dominante da área.
Na volta que atravessa a fronteira, a atribuição continua parcial, sem transportar espécies
da área anterior por suposição. Avistamentos não certificam número de criaturas mortas.

Em 14/10/2026, o Plunder Patriarch já estava salvo na volta 22 da sessão iniciada às 06:25:04,
mas era ocultado pelo filtro da área ativa. O clipe fornecido pelo usuário confirma a presença
por volta de 08:00:38. A correção preserva os registros e as provas originais.


### Recuperação da raw XP histórica (14/10/2026)

Na consulta do histórico, releituras comprovadas do XP Analyser têm prioridade. Para sessões até 12/10/2026, os valores salvos pelo coletor anterior são mantidos como `Registro antigo` quando não há releitura. Esta exceção autorizada para recuperar o histórico não altera a coleta atual, exclusiva do XP Analyser. `ui/xp_releituras.json` guarda revisões separadas; os resumos e provas originais permanecem intactos. A revisão também vale para a lista/Evolução, antes da união de sessões, evitando números diferentes da tela detalhada.

Painéis próximos do fim são registrados com horário, origem e prova. Seus acumulados podem começar antes da gravação e suas taxas têm outra janela: aparecem em coluna própria e na dica do gráfico, sem dividir o acumulado pelo tempo das voltas nem substituir a taxa típica. Onde não há medida, o gráfico interrompe a linha e mostra “sem leitura”; zero medido continua sendo zero.
