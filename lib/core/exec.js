/**
 * Command execution utilities
 *
 * Provides secure command execution with proper escaping,
 * timeout handling, and error management.
 *
 * @module lib/core/exec
 */

'use strict';

const { execSync } = require('child_process');
const platform = require('./platform');
const config = require('./config');

/**
 * Escape a shell argument for safe execution
 *
 * @param {string} arg - The argument to escape
 * @returns {string} The escaped argument
 *
 * @example
 * escapeShellArg('file with spaces.txt')
 * // Windows: "file with spaces.txt"
 * // Unix: 'file with spaces.txt'
 */
function escapeShellArg(arg) {
  if (typeof arg !== 'string') {
    throw new TypeError(`Expected string, got ${typeof arg}`);
  }

  if (platform.isWindows) {
    // Windows: use double quotes, escape internal double quotes
    return `"${arg.replace(/"/g, '\\"')}"`;
  }

  // Unix: use single quotes, escape internal single quotes
  return `'${arg.replace(/'/g, "'\\''")}'`;
}

/**
 * Escape a file path for shell execution
 *
 * @param {string} filePath - The file path to escape
 * @returns {string} The escaped path
 */
function escapeFilePath(filePath) {
  return escapeShellArg(filePath);
}

/**
 * Check if a command exists in PATH
 *
 * @param {string} cmd - The command to check
 * @returns {boolean} True if the command exists
 *
 * @example
 * commandExists('node') // true
 * commandExists('nonexistent') // false
 */
function commandExists(cmd) {
  try {
    const whichCmd = platform.getWhichCommand();
    execSync(`${whichCmd} ${cmd}`, {
      stdio: 'pipe',
      timeout: config.TIMEOUTS.QUICK
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Execute a command synchronously with proper error handling
 *
 * @param {string} command - The command to execute
 * @param {Object} [options={}] - Execution options
 * @param {string} [options.cwd] - Working directory
 * @param {number} [options.timeout] - Timeout in milliseconds
 * @param {boolean} [options.silent] - Suppress output
 * @returns {{success: boolean, output?: string, error?: string, code?: number}}
 *
 * @example
 * const result = exec('git status', { timeout: 5000 });
 * if (result.success) {
 *   console.log(result.output);
 * }
 */
function exec(command, options = {}) {
  const {
    cwd = process.cwd(),
    timeout = config.TIMEOUTS.STANDARD,
    silent = false
  } = options;

  try {
    const output = execSync(command, {
      cwd,
      timeout,
      stdio: silent ? 'pipe' : 'pipe',
      encoding: 'utf8'
    });

    return {
      success: true,
      output: output?.trim() || ''
    };
  } catch (e) {
    return {
      success: false,
      error: e.message,
      output: e.stdout?.toString()?.trim() || '',
      stderr: e.stderr?.toString()?.trim() || '',
      code: e.status
    };
  }
}

/**
 * Execute a command and return output, throwing on failure
 *
 * @param {string} command - The command to execute
 * @param {Object} [options={}] - Execution options
 * @returns {string} The command output
 * @throws {Error} If the command fails
 */
function execOrThrow(command, options = {}) {
  const result = exec(command, options);
  if (!result.success) {
    throw new Error(result.error || `Command failed: ${command}`);
  }
  return result.output;
}

/**
 * Execute a Python module command
 *
 * @param {string} pythonPath - Path to Python executable
 * @param {string} moduleName - Python module to run (e.g., 'ruff')
 * @param {string} args - Arguments to pass
 * @param {Object} [options={}] - Execution options
 * @returns {{success: boolean, output?: string, error?: string}}
 */
function execPythonModule(pythonPath, moduleName, args, options = {}) {
  const escapedPython = escapeFilePath(pythonPath);
  const command = `${escapedPython} -m ${moduleName} ${args}`;
  return exec(command, options);
}

module.exports = {
  escapeShellArg,
  escapeFilePath,
  commandExists,
  exec,
  execOrThrow,
  execPythonModule
};
