/**
 * Custom error types for dev-standards-plugin
 *
 * Provides a hierarchy of typed errors for better error handling,
 * debugging, and programmatic error identification.
 *
 * @module lib/errors
 */

'use strict';

/**
 * Base error class for all dev-standards errors
 *
 * @extends Error
 *
 * @example
 * throw new DevStandardsError('Something went wrong', { code: 'E_GENERIC' });
 */
class DevStandardsError extends Error {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   * @param {string} [options.code] - Error code for programmatic handling
   * @param {Error} [options.cause] - Original error that caused this error
   */
  constructor(message, options = {}) {
    super(message);
    this.name = this.constructor.name;
    this.code = options.code || 'E_DEV_STANDARDS';
    if (options.cause) {
      this.cause = options.cause;
    }
    Error.captureStackTrace?.(this, this.constructor);
  }
}

/**
 * Error thrown when input validation fails
 *
 * @extends DevStandardsError
 *
 * @example
 * throw new ValidationError('Invalid package name: evil;rm -rf /');
 */
class ValidationError extends DevStandardsError {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   */
  constructor(message, options = {}) {
    super(message, { code: 'E_VALIDATION', ...options });
  }
}

/**
 * Error thrown when virtual environment operations fail
 *
 * @extends DevStandardsError
 *
 * @example
 * throw new VenvError('Failed to create virtual environment');
 */
class VenvError extends DevStandardsError {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   */
  constructor(message, options = {}) {
    super(message, { code: 'E_VENV', ...options });
  }
}

/**
 * Error thrown when command or tool execution fails
 *
 * @extends DevStandardsError
 *
 * @example
 * throw new ExecutionError('ruff format failed', { cause: originalError });
 */
class ExecutionError extends DevStandardsError {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   */
  constructor(message, options = {}) {
    super(message, { code: 'E_EXECUTION', ...options });
  }
}

/**
 * Error thrown when a security violation is detected
 *
 * @extends DevStandardsError
 *
 * @example
 * throw new SecurityError('Dangerous command detected: rm -rf /');
 */
class SecurityError extends DevStandardsError {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   */
  constructor(message, options = {}) {
    super(message, { code: 'E_SECURITY', ...options });
  }
}

/**
 * Error thrown when configuration is invalid or missing
 *
 * @extends DevStandardsError
 *
 * @example
 * throw new ConfigError('Missing required configuration: formatters');
 */
class ConfigError extends DevStandardsError {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   */
  constructor(message, options = {}) {
    super(message, { code: 'E_CONFIG', ...options });
  }
}

/**
 * Error thrown when a git operation fails
 *
 * @extends DevStandardsError
 *
 * @example
 * throw new GitError('Cannot edit on protected branch: main');
 */
class GitError extends DevStandardsError {
  /**
   * @param {string} message - Error message
   * @param {Object} [options={}] - Error options
   */
  constructor(message, options = {}) {
    super(message, { code: 'E_GIT', ...options });
  }
}

module.exports = {
  DevStandardsError,
  ValidationError,
  VenvError,
  ExecutionError,
  SecurityError,
  ConfigError,
  GitError
};
