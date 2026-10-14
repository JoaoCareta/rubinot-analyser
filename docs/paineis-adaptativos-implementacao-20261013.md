# Leitura dos painéis — implementação de 13/10/2026

O usuário autorizou implementar o planejamento e informou que encerrou o aplicativo. A nova leitura é passiva: reconhece moldura e título no próprio quadro e normaliza o recorte antes de interpretar valores. Não altera o cliente, o RTC ou as configurações do personagem.

## Fontes e comportamento

| Informação | Origem e tratamento |
|---|---|
| Raw XP Gain, XP Gain, Raw XP/h e XP/h | Exclusivamente XP Analyser, inclusive nas voltas e no KS. Ausência é lacuna |
| Next Level | Estimativa textual do XP Analyser, convertida em segundos quando integralmente legível |
| Tempo de sessão | Exclusivamente `Session` do Party Hunt. Resolução de um minuto; zero válido. Sem relógio do computador, Hunt Analyser ou soma de voltas como substitutos |
| Economia pessoal | Loot, Supplies e Balance do Hunt Analyser. Balance exige coerência com Loot − Supplies no mesmo quadro |
| Economia da PT | Party Hunt, preservando Market/Leader. Valores de quadros distintos não são combinados para completar um snapshot econômico |
| Dano/cura da PT | Blocos de membros do Party Hunt. Soma dos balances deve conferir com o cabeçalho antes de publicar o conjunto como completo |
| Dano/cura pessoal | Hunt Analyser; números com `k` conservam resolução de mil unidades no diário |
| Dano recebido | Input Analyser, separado de Received Healing. Total, Max-DPS, valores e percentuais por tipo; identidade por referência visual confirmada |
| Supply/Loot Analyser | Gold Value, Per Hour, Target e contadores de itens visíveis como estimativas auxiliares. Não invalidam nem substituem a economia principal; não entram no contador de consumo confirmado |
| Skills | Campos numéricos e tempos integralmente legíveis, com lacunas por campo |
| Listas do Hunt/Input | Linhas textuais visíveis de Killed Monsters/Looted Items e Damage Sources quando reconhecidas. Ausência de linha não comprova zero |
| Server Log/Spells | Continuam como eventos parciais com horário, execução de magias, críticos e fatais; não viram acumulados oficiais dos painéis |

O indicador de tempo na tela e o histórico usam o contrato `tempo_sessao`, com espelho `tempoSessao` no JavaScript e teste de paridade. Duração das voltas e denominadores de taxas conservam seu próprio intervalo observado. Histórico antigo sem Session do Party continua com lacuna; não se inventa uma duração retroativa.

## Geometria, qualidade e retenção

O localizador cobre Hunt, XP, Party, Input, Supply, Loot, Battle List e Skills. Mede a largura pela moldura, exclui a scrollbar e usa o próximo cabeçalho da coluna para delimitar a altura. Títulos duplicados são ambíguos; painel ausente não reaproveita coordenadas antigas. Escalas candidatas são normalizadas; a validação automatizada inclui 100% e ampliação inteira de 200%, além de posição e largura alteradas sinteticamente.

Battle List passa a ser recortada pela geometria encontrada, com metadados de revisão e máscara de título no próprio PNG. Quando não é identificada, não produz uma lista vazia. Leitores de PNG antigos continuam usando seu layout legado.

Cada quadro completo lido gera `capture/<sessao>/paineis/observacoes.jsonl`, com versão, instante, arquivo, hash SHA-256, geometria, texto bruto, valor, origem, resolução e qualidade. `atual.json` publica o snapshot mais recente atomicamente. Provas das mudanças de geometria/qualidade ficam em `paineis/provas/`; uma prova de layout não deve ser confundida com a prova de todos os valores subsequentes. Os quadros completos permanecem a referência de cada observação enquanto retidos.

`pendentes.json` impede a limpeza da sessão se a leitura falhar. Uma leitura posterior não remove pendências de quadros anteriores. Não há descarte de histórico, modelos, configurações ou provas. A observação de execução também incorpora o contrato completo dos painéis, mantendo os campos antigos XP/Input compatíveis.

A calibração distingue valores efetivamente legíveis de meros rótulos. Não declara todos os membros lidos quando o quarto bloco foi cortado. Identificar todos os campos superiores não garante uma lista rolável completa.

## Evidência e limites

O replay isolado dos três quadros completos de 13/10 recuperou os quatro membros em todos eles, os quatro valores de XP e Session do Party em 26 minutos, 1h04 e 2h23. As parcelas de dano do Input conferiram com seu total em cada quadro. Os originais foram conferidos por hash e não foram regravados. Relatório local: `output/atualizacoes/20261013_paineis_adaptativos/replay-hunt.json`.

Esses quadros pertencem à mesma sessão e o último é posterior ao trecho principal de Monster Graveyard. Não demonstram ganho real da hunt nem generalização a todos os layouts. Testes sintéticos de geometria validam o mecanismo, não esse ganho.

Permanecem limites explícitos: tipos de Input sem referência mantêm nome nulo; modo recente/sessão não é presumido; nomes de itens sem referência ficam desconhecidos; contadores sobrepostos ou glifos ausentes ficam sem leitura. O leitor de itens reconheceu parte dos contadores, e não um inventário integral. Gráficos não são transformados em eventos ou números exatos.

Tela do jogo, Map View e consoles continuam usando sua calibração e leitores existentes. A adaptação automática nova é dos oito painéis com moldura reconhecível; esta entrega não certifica reposicionamento automático das onze regiões, todas as escalas fracionárias, barras sobrepostas ou listas fora da área visível. A ampliação desses casos precisa de provas próprias, conforme o plano.

Os testes cobrem movimento, largura, escala, scrollbar, títulos duplicados, ocultação, tempo exclusivo/zero/reset, precisão abreviada, membro cortado, Input, estimativas, paridade e preservação de pendências. Resultados de verificação, compilação e atualização são registrados na pasta local desta entrega.

## Entrega validada

Perfil rápido e perfil completo aprovados. A revisão final passou em 192 testes Python sem falhas, erros ou testes ignorados, nas suítes JavaScript, paridade, integração e testes ponta a ponta. O replay final está em `replay-final.json`; inclui a proteção contra membro cortado mesmo quando seu balance é zero.

Compilação feita no ambiente `instalador/ferramentas/build312`, seguida de autoteste do executável. A primeira tentativa no ambiente de testes foi interrompida por ausência do compilador; seu log foi preservado e não foi usado para aprovar a entrega. Os testes de abertura e resposta HTTP passaram no build e na instalação.

A instalação do atalho em `C:/Users/User/AppData/Local/HuntAnalyzer/` recebeu 11 arquivos de produto. Backup, manifesto dos 7.883 arquivos pessoais e teste de reversão estão em `output/atualizacoes/20261013_paineis_adaptativos/instalacao/`. Não foi gerado Setup.exe nem feito push. O programa fica encerrado para a próxima abertura do usuário.
