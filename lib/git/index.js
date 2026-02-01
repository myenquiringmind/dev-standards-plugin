/**
 * Git utilities
 *
 * Operations for git repository management and branch protection.
 *
 * @module lib/git
 */

'use strict';

const { config, exec } = require('../core');

/**
 * Get the current git branch name
 *
 * @returns {string|null} Branch name or null if not in a git repo
 *
 * @example
 * const branch = getCurrentBranch();
 * if (branch) {
 *   console.log(`On branch: ${branch}`);
 * }
 */
function getCurrentBranch() {
  const result = exec.exec('git branch --show-current', {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success ? result.output : null;
}

/**
 * Check if a branch is protected
 *
 * @param {string} [branch] - Branch name to check (defaults to current branch)
 * @returns {boolean} True if the branch is protected
 *
 * @example
 * if (isProtectedBranch('main')) {
 *   console.log('Cannot edit directly on main');
 * }
 */
function isProtectedBranch(branch) {
  const branchToCheck = branch || getCurrentBranch();
  return branchToCheck && config.PROTECTED_BRANCHES.includes(branchToCheck);
}

/**
 * Get git status in short format
 *
 * @returns {string} Status output or message if not a git repo
 *
 * @example
 * const status = getGitStatus();
 * console.log(status); // 'M file.js' or 'Working tree clean'
 */
function getGitStatus() {
  const result = exec.exec('git status --short', {
    timeout: config.TIMEOUTS.QUICK
  });

  if (!result.success) {
    return 'Not a git repo';
  }

  return result.output || 'Working tree clean';
}

/**
 * Check if the current directory is a git repository
 *
 * @returns {boolean} True if in a git repo
 */
function isGitRepo() {
  const result = exec.exec('git rev-parse --git-dir', {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success;
}

/**
 * Get the repository root directory
 *
 * @returns {string|null} Repository root path or null if not in a repo
 */
function getRepoRoot() {
  const result = exec.exec('git rev-parse --show-toplevel', {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success ? result.output : null;
}

/**
 * Get recent commit log
 *
 * @param {number} [count=10] - Number of commits to show
 * @returns {string|null} Commit log or null if not in a repo
 */
function getRecentCommits(count = 10) {
  const result = exec.exec(`git log -${count} --oneline`, {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success ? result.output : null;
}

/**
 * Check if there are uncommitted changes
 *
 * @returns {boolean} True if there are uncommitted changes
 */
function hasUncommittedChanges() {
  const result = exec.exec('git status --porcelain', {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success && result.output.length > 0;
}

/**
 * Get the current commit hash (short)
 *
 * @returns {string|null} Short commit hash or null if not in a repo
 */
function getCurrentCommit() {
  const result = exec.exec('git rev-parse --short HEAD', {
    timeout: config.TIMEOUTS.QUICK
  });

  return result.success ? result.output : null;
}

module.exports = {
  getCurrentBranch,
  isProtectedBranch,
  getGitStatus,
  isGitRepo,
  getRepoRoot,
  getRecentCommits,
  hasUncommittedChanges,
  getCurrentCommit
};
