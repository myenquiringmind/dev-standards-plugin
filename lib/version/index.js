/**
 * Version checking utilities
 *
 * Check for plugin updates from GitHub releases.
 *
 * @module lib/version
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');
const { config } = require('../core');
const logging = require('../logging');

/**
 * Get the plugin's installed directory
 *
 * @returns {string} Path to plugin root
 */
function getPluginDir() {
  return path.resolve(__dirname, '../..');
}

/**
 * Get cache file path for version checks
 *
 * @returns {string} Full path to cache file
 */
function getVersionCacheFile() {
  return path.join(os.homedir(), '.claude', config.VERSION_CACHE_FILE);
}

/**
 * Check if we should skip version check (cached recently)
 *
 * @returns {boolean} True if we should skip
 */
function shouldSkipVersionCheck() {
  try {
    const cacheFile = getVersionCacheFile();
    if (!fs.existsSync(cacheFile)) {
      return false;
    }

    const cache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    const lastCheck = new Date(cache.lastCheck).getTime();
    return Date.now() - lastCheck < config.TIMEOUTS.VERSION_CACHE_MS;
  } catch {
    return false;
  }
}

/**
 * Save version check result to cache
 *
 * @param {string} latestVersion - The latest version found
 */
function saveVersionCache(latestVersion) {
  try {
    const cacheDir = path.join(os.homedir(), '.claude');
    fs.mkdirSync(cacheDir, { recursive: true });

    fs.writeFileSync(getVersionCacheFile(), JSON.stringify({
      lastCheck: new Date().toISOString(),
      latestVersion,
      currentVersion: config.PLUGIN_VERSION
    }));
  } catch (e) {
    logging.debug('Failed to save version cache:', e.message);
  }
}

/**
 * Compare semantic versions
 *
 * @param {string} a - First version
 * @param {string} b - Second version
 * @returns {number} 1 if a > b, -1 if a < b, 0 if equal
 *
 * @example
 * compareVersions('1.2.0', '1.1.0'); // 1
 * compareVersions('1.0.0', '2.0.0'); // -1
 */
function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);

  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na > nb) return 1;
    if (na < nb) return -1;
  }
  return 0;
}

/**
 * Get current plugin version
 *
 * @returns {string} Current version
 */
function getPluginVersion() {
  return config.PLUGIN_VERSION;
}

/**
 * Check for newer plugin version (async, non-blocking)
 *
 * @returns {Promise<{hasUpdate?: boolean, latestVersion?: string, currentVersion: string, skipped?: boolean, error?: string}>}
 *
 * @example
 * const result = await checkForUpdates();
 * if (result.hasUpdate) {
 *   console.log(`Update available: ${result.latestVersion}`);
 * }
 */
async function checkForUpdates() {
  if (shouldSkipVersionCheck()) {
    logging.debug('Skipping version check (cached)');
    return { skipped: true, currentVersion: config.PLUGIN_VERSION };
  }

  return new Promise((resolve) => {
    const url = `https://api.github.com/repos/${config.PLUGIN_REPO}/releases/latest`;

    logging.debug('Checking for updates:', url);

    const req = https.get(url, {
      headers: { 'User-Agent': 'dev-standards-plugin' },
      timeout: config.TIMEOUTS.VERSION_CHECK
    }, (res) => {
      if (res.statusCode !== 200) {
        resolve({
          error: `HTTP ${res.statusCode}`,
          currentVersion: config.PLUGIN_VERSION
        });
        return;
      }

      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const release = JSON.parse(data);
          const latestVersion = release.tag_name?.replace(/^v/, '') || null;

          if (latestVersion) {
            saveVersionCache(latestVersion);

            const hasUpdate = compareVersions(latestVersion, config.PLUGIN_VERSION) > 0;
            resolve({
              hasUpdate,
              latestVersion,
              currentVersion: config.PLUGIN_VERSION,
              releaseUrl: release.html_url
            });
          } else {
            resolve({
              error: 'No version found',
              currentVersion: config.PLUGIN_VERSION
            });
          }
        } catch (e) {
          resolve({
            error: e.message,
            currentVersion: config.PLUGIN_VERSION
          });
        }
      });
    });

    req.on('error', (e) => {
      resolve({
        error: e.message,
        currentVersion: config.PLUGIN_VERSION
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({
        error: 'timeout',
        currentVersion: config.PLUGIN_VERSION
      });
    });
  });
}

/**
 * Check for updates and log if available (fire-and-forget)
 *
 * Call this at session start without awaiting.
 */
function checkForUpdatesAsync() {
  checkForUpdates().then(result => {
    if (result.hasUpdate) {
      logging.info(
        `Update available: ${result.currentVersion} -> ${result.latestVersion}`,
        `(https://github.com/${config.PLUGIN_REPO}/releases)`
      );
    }
  }).catch(() => {
    // Silently ignore errors
  });
}

module.exports = {
  getPluginDir,
  getVersionCacheFile,
  shouldSkipVersionCheck,
  saveVersionCache,
  compareVersions,
  getPluginVersion,
  checkForUpdates,
  checkForUpdatesAsync
};
