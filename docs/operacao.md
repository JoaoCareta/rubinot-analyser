# Operação

Gravações pós-hunt: abra a hunt no histórico e expanda **Rever gravação da hunt**. Escolha o trecho, arraste o seletor ou avance quadro a quadro. A imagem original pode ser aberta em outra aba. A gravação amostrada fica preservada até uma solicitação explícita de exclusão, sem expiração ao encerrar ou iniciar outra hunt. Lacunas são sinalizadas; mantenha o jogo à frente para capturar. Se o disco atingir a reserva mínima, o aplicativo avisa e interrompe novas capturas sem apagar as anteriores.

Releituras de XP ficam em `ui/xp_releituras.json`, arquivo pessoal por gravação e fronteiras exatas da volta. Exigem provas de quadros do XP Analyser. Corrigem os valores efetivos sem apagar cards, resumos ou previsões originais; uma revisão posterior não transforma previsão ausente em previsão prospectiva.

XP Analyser: o recorte deve terminar antes da seta da scrollbar. Na referência de 13/10 (janela 1936 × 1048), a região começa em x=187 e termina em x=344, largura 157; largura 158 inclui parte da seta ao lado de Raw XP Gain e invalida a linha. Não remover `?` do texto para recuperar números. A correção é na geometria, preservando a rejeição de dígitos desconhecidos. Releituras de quadros existentes continuam distintas das previsões originais.

Para 13/10: confirmar RTC, Cura e Roda, manter XP Analyser, Input Analyser e contadores das hotkeys visíveis, iniciar a hunt normalmente e manter o auxiliador ligado para seu diário. Sem leitura segura o estado permanece desconhecido. Magic Shield Potion: 17 unidades à direita de F4 na imagem fornecida; reposição por 1 Silver Token, 0,06 kk informado em 12/10. Nenhum ajuste automático do RTC no jogo durante a hunt.

O atalho abre a instalação compilada diretamente no navegador. O supervisor é invisível. Fechar a janela ou Desligar salva a hunt e encerra os processos do aplicativo. Minimizar conserva a execução. Clique repetido traz a janela existente.

O ícone da janela vem do favicon declarado em todas as páginas (`ui/hunt_analyzer_icone.png`); o ícone do atalho/executável é configurado separadamente em `instalador/assets/hunt-analyzer.ico`. Manter ambos com a mesma arte. Após atualizar a interface, recarregar a janela para o navegador buscar o favicon.

A calibração mostra a fonte da análise à esquerda e as referências de RTC, cura e roda à direita (em telas pequenas, os blocos ficam empilhados). As datas de referência manual guardada e última leitura são separadas: uma leitura automática não significa que o usuário marcou uma referência. Cada atalho abre o tipo escolhido para o personagem da fonte. A tela de configurações tem retorno explícito à calibração no cabeçalho.

Mudança de área dentro da mesma gravação exige mudança sustentada de andar e monstros: janela de 90 s, pelo menos oito leituras cobrindo 30 s, com 75% das leituras no novo andar e com novas espécies. Mudar só o andar (como nas Livrarias) ou ver um monstro de passagem não separa a hunt. A tela ao vivo recorta voltas e trilha para a área atual, mostra seu andar e espécies, e reinicia a estabilização de raw. Volta atravessando a fronteira é parcial, sem ratear números. A gravação completa e as fronteiras ficam preservadas no histórico; `areas_observacoes.jsonl` guarda as observações compactas, sem abrir captura adicional.

Iniciar hunt abre sessão nova; Encerrar conserva o servidor e guarda histórico. Reiniciar encerra a análise atual e volta a observar. Não iniciar uma segunda captura manual se o aplicativo está gravando.

Encerramento: interromper produção de quadros, drenar consumidores, guardar números e mapas, consolidar aprendizado, somente então autorizar limpeza. Se a extração falhou, conservar quadros e corrigir o consumidor; não apagar a sessão para esconder o erro.

Capture/lap_watch/KS continuam sendo entradas do dispatcher compilado. CLIs e ferramentas manuais estão classificadas em `runtime-manifest.json`. Os nomes antigos permanecem executáveis pelas fachadas. Usar caminho completo ao iniciar processo manual para permitir sua identificação pelo supervisor.

