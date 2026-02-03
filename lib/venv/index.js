/**
 * Virtual environment utilities
 *
 * Provides cross-platform venv discovery, creation, and package management.
 *
 * @module lib/venv
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { platform, config, exec } = require('../core');
const errors = require('../errors');

/**
 * Get path to Python executable in a venv
 *
 * @param {string} venvPath - Path to venv directory
 * @returns {string} Path to python executable
 *
 * @example
 * getVenvPython('/project/.venv')
 * // Unix: '/project/.venv/bin/python'
 * // Windows: '/project/.venv/Scripts/python.exe'
 */
function getVenvPython(venvPath) {
  if (platform.isWindows) {
    return path.join(venvPath, 'Scripts', 'python.exe');
  }
  return path.join(venvPath, 'bin', 'python');
}

/**
 * Get path to pip executable in a venv
 *
 * @param {string} venvPath - Path to venv directory
 * @returns {string} Path to pip executable
 *
 * @example
 * getVenvPip('/project/.venv')
 * // Unix: '/project/.venv/bin/pip'
 * // Windows: '/project/.venv/Scripts/pip.exe'
 */
function getVenvPip(venvPath) {
  if (platform.isWindows) {
    return path.join(venvPath, 'Scripts', 'pip.exe');
  }
  return path.join(venvPath, 'bin', 'pip');
}

/**
 * Find existing venv in a directory
 *
 * Searches for common venv directory names and returns the first one found
 * that contains a valid Python executable.
 *
 * @param {string} [dir=process.cwd()] - Directory to search in
 * @returns {string|null} Path to venv directory, or null if not found
 *
 * @example
 * findVenv('/project')
 * // Returns '/project/.venv' if it exists with valid python
 */
function findVenv(dir = process.cwd()) {
  for (const name of config.VENV_NAMES) {
    const venvPath = path.join(dir, name);
    const pythonPath = getVenvPython(venvPath);

    if (fs.existsSync(pythonPath)) {
      return venvPath;
    }
  }
  return null;
}

/**
 * Validate a package name for security
 *
 * @param {string} name - Package name to validate
 * @returns {boolean} True if valid
 * @throws {errors.SecurityError} If package name is invalid or dangerous
 *
 * @example
 * validatePackageName('ruff')  // true
 * validatePackageName('rm -rf')  // throws SecurityError
 */
