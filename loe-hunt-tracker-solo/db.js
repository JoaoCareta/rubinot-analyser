// Leitura do solo.db. Quem escreve o banco e o scripts/build_db.py — aqui e read-only.
import { DatabaseSync } from 'node:sqlite';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = dirname(fileURLToPath(import.meta.url));
export const CAMINHO = process.env.DB_PATH || join(AQUI, 'solo.db');
export const COMO_CRIAR = `banco nao encontrado em ${CAMINHO} — rode "python scripts/build_db.py" primeiro`;

// A conexao abre e fecha a cada consulta de proposito: no Windows um handle
// aberto impede o build_db.py de apagar o solo.db para regerar. O banco tem 76
// linhas, entao segurar a conexao nao economizava nada.
function comBanco(fn) {
  let db;
  try {
    db = new DatabaseSync(CAMINHO, { readOnly: true });
  } catch (e) {
    throw new Error(`${COMO_CRIAR} (${e.message})`);
  }
  try {
    return fn(db);
  } finally {
    db.close();
  }
}

/** A rota de pagina precisa saber se o numero existe para devolver 404 de verdade. */
export function sessaoExiste(id) {
  const n = Number(id);
  if (!Number.isInteger(n)) return false;
  return comBanco((db) => db.prepare('SELECT 1 FROM sessao WHERE id = ?').get(n) !== undefined);
}

// referencias_json guarda mapas e matrizes inteiras (centenas de KB).
// A tela so precisa de dois campos, entao o resto nao vai pela rede.
function fichaDaCave(bruto) {
  try {
    const j = JSON.parse(bruto || '{}');
    return {
      dur_tipica_s: j.volta?.dur_tipica_s ?? null,
      ks_historico: j.ks_historico ?? null,
    };
  } catch {
    return { dur_tipica_s: null, ks_historico: null };
  }
}

function talvezJson(txt) {
  try { return JSON.parse(txt); } catch { return null; }
}

/**
 * Tudo o que as telas usam, num objeto. O banco inteiro tem 76 linhas,
 * entao nao vale a pena uma rota por consulta: o front carrega uma vez e filtra.
 */
export function getPayload() {
  return comBanco((db) => {
    const grupo = db.prepare('SELECT id, nome FROM grupo ORDER BY id').all()[0] ?? null;

    const personagens = db.prepare(
      'SELECT id, nome, vocacao, nivel, rate_pct, grupo_id FROM personagem ORDER BY id'
    ).all();

    const hunts = db.prepare(
      'SELECT id, slug, nome, andar, bbox, referencias_json FROM hunt ORDER BY nome'
    ).all().map((h) => ({
      id: h.id,
      slug: h.slug,
      nome: h.nome,
      andar: h.andar,
      bbox: talvezJson(h.bbox),
      ...fichaDaCave(h.referencias_json),
    }));

    const sessoes = db.prepare(`
      SELECT s.*, p.nome AS personagem, p.vocacao, p.rate_pct,
             h.nome AS hunt, h.slug AS hunt_slug
        FROM sessao s
        JOIN personagem p ON p.id = s.personagem_id
        JOIN hunt h       ON h.id = s.hunt_id
       ORDER BY s.data DESC, s.id DESC
    `).all();

    return {
      grupo,
      personagens,
      hunts,
      sessoes,
      // por id, nao por numero: sessao com dois blocos repete numeros (1,2,.. 1,2,..)
      // e ordenar por numero intercalaria os blocos fora da ordem do relogio
      voltas: db.prepare('SELECT * FROM volta ORDER BY sessao_id, id').all(),
      abates: db.prepare('SELECT * FROM abate_especie ORDER BY sessao_id, abates DESC').all(),
      zonas: db.prepare('SELECT * FROM zona ORDER BY sessao_id, rank').all(),
      boxes: db.prepare('SELECT * FROM box_travada ORDER BY sessao_id, n').all(),
    };
  });
}