Interface e API podem ser verificadas sem jogo com `app.py --sem-gravacao --sem-observacao --sem-navegador`. Não usar esse modo para medir desempenho de captura real.
# Seletor Hunt/KS

Correções de integrante declaradas pelo usuário ficam em `ui/party_correcoes.json`, por ID exato da gravação e com origem `usuario`. Não são inferidas de cura, proximidade ou roster de outra hunt. A classificação efetiva exclui episódios causados somente por esses aliados; os episódios originais ficam em `episodios_reclassificados`, com provas preservadas. Intrusos reais em episódios mistos continuam classificados como KS. A tela consulta a declaração também com o motor anterior em execução, sem interromper captura; o motor atualizado aplica a mesma declaração aos relatórios. O arquivo é pessoal e não entra na distribuição.

O card lateral só mostra o seletor quando a sessão tem algum episódio de KS. Sem KS, mostra diretamente a Hunt, inclusive quando a preferência salva era KS. Os botões retangulares seguem o estilo de ED/MS, com ⚔️ Hunt e KS. KS usa um único ícone vetorial de caveira atravessada por faca, inspirado na referência do BOPE pedida pelo usuário; o mesmo desenho aparece no selo do histórico, substituindo os dois emojis. O texto KS e os rótulos acessíveis continuam identificando a ação. Um episódio novo continua abrindo KS automaticamente; a escolha manual é preservada nas atualizações do mesmo episódio.

Em Magias e elementos, os botões MS/ED dividem toda a largura disponível. MS usa o ícone de Hell's Core (UE de fogo) e ED usa Eternal Winter (UE de gelo).

Magias e elementos, RTC e Roda de habilidades têm painéis independentes que expandem/recolhem pelo título. A preferência fica guardada neste navegador. Ações do cabeçalho têm 44 px de altura e 148 px de largura. As qualidades Sem gemas, Lesser, Regular e Greater dividem igualmente o espaço; em tela estreita ficam em duas colunas. Ícones são os sprites de Mystic Gem (ED) e Sage Gem (MS), preservados em PNG local.

As doze combinações de rodas são preparadas em segundo plano para as voltas concluídas e a configuração consultada: Dano e Cura (Vida/Utamo), cada uma sem gemas/Lesser/Regular/Greater. Selecionar uma opção pronta apenas consulta o resultado; não inicia busca. Resultados ficam no IndexedDB do perfil do navegador e são reutilizados ao reabrir o mesmo contexto. A primeira preparação ou uma mudança de pontos, vocação, configuração, regras ou conjunto de voltas exige preparar novo conjunto; botões indisponíveis aguardam esse trabalho. Dados novos do aprendizado entram no próximo conjunto de voltas. Sem total de pontos não há roda pronta. Código de pontos, intenção de adoção e APIs preservam os tiers numéricos 0–3; nada é aplicado no jogo.



O RTC permite limiar de criaturas até 10+. A busca de sugestões respeita esse limite; contagens observadas de levas maiores são preservadas. Trocas detectadas iniciam fases distintas e não reescrevem a configuração anterior.

Nos cards de sugestões, o ícone ✓ verde indica que aquele campo coincide com a leitura usada como referência. A comparação distingue autocura, EK, RP, magias e runas; campos ausentes, ambíguos, desativados ou marcados como antigos não recebem o ícone. Valores diferentes aparecem uma única vez como atual → sugerido, em destaque dourado para a próxima hunt. Na roda, o mesmo ícone representa o critério existente de semelhança dos benefícios. Esses ícones não confirmam uso, igualdade integral da configuração nem melhoria comprovada.

A leitura de vida por nameplate exige moldura completa, duas linhas iguais e preenchimento contínuo, com largura interior de 29 pixels. Não dividir a cauda de um recorte pelo tamanho da janela: o centro do nome inclui espaçamento e não coincide necessariamente com o centro da barra. Recortes ambíguos ficam sem leitura; dados anteriores e provas permanecem preservados.

