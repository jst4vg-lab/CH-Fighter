const { app, BrowserWindow, dialog, ipcMain, shell, clipboard } = require('electron');
const { spawn, execFileSync } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { resolveDragFiles } = require('./drag-files.cjs');
const { discordUsesFlatpak, exportForDiscord } = require('./document-portal.cjs');
const { syncHotFolder } = require('./hot-folder.cjs');
const { hardenWindow } = require('./security.cjs');

const project = path.resolve(__dirname, '..');
let backend;
let window;
let ready = false;
let appOrigin;
const desktopSecret = randomUUID();
let dataDirectory;
let hotFolder;
let dragIcon;
let discordFlatpak = false;
const dragDiagnostic = process.env.CH_DRAG_DIAGNOSTIC === '1';
const dragPathMode = dragDiagnostic && ['host', 'portal'].includes(process.env.CH_DRAG_PATH_MODE)
  ? process.env.CH_DRAG_PATH_MODE : null;
const dragTokens = new Map();
const hotFolderCache = new Map();
let folderQueue = Promise.resolve();
let folderPollPending = false;
let clipboardHelper;
let clipboardQueue = Promise.resolve();
let clipboardPollPending = false;
if (process.env.CH_DIAGNOSTIC_USER_DATA) {
  const diagnosticPath = path.resolve(process.env.CH_DIAGNOSTIC_USER_DATA);
  if (!diagnosticPath.startsWith('/tmp/')) throw Error('Diagnostic user data must be under /tmp');
  fs.mkdirSync(diagnosticPath, { recursive: true });
  app.setName('CH Command Suite Diagnostic');
  app.setPath('userData', diagnosticPath);
}

ipcMain.handle('copy-submission-text', (event, text) => {
  if (!trusted(event) || typeof text !== 'string' || text.length > 5000) throw Error('Invalid clipboard text');
  clipboard.writeText(text);
  return true;
});
ipcMain.handle('choose-crea-library', async event => {
  if (!trusted(event)) throw Error('Untrusted library request');
  const result=await dialog.showOpenDialog(window,{title:'Select Crea Library',properties:['openDirectory']});
  return result.canceled ? null : result.filePaths[0];
});
function copyHotPackage(packageId) {
  const next = clipboardQueue.catch(() => {}).then(async () => {
    const response = await fetch(`${appOrigin}/api/staging`, { headers: { 'X-CH-Desktop': desktopSecret } });
    if (!response.ok) throw Error('Unable to read Hot Staging');
    const files = resolveDragFiles((await response.json()).hot, packageId, dataDirectory);
    const script = fs.readFileSync(path.join(__dirname, 'clipboard-transfer.py'), 'utf8');
    const helper = spawn('/usr/bin/python3', ['-u', '-c', script, ...files], {
      env: { ...process.env, QT_QPA_PLATFORM: 'xcb' }, stdio: ['ignore', 'pipe', 'pipe']
    });
    try {
      await new Promise((resolve, reject) => {
        let output = '', errors = '';
        const timer = setTimeout(() => reject(Error('File clipboard timed out')), 12000);
        helper.stdout.on('data', chunk => { output += chunk.toString(); if (output.includes('READY ')) { clearTimeout(timer); resolve(); } });
        helper.stderr.on('data', chunk => { errors += chunk.toString(); });
        helper.on('error', error => { clearTimeout(timer); reject(error); });
        helper.on('exit', code => { clearTimeout(timer); reject(Error(errors.trim() || `File clipboard exited (${code})`)); });
      });
    } catch (error) { helper.kill('SIGTERM'); throw error; }
    const previous = clipboardHelper;
    clipboardHelper = helper;
    if (previous && !previous.killed) previous.kill('SIGTERM');
    return { count: files.length };
  });
  clipboardQueue = next;
  return next;
}

async function pollClipboardRequests() {
  if (clipboardPollPending) return;
  clipboardPollPending = true;
  try {
    const headers = { 'X-CH-Desktop': desktopSecret };
    const response = await fetch(`${appOrigin}/api/desktop/clipboard-request`, { headers });
    if (!response.ok) return;
    const { request } = await response.json();
    if (!request) return;
    let result;
    try { result = { id: request.id, ok: true, ...(await copyHotPackage(request.package_id)) }; }
    catch (error) { result = { id: request.id, ok: false, error: error.message }; }
    await fetch(`${appOrigin}/api/desktop/clipboard-result`, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(result) });
  } catch (error) { console.error('Clipboard request failed:', error.message); }
  finally { clipboardPollPending = false; }
}

