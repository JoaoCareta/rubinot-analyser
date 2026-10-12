# Tracker solo

Aplicativo local em 127.0.0.1:3311. Node 24, sem dependências npm.

- `npm start`: interface atual em `public/index.html`.
- `npm run check`: API atual, importação idempotente, lacuna, taxa canônica e paths com SQLite temporário.
- `criarServidor({pastaDados, publico, personagens})`: contrato para testes isolados; importar o módulo não abre porta.
- `PORT=0`: porta efêmera. `HUNT_SOLO_DADOS`: raiz de dados alternativa.

`solo.db` é uma projeção derivada; `coladas.db` guarda as importações manuais e não é substituído pela reconstrução. Não versionar bancos ou prints. Dados ausentes ficam nulos; raw estabilizada já fornecida no banco tem precedência sobre total dividido pelo tempo.

O código comum de números e Party Hunt vem de `hunt-analyzer/ui/shared/tracker.js`, copiado pelo sincronizador e acompanhado de SHA-256. Cópias são verificadas pelo harness; não editar manualmente `public/shared/tracker.js`.

O frontend e servidor anteriores foram retirados depois da substituição do check. O marco inicial Git conserva as fontes legadas para recuperação.
