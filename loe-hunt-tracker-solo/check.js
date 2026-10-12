// Contratos do servidor atual, com SQLite temporário e porta efêmera.
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { criarServidor, dentro } from './server.js';
const pasta = await mkdtemp(join(tmpdir(), 'rubinot-solo-'));
const db = new DatabaseSync(join(pasta, 'solo.db'));
db.exec(`CREATE TABLE personagem(id INTEGER, nome TEXT, nivel INTEGER, vocacao TEXT);
CREATE TABLE hunt(id INTEGER, slug TEXT);
CREATE TABLE sessao(id INTEGER, personagem_id INTEGER, hunt_id INTEGER, data TEXT, janela TEXT, minutos REAL,
loot REAL, supplies REAL, balance REAL, profit REAL, kills INTEGER, xp_raw_h_mediana REAL);
CREATE TABLE abate_especie(sessao_id INTEGER, especie TEXT, abates INTEGER);
CREATE TABLE volta(sessao_id INTEGER, xp_raw REAL, xp_chat REAL, descartada INTEGER);
INSERT INTO personagem VALUES (1,'QA',100,'druid'); INSERT INTO hunt VALUES (1,'qa');
INSERT INTO sessao VALUES (1,1,1,'2026-01-01','01:00:00 - 02:00:00',60,100,NULL,100,100,NULL,30000000);
INSERT INTO volta VALUES (1,1000000,NULL,0);`);
db.close();
const srv = criarServidor({pastaDados:pasta, personagens:new Set(['QA'])});
await new Promise(resolve => srv.listen(0, '127.0.0.1', resolve));
const url = `http://127.0.0.1:${srv.address().port}`;
try {
  assert(dentro(pasta,join(pasta,'arquivo')));
  assert(!dentro(pasta,pasta+'-vizinho/arquivo'));
  assert(!dentro(pasta,join(pasta,'..','segredo')));
  const sessoes = await (await fetch(url+'/api/sessions')).json();
  assert.equal(sessoes.length,1);
  assert.equal(sessoes[0].mines[0].rawXpH,30000000,'mediana canônica preservada');
  assert.equal(sessoes[0].party.supplies,null,'lacuna nunca vira zero');
  const post = corpo => fetch(url+'/api/sessions',{method:'POST',body:corpo,headers:{'content-type':'application/json'}});
  assert.equal((await post('{')).status,400);
  const sessao=JSON.stringify({party:{players:[{name:'QA'}],start:'2026-01-02, 01:00:00'}});
  assert.equal((await (await post(sessao)).json()).ok,true);
  assert.equal((await (await post(sessao)).json()).duplicada,true);
  assert.equal((await (await fetch(url+'/api/sessions')).json()).length,2);
  assert.equal((await fetch(url+'/api/sessions',{method:'PUT'})).status,405);
  assert.equal((await fetch(url+'/%00')).status,400);
  assert.equal((await fetch(url+'/arquivo-inexistente')).status,404);
  console.log('Solo: rotas atuais, mediana, lacuna, importação idempotente e caminhos aprovados.');
} finally {
  await new Promise(resolve => srv.close(resolve));
  await rm(pasta,{recursive:true,force:true});
}