function refreshHotFolder() {
  const next = folderQueue.catch(() => {}).then(async () => {
    const response = await fetch(`${appOrigin}/api/staging`, { headers: { 'X-CH-Desktop': desktopSecret } });
    if (!response.ok) throw Error('Unable to read Hot Staging for Files');
    const hot = (await response.json()).hot;
    const result = await syncHotFolder(hot, dataDirectory, hotFolder, hotFolderCache);
    if (result.missing && window && !window.isDestroyed()) {
      window.webContents.send('native-drag-error', 'Hot folder is incomplete: a formatted crea is unavailable');
    }
    return { hot, result };
  });
  folderQueue = next;
  return next;
}

function trusted(event) {
  try {
    return Boolean(window && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame &&
      new URL(event.senderFrame.url).origin === appOrigin);
  } catch { return false; }
}

ipcMain.handle('prepare-native-drag', async (event, packageId) => {
  if (!trusted(event) || typeof packageId !== 'string') throw Error('Invalid drag request');
  const response = await fetch(`${appOrigin}/api/staging`, { headers: { 'X-CH-Desktop': desktopSecret } });
  if (!response.ok) throw Error('Unable to read Hot Staging');
  const hot = (await response.json()).hot;
  const files = resolveDragFiles(hot, packageId, dataDirectory);
  const usePortal = dragPathMode ? dragPathMode === 'portal' : discordFlatpak;
  const offeredFiles = usePortal ? await exportForDiscord(files) : files;
  if (dragDiagnostic) console.info('Drag prepared', { pathMode: usePortal ? 'portal' : 'host', count: offeredFiles.length,
    bytes: offeredFiles.map(file => fs.statSync(file).size) });
  const token = randomUUID();
  for (const [key, value] of dragTokens) if (value.expires < Date.now()) dragTokens.delete(key);
  dragTokens.set(token, { files: offeredFiles, expires: Date.now() + 900000 });
  return token;
});

ipcMain.on('start-native-drag', (event, token) => {
  if (!trusted(event)) return;
  const prepared = dragTokens.get(token);
  dragTokens.delete(token);
  if (!prepared || Date.now() > prepared.expires) return event.sender.send('native-drag-error', 'Drag preparation expired; try again');
  try {
    for (const file of prepared.files) if (!fs.statSync(file).isFile()) throw Error('A formatted crea is unavailable');
    if (dragDiagnostic) console.info('Native startDrag called', { count: prepared.files.length,
      bytes: prepared.files.map(file => fs.statSync(file).size) });
    event.sender.startDrag(prepared.files.length === 1 ? { file: prepared.files[0], icon: dragIcon } : { files: prepared.files, icon: dragIcon });
  } catch (error) {
    event.sender.send('native-drag-error', error.message);
  }
});

ipcMain.handle('open-package-in-files', async (event, packageId) => {
  if (!trusted(event) || typeof packageId !== 'string') throw Error('Invalid package request');
  const { hot, result } = await refreshHotFolder();
  if (!hot || hot.id !== packageId || result.missing) throw Error('Hot folder is not ready for this package');
  const error = await shell.openPath(hotFolder);
  if (error) throw Error(`Unable to open package in Files: ${error}`);
});

ipcMain.handle('copy-hot-package', async (event, packageId) => {
  if (!trusted(event) || typeof packageId !== 'string') throw Error('Invalid clipboard request');
  return copyHotPackage(packageId);
});

const hasInstanceLock = app.requestSingleInstanceLock();
if (process.env.CH_COMMUNICATIONS_DIAGNOSTIC === '1') console.info('Communications diagnostic instance lock:', hasInstanceLock);
if (!hasInstanceLock) app.quit();
else {
  app.on('second-instance', () => { if (window) { window.show(); window.focus(); } });
  app.whenReady().then(start);
}

