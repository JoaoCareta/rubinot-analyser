// Tracker SOLO local — clone do app da pt servindo dados do solo.db.
// LOCAL-ONLY: escuta em 127.0.0.1, nunca expor. Zero dependência (node:sqlite).
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname, normalize, sep } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC = join(__dirname, 'public');
const PORT = 3311;
const HOST = '127.0.0.1';

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json',
  '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
};

// nome no banco (minusculo) -> nome do codex no front
const TITULO = {
  'harpy': 'Harpy', 'crape man': 'Crape Man', 'rhindeer': 'Rhindeer', 'boar man': 'Boar Man',
  'carnivostrich': 'Carnivostrich', 'liodile': 'Liodile', 'vexclaw': 'Vexclaw',
  'hellfire fighter': 'Hellfire Fighter', 'fury': 'Fury', 'hellflayer': 'Hellflayer',
  'hellhound': 'Hellhound', 'falcon knight': 'Falcon Knight', 'falcon paladin': 'Falcon Paladin',
  'wardragon': 'Wardragon', 'dragolisk': 'Dragolisk', 'mega dragon': 'Mega Dragon',
  'headpecker': 'Headpecker', 'mantosaurus': 'Mantosaurus', 'mercurial menace': 'Mercurial Menace',
  'noxious ripptor': 'Noxious Ripptor', 'shrieking cry-stal': 'Shrieking Cry-Stal',
  'outro': 'Nao identificada', 'compartilhado': 'Nao identificada', '?': 'Nao identificada',
};

const CHARS_VALIDOS = new Set(['Hetero afeminado', 'Traps the cat']);

function comColadas(fn, escrita = false) {
  const db = new DatabaseSync(join(__dirname, 'coladas.db'));
  try {
    db.exec(`CREATE TABLE IF NOT EXISTS colada (
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, personagem TEXT, data TEXT,
      UNIQUE(personagem, ts))`);
    return fn(db);
  } finally { db.close(); }
}

function guardarColada(sess) {
  const nome = sess?.party?.players?.[0]?.name;
  const ts = sess?.party?.start;
  if (!CHARS_VALIDOS.has(nome) || !ts) return { erro: 'sessao invalida' };
  return comColadas((db) => {
    const r = db.prepare('INSERT OR IGNORE INTO colada (ts, personagem, data) VALUES (?, ?, ?)')
      .run(String(ts), nome, JSON.stringify(sess));
    return r.changes === 0 ? { duplicada: true } : { ok: true };
  });
}

function coladas() {
  try {
    return comColadas((db) => db.prepare('SELECT id, data FROM colada').all()
      .map((r) => ({ ...JSON.parse(r.data), id: 'c' + r.id })));
  } catch { return []; }
}

function comBanco(fn) {
  const db = new DatabaseSync(join(__dirname, 'solo.db'), { readOnly: true });
  try { return fn(db); } finally { db.close(); }
}

