const { app, BrowserWindow } = require('electron');
const path = require('node:path');

app.whenReady().then(() => {
  const displayMode = process.argv.includes('--ozone-platform=x11') ? 'XWayland' : 'Wayland';
  const window = new BrowserWindow({ width: 900, height: 700, minWidth: 460, minHeight: 420,
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } });
  window.loadFile(path.join(__dirname, 'drop-target.html'));
  window.webContents.on('did-finish-load', () => window.setTitle(`Clan Hub drag diagnostic — ${displayMode}`));
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  let lastReport = '';
  const timer = setInterval(async () => {
    if (window.isDestroyed()) return;
    try {
      const text = await window.webContents.executeJavaScript('document.getElementById("report").textContent');
      if (text !== lastReport && text !== 'Waiting for a drop.') {
        lastReport = text;
        console.log('Received drop', text);
      }
    } catch {}
  }, 500);
  window.on('closed', () => clearInterval(timer));
});
app.on('window-all-closed', () => app.quit());
