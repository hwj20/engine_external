const { app, BrowserWindow, shell, ipcMain, Menu } = require("electron");
const path = require("path");
const { initAutoUpdater, checkForUpdates } = require("./updater");

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    webPreferences: { preload: path.join(__dirname, "preload.js") }
  });

  win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  // Create application menu with update check
  const menuTemplate = [
    {
      label: 'File',
      submenu: [
        { role: 'quit' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Check for Updates...',
          click: () => checkForUpdates(false)
        },
        { type: 'separator' },
        {
          label: 'About',
          click: () => {
            const pkg = require('../package.json');
            const { dialog } = require('electron');
            dialog.showMessageBox(win, {
              type: 'info',
              title: 'About AURORA',
              message: 'AURORA Local Agent MVP',
              detail: `Version: ${pkg.version}\n\nA local AI assistant with memory capabilities.`
            });
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(menuTemplate);
  Menu.setApplicationMenu(menu);

  return win;
}

app.whenReady().then(() => {
  const mainWindow = createWindow();
  
  // Initialize auto-updater
  initAutoUpdater();
  
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// IPC handlers for renderer process
ipcMain.handle('check-for-updates', async () => {
  return await checkForUpdates(false);
});

ipcMain.handle('get-app-version', () => {
  return require('../package.json').version;
});
