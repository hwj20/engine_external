const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("aurora", { 
  version: "0.1.0",
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version')
});
