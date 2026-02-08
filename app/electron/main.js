const { app, BrowserWindow, shell, ipcMain, Menu } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");
const { autoUpdater } = require("electron-updater");
const log = require("electron-log");
const { initAutoUpdater, checkForUpdates } = require("./updater");

// Configure electron-updater logging
autoUpdater.logger = log;
autoUpdater.logger.transports.file.level = 'info';
log.info('App starting...');

const BACKEND_PORT = 8787;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

// ── Backend process management ──────────────────────────────────
let backendProcess = null;

/**
 * Resolve the path to the backend binary.
 * In production the binary lives inside the extraResources directory
 * that electron-builder copies next to the asar:
 *   <install>/resources/bin/backend[.exe]
 * During development we fall back to running the Python source directly.
 */
function getBackendPath() {
  const isPackaged = app.isPackaged;
  
  if (isPackaged) {
    // Production: binary is in resources/bin/
    const binName = process.platform === 'win32' ? 'backend.exe' : 'backend';
    const binPath = path.join(process.resourcesPath, 'bin', binName);
    log.info('Backend binary path (packaged):', binPath);
    // cwd is the bin directory itself; the backend reads DATA_DIR from AppData
    return { executable: binPath, args: [], cwd: path.join(process.resourcesPath, 'bin') };
  } else {
    // Development: run Python source directly
    const backendDir = path.join(__dirname, '..', '..', 'backend');
    log.info('Backend path (dev):', backendDir);
    return { executable: 'python', args: ['main.py'], cwd: backendDir };
  }
}

function startBackend() {
  if (backendProcess) {
    log.info('Backend already running (pid:', backendProcess.pid, ')');
    return;
  }

  const { executable, args, cwd } = getBackendPath();
  log.info('Starting backend:', executable, args.join(' '), '| cwd:', cwd);

  try {
    backendProcess = spawn(executable, args, {
      cwd: cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      // Ensure the child is killed when the parent exits
      detached: false
    });

    backendProcess.stdout.on('data', (data) => {
      log.info('[backend]', data.toString().trim());
    });

    backendProcess.stderr.on('data', (data) => {
      log.warn('[backend]', data.toString().trim());
    });

    backendProcess.on('error', (err) => {
      log.error('Failed to start backend:', err.message);
      backendProcess = null;
    });

    backendProcess.on('exit', (code, signal) => {
      log.info(`Backend exited (code=${code}, signal=${signal})`);
      backendProcess = null;
    });

    log.info('Backend started, pid:', backendProcess.pid);
  } catch (err) {
    log.error('Error spawning backend:', err);
    backendProcess = null;
  }
}

function stopBackend() {
  if (!backendProcess) return;
  log.info('Stopping backend (pid:', backendProcess.pid, ')');
  
  try {
    if (process.platform === 'win32') {
      // On Windows, spawn taskkill to kill the process tree
      spawn('taskkill', ['/pid', backendProcess.pid.toString(), '/f', '/t'], { windowsHide: true });
    } else {
      // Send SIGTERM; if still alive after 3s, force kill
      backendProcess.kill('SIGTERM');
      setTimeout(() => {
        if (backendProcess) {
          try { backendProcess.kill('SIGKILL'); } catch (_) {}
        }
      }, 3000);
    }
  } catch (err) {
    log.error('Error stopping backend:', err);
  }
  backendProcess = null;
}

/**
 * Wait for the backend to respond to a health check.
 * Retries every `interval` ms, up to `timeout` ms total.
 */
function waitForBackend(timeout = 30000, interval = 500) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    function check() {
      const req = http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) {
          log.info('Backend is ready');
          resolve();
        } else {
          retry();
        }
      });
      req.on('error', retry);
      req.setTimeout(1000, () => { req.destroy(); retry(); });
    }
    function retry() {
      if (Date.now() - start >= timeout) {
        log.warn('Backend did not become ready within timeout');
        resolve(); // still show window so user can see error state
      } else {
        setTimeout(check, interval);
      }
    }
    check();
  });
}

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

app.whenReady().then(async () => {
  // Start the backend process first
  startBackend();
  
  // Wait for backend to be ready before showing UI
  log.info('Waiting for backend health check...');
  await waitForBackend();
  
  const mainWindow = createWindow();
  
  // Initialize auto-updater with electron-updater
  log.info('Initializing auto-updater...');
  autoUpdater.checkForUpdatesAndNotify();
  
  // Also initialize custom updater as fallback
  initAutoUpdater();
  
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("will-quit", () => {
  stopBackend();
});

// IPC handlers for renderer process
ipcMain.handle('check-for-updates', async () => {
  return await checkForUpdates(false);
});

ipcMain.handle('get-app-version', () => {
  return require('../package.json').version;
});

// electron-updater events
autoUpdater.on('checking-for-update', () => {
  log.info('Checking for updates...');
});

autoUpdater.on('update-available', (info) => {
  log.info('Update available:', info.version);
});

autoUpdater.on('update-not-available', (info) => {
  log.info('Already on latest version');
});

autoUpdater.on('error', (err) => {
  log.error('Update error:', err);
});

autoUpdater.on('download-progress', (progressObj) => {
  log.info(`Download progress: ${progressObj.percent.toFixed(2)}%`);
});

autoUpdater.on('update-downloaded', (info) => {
  log.info('Update downloaded:', info.version);
  autoUpdater.quitAndInstall();
});
