/**
 * Platform detection utilities
 *
 * Single source of truth for all platform-specific logic.
 * Eliminates scattered `process.platform === 'win32'` checks.
 *
 * @module lib/core/platform
 */

'use strict';

/**
 * Whether the current platform is Windows
 * @type {boolean}
 */
const isWindows = process.platform === 'win32';

/**
 * Whether the current platform is macOS
 * @type {boolean}
 */
const isMacOS = process.platform === 'darwin';

/**
 * Whether the current platform is Linux
 * @type {boolean}
 */
const isLinux = process.platform === 'linux';

/**
 * Get the Python executable name for the current platform
 * @returns {string} 'python' on Windows, 'python3' on Unix
 */
function getPythonCommand() {
  return isWindows ? 'python' : 'python3';
}

/**
 * Get the command to check if an executable exists
 * @returns {string} 'where' on Windows, 'which' on Unix
 */
function getWhichCommand() {
  return isWindows ? 'where' : 'which';
}

/**
 * Get the venv subdirectory for Python executables
 * @returns {string} 'Scripts' on Windows, 'bin' on Unix
 */
function getVenvBinDir() {
  return isWindows ? 'Scripts' : 'bin';
}

/**
 * Get the Python executable filename
 * @returns {string} 'python.exe' on Windows, 'python' on Unix
 */
function getPythonExecutable() {
  return isWindows ? 'python.exe' : 'python';
}

/**
 * Get the pip executable filename
 * @returns {string} 'pip.exe' on Windows, 'pip' on Unix
 */
function getPipExecutable() {
  return isWindows ? 'pip.exe' : 'pip';
}

/**
 * Get the path separator for the current platform
 * @returns {string} ';' on Windows, ':' on Unix
 */
function getPathSeparator() {
  return isWindows ? ';' : ':';
}

/**
 * Get the line ending for the current platform
 * @returns {string} '\r\n' on Windows, '\n' on Unix
 */
function getLineEnding() {
  return isWindows ? '\r\n' : '\n';
}

module.exports = {
  // Platform flags
  isWindows,
  isMacOS,
  isLinux,

  // Platform-specific commands
  getPythonCommand,
  getWhichCommand,

  // Venv paths
  getVenvBinDir,
  getPythonExecutable,
  getPipExecutable,

  // System
  getPathSeparator,
  getLineEnding
};
