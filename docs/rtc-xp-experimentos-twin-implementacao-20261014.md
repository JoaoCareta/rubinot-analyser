# RTC e experimentos da Twin por XP

Implementação de 14/10/2026. Provas de verificação e revisão entregue em `output/rtc_xp_twin_20261014/`. O estado da instalação e das verificações está no relatório de entrega dessa pasta; código preparado não equivale a instalação aprovada.

## Coleta e confirmação

O monitor tem consumidores separados para configuração e combate. `fila_rtc.sqlite3`, na pasta da gravação, guarda recibos por personagem e quadro. Processa q_ e f_ em ordem de captura, inclusive quadros atrasados e sessões encerradas; só confirma consumo depois da leitura persistida. `coleta_rtc.json` guarda pendências, atraso e falha. Recibos não autorizam exclusão: a retenção permanente continua vigente. Uma abertura inteiramente entre capturas permanece uma lacuna (cadência alvo 0,5 s).

Leituras iguais atualizam a última observação sem gerar configuração nova. Imagens de configuração modificada ficam preservadas, inclusive as anteriores ao estado atual. Identidade determinística da prova torna retomadas idempotentes. Registros `configuracao_leitura` permitem reconstrução temporal sem substituir o passado pela configuração final. Leituras tardias reconstroem a avaliação da hunt encerrada; avaliações derivadas são identificadas pelas fontes e preservam os registros originais. O comparativo contém componentes e campos independentes: a Twin legível pode conferir mesmo com a roda parcial/reprovada. Configuração visível não confirma ativação automática; declarações continuam com origem identificada.

Na tela do RTC, a última Twin e a sugestão da próxima hunt são atualizadas antes da consulta aos resultados da roda. O ícone ✓ confirma exclusivamente o valor legível. Horário, lacunas de aplicação, falha e atraso de leitura são explícitos. RTC ou Twin desativados não recebem confirmação visual de uso. Estudos, treinamento e análises retrospectivas ficam internos.

## Períodos e medidas

`planejamento/twin.py` reconstrói períodos cronologicamente por RTC, cura, roda, composição, Hazard, rota e interferências conhecidas. Mudanças visuais têm fronteira incerta entre a última leitura igual e a primeira diferente. Um intervalo ou volta atravessando essa fronteira é excluído, sem rateio. Ausência de contexto não autoriza comparação.

`hunt.metricas.taxas_intervalos` é canônico, exposto pela fachada ao_vivo e espelhado em `ui/taxas.js`. Cada numerador usa somente o próprio tempo coberto; zero é válido, lacuna não é zero. XP usa delta de RawXPGain do XP Analyser. Party Hunt fornece dano próprio e da PT, com integrantes integralmente identificados. Contadores reiniciados, intervalos mistos e sobrepostos não entram. A coleta prospectiva exclui lacunas de contadores maiores que 30 s. Battle List não fornece alvos atingidos nem dano da Twin.

Os recortes de 13 e 14/10 são importados como `twin_retrospectiva`, com fontes, imagens, hashes, intervalos, deltas originais e ressalvas. A união de 5+ é ponderada pelo tempo; não serve como validação causal nem como fase prospectiva. O corte de 07:56 é informado e analítico, representado pelos quadros de 07:55:58,556. A leitura de 9+ às 07:45:16 é preservada. Hazard 5/6 impede tratar o agrupamento dos dias como contexto equivalente.

## Experimentos prospectivos

A referência escolhida é 5+ no contexto informado. 4+ e 6+ são candidatos, sem ganho prometido. Uma proposta só é preparada depois de uma referência recente e identificada. Registro, observação, avaliação, resultado negativo/inconclusivo e confirmação posterior são fatos distintos; não há alteração do cliente.

Critérios definidos antes da avaliação: três voltas completas no mesmo período, pelo menos 80% de cobertura de XP e vida por integrante, leitura de vida com intervalos de até 2 s, mínimo observado acima de 30%, nenhuma morte confirmada e uso declarado/aplicado. A comparação também exige mesma rota, roda, composição, Hazard e interferências. A segurança é observacional e amostrada; lacunas impedem recomendação. Não deriva ausência de crises da ausência de registros.

Margem mínima de XP: 2% da referência, ampliada pela metade da amplitude das taxas das voltas de referência. Incerteza do candidato usa metade da amplitude das próprias voltas. Mais dano não compensa perda de XP. Piora de vida também bloqueia promoção. Resultado promissor precisa de outra hunt posterior, sem reutilizar a mesma sessão como confirmação. Pior/inconclusivo mantém a referência vigente, inicialmente 5+. Uma confirmação independente pode promover 4+ ou 6+ somente naquele contexto. Um candidato já avaliado não é novamente selecionado usando a mesma referência; uma nova referência permite outro teste.

`experimento_twin` acrescenta operação compatível na API de configurações. Ao preparar o teste, os campos observados de RTC e cura são mantidos e somente o limiar da Twin muda; propostas gerais de roda não são incorporadas ao experimento. Critérios insuficientes mantêm a coleta interna e a referência, sem sugerir benefício validado.

## Validação

Regressões cobrem janela real aberta brevemente e processada após fechar, retomada/falha/quadro atrasado, leituras parciais e idempotência, concordância sem roda/cura, ativação desconhecida, fases mistas, prioridade de XP, variação e cobertura, confirmação em sessão independente e paridade de métricas. O navegador verifica atualização da Twin sem resultado da roda e sem selo em campo ilegível. Testes usam pastas temporárias e rede local simulada.

Antes de atualizar o atalho: perfil completo da revisão entregue, compilado/autoteste, cópia de reversão, hashes dos dados pessoais e conferência na aplicação instalada. Timeout, falha ou teste ignorado impede aprovação geral. Não gerar Setup.exe nem publicar em main.

## Entrega conferida

Atalho atualizado em 14/10/2026. A revisão fixa `9d2a13d0da76f782515629d7dc0f6e018fe6a1396171f9ad9cfc325a70e8a923` passou nos perfis rápido e completo, autoteste do compilado, conferência HTTP do pacote e da instalação, reversão e navegador com histórico real em três larguras. Os 9.472 arquivos pessoais foram preservados. Os 336.462 registros anteriores permanecem intactos; três fatos retrospectivos foram acrescentados com hashes das provas conferidos.

A tela histórica mantém 9+ às 07:45:16 e a referência 5+, sem selo indevido nem confirmação de ativação. A última leitura global 2+ da sessão posterior não foi substituída pelo histórico. Não houve alteração do RTC no jogo. Não há ganho observado de 4+/6+. Evidências e limites: [relatório de entrega](../output/rtc_xp_twin_20261014/entrega.json). Este registro de entrega foi escrito após a aprovação; o pacote corresponde ao snapshot identificado, conservado no relatório.
