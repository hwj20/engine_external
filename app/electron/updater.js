/**
 * Auto-Updater Module for AURORA Local Agent
 * Checks GitHub releases for updates and downloads them
 */

const { app, dialog, shell, BrowserWindow } = require('electron');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration - Update these with your GitHub repo info
const UPDATE_CONFIG = {
  owner: 'hwj20',  // GitHub username
  repo: 'engine_external', // Repo name
  currentVersion: require('../package.json').version
};

/**
 * Fetch JSON from URL
 */
function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, {
      headers: {
        'User-Agent': 'AURORA-Local-Agent-Updater',
        'Accept': 'application/vnd.github.v3+json'
      }
    }, (response) => {
      // Handle redirects
      if (response.statusCode === 301 || response.statusCode === 302) {
        fetchJSON(response.headers.location).then(resolve).catch(reject);
        return;
      }

      if (response.statusCode !== 200) {
        reject(new Error(`HTTP ${response.statusCode}`));
        return;
      }

      let data = '';
      response.on('data', chunk => data += chunk);
      response.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    });

    request.on('error', reject);
    request.setTimeout(10000, () => {
      request.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

/**
 * Compare version strings (semver-like)
 * Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
 */
function compareVersions(v1, v2) {
  const parts1 = v1.replace(/^v/, '').split('.').map(Number);
  const parts2 = v2.replace(/^v/, '').split('.').map(Number);

  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return 1;
    if (p1 < p2) return -1;
  }
  return 0;
}

/**
 * Get latest release info from GitHub
 */
async function getLatestRelease() {
  const url = `https://api.github.com/repos/${UPDATE_CONFIG.owner}/${UPDATE_CONFIG.repo}/releases/latest`;
  
  try {
    const release = await fetchJSON(url);
    
    // Determine platform-specific asset pattern
    let assetPattern;
    const platform = process.platform;
    
    if (platform === 'win32') {
      assetPattern = (a) => a.name.includes('win') && (a.name.endsWith('.exe') || a.name.endsWith('.zip'));
    } else if (platform === 'darwin') {
      assetPattern = (a) => (a.name.endsWith('.dmg') || a.name.endsWith('.zip')) && !a.name.includes('win');
    } else if (platform === 'linux') {
      assetPattern = (a) => (a.name.endsWith('.AppImage') || a.name.endsWith('.deb')) && !a.name.includes('mac') && !a.name.includes('win');
    } else {
      console.log('[Updater] Unknown platform:', platform);
      return null;
    }
    
    // Find the appropriate asset
    const asset = release.assets.find(assetPattern);

    if (!asset) {
      console.log(`[Updater] No asset found for platform ${platform} in release`);
      console.log('[Updater] Available assets:', release.assets.map(a => a.name).join(', '));
      return null;
    }

    return {
      version: release.tag_name.replace(/^v/, ''),
      downloadUrl: asset.browser_download_url,
      releaseUrl: release.html_url,
      releaseNotes: release.body,
      publishedAt: release.published_at,
      assetName: asset.name,
      assetSize: asset.size
    };
  } catch (error) {
    console.error('[Updater] Failed to fetch release:', error.message);
    return null;
  }
}

/**
 * Check for updates
 * @param {boolean} silent - If true, don't show "no updates" dialog
 */
async function checkForUpdates(silent = true) {
  console.log('[Updater] Checking for updates...');
  console.log('[Updater] Current version:', UPDATE_CONFIG.currentVersion);

  const latestRelease = await getLatestRelease();
  
  if (!latestRelease) {
    if (!silent) {
      dialog.showMessageBox({
        type: 'info',
        title: 'Update Check',
        message: 'Could not check for updates',
        detail: 'Please check your internet connection or try again later.'
      });
    }
    return { updateAvailable: false };
  }

  console.log('[Updater] Latest version:', latestRelease.version);

  const comparison = compareVersions(latestRelease.version, UPDATE_CONFIG.currentVersion);
  
  if (comparison > 0) {
    console.log('[Updater] Update available!');
    return {
      updateAvailable: true,
      currentVersion: UPDATE_CONFIG.currentVersion,
      newVersion: latestRelease.version,
      downloadUrl: latestRelease.downloadUrl,
      releaseUrl: latestRelease.releaseUrl,
      releaseNotes: latestRelease.releaseNotes
    };
  } else {
    console.log('[Updater] Already up to date');
    if (!silent) {
      dialog.showMessageBox({
        type: 'info',
        title: 'No Updates Available',
        message: 'You are running the latest version',
        detail: `Current version: ${UPDATE_CONFIG.currentVersion}`
      });
    }
    return { updateAvailable: false };
  }
}

/**
 * Show update dialog and handle user response
 */
async function promptUpdate(updateInfo) {
  const response = await dialog.showMessageBox({
    type: 'info',
    title: 'Update Available',
    message: `A new version is available: v${updateInfo.newVersion}`,
    detail: `Current version: v${updateInfo.currentVersion}\n\nWould you like to download the update now?`,
    buttons: ['Download Update', 'View Release Notes', 'Later'],
    defaultId: 0,
    cancelId: 2
  });

  switch (response.response) {
    case 0: // Download
      shell.openExternal(updateInfo.downloadUrl);
      dialog.showMessageBox({
        type: 'info',
        title: 'Download Started',
        message: 'The update is being downloaded',
        detail: 'After the download completes:\n1. Close this application\n2. Extract the new version\n3. Replace the old files\n4. Restart the application'
      });
      break;
    case 1: // View release notes
      shell.openExternal(updateInfo.releaseUrl);
      // Show the prompt again after they've seen the notes
      setTimeout(() => promptUpdate(updateInfo), 1000);
      break;
    case 2: // Later
      console.log('[Updater] User chose to update later');
      break;
  }
}

/**
 * Initialize auto-updater
 * Call this when the app is ready
 */
async function initAutoUpdater(mainWindow = null) {
  // Wait a bit before checking (let the app load first)
  setTimeout(async () => {
    try {
      const updateInfo = await checkForUpdates(true);
      if (updateInfo.updateAvailable) {
        await promptUpdate(updateInfo);
        // Notify renderer process if window exists
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('update-available', updateInfo);
        }
      }
    } catch (error) {
      console.error('[Updater] Error during update check:', error);
    }
  }, 3000);
}

/**
 * Send update status to renderer process
 */
function notifyRenderer(win, status, data = {}) {
  if (win && !win.isDestroyed()) {
    win.webContents.send('update-status', { status, ...data });
  }
}

module.exports = {
  checkForUpdates,
  promptUpdate,
  initAutoUpdater,
  getLatestRelease,
  UPDATE_CONFIG
};
