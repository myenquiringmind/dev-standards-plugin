/**
 * Shared utilities for dev-standards plugin
 *
 * This module re-exports from domain-specific modules for backward compatibility.
 * New code should import from the specific modules directly.
 *
 * @module lib/utils
 * @deprecated Import from specific modules instead (lib/venv, lib/git, etc.)
 */

'use strict';

// Import domain modules
const { platform, config, exec } = require('./core');
const venv = require('./venv');
const git = require('./git');
const logging = require('./logging');
const validation = require('./validation');
const tools = require('./tools');
const version = require('./version');
const errors = require('./errors');
const orchestrator = require('./orchestrator');

// ============================================
// Re-exports for backward compatibility
// ============================================

module.exports = {
  // Constants (from config)
  PLUGIN_VERSION: config.PLUGIN_VERSION,
  PLUGIN_REPO: config.PLUGIN_REPO,
  PYTHON_DEPS: config.PYTHON_DEPS,
  VENV_NAMES: config.VENV_NAMES,
  PROTECTED_BRANCHES: config.PROTECTED_BRANCHES,
  FORMATTERS: config.FORMATTERS,
  TYPE_CHECKERS: config.TYPE_CHECKERS,
  LINTERS: config.LINTERS,
  DANGEROUS_PATTERNS: config.DANGEROUS_PATTERNS,

  // Path utilities (from logging, tools)
  getLogDir: logging.getLogDir,
  getLogFile: logging.getLogFile,
  getExt: tools.getExt,
  getPluginDir: version.getPluginDir,

  // Venv utilities
  getVenvPython: venv.getVenvPython,
  getVenvPip: venv.getVenvPip,
  findVenv: venv.findVenv,
  commandExists: exec.commandExists,
  createVenv: venv.createVenv,
  installPackage: venv.installPackage,
  ensureVenvWithTool: venv.ensureVenvWithTool,

  // Logging
  ensureLogDir: logging.ensureLogDir,
  log: logging.log,

  // Git
  getCurrentBranch: git.getCurrentBranch,
  isProtectedBranch: git.isProtectedBranch,
  getGitStatus: git.getGitStatus,
  getUncommittedFiles: git.getUncommittedFiles,
  validateCommitMessage: git.validateCommitMessage,
  stageFiles: git.stageFiles,
  createCommit: git.createCommit,

  // Validation
  isDangerousCommand: validation.isDangerousCommand,

  // Tool execution
  runPythonTool: tools.runPythonTool,
  formatFile: tools.formatFile,
  typeCheckFile: tools.typeCheckFile,
  lintFile: tools.lintFile,

  // Version checking
  getPluginVersion: version.getPluginVersion,
  checkForUpdates: version.checkForUpdates,
  compareVersions: version.compareVersions,

  // New exports (for enhanced functionality)
  platform,
  config,
  exec,
  venv,
  git,
  logging,
  validation,
  tools,
  version,
  errors,

  // Error types (direct export for convenience)
  DevStandardsError: errors.DevStandardsError,
  ValidationError: errors.ValidationError,
  VenvError: errors.VenvError,
  ExecutionError: errors.ExecutionError,
  SecurityError: errors.SecurityError,
  ConfigError: errors.ConfigError,
  GitError: errors.GitError,

  // Orchestrator
  orchestrator,
  initializeOrchestrator: orchestrator.initialize,
  advancePhase: orchestrator.advancePhase,
  processCheckpoint: orchestrator.processCheckpoint,
  getOrchestratorState: orchestrator.getState,
  resetOrchestrator: orchestrator.reset
};
