const assert=require('node:assert/strict');
const T=require('./ui/shared/tracker.js');
assert.equal(T.parseNum('23,584,076'),23584076);
assert.equal(T.parseNum('-.694.631'),-694631);
assert.equal(T.kkC(8991163,1),'9,0 kk');
const p=T.parseParty('Session: 00:30\nLoot Type: Market\nLoot: 100\nSupplies: 0\nBalance: 100\nQA\n  Loot: 100\n  Supplies: 0\n  Balance: 100');
assert(p);assert.equal(p.supplies,0);assert.equal(p.durationH,0.5);
console.log('Tracker compartilhado: números, zero observado e Party Hunt aprovados.');
