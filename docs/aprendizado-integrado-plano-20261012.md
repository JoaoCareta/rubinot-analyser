# Implementação do aprendizado de RTC roda e Utamo

Preparar a coleta da hunt de 13/10/2026 e tornar as recomendações sensíveis às combinações de benefícios da roda. O aprendizado atual permanece como referência; modelos novos precisam vencer a referência em sessões posteriores para serem usados. A implementação foi autorizada em 12/10, incluindo o auxiliador sonoro de Utamo.

## Mecânicas e critérios

- Revelation por domínio: 250/500/1000 pontos desbloqueiam I/II/III. Bônus fixos de dano e cura: 4/9/20, somados entre domínios. II + I resulta em 13, enquanto apenas II resulta em 9. Não são percentuais, Base Power ou aumento da vida máxima. III pode superar combinações menores; quantidade de benefícios não decide sozinha.
- Healing Link é Conviction, não Revelation; sua cura depende de sio/gran sio e do déficit de vida. Avatar e Gift of Life não ganham utilização fictícia por estarem desbloqueados. Distinguir benefício passivo, condicional e ativado.
- RTC disputa oportunidades com mana, alvos e relógios próprios/compartilhados. Lacunas e origem manual não demonstram a política do RTC. Roda candidata não muda a configuração atual usada para aprender.
- Utamo aprende qualidade/antecedência dos avisos, duplicações e resposta observada. Ausência de dano depois do som não comprova que o som salvou o jogador; ausência de resposta não significa aviso inútil. Vida de emergência e arbitragem de um som por vez continuam protegidas.

## Sequência executável

1. Ampliar busca de rodas com sementes de combinações de estágios em todos os domínios, preservar diversidade, caminhos válidos e orçamento total menos três. Expor bônus fixo e benefícios condicionais sem misturar unidades. Regressões II + I versus II, limites de pontos, ED/MS e gemas.
2. Acrescentar avaliação conjunta dos benefícios, com métricas explícitas de bônus fixo e limites quando falta conversão para HP. Não atribuir dano ofensivo a Healing Link/Avatar sem oportunidade. Mostrar a composição e o motivo da escolha no planejamento.
3. Acrescentar motor puro de aprendizado residual com regularização por contexto, avaliação cronológica por sessão e previsão anterior ao resultado. Conservar catálogo/modelo vigente na insuficiência de evidência; alimentar automaticamente pelos exemplos reais existentes, sem QA nem confirmação retroativa.
4. Integrar diário persistente do auxiliador: observações, decisão, som emitido/suprimido, versão da política, contexto, frescor e resultados posteriores. Treinar candidatos em sessões anteriores e comparar com a referência em sessões independentes. Congelar a política durante cada sessão; promoção só para sessão futura. Aprender redução de repetição sem silenciar emergência nem inventar cooldown/prontidão.
5. Testar limites, ausência de dados, falsos ganhos, contaminação temporal, reutilização de sessão, persistência e recuperação. Executar perfil rápido e completo, compilar aplicativo, autotestes, smoke e atualização reversível do atalho preservando hashes pessoais e backup SQLite.

## Arquitetura e aceites

Regras puras em Planejamento/Assistência, armazenamento em adaptadores e composição nos consumidores existentes. Sem novas capturas, dependências pesadas ou serviços externos. Registro de treino identifica fontes, contexto, corte temporal, versão e comparação com a referência. Eventos brutos e modelos anteriores são preservados.

Amanhã o aplicativo deve coletar sem esperar uma personalização aprovada. Estados distintos: coletando, avaliado sem melhoria, candidato aprovado no contexto. Nenhum teste sintético certifica benefício pessoal. Seleção futura de experimentos por otimização bayesiana ou bandits permanece condicionada a diversidade e suporte; esta entrega implementa o ciclo verificável que os alimenta, sem experimentação automática no jogo.

## Supplies e integração da conversa anterior

Conversa integral conferida: Implementar melhorias do plano RTC, ID 01a13181-221c-7550-b2b8-e9e9b38a90fe, 15 turnos até as imagens de supplies e preço. Correções posteriores prevalecem: Ice Burst começa em 5+ em Carrinho 1, HZ 4, PT x4 de ED. Comparar 2+ exige previsão preservada e validação em outra hunt, sem aplicar automaticamente.

- Gasto total do Hunt Analyser/Party Hunt já é válido mesmo sem saber o item. Manter gold, quantidade, estoque e mana em unidades distintas; não dividir todo o supplies pelo preço de uma potion.
- Leitor visual de hotkeys deve identificar ícone + contador; guardar estoque, horário, identidade e prova. Ultimate mana potion a 488 gold é preço observado na imagem do usuário em 12/10, não preço universal nem equivalência garantida ao valor configurado no Supply Analyser.
- Consumo por contador de uso é confirmado. Queda de estoque é estimativa: reposição, movimentação, desaparecimento, mudança de layout e lacunas abrem segmentos e impedem atribuição automática. Aumento de estoque é reposição/movimentação, não consumo negativo. Valor ausente não vira zero.
- Magic Shield Potion e magia Utamo Vita têm origens distintas; subida do escudo não identifica qual delas foi usada. Cruzar consumo estimado, casts, mana, vida e proteção com suas respectivas incertezas.
- Aprender gasto por minuto/volta e comparar configurações equivalentes. Mana Leech, dano, cura e proteção podem mudar o consumo conjuntamente; economizar potions só é ganho quando a produção e a margem de segurança permanecem adequadas.
- Registrar matriz de observabilidade nos estudos: RTC/Cura/Roda confirmados; contadores e painéis legíveis; alvos, orientação e cooldowns desconhecidos; cobertura de saúde por integrante. Suave/pressionada exige política validada e cobertura. Pods, esquivas e críticos especiais do Hazard permanecem não certificados até haver leitores específicos validados; HZ é apenas o nível observado dos membros atuais da PT.

