// Servidor local do tracker. Escuta SO em 127.0.0.1 e nao faz nenhuma
// requisicao para fora. As imagens vem da pasta de relatorios, somente leitura.
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { dirname, extname, join, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CAMINHO, COMO_CRIAR, getPayload, sessaoExiste } from './db.js';

const AQUI = dirname(fileURLToPath(import.meta.url));

// A barra no fim tem que cair fora: "…/reports/" faria a barreira comparar com
// "…/reports/" + sep e nenhuma imagem passaria (403 em tudo).
export const raizDe = (p) => normalize(p).replace(/[\\/]+$/, '') || sep;

const PUBLICO = raizDe(join(AQUI, 'public'));
const RELATORIOS = raizDe(process.env.REPORTS_DIR || 'D:/Documentos/rubinot/hunt-analyzer/reports');

const HOST = '127.0.0.1'; // fixo de proposito: nunca 0.0.0.0
const PORTA = Number(process.env.PORT) || 3311;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
};

// "/", "/sessao/1", "/sessao/1/zonas", "/sessao/1/boxes" -> todas servem a mesma casca
const PAGINA = /^\/(?:$|sessao\/(\d+)(?:\/(?:zonas|boxes))?$)/;

/** Caminho de dentro da raiz, ou null se o pedido tentou sair dela. */
export function dentro(raiz, relativo) {
  const caminho = normalize(join(raiz, relativo));
  const ok = caminho === raiz || caminho.startsWith(raiz + sep);
  return ok ? caminho : null;
}

function json(res, codigo, obj) {
  res.writeHead(codigo, { 'content-type': MIME['.json'] });
  res.end(JSON.stringify(obj));
}

async function servirArquivo(res, raiz, relativo, codigo = 200) {
  const caminho = dentro(raiz, relativo);
  if (!caminho) {
    res.writeHead(403);
    return res.end('proibido');
  }
  const dados = await readFile(caminho);
  res.writeHead(codigo, {
    'content-type': MIME[extname(caminho).toLowerCase()] || 'application/octet-stream',
  });
  res.end(dados);
}

const servidor = createServer(async (req, res) => {
  try {
    // dentro do try: um request-target malformado (ex.: "//[") faz o new URL
    // lancar e, solto, derrubava o processo inteiro
    const { pathname } = new URL(req.url, `http://${HOST}`);
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.writeHead(405);
      return res.end('so leitura');
    }
    if (pathname === '/api/dados') {
      try {
        return json(res, 200, getPayload());
      } catch (e) {
        return json(res, 503, { erro: e.message });
      }
    }

    // "/sessao/1/" e o mesmo endereco que "/sessao/1"
    if (pathname.length > 1 && pathname.endsWith('/')) {
      res.writeHead(301, { location: pathname.replace(/\/+$/, '') });
      return res.end();
    }

    let relativo;
    try {
      relativo = decodeURIComponent(pathname);
    } catch {
      res.writeHead(400);
      return res.end('endereco invalido');
    }
    if (relativo.includes('\0')) {
      res.writeHead(400);
      return res.end('endereco invalido');
    }

    if (relativo.startsWith('/img/')) return await servirArquivo(res, RELATORIOS, relativo.slice(5));
    if (relativo.startsWith('/static/')) return await servirArquivo(res, PUBLICO, relativo);
    if (relativo.startsWith('/assets/')) return await servirArquivo(res, PUBLICO, relativo);

    const pagina = PAGINA.exec(pathname);
    if (pagina) {
      // numero de sessao que nao existe: a tela explica, mas o codigo tem que ser 404
      const achou = !pagina[1] || sessaoExiste(pagina[1]);
      return await servirArquivo(res, PUBLICO, '/index.html', achou ? 200 : 404);
    }

    res.writeHead(404);
    res.end('nao encontrado');
  } catch (e) {
    if (e.code === 'ERR_INVALID_URL') {
      res.writeHead(400);
      return res.end('endereco invalido');
    }
    if (e.code === 'ENOENT' || e.code === 'EISDIR' || e.code === 'ENOTDIR') {
      res.writeHead(404);
      return res.end('nao encontrado');
    }
    console.error(e);
    res.writeHead(500);
    res.end('erro interno');
  }
});

if (!existsSync(CAMINHO)) {
  console.error(COMO_CRIAR);
  process.exit(1);
}

servidor.listen(PORTA, HOST, () => {
  console.log(`Johanes Characters — hunts  ->  http://${HOST}:${PORTA}`);
  console.log(`imagens (somente leitura)   ->  ${RELATORIOS}`);
});
