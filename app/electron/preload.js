const { contextBridge, ipcRenderer } = require("electron");

// Expose API to renderer process
contextBridge.exposeInMainWorld("aurora", { 
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version')
});
