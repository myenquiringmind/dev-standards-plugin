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

// ============================================
// Branch Management Functions (Orchestrator)
// ============================================

/**
 * Generate a branch name for orchestrator workflow
 *
 * @param {string} domain - Domain being worked on
 * @returns {string} Branch name like 'feat/orchestrator-git-1738600000'
 */
function generateOrchestratorBranchName(domain) {
  const timestamp = Math.floor(Date.now() / 1000);
  return `feat/orchestrator-${domain}-${timestamp}`;
}

/**
 * Create and checkout a new branch
 *
 * @param {string} branchName - Name for the new branch
 * @returns {{success: boolean, branch?: string, error?: string}}
 */
function createBranch(branchName) {
  if (!branchName || typeof branchName !== 'string') {
    return { success: false, error: 'Branch name is required' };
  }

  // Validate branch name (basic check)
  if (!/^[\w\-\/]+$/.test(branchName)) {
    return { success: false, error: 'Invalid branch name format' };
  }

  const result = exec.exec(`git checkout -b ${exec.escapeShellArg(branchName)}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  if (result.success) {
    return { success: true, branch: branchName };
  }

  return { success: false, error: result.error || 'Failed to create branch' };
}

/**
 * Switch to an existing branch
 *
 * @param {string} branchName - Branch to switch to
 * @returns {{success: boolean, error?: string}}
 */
function checkoutBranch(branchName) {
  if (!branchName) {
    return { success: false, error: 'Branch name is required' };
  }

  const result = exec.exec(`git checkout ${exec.escapeShellArg(branchName)}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  return { success: result.success, error: result.error };
}

/**
 * Check if a branch exists locally
 *
 * @param {string} branchName - Branch to check
 * @returns {boolean}
 */
function branchExists(branchName) {
  const result = exec.exec(`git show-ref --verify --quiet refs/heads/${exec.escapeShellArg(branchName)}`, {
    timeout: config.TIMEOUTS.QUICK
  });
  return result.success;
}

/**
 * Get the default branch name (main or master)
 *
 * @returns {string} 'main' or 'master' or 'develop'
 */
function getDefaultBranch() {
  // Check for main first (modern default)
  if (branchExists('main')) return 'main';
  if (branchExists('master')) return 'master';
  if (branchExists('develop')) return 'develop';

  // Try to get from remote
  const result = exec.exec('git symbolic-ref refs/remotes/origin/HEAD', {
    timeout: config.TIMEOUTS.QUICK
  });
  if (result.success) {
    const match = result.output.match(/refs\/remotes\/origin\/(.+)/);
    if (match) return match[1];
  }

  return 'main'; // Default fallback
}

// ============================================
// Remote and PR Detection Functions
// ============================================

/**
 * Get remote repository information
 *
 * @param {string} [remoteName='origin'] - Remote name to check
 * @returns {{exists: boolean, url?: string}}
 */
function getRemoteInfo(remoteName = 'origin') {
  const result = exec.exec(`git remote get-url ${exec.escapeShellArg(remoteName)}`, {
    timeout: config.TIMEOUTS.QUICK
  });

  if (result.success && result.output) {
    return { exists: true, url: result.output };
  }

  return { exists: false };
}

/**
 * Detect if repository has PR requirements based on remote platform
 *
 * @returns {{hasPRRequirements: boolean, platform?: string, prRequired?: boolean}}
 */
function detectPRRequirements() {
  const remote = getRemoteInfo();
  if (!remote.exists || !remote.url) {
    return { hasPRRequirements: false, platform: null, prRequired: false };
  }

  const url = remote.url.toLowerCase();
  let platform = null;
  let prRequired = false;

  if (url.includes('github.com')) {
    platform = 'github';
    // Assume PR required for GitHub repos (can't check branch protection without API)
    prRequired = true;
  } else if (url.includes('gitlab')) {
    platform = 'gitlab';
    prRequired = true;
  } else if (url.includes('bitbucket')) {
    platform = 'bitbucket';
    prRequired = true;
  } else if (url.includes('azure')) {
    platform = 'azure';
    prRequired = true;
  }

  return {
    hasPRRequirements: prRequired,
    platform,
    prRequired
  };
}

/**
 * Push a branch to remote
 *
 * @param {string} branchName - Branch to push
 * @param {boolean} [setUpstream=true] - Set upstream tracking
 * @returns {{success: boolean, error?: string}}
 */
function pushBranch(branchName, setUpstream = true) {
  const remote = getRemoteInfo();
  if (!remote.exists) {
    return { success: false, error: 'No remote configured' };
  }

  const upstreamFlag = setUpstream ? '-u ' : '';
  const result = exec.exec(`git push ${upstreamFlag}origin ${exec.escapeShellArg(branchName)}`, {
    timeout: config.TIMEOUTS.LONG || 60000
  });

  return { success: result.success, error: result.error };
}

/**
 * Check if GitHub CLI (gh) is available
 *
 * @returns {boolean}
 */
function hasGitHubCLI() {
  return exec.commandExists('gh');
}

// ============================================
// Phase Commit Functions
// ============================================

/**
 * Create a commit for a completed orchestrator phase
 *
 * @param {string} domain - Domain name (e.g., 'git', 'test')
 * @param {string} phase - Phase name (e.g., 'design', 'build')
 * @param {string[]} [files=['.'] ] - Files to stage
 * @returns {{success: boolean, hash?: string, error?: string, noChanges?: boolean}}
 */
function createPhaseCommit(domain, phase, files = ['.']) {
  // Check for uncommitted changes first
  if (!hasUncommittedChanges()) {
    return {
      success: true,
      hash: getCurrentCommit(),
      noChanges: true
    };
  }

  // Stage files
  const stageResult = stageFiles(files);
  if (!stageResult.success) {
    return { success: false, error: `Failed to stage files: ${stageResult.error}` };
  }

  // Generate commit message
  const message = `feat(${domain}): complete ${phase} phase`;

  // Use raw commit to bypass conventional commit validation for phase commits
  const escaped = exec.escapeShellArg(message);
  const result = exec.exec(`git commit -m ${escaped}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  if (result.success) {
    const hash = getCurrentCommit();
    return { success: true, hash };
  }

  return { success: false, error: result.error || 'Commit failed' };
}

/**
 * Get the HEAD commit hash (full)
 *
 * @returns {string|null}
 */
function getHeadCommit() {
  const result = exec.exec('git rev-parse HEAD', {
    timeout: config.TIMEOUTS.QUICK
  });
  return result.success ? result.output : null;
}

/**
 * Get commits since a specific hash
 *
 * @param {string} sinceHash - Starting commit hash
 * @returns {Array<{hash: string, message: string}>}
 */
function getCommitsSince(sinceHash) {
  const result = exec.exec(`git log ${exec.escapeShellArg(sinceHash)}..HEAD --oneline`, {
    timeout: config.TIMEOUTS.QUICK
  });

  if (!result.success || !result.output) {
    return [];
  }

  return result.output.split('\n').filter(l => l).map(line => {
    const [hash, ...messageParts] = line.split(' ');
    return { hash, message: messageParts.join(' ') };
  });
}

// ============================================
// Rollback Functions
// ============================================

/**
 * Rollback to a specific commit
 *
 * @param {string} commitHash - Commit to rollback to
 * @param {string} [mode='soft'] - Reset mode: 'soft', 'mixed', or 'hard'
 * @returns {{success: boolean, error?: string}}
 */
function rollbackToCommit(commitHash, mode = 'soft') {
  if (!commitHash) {
    return { success: false, error: 'Commit hash is required' };
  }

  const validModes = ['soft', 'mixed', 'hard'];
  if (!validModes.includes(mode)) {
    return { success: false, error: `Invalid mode. Must be one of: ${validModes.join(', ')}` };
  }

  const result = exec.exec(`git reset --${mode} ${exec.escapeShellArg(commitHash)}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  return { success: result.success, error: result.error };
}

/**
 * Stash uncommitted changes
 *
 * @param {string} [message] - Stash message
 * @returns {{success: boolean, error?: string}}
 */
function stashChanges(message) {
  if (!hasUncommittedChanges()) {
    return { success: true }; // Nothing to stash
  }

  const msgPart = message ? ` -m ${exec.escapeShellArg(message)}` : '';
  const result = exec.exec(`git stash push${msgPart}`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  return { success: result.success, error: result.error };
}

/**
 * Pop the most recent stash
 *
 * @returns {{success: boolean, error?: string}}
 */
function popStash() {
  const result = exec.exec('git stash pop', {
    timeout: config.TIMEOUTS.STANDARD
  });

  return { success: result.success, error: result.error };
}

/**
 * List stashes
 *
 * @returns {Array<{index: number, message: string}>}
 */
function listStashes() {
  const result = exec.exec('git stash list', {
    timeout: config.TIMEOUTS.QUICK
  });

  if (!result.success || !result.output) {
    return [];
  }

  return result.output.split('\n').filter(l => l).map((line, index) => {
    const match = line.match(/stash@\{(\d+)\}: (.+)/);
    return {
      index: match ? parseInt(match[1], 10) : index,
      message: match ? match[2] : line
    };
  });
}

// ============================================
// Finalization Functions
// ============================================

/**
 * Create a pull request using GitHub CLI
 *
 * @param {Object} options - PR options
 * @param {string} options.title - PR title
 * @param {string} options.body - PR body
 * @param {string} [options.base] - Base branch (default: main/master)
 * @returns {{success: boolean, prUrl?: string, error?: string}}
 */
function createPullRequest(options) {
  if (!hasGitHubCLI()) {
    return { success: false, error: 'GitHub CLI (gh) not available' };
  }

  const { title, body, base } = options;
  if (!title) {
    return { success: false, error: 'PR title is required' };
  }

  const baseBranch = base || getDefaultBranch();
  const bodyEscaped = body ? ` --body ${exec.escapeShellArg(body)}` : '';

  const result = exec.exec(
    `gh pr create --title ${exec.escapeShellArg(title)}${bodyEscaped} --base ${exec.escapeShellArg(baseBranch)}`,
    { timeout: config.TIMEOUTS.LONG || 60000 }
  );

  if (result.success) {
    // Extract PR URL from output
    const urlMatch = result.output.match(/https:\/\/github\.com\/[^\s]+/);
    return {
      success: true,
      prUrl: urlMatch ? urlMatch[0] : result.output
    };
  }

  return { success: false, error: result.error || 'Failed to create PR' };
}

/**
 * Merge a branch into another (local only)
 *
 * @param {string} sourceBranch - Branch to merge
 * @param {string} targetBranch - Branch to merge into
 * @returns {{success: boolean, error?: string}}
 */
function mergeBranch(sourceBranch, targetBranch) {
  // First checkout target
  const checkoutResult = checkoutBranch(targetBranch);
  if (!checkoutResult.success) {
    return { success: false, error: `Failed to checkout ${targetBranch}: ${checkoutResult.error}` };
  }

  // Then merge source
  const result = exec.exec(`git merge ${exec.escapeShellArg(sourceBranch)} --no-ff`, {
    timeout: config.TIMEOUTS.STANDARD
  });

  return { success: result.success, error: result.error };
}

/**
 * Delete a branch (local and optionally remote)
 *
 * @param {string} branchName - Branch to delete
 * @param {boolean} [deleteRemote=false] - Also delete from remote
 * @returns {{success: boolean, error?: string}}
 */
function deleteBranch(branchName, deleteRemote = false) {
  // Don't delete protected branches
  if (isProtectedBranch(branchName)) {
    return { success: false, error: 'Cannot delete protected branch' };
  }

  // Delete local
  const localResult = exec.exec(`git branch -d ${exec.escapeShellArg(branchName)}`, {
    timeout: config.TIMEOUTS.QUICK
  });

  if (!localResult.success) {
    return { success: false, error: localResult.error };
  }

  // Optionally delete remote
  if (deleteRemote) {
    const remoteResult = exec.exec(`git push origin --delete ${exec.escapeShellArg(branchName)}`, {
      timeout: config.TIMEOUTS.STANDARD
    });
    if (!remoteResult.success) {
      return { success: false, error: `Local deleted but remote failed: ${remoteResult.error}` };
    }
  }

  return { success: true };
}

module.exports = {
  // Basic git info
  getCurrentBranch,
  isProtectedBranch,
  getGitStatus,
  isGitRepo,
  getRepoRoot,
  getRecentCommits,
  hasUncommittedChanges,
  getCurrentCommit,
  getUncommittedFiles,

  // Commit operations
  validateCommitMessage,
  stageFiles,
  createCommit,

  // Branch management (orchestrator)
  generateOrchestratorBranchName,
  createBranch,
  checkoutBranch,
  branchExists,
  getDefaultBranch,

  // Remote and PR detection
  getRemoteInfo,
  detectPRRequirements,
  pushBranch,
  hasGitHubCLI,

  // Phase commits
  createPhaseCommit,
  getHeadCommit,
  getCommitsSince,

  // Rollback
  rollbackToCommit,
  stashChanges,
  popStash,
  listStashes,

  // Finalization
  createPullRequest,
  mergeBranch,
  deleteBranch
};
