/**
 * Tool execution utilities
 *
 * Formatters, linters, and type checkers with venv support.
 *
 * @module lib/tools
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { config, exec } = require('../core');
const venv = require('../venv');
const logging = require('../logging');

/**
 * Get file extension (lowercase, without dot)
 *
 * @param {string} filePath - Path to the file
 * @returns {string} File extension
 */
function getExt(filePath) {
  return path.extname(filePath).slice(1).toLowerCase();
}

/**
 * Run a Python tool through venv
 *
 * @param {string} toolName - Tool module name (e.g., 'ruff')
 * @param {string} args - Arguments for the tool
 * @param {Object} [options={}] - Options
 * @param {boolean} [options.autoCreate=true] - Create venv if needed
 * @param {string} [options.cwd=process.cwd()] - Working directory
 * @param {number} [options.timeout] - Timeout in ms
 * @returns {{success: boolean, output?: string, error?: string}}
 */
function runPythonTool(toolName, args, options = {}) {
  const {
    autoCreate = true,
    cwd = process.cwd(),
    timeout = config.TIMEOUTS.EXTENDED
  } = options;

  let pythonPath = null;
  const venvPath = venv.findVenv(cwd);

  if (venvPath) {
    pythonPath = venv.getVenvPython(venvPath);
  } else if (autoCreate) {
    try {
      pythonPath = venv.ensureVenvWithTool(cwd, toolName);
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  const escapedArgs = exec.escapeFilePath(args.replace(/^["']|["']$/g, ''));
  const cmd = pythonPath
    ? `"${pythonPath}" -m ${toolName} ${escapedArgs}`
    : `${toolName} ${escapedArgs}`;

  logging.debug(`Running: ${cmd}`);

  return exec.exec(cmd, { cwd, timeout });
}

/**
 * Format a file
 *
 * @param {string} filePath - Path to the file
 * @returns {{success: boolean, error?: string}|null} Result or null if no formatter
 */
function formatFile(filePath) {
  const ext = getExt(filePath);
  const formatter = config.FORMATTERS[ext];

  if (!formatter) {
    logging.debug(`No formatter for extension: ${ext}`);
    return null;
  }

  if (!fs.existsSync(filePath)) {
    return { success: false, error: 'File not found' };
  }

  logging.debug(`Formatting ${filePath} with ${formatter}`);

  // Python files use venv-aware execution
  if (ext === 'py') {
    return runPythonTool('ruff', `format "${filePath}"`, {
      timeout: config.TIMEOUTS.STANDARD
    });
  }

  // Other formatters run directly
  const escapedPath = exec.escapeFilePath(filePath);
  const result = exec.exec(`${formatter} ${escapedPath}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  return {
    success: result.success,
    error: result.error
  };
}

/**
 * Type check a file
 *
 * @param {string} filePath - Path to the file
 * @returns {{success: boolean, error?: string}|null} Result or null if no checker
 */
function typeCheckFile(filePath) {
  const ext = getExt(filePath);
  const checker = config.TYPE_CHECKERS[ext];

  if (!checker) {
    logging.debug(`No type checker for extension: ${ext}`);
    return null;
  }

  logging.debug(`Type checking ${filePath}`);

  // Python uses mypy through venv
  if (ext === 'py') {
    const result = runPythonTool('mypy', `--ignore-missing-imports "${filePath}"`, {
      timeout: config.TIMEOUTS.EXTENDED
    });

    if (!result.success) {
      const output = result.output || result.error || '';
      if (output.includes(checker.errorPattern)) {
        const errorLine = output.split('\n').find(l => l.includes(checker.errorPattern));
        return {
          success: false,
          error: (errorLine || 'type error').substring(0, 100)
        };
      }
    }
    return { success: true };
  }

  // TypeScript uses tsc
  const escapedPath = exec.escapeFilePath(filePath);
  const result = exec.exec(`${checker.cmd} ${escapedPath}`, {
    timeout: config.TIMEOUTS.EXTENDED
  });

  if (!result.success) {
    const output = result.output || result.stderr || '';
    if (output.includes(checker.errorPattern)) {
      const errorLine = output.split('\n').find(l => l.includes(checker.errorPattern));
      return {
        success: false,
        error: (errorLine || 'type error').substring(0, 100)
      };
    }
  }

  return { success: true };
}

/**
 * Lint a file
 *
 * @param {string} filePath - Path to the file
 * @returns {{success: boolean, warning?: string}|null} Result or null if no linter
 */
function lintFile(filePath) {
  const ext = getExt(filePath);
  const linter = config.LINTERS[ext];

  if (!linter) {
    logging.debug(`No linter for extension: ${ext}`);
    return null;
  }

  logging.debug(`Linting ${filePath}`);

  // Python uses ruff through venv
  if (ext === 'py') {
    const result = runPythonTool('ruff', `check "${filePath}"`, {
      timeout: config.TIMEOUTS.STANDARD
    });

    if (!result.success) {
      const output = result.output || result.error || '';
      if (linter.successPattern && output.includes(linter.successPattern)) {
        return { success: true };
      }
      if (output.trim()) {
        return {
          success: false,
          warning: output.split('\n')[0]
        };
      }
    }
    return { success: true };
  }

  // JS/TS use eslint
  const escapedPath = exec.escapeFilePath(filePath);
  const result = exec.exec(`${linter.cmd} ${escapedPath}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  if (!result.success) {
    const output = result.output || result.stderr || '';
    if (linter.errorPattern && linter.errorPattern.test(output)) {
      const errorLine = output.split('\n').find(l => linter.errorPattern.test(l));
      return {
        success: false,
        warning: errorLine || 'lint issues'
      };
    }
  }

  return { success: true };
}

/**
 * Process a file with all tools (format, typecheck, lint)
 *
 * @param {string} filePath - Path to the file
 * @returns {{format?: object, typecheck?: object, lint?: object}}
 */
function processFile(filePath) {
  const results = {};

  const formatResult = formatFile(filePath);
  if (formatResult) {
    results.format = formatResult;
  }

  const typeResult = typeCheckFile(filePath);
  if (typeResult) {
    results.typecheck = typeResult;
  }

  const lintResult = lintFile(filePath);
  if (lintResult) {
    results.lint = lintResult;
  }

  return results;
}

module.exports = {
  getExt,
  runPythonTool,
  formatFile,
  typeCheckFile,
  lintFile,
  processFile
};
