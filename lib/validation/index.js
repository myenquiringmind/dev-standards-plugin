/**
 * Input validation and security utilities
 *
 * Dangerous command detection and input sanitization.
 *
 * @module lib/validation
 */

'use strict';

const { config } = require('../core');

/**
 * Check if a command is potentially dangerous
 *
 * @param {string} cmd - The command to check
 * @returns {boolean} True if the command matches a dangerous pattern
 *
 * @example
 * isDangerousCommand('rm -rf /'); // true
 * isDangerousCommand('git status'); // false
 */
function isDangerousCommand(cmd) {
  if (typeof cmd !== 'string') {
    return false;
  }

  for (const pattern of config.DANGEROUS_PATTERNS) {
    if (pattern.test(cmd)) {
      return true;
    }
  }
  return false;
}

/**
 * Get the reason why a command is dangerous
 *
 * @param {string} cmd - The command to check
 * @returns {string|null} Description of why it's dangerous, or null if safe
 */
function getDangerReason(cmd) {
  if (typeof cmd !== 'string') {
    return null;
  }

  const reasons = [
    { pattern: /rm\s+-rf\s+\/(?!tmp)/, reason: 'Recursive delete of root directory' },
    { pattern: /rm\s+-rf\s+~/, reason: 'Recursive delete of home directory' },
    { pattern: /rm\s+-rf\s+\*/, reason: 'Recursive delete with wildcard' },
    { pattern: /DROP\s+(DATABASE|TABLE)/i, reason: 'SQL DROP statement' },
    { pattern: /TRUNCATE\s+TABLE/i, reason: 'SQL TRUNCATE statement' },
    { pattern: /DELETE\s+FROM\s+\w+\s*;?$/i, reason: 'Unrestricted SQL DELETE' },
    { pattern: /:(){.*};:/, reason: 'Fork bomb' },
    { pattern: /mkfs\./, reason: 'Filesystem formatting command' },
    { pattern: /dd\s+if=.*of=\/dev/, reason: 'Direct disk write' },
    { pattern: /chmod\s+-R\s+777\s+\//, reason: 'Recursive permission change on root' },
    { pattern: /curl.*\|\s*(bash|sh)/, reason: 'Remote code execution via curl' },
    { pattern: /wget.*\|\s*(bash|sh)/, reason: 'Remote code execution via wget' },
    { pattern: /format\s+[cdefgh]:/i, reason: 'Windows format command' },
    { pattern: /Remove-Item.*-Recurse.*-Force.*[A-Z]:\\/i, reason: 'PowerShell recursive delete' }
  ];

  for (const { pattern, reason } of reasons) {
    if (pattern.test(cmd)) {
      return reason;
    }
  }

  return null;
}

/**
 * Validate package name for security
 *
 * @param {string} name - Package name to validate
 * @returns {boolean} True if valid
 *
 * @example
 * isValidPackageName('ruff'); // true
 * isValidPackageName('evil; rm -rf /'); // false
 */
function isValidPackageName(name) {
  return config.VALID_PACKAGE_NAME.test(name);
}

/**
 * Validate file path for security
 *
 * @param {string} filePath - Path to validate
 * @returns {{valid: boolean, reason?: string}}
 */
function validateFilePath(filePath) {
  if (typeof filePath !== 'string') {
    return { valid: false, reason: 'Path must be a string' };
  }

  if (filePath.length === 0) {
    return { valid: false, reason: 'Path cannot be empty' };
  }

  // Check for path traversal attempts
  if (filePath.includes('..')) {
    // Allow relative paths that don't try to escape
    const normalized = require('path').normalize(filePath);
    if (normalized.startsWith('..')) {
      return { valid: false, reason: 'Path traversal detected' };
    }
  }

  // Check for null bytes (security vulnerability)
  if (filePath.includes('\0')) {
    return { valid: false, reason: 'Null byte in path' };
  }

  return { valid: true };
}

/**
 * Sanitize user input by removing dangerous characters
 *
 * @param {string} input - Input to sanitize
 * @returns {string} Sanitized input
 */
function sanitizeInput(input) {
  if (typeof input !== 'string') {
    return '';
  }

  return input
    .replace(/[;&|`$(){}[\]<>]/g, '') // Remove shell metacharacters
    .replace(/\0/g, '')                // Remove null bytes
    .trim();
}

/**
 * Check stdin size against limit
 *
 * @param {string|Buffer} data - Data to check
 * @returns {{valid: boolean, size: number, limit: number}}
 */
function checkStdinSize(data) {
  const size = Buffer.byteLength(data);
  const limit = config.MAX_STDIN_SIZE;

  return {
    valid: size <= limit,
    size,
    limit
  };
}

module.exports = {
  isDangerousCommand,
  getDangerReason,
  isValidPackageName,
  validateFilePath,
  sanitizeInput,
  checkStdinSize
};
