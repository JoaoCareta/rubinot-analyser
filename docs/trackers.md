# Trackers

O tracker solo integra este Git, sem `solo.db`, `coladas.db`, prints ou dados pessoais. `npm run check` agora testa `/api/sessions` atual e SQLite temporário. `PORT=0` e `criarServidor` permitem portas efêmeras; execução normal continua em 127.0.0.1:3311.

O tracker da party conserva seu Git independente. Mudanças foram publicadas no PR rascunho #1, na branch `refactor/contratos-tracker`; push em main dispara deploy e exige uma entrega separada. Não foi alterado o ambiente da VPS.

Fonte canônica de formatação/parser comum: `hunt-analyzer/ui/shared/tracker.js`. As cópias em `public/shared/` são geradas por `tools/sincronizar_trackers.py` e verificadas por conteúdo e SHA-256. Clone do repo principal verifica o solo; workspace com party verifica os dois. Funções que diferem no significado dos dados permanecem separadas.

Party: para escrita remota, configurar `SESSIONS_TOKEN`; navegador pede o token e o conserva na sessão. O scraper continua usando `LEVELS_TOKEN`, separado. Sem token, escrita só é aceita com bind e cliente loopback. GET fornece ETag; PUT exige `If-Match`, rejeita conflito com 409 e preserva os dados. 428 indica ausência de versão; 401 indica autorização ausente; JSON inválido recebe 400.

Antes de publicar essa branch, configurar o token no ambiente e conferir a proteção do proxy real. Os testes locais não certificam a configuração da VPS. A pipeline da party executa o check antes do deploy.
