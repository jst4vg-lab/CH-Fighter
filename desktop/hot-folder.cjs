const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

const UUID = /^[0-9a-f-]{36}$/;
const MANAGED = /^\d\d-[0-9a-f-]{36}\.jpg$/;

async function syncHotFolder(hot, dataDirectory, folder, cache = new Map()) {
  await fs.mkdir(folder, { recursive: true, mode: 0o700 });
  const wanted = new Map();
  let missing = 0;
  for (const [index, item] of (hot?.items || []).entries()) {
    if (!UUID.test(item.id)) throw Error('Invalid Hot crea identifier');
    if (item.missing) { missing++; continue; }
    const source = path.join(dataDirectory, 'formatted', `${item.id}.jpg`);
    const name = `${String(index + 1).padStart(2, '0')}-${item.id}.jpg`;
    let sourceStat;
    try { sourceStat = await fs.stat(source); } catch { missing++; continue; }
    if (!sourceStat.isFile() || !sourceStat.size) { missing++; continue; }
    const signature = `${item.render_key || ''}:${sourceStat.size}:${sourceStat.mtimeMs}`;
    const destination = path.join(folder, name);
    wanted.set(name, signature);
    let destinationExists = false;
    try { destinationExists = (await fs.stat(destination)).isFile(); } catch {}
    if (cache.get(name) === signature && destinationExists) continue;
    const temporary = path.join(folder, `.${name}.${randomUUID()}.tmp`);
    try {
      await fs.copyFile(source, temporary);
      await fs.rename(temporary, destination);
    } finally {
      await fs.unlink(temporary).catch(() => {});
    }
  }
  for (const name of await fs.readdir(folder)) {
    if (!MANAGED.test(name) || wanted.has(name)) continue;
    const existing = path.join(folder, name);
    if ((await fs.lstat(existing)).isDirectory()) continue;
    await fs.unlink(existing);
  }
  cache.clear();
  for (const [name, signature] of wanted) cache.set(name, signature);
  return { count: wanted.size, missing };
}

module.exports = { syncHotFolder };
