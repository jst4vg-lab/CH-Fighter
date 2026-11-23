const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('chDesktop', {
  prepareDrag: packageId => ipcRenderer.invoke('prepare-native-drag', packageId),
  startDrag: token => ipcRenderer.send('start-native-drag', token),
  openPackageInFiles: packageId => ipcRenderer.invoke('open-package-in-files', packageId),
  copyHotPackage: packageId => ipcRenderer.invoke('copy-hot-package', packageId),
  chooseCreaLibrary: () => ipcRenderer.invoke('choose-crea-library'),
  setCommunicationsBounds: bounds => ipcRenderer.invoke('communications-bounds', bounds),
  openDiscordExternally: url => ipcRenderer.invoke('communications-external', url),
  navigateDiscord: url => ipcRenderer.invoke('communications-navigate', url),
  communicationsCapabilities: () => ipcRenderer.invoke('communications-capabilities'),
  onCommunicationsStatus: callback => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('communications-status', listener);
    return () => ipcRenderer.removeListener('communications-status', listener);
  },
  onDragError: callback => {
    const listener = (_event, message) => callback(message);
    ipcRenderer.on('native-drag-error', listener);
    return () => ipcRenderer.removeListener('native-drag-error', listener);
  }
});
