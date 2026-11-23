/* Isolated page-load probe only. No login, DOM access, or message actions. */
const { app, BrowserWindow, WebContentsView, session } = require('electron');
const fs = require('node:fs');
const profile = '/tmp/ch-command-discord-view-probe';
fs.mkdirSync(profile, { recursive: true });
app.setName('CH Discord View Probe');
app.setPath('userData', profile);
let window;
app.whenReady().then(async () => {
  window = new BrowserWindow({ width: 900, height: 650, show: false, webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } });
  const isolated = session.fromPartition('persist:ch-command-discord-probe');
  const view = new WebContentsView({ webPreferences: { session: isolated, nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true } });
  window.contentView.addChildView(view);
  view.setBounds({ x: 0, y: 0, width: 900, height: 650 });
  view.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  view.webContents.on('did-finish-load', () => console.log('DISCORD_VIEW_LOADED', view.webContents.getURL()));
  view.webContents.on('did-fail-load', (_event, code, description, url, mainFrame) => {
    if (mainFrame && code !== -3) console.log('DISCORD_VIEW_FAILED', code, description, url);
  });
  setTimeout(() => { if (window && !window.isDestroyed()) window.close(); app.quit(); }, 15000);
  try { await view.webContents.loadURL('https://discord.com/channels/@me'); }
  catch (error) { console.log('DISCORD_VIEW_LOAD_REJECTED', error.message); }
}).catch(error => { console.error(error); app.quit(); });
