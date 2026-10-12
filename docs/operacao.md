# Operação

O atalho abre a instalação compilada diretamente no navegador. O supervisor é invisível. Fechar a janela ou Desligar salva a hunt e encerra os processos do aplicativo. Minimizar conserva a execução. Clique repetido traz a janela existente.

O ícone da janela vem do favicon declarado em todas as páginas (`ui/hunt_analyzer_icone.png`); o ícone do atalho/executável é configurado separadamente em `instalador/assets/hunt-analyzer.ico`. Manter ambos com a mesma arte. Após atualizar a interface, recarregar a janela para o navegador buscar o favicon.

A calibração mostra a fonte da análise à esquerda e as referências de RTC, cura e roda à direita (em telas pequenas, os blocos ficam empilhados). As datas de referência manual guardada e última leitura são separadas: uma leitura automática não significa que o usuário marcou uma referência. Cada atalho abre o tipo escolhido para o personagem da fonte. A tela de configurações tem retorno explícito à calibração no cabeçalho.

Mudança de área dentro da mesma gravação exige mudança sustentada de andar e monstros: janela de 90 s, pelo menos oito leituras cobrindo 30 s, com 75% das leituras no novo andar e com novas espécies. Mudar só o andar (como nas Livrarias) ou ver um monstro de passagem não separa a hunt. A tela ao vivo recorta voltas e trilha para a área atual, mostra seu andar e espécies, e reinicia a estabilização de raw. Volta atravessando a fronteira é parcial, sem ratear números. A gravação completa e as fronteiras ficam preservadas no histórico; `areas_observacoes.jsonl` guarda as observações compactas, sem abrir captura adicional.

Iniciar hunt abre sessão nova; Encerrar conserva o servidor e guarda histórico. Reiniciar encerra a análise atual e volta a observar. Não iniciar uma segunda captura manual se o aplicativo está gravando.

Encerramento: interromper produção de quadros, drenar consumidores, guardar números e mapas, consolidar aprendizado, somente então autorizar limpeza. Se a extração falhou, conservar quadros e corrigir o consumidor; não apagar a sessão para esconder o erro.

Capture/lap_watch/KS continuam sendo entradas do dispatcher compilado. CLIs e ferramentas manuais estão classificadas em `runtime-manifest.json`. Os nomes antigos permanecem executáveis pelas fachadas. Usar caminho completo ao iniciar processo manual para permitir sua identificação pelo supervisor.

Interface e API podem ser verificadas sem jogo com `app.py --sem-gravacao --sem-observacao --sem-navegador`. Não usar esse modo para medir desempenho de captura real.
