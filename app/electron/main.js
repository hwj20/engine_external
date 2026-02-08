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
  const fs = require('fs');
  
  if (isPackaged) {
    // Production: PyInstaller --onedir outputs to resources/bin/backend/backend[.exe]
    const binName = process.platform === 'win32' ? 'backend.exe' : 'backend';
    const binDir = path.join(process.resourcesPath, 'bin', 'backend');
    const binPath = path.join(binDir, binName);
    
    log.info('Backend binary path (packaged):', binPath);
    log.info('Backend directory exists:', fs.existsSync(binDir));
    log.info('Backend executable exists:', fs.existsSync(binPath));
    
    // List contents of bin directory for debugging
    try {
      const binParent = path.join(process.resourcesPath, 'bin');
      if (fs.existsSync(binParent)) {
        log.info('Contents of resources/bin/:', fs.readdirSync(binParent));
      }
      if (fs.existsSync(binDir)) {
        log.info('Contents of resources/bin/backend/:', fs.readdirSync(binDir).slice(0, 20), '...');
      }
    } catch (e) {
      log.warn('Could not list bin directory:', e.message);
    }
    
    return { executable: binPath, args: [], cwd: binDir };
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
  
  // Verify binary exists before spawning
  const fs = require('fs');
  if (!fs.existsSync(executable)) {
    log.error('Backend executable not found:', executable);
    throw new Error(`Backend executable not found: ${executable}`);
  }

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
      log.error('Error code:', err.code);
      log.error('Error stack:', err.stack);
      backendProcess = null;
    });

    backendProcess.on('exit', (code, signal) => {
      log.info(`Backend exited (code=${code}, signal=${signal})`);
      backendProcess = null;
    });

    log.info('Backend started, pid:', backendProcess.pid);
  } catch (err) {
    log.error('Error spawning backend:', err.message);
    log.error('Stack:', err.stack);
    backendProcess = null;
    throw err;
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
  let attemptCount = 0;
  return new Promise((resolve, reject) => {
    function check() {
      attemptCount++;
      const elapsed = Date.now() - start;
      log.info(`[Health Check] Attempt ${attemptCount} (${elapsed}ms elapsed) - Checking ${BACKEND_URL}/health`);
      
      const req = http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) {
          log.info('[Health Check] Backend is ready ✓');
          resolve();
        } else {
          log.warn(`[Health Check] Got status ${res.statusCode}, retrying...`);
          retry();
        }
      });
      
      req.on('error', (err) => {
        log.debug(`[Health Check] Request error (${err.code}): ${err.message}`);
        retry();
      });
      
      req.setTimeout(2000, () => {
        log.debug('[Health Check] Request timeout, retrying...');
        req.destroy();
        retry();
      });
    }
    
    function retry() {
      const elapsed = Date.now() - start;
      if (elapsed >= timeout) {
        log.error(`[Health Check] Backend did not become ready within ${timeout}ms after ${attemptCount} attempts`);
        log.error('[Health Check] Showing window anyway - user may see connection errors');
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
  
  // Create window immediately but show loading state
  const mainWindow = createWindow();
  
  // Wait for backend to be ready (up to 60 seconds)
  log.info('Waiting for backend health check...');
  await waitForBackend(60000, 800);
  
  // Reload the page once backend is ready so the frontend can connect
  mainWindow.webContents.reload();
  
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
