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

/**
 * Get list of uncommitted files with status
 *
 * @returns {{modified: string[], untracked: string[], deleted: string[], staged: string[]}}
 *
 * @example
 * const files = getUncommittedFiles();
 * console.log(`${files.untracked.length} untracked files`);
 */
function getUncommittedFiles() {
  const result = exec.exec('git status --porcelain', {
    timeout: config.TIMEOUTS.QUICK
  });

  const files = { modified: [], untracked: [], deleted: [], staged: [] };

  if (!result.success || !result.output) {
    return files;
  }

  result.output.split('\n').filter(l => l).forEach(line => {
    const indexStatus = line.charAt(0);
    const workTreeStatus = line.charAt(1);
    const file = line.substring(3);

    if (indexStatus === '?' && workTreeStatus === '?') {
      files.untracked.push(file);
    } else if (indexStatus === 'D' || workTreeStatus === 'D') {
      files.deleted.push(file);
    } else if (indexStatus !== ' ' && indexStatus !== '?') {
      files.staged.push(file);
    } else if (workTreeStatus !== ' ') {
      files.modified.push(file);
    }
  });

  return files;
}

/**
 * Validate commit message against conventional commit format
 *
 * @param {string} message - Commit message to validate
 * @returns {{valid: boolean, reason?: string}}
 *
 * @example
 * const result = validateCommitMessage('feat(core): add new feature');
 * if (!result.valid) {
 *   console.error(result.reason);
 * }
 */
function validateCommitMessage(message) {
  if (!message || typeof message !== 'string') {
    return { valid: false, reason: 'Commit message is required' };
  }

  const header = message.split('\n')[0];

  // Check header length
  if (header.length > 72) {
    return { valid: false, reason: 'Header must be <= 72 characters, current length is ' + header.length };
  }

  // Check conventional commit format
  const conventionalPattern = /^(feat|fix|docs|style|refactor|test|chore|perf|ci|build)(\(.+\))?: .{1,}/;
  if (!conventionalPattern.test(header)) {
    return {
      valid: false,
      reason: 'Must follow conventional commit format: type(scope): description. Valid types: feat, fix, docs, style, refactor, test, chore, perf, ci, build'
    };
  }

  // Check for AI co-authoring (blocked per project requirement)
  if (/co-authored-by:.*\b(claude|anthropic|ai|gpt|openai|copilot)\b/i.test(message)) {
    return { valid: false, reason: 'AI co-authoring references not allowed in commit messages' };
  }

  return { valid: true };
}

/**
 * Stage files for commit
 *
 * @param {string[]} files - Files to stage (or ['.'] for all)
 * @returns {{success: boolean, error?: string}}
 *
 * @example
 * const result = stageFiles(['src/index.js', 'README.md']);
 * if (!result.success) {
 *   console.error(result.error);
 * }
 */
function stageFiles(files) {
  if (!Array.isArray(files) || files.length === 0) {
    return { success: false, error: 'Files array is required' };
  }

  // Escape file paths for shell
  const escapedFiles = files.map(f => exec.escapeShellArg(f)).join(' ');
  const result = exec.exec(`git add ${escapedFiles}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  return { success: result.success, error: result.error };
}

/**
 * Create a commit with the given message
 *
 * @param {string} message - Commit message
 * @returns {{success: boolean, hash?: string, error?: string}}
 *
 * @example
 * const result = createCommit('feat(api): add user endpoint');
 * if (result.success) {
 *   console.log(`Created commit ${result.hash}`);
 * }
 */
function createCommit(message) {
  const validation = validateCommitMessage(message);
  if (!validation.valid) {
    return { success: false, error: validation.reason };
  }

  // Escape message for shell
  const escaped = exec.escapeShellArg(message);
  const result = exec.exec(`git commit -m ${escaped}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  if (result.success) {
    const hashResult = exec.exec('git rev-parse --short HEAD', {
      timeout: config.TIMEOUTS.QUICK
    });
    return { success: true, hash: hashResult.output };
  }

  return { success: false, error: result.error || 'Commit failed' };
}

module.exports = {
  // Existing
  getCurrentBranch,
  isProtectedBranch,
  getGitStatus,
  isGitRepo,
  getRepoRoot,
  getRecentCommits,
  hasUncommittedChanges,
  getCurrentCommit,

  // New
  getUncommittedFiles,
  validateCommitMessage,
  stageFiles,
  createCommit
};
