const { contextBridge, ipcRenderer } = require("electron");
const pkg = require("../package.json");

contextBridge.exposeInMainWorld("aurora", { 
  version: pkg.version,
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version')
});
