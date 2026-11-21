const { execFile, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { promisify } = require('node:util');

const run = promisify(execFile);
const discordId = 'com.discordapp.Discord';

function discordUsesFlatpak() {
  try {
    execFileSync('flatpak', ['info', '--show-location', discordId], { stdio: 'ignore', timeout: 5000 });
    return true;
  } catch { return false; }
}

async function exportForDiscord(files, execute = run) {
  return Promise.all(files.map(async file => {
    const { stdout } = await execute('flatpak', ['document-export', `--app=${discordId}`, '--allow-read', file], { timeout: 15000 });
    const exported = stdout.trim();
    const documentRoot = `/run/user/${process.getuid()}/doc/`;
    if (!exported.startsWith(documentRoot) || path.basename(exported) !== path.basename(file) ||
        !fs.statSync(exported).isFile()) throw Error('Document portal did not provide a readable crea file');
    return exported;
  }));
}

module.exports = { discordUsesFlatpak, exportForDiscord };