Aceites adicionais: delta de estoque contínuo, reset/refill, lacuna, duplicação de ícone, leitura inválida, preço ausente, discrepância de custo e recurso de proteção não atribuível. Coleta integrada aos quadros compartilhados; estudo de supplies consultável no planejamento. Reprocessamento antigo não inventa confirmação de configuração nem preço retroativo.

## Referências

- [CipSoft sobre bônus Revelation](https://www.tibia.com/news/?id=7071&subtopic=newsarchive) e [planejador oficial](https://www.tibia.com/community/?subtopic=wheelofdestinyplanner): regras versionadas no catálogo local; conferir cada efeito sem generalizar versões antigas.
- [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml): modelos simples, infraestrutura e métricas antes de complexidade.
- [PyMC partial pooling](https://www.pymc.io/projects/examples/en/latest/case_studies/hierarchical_partial_pooling.html): compartilhar evidência com regularização, sem equivalência automática entre contextos.
- [Validação temporal](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html): futuro separado do treino, complementado aqui por grupos de sessões.
- [SHAP e causalidade](https://shap.readthedocs.io/en/latest/example_notebooks/overviews/Be%20careful%20when%20interpreting%20predictive%20models%20in%20search%20of%20causal%20insights.html): previsão não prova efeito de uma intervenção.

## Estado

Plano executado e instalação do atalho atualizada em 12/10/2026. Verificação completa: 161 testes Python, paridade, arquitetura, matriz da roda ED/MS, testes JavaScript, trackers e navegador aprovados. Executável compilado com autoteste aprovado; 8 arquivos de produto atualizados, 4.224 pessoais preservados por hash e reversão testada. Provas em `output/atualizacoes/20261012_ml_integral/qa-final/resultado.json` e `instalacao/manifesto.json`. Nenhum Setup.exe foi gerado; nenhuma captura do jogo foi iniciada.

## Correções finais e fontes obrigatórias

Tibia Global é a referência do RubinOT, conforme decisão do usuário. O catálogo incorpora os ajustes oficiais de 2026 (CipSoft 8833, lançamento 8849) e o planejador oficial. Regras catalogadas, efeitos modelados e dados observados são camadas distintas; não afirmar cobertura integral de todas as mecânicas sem implementação e teste.

XP vem exclusivamente do XP Analyser. O Hunt Analyser fornece os outros números. Leitura antiga de XP no Hunt e multiplicadores presumidos saem dos cálculos. Arquivos históricos são preservados; XP sem origem certificada fica fora das novas comparações.

Dano recebido total e Max-DPS vêm do Input Analyser. A distribuição visível e a prova também são registradas; ícone não identificado e percentual ilegível permanecem desconhecidos. Deltas por volta exigem fronteiras legíveis e ausência de reset observável. Utamo prioriza o delta recente do Input quando existe continuidade. O log permanece complementar e parcial, nunca somado ao total do painel.

A Magic Shield Potion é o item com **17 unidades à direita de F4**, identificado pelo usuário. Custa **1 Silver Token por unidade**, conforme [CipSoft](https://www.tibia.com/news/?id=5836&subtopic=newsarchive). Token a **0,06 kk** é o preço informado pelo usuário em 12/10, usado como custo estimado de reposição. Ultimate mana potion: 488 gold mostrados no market. Os itens azul/verde inicialmente investigados foram removidos das referências desta entrega.

## Cobertura da entrega

- Roda: combinações Revelation, caminhos/gemas válidos, diversidade da busca e composição dos benefícios. II + I soma 13 HP fixos por aplicação, contra 9 de II. HP fixo desempata potência equivalente; não é somado a Base Power nem convertido em ganho causal.
- Residual: regularização por contexto/faixa, voto por sessão, treino/seleção/teste separados e pelo menos seis sessões. Seus registros são replays identificados, separados das previsões prospectivas por volta. Testes sintéticos não aprovam um modelo pessoal.
- Utamo: diário de observações, avisos e supressões; política congelada por sessão/contexto; intervenções/lacunas censuram negativos. Emergência de vida e arbitragem de sons preservadas. Ajuste aprendido exige prontidão positiva e ausência de escudo certificada; sem isso continua coletando.
- Supplies: Ultimate e Magic Shield Potion, referências pessoais, estoque separado de contador de uso e gasto em gold, refil/lacuna sem consumo fabricado, provas preservadas.
- Painéis: XP exclusivo do XP Analyser; Input para dano recebido; Hunt/Party para os demais totais conforme modalidade. Informações e incertezas ficam vinculadas ao quadro.
- Limites explícitos: pods, esquivas e críticos especiais do Hazard ainda não têm leitor específico; alguns ícones, alvos, orientação e prontidão permanecem desconhecidos. Cobertura insuficiente impede classificar a hunt como suave ou afirmar otimização pessoal comprovada.

Para 13/10: confirmar RTC, Cura e Roda; iniciar a coleta normalmente e manter o auxiliador ligado para seu diário. Ice Burst continua em 5+ na referência inicial. Mudanças futuras exigem números, no máximo dois ajustes, sem aplicação no jogo durante a hunt.