function apiSessions() {
  return comBanco((db) => {
    const sess = db.prepare(`
      SELECT s.*, p.nome AS char_nome, h.slug AS hunt_slug FROM sessao s
      JOIN personagem p ON p.id = s.personagem_id
      JOIN hunt h ON h.id = s.hunt_id
      ORDER BY s.data, s.janela`).all();
    const abates = db.prepare('SELECT sessao_id, especie, abates FROM abate_especie').all();
    const voltas = db.prepare(`SELECT sessao_id, SUM(xp_raw) AS raw, SUM(xp_chat) AS chat
                               FROM volta WHERE descartada = 0 GROUP BY sessao_id`).all();
    const porSessao = {};
    for (const a of abates) (porSessao[a.sessao_id] ||= []).push({ count: a.abates, name: TITULO[a.especie] || a.especie });
    const xpDe = {}; for (const v of voltas) xpDe[v.sessao_id] = v;

    return sess.map((s) => {
      const durH = (s.minutos || 0) / 60;
      const [ini, fim] = String(s.janela || '').split(' - ');
      const kills = porSessao[s.id] || [];
      const totalKills = s.kills || kills.reduce((a, k) => a + k.count, 0);
      // XP da mensagem do chat = raw x rate x 1,1 VIP -> raw = chat / mult.
      // Traps 450% -> 4,95. (Hetero nunca cai no fallback: as sessoes dele tem painel.)
      const MULT = { 'Traps the cat': 4.95, 'Hetero afeminado': 12.375 };
      let rawXp = (xpDe[s.id] && xpDe[s.id].raw) ||
        (s.xp_raw_h_mediana ? Math.round(s.xp_raw_h_mediana * durH) : null);
      const xp = (xpDe[s.id] && xpDe[s.id].chat) || rawXp;
      if (rawXp == null && xp) rawXp = Math.round(xp / (MULT[s.char_nome] || 4.95));
      const HUNT_LABEL = { ingol: 'Ingol', falcon_bastion: 'Falcon Bastion',
        infernatil_hell: 'Infernatil', dragolisk: 'Dragolisk', gnomprona_carrinho2: 'Gnomprona (carrinho 2)' };
      return {
        id: s.id,
        hunt: HUNT_LABEL[s.hunt_slug] || s.hunt_slug,
        party: {
          players: [{
            name: s.char_nome, leader: false,
            loot: s.loot ?? null, supplies: s.supplies ?? null,
            balance: s.balance ?? s.profit ?? null,
            damage: s.damage || 0, healing: s.healing || 0,
          }],
          start: `${s.data}, ${ini || '00:00:00'}`,
          end: `${s.data}, ${fim || ini || '00:00:00'}`,
          durationH: durH, lootType: 'Solo',
          loot: s.loot ?? null, supplies: s.supplies ?? null, balance: s.balance ?? s.profit ?? null,
        },
        mines: [{
          kills, items: [], durationH: durH,
          rawXp, xp,
          xpH: (xp != null && durH) ? Math.round(xp / durH) : null,
          rawXpH: (rawXp != null && durH) ? Math.round(rawXp / durH) : null,
          damage: s.damage || 0, damageH: durH ? Math.round((s.damage || 0) / durH) : 0,
          healing: s.healing || 0, healingH: durH ? Math.round((s.healing || 0) / durH) : 0,
          totalKills,
        }],
      };
    });
  });
}

function apiLevels() {
  return comBanco((db) => {
    const out = {};
    for (const p of db.prepare('SELECT nome, nivel, vocacao FROM personagem').all()) {
      const voc = p.vocacao === 'druid' ? 'Elder Druid' : p.vocacao === 'paladin' ? 'Royal Paladin' : p.vocacao;
      out[p.nome] = { level: p.nivel, vocation: voc, world: 'Etherian', updatedAt: null };
    }
    return out;
  });
}

const json = (res, code, obj) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(JSON.stringify(obj)); };

const server = createServer(async (req, res) => {
  try {
    const { pathname } = new URL(req.url, 'http://localhost');
    if (pathname === '/api/sessions' && req.method === 'GET') {
      const tudo = [...apiSessions(), ...coladas()];
      tudo.sort((a, b) => String(a.party?.start || '').localeCompare(String(b.party?.start || '')));
      return json(res, 200, tudo);
    }
    if (pathname === '/api/sessions' && req.method === 'POST') {
      let corpo = '';
      req.on('data', (c) => { corpo += c; if (corpo.length > 2e6) req.destroy(); });
      req.on('end', () => {
        try { json(res, 200, guardarColada(JSON.parse(corpo || '{}'))); }
        catch { json(res, 400, { erro: 'json invalido' }); }
      });
      return;
    }
    if (pathname === '/api/levels' && req.method === 'GET') return json(res, 200, apiLevels());
    if (pathname.startsWith('/api/')) { res.writeHead(405); return res.end('somente leitura'); }

    const rel = pathname === '/' ? '/index.html' : decodeURIComponent(pathname);
    if (rel.includes('\0')) { res.writeHead(400); return res.end('endereco invalido'); }
    const filePath = normalize(join(PUBLIC, rel));
    if (filePath !== PUBLIC && !filePath.startsWith(PUBLIC + sep)) { res.writeHead(403); return res.end('proibido'); }
    const data = await readFile(filePath);
    res.writeHead(200, { 'content-type': MIME[extname(filePath)] || 'application/octet-stream' });
    return res.end(data);
  } catch (e) {
    if (e.code === 'ENOENT') { res.writeHead(404); return res.end('nao encontrado'); }
    if (e.code === 'ERR_INVALID_URL') { res.writeHead(400); return res.end('endereco invalido'); }
    console.error(e); res.writeHead(500); return res.end('erro');
  }
});

server.listen(PORT, HOST, () => console.log(`Solo Hunt Tracker -> http://${HOST}:${PORT}`));
