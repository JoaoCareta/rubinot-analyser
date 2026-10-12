# Dados e recuperação

Git guarda fontes, documentação, assets de produto e fixtures sanitizadas. Não guarda `capture`, `hunt_data`, `KS`, `configuracoes_player`, bancos, modelos pessoais, calibração, prints, logs, perfil do navegador, ambientes, builds ou backups.

As pastas pessoais não foram movidas. O resolvedor atual permite raízes por ambiente: `HUNT_DATA`, `HUNT_CAPTURAS_RAIZ`, `HUNT_CONFIGURACOES_RAIZ`, `HUNT_APRENDIZADO_RAIZ`, `HUNT_FONTES_RAIZ`, `HUNT_KS_RAIZ` e `HUNT_AUXILIARES_CONFIG`. Sem overrides, os caminhos antigos continuam valendo.

Backup do aprendizado: usar `Registro(raiz).backup(destino)` enquanto o aplicativo pode escrever; copiar apenas o `.sqlite3` aberto não substitui a API de backup. O backup precisa passar `PRAGMA integrity_check`. O teste restaura o snapshot numa raiz temporária e compara registros.

Para recuperar a instalação: encerrar o aplicativo, restaurar os arquivos alterados listados no manifesto da atualização e executar o autoteste. Calibração, números, provas e aprendizado continuam na instalação; não restaurar dados antigos por cima de novas hunts. Reversão de schema exige uma cópia compatível e não autoriza apagar registros atuais.

Gerações incompletas do histórico não são publicadas. Gerações anteriores permanecem recuperáveis; nenhuma limpeza delas foi automatizada nesta mudança. Quadros só são removidos pela política existente após consumidores terminarem; números e provas permanecem.
