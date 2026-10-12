# LoE Hunt Tracker — solo (Johanes Characters)

Site **local**. Escuta só em `127.0.0.1:3311`, não fala com a internet, não usa CDN,
não baixa fonte nenhuma: o CSS e o JS são arquivos locais em `public/static/`.

## Como rodar

```
npm start          # abre http://127.0.0.1:3311
npm run check      # confere formatação de números, somas e barreira de caminho
```

Sem instalar nada: zero dependência, só Node. Precisa de Node 22.5 ou mais novo,
porque o banco é lido com o `node:sqlite` que já vem embutido — aqui foi testado
no Node 24.12. (Se um dia o Node for mais antigo, o caminho é o `build_db.py`
cuspir um `public/snapshot.json` e trocar o `fetch("/api/dados")` do `app.js` por
`fetch("/snapshot.json")` — o front só recebe JSON e desenha.)

A página é montada no navegador: ela busca `/api/dados` uma vez e desenha. Isso
quer dizer que `curl /` devolve só a casca — para conferir dados na linha de
comando, use `curl /api/dados`. Sem JavaScript o site mostra um aviso apontando
para lá.

## Rotas

| Rota | O que mostra |
|---|---|
| `/` | Integrantes, barra de filtros (datas + hunt), sessões e o comparativo das caves |
| `/sessao/:id` | Totais, bichos abatidos por espécie, gráficos e tabela volta a volta |
| `/sessao/:id/zonas` | As zonas por posição, com todas as colunas, ordenável |
| `/sessao/:id/boxes` | As travadas: motivo, os 3 passos e o quadro a quadro |
| `/api/dados` | O banco inteiro em JSON (76 linhas), só leitura |
| `/static/**` | CSS e JS locais |
| `/assets/**` | Outfits dos personagens, arquivos locais em `public/assets` |
| `/img/**` | Imagens de `hunt-analyzer/reports`, **somente leitura** |

## Dados

- Banco: `solo.db`, aberto em modo somente leitura. Quem escreve é só o
  `python scripts/build_db.py`. A conexão abre e fecha em cada consulta, então
  dá para regerar o banco com o site rodando — não precisa derrubar nada.
  Se o `solo.db` não existir, o `npm start` avisa para rodar o `build_db.py`
  em vez de estourar um erro cru.
- Imagens: nada é copiado. `/img/...` lê direto de
  `D:\Documentos\rubinot\hunt-analyzer\reports` (ajustável com `REPORTS_DIR`,
  com ou sem barra no fim). Sai da pasta com `..` → 403.

## Três regras de leitura que o site respeita

1. **A volta descartada não entra na conta.** Com as 23 linhas dá 1.267 abates;
   as 22 boas dão 1.212, que é o que está no cabeçalho da sessão.
2. **Experiência e lucro por zona são estimativa**, não medição: é o valor
   medido por bicho na sessão, multiplicado pelos abates da zona. As zonas somam
   1.179 abates e a sessão 1.212, porque as duas contagens saem de leituras
   diferentes — por isso as colunas estimadas não fecham com o total do topo.
   A tela diz isso. Vida por bicho e tempo na zona, esses sim, são medidos.
3. **O que não foi medido fica vazio, nunca zero.** A sessão de Ingol não tem
   percentual de bicho roubado (a fonte só anotou por escrito), então a coluna
   mostra `—`. Vale igual para a volta 1 sem leitura de experiência e para a
   travada sem volta identificada.

Abates e dano recebido vêm da leitura do chat e ficam abaixo do real, de forma
parecida em todas as voltas: servem para comparar volta com volta, não como
número absoluto. Lucro e experiência vêm do painel do jogo. A tela da sessão
traz esse aviso escrito.

## Como as sessões entram

1. **Automático (sessões medidas pelo harness):** no fim de cada análise, rodar
   `python scripts/build_db.py` — relê `hunt-analyzer/hunt_data/` e recria o `solo.db`.
   As sessões coladas ficam em `coladas.db` e sobrevivem ao rebuild.
2. **Manual (colar o analyser):** botão "+ Adicionar sessão" no site → escolher o
   personagem → colar o export do Hunt Analyser (precisa da linha "Session data:
   From ... to ..."). Duplicata (mesmo personagem + mesmo início) é recusada.
