const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('dragDiagnostic', {
  start: form => ipcRenderer.send('diagnostic-start-drag', form),
  onError: callback => ipcRenderer.on('diagnostic-drag-error', (_event, message) => callback(message))
});
