const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('chDesktop', {
  prepareDrag: packageId => ipcRenderer.invoke('prepare-native-drag', packageId),
  startDrag: token => ipcRenderer.send('start-native-drag', token),
  openPackageInFiles: packageId => ipcRenderer.invoke('open-package-in-files', packageId),
  copyHotPackage: packageId => ipcRenderer.invoke('copy-hot-package', packageId),
  copyText: text => ipcRenderer.invoke('copy-submission-text', text),
  chooseCreaLibrary: () => ipcRenderer.invoke('choose-crea-library'),
  onDragError: callback => {
    const listener = (_event, message) => callback(message);
    ipcRenderer.on('native-drag-error', listener);
    return () => ipcRenderer.removeListener('native-drag-error', listener);
  }
});
