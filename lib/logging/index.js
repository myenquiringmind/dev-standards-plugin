/**
 * Logging utilities
 *
 * Session logging with debug support and structured output.
 *
 * @module lib/logging
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const { config } = require('../core');

/**
 * Get the log directory path
 *
 * @returns {string} Full path to log directory
 */
function getLogDir() {
  return path.join(os.homedir(), config.LOG_DIR);
}

/**
 * Get the session log file path
 *
 * @returns {string} Full path to session log file
 */
function getLogFile() {
  return path.join(getLogDir(), config.SESSION_LOG);
}

/**
 * Ensure the log directory exists
 *
 * @returns {string} Path to the log directory
 */
function ensureLogDir() {
  const logDir = getLogDir();
  try {
    fs.mkdirSync(logDir, { recursive: true });
  } catch (e) {
    // Directory might already exist or we don't have permissions
    if (config.DEBUG) {
      console.error(`[DEBUG] Failed to create log dir: ${e.message}`);
    }
  }
  return logDir;
}

/**
 * Log an event to the session log
 *
 * @param {string} event - Event type (e.g., 'SESSION_START', 'PROMPT')
 * @param {string} [details=''] - Additional details
 *
 * @example
 * log('SESSION_START', `in ${process.cwd()}`);
 * log('TOOL_COMPLETE');
 */
function log(event, details = '') {
  ensureLogDir();

  const timestamp = new Date().toISOString();
  const entry = `[${timestamp}] ${event}${details ? ' ' + details : ''}\n`;

  try {
    fs.appendFileSync(getLogFile(), entry);
  } catch (e) {
    if (config.DEBUG) {
      console.error(`[DEBUG] Failed to write log: ${e.message}`);
    }
  }
}

/**
 * Debug log - only outputs when DEBUG=true
 *
 * @param {...any} args - Arguments to log
 *
 * @example
 * debug('Processing file:', filePath);
 */
function debug(...args) {
  if (config.DEBUG) {
    console.error('[DEBUG]', ...args);
  }
}

/**
 * Info log - always outputs to stderr
 *
 * @param {...any} args - Arguments to log
 */
function info(...args) {
  console.error('[dev-standards]', ...args);
}

/**
 * Warning log - outputs to stderr with warning prefix
 *
 * @param {...any} args - Arguments to log
 */
function warn(...args) {
  console.error('[dev-standards] WARNING:', ...args);
}

/**
 * Error log - outputs to stderr with error prefix
 *
 * @param {...any} args - Arguments to log
 */
function error(...args) {
  console.error('[dev-standards] ERROR:', ...args);
}

/**
 * Read recent log entries
 *
 * @param {number} [lines=50] - Number of lines to read
 * @returns {string[]} Array of log lines
 */
function readRecentLogs(lines = 50) {
  const logFile = getLogFile();

  try {
    if (!fs.existsSync(logFile)) {
      return [];
    }

    const content = fs.readFileSync(logFile, 'utf8');
    const allLines = content.split('\n').filter(line => line.trim());
    return allLines.slice(-lines);
  } catch (e) {
    debug('Failed to read logs:', e.message);
    return [];
  }
}

/**
 * Clear the session log
 *
 * @returns {boolean} True if successful
 */
function clearLog() {
  const logFile = getLogFile();

  try {
    if (fs.existsSync(logFile)) {
      fs.writeFileSync(logFile, '');
    }
    return true;
  } catch (e) {
    debug('Failed to clear log:', e.message);
    return false;
  }
}

module.exports = {
  getLogDir,
  getLogFile,
  ensureLogDir,
  log,
  debug,
  info,
  warn,
  error,
  readRecentLogs,
  clearLog
};