function start() {
  discordFlatpak = discordUsesFlatpak();
  const resources = app.isPackaged ? process.resourcesPath : project;
  dragIcon = path.join(resources, 'public', 'icons', 'icon-48.png');
  const legacyProject = path.join(os.homedir(), 'Desktop', 'CH-Fighter');
  const source = path.join(legacyProject, 'Crea');
  const dataBase = process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share');
  const data = path.join(dataBase, 'clan-hub-crea-manager');
  dataDirectory = data;
  hotFolder = path.join(data, 'hot-staging');
  const config = path.join(dataBase, 'clan-hub-crea-manager-source.json');
  let remoteHost = '';
  try {
    const status = JSON.parse(execFileSync('tailscale', ['status', '--json'], { timeout: 3000, encoding: 'utf8' }));
    remoteHost = (status.Self?.DNSName || '').replace(/\.$/, '').toLowerCase();
  } catch { /* Tailscale is optional until mobile setup. */ }
  remoteHost ||= (process.env.CH_REMOTE_HOST || '').toLowerCase();
  let sourcePath = source;
  let hasSavedSource=false;
  try { sourcePath = JSON.parse(fs.readFileSync(config, 'utf8')).source;hasSavedSource=true; } catch {}
  if (!hasSavedSource && !fs.existsSync(sourcePath)) {
    const choice = dialog.showOpenDialogSync({ title: 'Select the original Crea folder', properties: ['openDirectory'] });
    if (!choice) { app.quit(); return; }
    sourcePath = choice[0];
  }
  fs.mkdirSync(dataBase, { recursive: true });
  fs.writeFileSync(config, JSON.stringify({ source: sourcePath }));
  const executable = app.isPackaged ? path.join(resources, 'backend', 'clan-hub-backend') : (process.env.CH_PYTHON || 'python3');
  const args = app.isPackaged ? ['--port', '8765'] : [path.join(project, 'server.py'), '--port', '8765'];
  backend = spawn(executable, args, {
    cwd: resources,
    env: { ...process.env, CH_DESKTOP: '1', CH_DESKTOP_SECRET: desktopSecret, CH_REMOTE_HOST: remoteHost, CH_CREA_SOURCE: sourcePath, CH_DATA_DIR: data,
      CH_LEGACY_DATA: path.join(legacyProject, 'data'), CH_WEB_ROOT: path.join(resources, 'dist'),
      CH_FONT_PATH: path.join(resources, 'assets', 'fonts', 'NotoSans-Bold.ttf') },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  let output = '';
  let errors = '';
  backend.stdout.on('data', chunk => {
    output += chunk.toString();
    const match = output.match(/CH_READY (\d+)/);
    if (match && !ready) {
      ready = true;
      appOrigin = `http://127.0.0.1:${match[1]}`;
      window = new BrowserWindow({ width: 1440, height: 900, minWidth: 420, minHeight: 520,
        icon: path.join(resources, 'public', 'icons', 'icon-512.png'),
        webPreferences: { partition: 'ch-local-app', preload: path.join(__dirname, 'preload.cjs'), nodeIntegration: false, contextIsolation: true, sandbox: true } });
      hardenWindow(window, appOrigin, desktopSecret);
      window.loadURL(`${appOrigin}/`);
      refreshHotFolder().catch(error => console.error('Hot folder sync failed:', error));
      const folderTimer = setInterval(() => {
        if (folderPollPending) return;
        folderPollPending = true;
        refreshHotFolder().catch(error => console.error('Hot folder sync failed:', error))
          .finally(() => { folderPollPending = false; });
      }, 1000);
      const clipboardTimer = setInterval(pollClipboardRequests, 1000);
      window.on('closed', () => clearInterval(folderTimer));
      window.on('closed', () => clearInterval(clipboardTimer));
      window.on('closed', () => app.quit());
    }
  });
  backend.stderr.on('data', chunk => { errors += chunk.toString(); });
  backend.on('error', error => startupError(error.message));
  backend.on('exit', code => { if (!ready) startupError(errors || `Backend exited (${code})`); else app.quit(); });
  setTimeout(() => { if (!ready) startupError(errors || 'Backend startup timed out'); }, 30000).unref();
}

function startupError(message) {
  if (ready) return;
  ready = true;
  dialog.showErrorBox('Clan Hub could not start', message);
  app.quit();
}

app.on('before-quit', () => { if (backend && !backend.killed) backend.kill('SIGTERM'); if (clipboardHelper && !clipboardHelper.killed) clipboardHelper.kill('SIGTERM'); });