Contatos de KS recuperados do Server Log podem ser anexados à declaração pessoal da sessão em `episodios_recuperados`, com origem `releitura_server_log`, hash da prova e dano adversário identificado. A correção exclui aliados declarados, evita repetir episódio já observado e mantém os contatos sem atribuir duração total ou XP perdida a registros parciais.

Releituras comprovadas do Party Hunt e do console podem preencher `relatorio_releitura` na declaração pessoal da sessão. O relatório original permanece preservado; o painel usa as medidas recuperadas, inclusive a última linha de integrante. Hazard confirmado pelo usuário requer prova e aplica-se somente à sessão declarada. Membro da PT é confirmado pelo escudo amarelo ou azul e pelo nome no Party Hunt; cor do nome e curas não bastam. O RTC exibe os ajustes numéricos sugeridos; diagnósticos de coleta, estoques e aprendizado ficam fora desse painel.

O formulário de guilda usa o personagem da sessão em Chars da PT que deu KS e os nomes externos em Chars oprimidos. Rascunhos antigos são migrados preservando o nome informado. XP e gold são deltas entre duas leituras válidas nas fronteiras do KS (até 5 s), sem rateio de voltas. XP provém somente do XP Analyser; loot do Party Hunt/solo exige mesma base de preço e ausência de reset. Prints recuperados mantêm originais e cópias servidas por rotas compatíveis.

Contatos de KS de baixo impacto confirmados pelo usuário podem ser ocultados por ID na declaração da sessão. Permanecem em episodios_ocultos e com provas preservadas: não existe limiar arbitrário de dano/golpes. Um estudo documentado de limiares usa a fase, o RTC, os estágios da roda e o Hazard correspondentes; comparações previstas não comprovam dano real. Propostas de cura por feedback são separadas de leituras no jogo e aplicam-se somente ao planejamento da sessão analisada.

Cada card do histórico mostra o indicador KS com caveira e faca quando há episódios relevantes no relatório efetivo da hunt. Modalidade e indicador usam a mesma fonte corrigida; episódios ocultos por baixo impacto não acionam o indicador. Para motores anteriores, resumos pessoais de hunts fechadas em party_correcoes.json permitem exibir os metadados corrigidos sem regravar o histórico. Respostas novas da API prevalecem sobre o resumo de compatibilidade.

O card também mostra o selo dourado “✦ Plunder avistado” no canto inferior direito do pôster, acima da quantidade de voltas, quando há observação positiva de Plunder Patriarch nas espécies da sessão ou de suas voltas, incluindo gravações agrupadas. A API do histórico expõe `tem_plunder`; ausência de observação não comprova ausência da criatura. O selo é exclusivo da sessão observada, independente do pôster compartilhado da hunt, e pode coexistir com KS. Contagens de leituras não são apresentadas como quantidade de aparições ou abates; históricos e provas permanecem intactos.

Quando o motor ainda não fornece `tem_plunder`, a interface consulta as voltas dos cards visíveis pela API existente, com até duas consultas simultâneas. Resultados de sessões fechadas são reutilizados por ID e data de salvamento enquanto a página estiver aberta. Falha de consulta não é guardada como ausência. Isso permite atualizar o destaque sem interromper o motor ou a gravação.


O quadro Dano da party (ou Dano solo) exibe somente dano acumulado, participação, críticos e fatais com contagem/percentual juntos, e maior golpe. Não exibe Loot, Supplies, Profit, explicações ou identificação da fonte. A coleta e as APIs permanecem preservadas. Em telas estreitas cada jogador vira um bloco sem rolagem horizontal.

Os efeitos de crítico e Onslaught são animações reais do Tibia armazenadas localmente como PNG animado, compatível com a rota de imagens existente. O fatal recebe brilho e contorno luminoso para contraste no tema escuro. Fontes dos assets: https://tibia.fandom.com/wiki/File:Critical_Hit_Effect.gif e https://www.tibiawiki.com.br/images/4/4a/Onslaught.gif.

O selo dourado “Plunder avistado” no histórico usa fonte de 10 px e preenchimento compacto no canto inferior direito, entre os monstros e o rodapé de voltas. Seu título acessível identifica Plunder Patriarch observado naquela hunt.
