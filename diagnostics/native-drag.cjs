const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const file = process.env.CH_DRAG_TEST_FILE;
const secondFile = process.env.CH_DRAG_TEST_SECOND_FILE;
if (!file || !path.isAbsolute(file)) throw Error('Set CH_DRAG_TEST_FILE to an absolute formatted JPEG path');
const stat = fs.statSync(file);
const magic = fs.readFileSync(file).subarray(0, 3);
if (!stat.isFile() || !stat.size || !magic.equals(Buffer.from([0xff, 0xd8, 0xff]))) {
  throw Error('Diagnostic file must be a readable JPEG');
}
if (secondFile) {
  if (!path.isAbsolute(secondFile) || !fs.statSync(secondFile).isFile()) throw Error('Second diagnostic path must be an absolute file');
  const secondMagic = fs.readFileSync(secondFile).subarray(0, 3);
  if (!secondMagic.equals(Buffer.from([0xff, 0xd8, 0xff]))) throw Error('Second diagnostic file must be a JPEG');
}
const icon = path.resolve(__dirname, '..', 'public', 'icons', 'icon-48.png');
const mode = process.argv.includes('--ozone-platform=x11') ? 'XWayland' : 'Wayland';
console.log('Diagnostic source ready', { mode, file, bytes: stat.size, secondFile,
  secondBytes: secondFile ? fs.statSync(secondFile).size : null, iconExists: fs.existsSync(icon) });

ipcMain.on('diagnostic-start-drag', (event, apiForm) => {
  const when = new Date().toISOString();
  console.log(when, 'IPC drag request', { apiForm, sender: event.sender.id });
  if (!['file', 'files', 'two-files'].includes(apiForm) || (apiForm === 'two-files' && !secondFile)) return;
  try {
    const item = apiForm === 'file' ? { file, icon } : { files: apiForm === 'two-files' ? [file, secondFile] : [file], icon };
    console.log(new Date().toISOString(), 'calling startDrag', { apiForm, bytes: item.files?.map(name => fs.statSync(name).size) || [stat.size] });
    event.sender.startDrag(item);
    console.log(new Date().toISOString(), 'startDrag returned', { apiForm });
  } catch (error) {
    console.error(new Date().toISOString(), 'startDrag threw', error);
    event.sender.send('diagnostic-drag-error', error.message);
  }
});

app.whenReady().then(() => {
  const window = new BrowserWindow({ width: 500, height: 360,
    webPreferences: { preload: path.join(__dirname, 'native-drag-preload.cjs'),
      nodeIntegration: false, contextIsolation: true, sandbox: true } });
  window.loadFile(path.join(__dirname, 'native-drag.html'));
  window.webContents.on('did-finish-load', () => window.setTitle(`Native JPEG drag test — ${mode}`));
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
});
app.on('window-all-closed', () => app.quit());
