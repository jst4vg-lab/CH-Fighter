const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { resolveDragFiles } = require('../desktop/drag-files.cjs');

const PACKAGE = '11111111-1111-4111-8111-111111111111';
const FIRST = '22222222-2222-4222-8222-222222222222';
const SECOND = '33333333-3333-4333-8333-333333333333';

test('native drag resolves every formatted file in package order', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ch-drag-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'formatted'));
  for (const id of [FIRST, SECOND]) fs.writeFileSync(path.join(root, 'formatted', `${id}.jpg`), 'fixture');
  const hot = { id: PACKAGE, missing_count: 0, items: [{ id: SECOND }, { id: FIRST }] };
  assert.deepEqual(resolveDragFiles(hot, PACKAGE, root), [SECOND, FIRST].map(id => path.join(root, 'formatted', `${id}.jpg`)));
  assert.throws(() => resolveDragFiles(hot, 'wrong', root));
  hot.missing_count = 1;
  assert.throws(() => resolveDragFiles(hot, PACKAGE, root));
  hot.missing_count = 0;
  hot.items[0].missing = 1;
  assert.throws(() => resolveDragFiles(hot, PACKAGE, root));
  hot.items[0].missing = 0;
  fs.unlinkSync(path.join(root, 'formatted', `${SECOND}.jpg`));
  assert.throws(() => resolveDragFiles(hot, PACKAGE, root));
});
