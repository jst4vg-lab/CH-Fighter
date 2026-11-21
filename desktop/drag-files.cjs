const fs = require('node:fs');
const path = require('node:path');

const UUID = /^[0-9a-f-]{36}$/;

function resolveDragFiles(hot, packageId, dataDirectory) {
  if (!UUID.test(packageId) || !hot || hot.id !== packageId || !Array.isArray(hot.items) ||
      !hot.items.length || hot.missing_count) throw Error('Hot package is unavailable for dragging');
  return hot.items.map(item => {
    if (!UUID.test(item.id) || item.missing) throw Error('Invalid crea in package');
    const file = path.join(dataDirectory, 'formatted', `${item.id}.jpg`);
    const stat = fs.statSync(file);
    if (!stat.isFile() || !stat.size) throw Error('A formatted crea is unavailable');
    return file;
  });
}

module.exports = { resolveDragFiles };
