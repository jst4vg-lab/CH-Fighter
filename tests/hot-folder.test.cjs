const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { syncHotFolder } = require('../desktop/hot-folder.cjs');

const FIRST = '22222222-2222-4222-8222-222222222222';
const SECOND = '33333333-3333-4333-8333-333333333333';

test('persistent Hot folder mirrors package changes without changing formatted sources', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ch-hot-folder-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const data = path.join(root, 'data');
  const formatted = path.join(data, 'formatted');
  const folder = path.join(data, 'hot-staging');
  fs.mkdirSync(formatted, { recursive: true });
  fs.writeFileSync(path.join(formatted, `${FIRST}.jpg`), 'first fixture');
  fs.writeFileSync(path.join(formatted, `${SECOND}.jpg`), 'second fixture');
  const cache = new Map();
  const first = { id: FIRST, render_key: 'v1' };
  const second = { id: SECOND, render_key: 'v1' };

  assert.deepEqual(await syncHotFolder({ items: [first, second] }, data, folder, cache), { count: 2, missing: 0 });
  assert.deepEqual(fs.readdirSync(folder), [`01-${FIRST}.jpg`, `02-${SECOND}.jpg`]);
  assert.equal(fs.readFileSync(path.join(folder, `01-${FIRST}.jpg`), 'utf8'), 'first fixture');
  fs.writeFileSync(path.join(folder, 'user-note.txt'), 'leave alone');

  await syncHotFolder({ items: [second] }, data, folder, cache);
  assert.deepEqual(fs.readdirSync(folder), [`01-${SECOND}.jpg`, 'user-note.txt']);
  assert.equal(fs.readFileSync(path.join(formatted, `${FIRST}.jpg`), 'utf8'), 'first fixture');

  fs.writeFileSync(path.join(formatted, `${SECOND}.jpg`), 'updated fixture');
  await syncHotFolder({ items: [{ ...second, render_key: 'v2' }] }, data, folder, cache);
  assert.equal(fs.readFileSync(path.join(folder, `01-${SECOND}.jpg`), 'utf8'), 'updated fixture');
  assert.equal(fs.readFileSync(path.join(formatted, `${SECOND}.jpg`), 'utf8'), 'updated fixture');

  assert.deepEqual(await syncHotFolder({ items: [{ ...second, missing: true }] }, data, folder, cache), { count: 0, missing: 1 });
  assert.deepEqual(fs.readdirSync(folder), ['user-note.txt']);
  await syncHotFolder(null, data, folder, cache);
  assert.ok(fs.statSync(folder).isDirectory());
});