function validatePackageName(name) {
  if (!name || typeof name !== 'string') {
    throw new errors.SecurityError('Package name required');
  }

  if (!config.VALID_PACKAGE_NAME.test(name)) {
    throw new errors.SecurityError(`Invalid package name: ${name}`);
  }

  // Check for path traversal or command injection
  if (name.includes('..') || name.includes('/') || name.includes('\\')) {
    throw new errors.SecurityError(`Unsafe package name: ${name}`);
  }

  // Check for shell metacharacters
  if (/[;&|`$(){}[\]<>]/.test(name)) {
    throw new errors.SecurityError(`Package name contains unsafe characters: ${name}`);
  }

  return true;
}

/**
 * Create a new virtual environment
 *
 * Prefers uv for speed if available, falls back to standard venv.
 *
 * @param {string} venvPath - Path where venv should be created
 * @param {Object} [options={}] - Options
 * @param {boolean} [options.preferUv=true] - Prefer uv over standard venv
 * @returns {{success: boolean, error?: string}}
 *
 * @example
 * createVenv('/project/.venv')
 * // Creates venv at /project/.venv
 */
function createVenv(venvPath, options = {}) {
  const { preferUv = true } = options;

  // Security: Validate venv path
  const absPath = path.resolve(venvPath);
  if (absPath.includes('..') || !absPath.startsWith(process.cwd())) {
    return { success: false, error: 'Venv path must be within project directory' };
  }

  // Try uv first if preferred and available
  if (preferUv && exec.commandExists('uv')) {
    const result = exec.exec(`uv venv "${absPath}"`, {
      timeout: config.TIMEOUTS.LONG
    });

    if (result.success) {
      return { success: true };
    }
    // Fall through to standard venv if uv fails
  }

  // Use standard python venv
  const pythonCmd = platform.isWindows ? 'python' : 'python3';
  const result = exec.exec(`${pythonCmd} -m venv "${absPath}"`, {
    timeout: config.TIMEOUTS.LONG
  });

  return {
    success: result.success,
    error: result.error
  };
}

/**
 * Install a package in a venv
 *
 * @param {string} venvPath - Path to venv
 * @param {string} packageName - Package to install
 * @param {Object} [options={}] - Options
 * @param {boolean} [options.preferUv=true] - Use uv pip if available
 * @returns {{success: boolean, error?: string}}
 *
 * @example
 * installPackage('/project/.venv', 'ruff')
 */
function installPackage(venvPath, packageName, options = {}) {
  const { preferUv = true } = options;

  // Validate package name
  try {
    validatePackageName(packageName);
  } catch (e) {
    return { success: false, error: e.message };
  }

  const pythonPath = getVenvPython(venvPath);

  if (!fs.existsSync(pythonPath)) {
    return { success: false, error: 'Venv does not exist' };
  }

  // Try uv pip first if preferred and available
  if (preferUv && exec.commandExists('uv')) {
    const result = exec.exec(`uv pip install ${packageName} --python "${pythonPath}"`, {
      timeout: config.TIMEOUTS.INSTALL
    });

    if (result.success) {
      return { success: true };
    }
    // Fall through to standard pip if uv fails
  }

  // Use standard pip
  const pipPath = getVenvPip(venvPath);
  const result = exec.exec(`"${pipPath}" install ${packageName}`, {
    timeout: config.TIMEOUTS.INSTALL
  });

  return {
    success: result.success,
    error: result.error
  };
}

/**
 * Check if a tool is installed in the venv
 *
 * @param {string} venvPath - Path to venv
 * @param {string} toolName - Tool/module name to check
 * @returns {boolean} True if tool is installed
 *
 * @example
 * isToolInstalled('/project/.venv', 'ruff')  // true if ruff is installed
 */
function isToolInstalled(venvPath, toolName) {
  const pythonPath = getVenvPython(venvPath);

  if (!fs.existsSync(pythonPath)) {
    return false;
  }

  const result = exec.exec(`"${pythonPath}" -m ${toolName} --version`, {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success;
}

/**
 * Ensure venv exists with a specific tool installed
 *
 * Creates venv if needed, installs tool if needed.
 *
 * @param {string} [dir=process.cwd()] - Project directory
 * @param {string} toolName - Tool that must be available
 * @returns {string} Path to Python executable
 * @throws {errors.VenvError} If venv creation or tool installation fails
 *
 * @example
 * const python = ensureVenvWithTool('/project', 'ruff');
 * // Returns '/project/.venv/bin/python' with ruff installed
 */
function ensureVenvWithTool(dir = process.cwd(), toolName) {
  // Validate tool name
  try {
    validatePackageName(toolName);
  } catch (e) {
    throw new errors.VenvError(`Invalid tool name: ${e.message}`);
  }

  // Try to find existing venv
  let venvPath = findVenv(dir);

  // Create venv if not found
  if (!venvPath) {
    venvPath = path.join(dir, '.venv');
    const createResult = createVenv(venvPath);

    if (!createResult.success) {
      throw new errors.VenvError(`Failed to create venv: ${createResult.error}`);
    }
  }

  // Check if tool is installed
  if (!isToolInstalled(venvPath, toolName)) {
    const installResult = installPackage(venvPath, toolName);

    if (!installResult.success) {
      throw new errors.VenvError(`Failed to install ${toolName}: ${installResult.error}`);
    }
  }

  return getVenvPython(venvPath);
}

/**
 * Get all Python dependencies that should be installed
 *
 * @returns {string[]} List of package names
 */
function getRequiredDependencies() {
  return [...config.PYTHON_DEPS];
}

/**
 * Ensure all required Python tools are installed in a venv
 *
 * @param {string} [dir=process.cwd()] - Project directory
 * @returns {{success: boolean, installed: string[], failed: string[]}}
 *
 * @example
 * ensureAllTools('/project')
 * // Installs ruff, mypy, etc. as needed
 */
function ensureAllTools(dir = process.cwd()) {
  const installed = [];
  const failed = [];

  // Find or create venv
  let venvPath = findVenv(dir);
  if (!venvPath) {
    venvPath = path.join(dir, '.venv');
    const result = createVenv(venvPath);
    if (!result.success) {
      return { success: false, installed, failed: config.PYTHON_DEPS };
    }
  }

  // Install each dependency
  for (const dep of config.PYTHON_DEPS) {
    if (!isToolInstalled(venvPath, dep)) {
      const result = installPackage(venvPath, dep);
      if (result.success) {
        installed.push(dep);
      } else {
        failed.push(dep);
      }
    }
  }

  return {
    success: failed.length === 0,
    installed,
    failed
  };
}

module.exports = {
  getVenvPython,
  getVenvPip,
  findVenv,
  validatePackageName,
  createVenv,
  installPackage,
  isToolInstalled,
  ensureVenvWithTool,
  getRequiredDependencies,
  ensureAllTools
};
