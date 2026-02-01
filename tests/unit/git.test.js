#!/usr/bin/env node
/**
 * Unit tests for lib/git module
 * Tests git operations and branch protection
 */

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
    passed++;
  } catch (e) {
    console.log(`  \x1b[31m✗\x1b[0m ${name}: ${e.message}`);
    failed++;
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

// Load module
const git = require('../../lib/git');

// ============================================
// Test: Protected Branch Detection
// ============================================
console.log('\n\x1b[1mProtected Branch Detection\x1b[0m');

// Only test branches that are actually in config (Phase 11 added develop, staging, release)
const protectedBranches = ['main', 'master', 'production', 'develop', 'staging', 'release'];
const safeBranches = ['feature/test', 'fix/bug', 'dev', 'prod', 'hotfix/urgent', 'chore/cleanup'];

for (const branch of protectedBranches) {
  test(`${branch} is protected`, () => {
    assert(git.isProtectedBranch(branch), `${branch} should be protected`);
  });
}

for (const branch of safeBranches) {
  test(`${branch} is not protected`, () => {
    assert(!git.isProtectedBranch(branch), `${branch} should not be protected`);
  });
}

// ============================================
// Test: Git Status Functions
// ============================================
console.log('\n\x1b[1mGit Status Functions\x1b[0m');

test('getCurrentBranch returns string or null', () => {
  const branch = git.getCurrentBranch();
  assert(branch === null || typeof branch === 'string');
});

test('getGitStatus returns string', () => {
  const status = git.getGitStatus();
  assert(typeof status === 'string');
});

test('isGitRepo returns boolean', () => {
  const result = git.isGitRepo();
  assert(typeof result === 'boolean');
});

test('getRepoRoot returns string or null', () => {
  const root = git.getRepoRoot();
  assert(root === null || typeof root === 'string');
});

test('getRecentCommits returns string or null', () => {
  const commits = git.getRecentCommits(5);
  assert(commits === null || typeof commits === 'string');
});

test('hasUncommittedChanges returns boolean', () => {
  const result = git.hasUncommittedChanges();
  assert(typeof result === 'boolean');
});

test('getCurrentCommit returns string or null', () => {
  const commit = git.getCurrentCommit();
  assert(commit === null || typeof commit === 'string');
});

// ============================================
// Test: getUncommittedFiles
// ============================================
console.log('\n\x1b[1mgetUncommittedFiles\x1b[0m');

test('getUncommittedFiles returns categorized object', () => {
  const files = git.getUncommittedFiles();
  assert(typeof files === 'object', 'should return object');
  assert(Array.isArray(files.modified), 'should have modified array');
  assert(Array.isArray(files.untracked), 'should have untracked array');
  assert(Array.isArray(files.deleted), 'should have deleted array');
  assert(Array.isArray(files.staged), 'should have staged array');
});

// ============================================
// Test: validateCommitMessage
// ============================================
console.log('\n\x1b[1mvalidateCommitMessage\x1b[0m');

test('validateCommitMessage accepts valid conventional format', () => {
  const result = git.validateCommitMessage('feat(core): add new feature');
  assert(result.valid === true, 'should accept valid message');
});

test('validateCommitMessage accepts feat without scope', () => {
  const result = git.validateCommitMessage('feat: add feature');
  assert(result.valid === true, 'should accept feat without scope');
});

test('validateCommitMessage accepts fix type', () => {
  const result = git.validateCommitMessage('fix(api): resolve null pointer');
  assert(result.valid === true, 'should accept fix type');
});

test('validateCommitMessage accepts all valid types', () => {
  const types = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore', 'perf', 'ci', 'build'];
  for (const type of types) {
    const result = git.validateCommitMessage(`${type}: description`);
    assert(result.valid === true, `should accept ${type} type`);
  }
});

test('validateCommitMessage rejects non-conventional format', () => {
  const result = git.validateCommitMessage('added new feature');
  assert(result.valid === false, 'should reject invalid message');
  assert(result.reason.includes('conventional commit'), 'should mention conventional format');
});

test('validateCommitMessage rejects invalid type', () => {
  const result = git.validateCommitMessage('feature: add something');
  assert(result.valid === false, 'should reject invalid type');
});

test('validateCommitMessage rejects long header', () => {
  const longMsg = 'feat: ' + 'x'.repeat(70);
  const result = git.validateCommitMessage(longMsg);
  assert(result.valid === false, 'should reject long header');
  assert(result.reason.includes('72'), 'should mention 72 character limit');
});

test('validateCommitMessage rejects AI co-authoring (Claude)', () => {
  const result = git.validateCommitMessage('feat: add feature\n\nCo-Authored-By: Claude <noreply@anthropic.com>');
  assert(result.valid === false, 'should reject Claude co-authoring');
  assert(result.reason.includes('AI co-authoring'), 'should mention AI co-authoring');
});

test('validateCommitMessage rejects AI co-authoring (Anthropic)', () => {
  const result = git.validateCommitMessage('feat: add feature\n\nCo-Authored-By: Anthropic AI');
  assert(result.valid === false, 'should reject Anthropic co-authoring');
});

test('validateCommitMessage rejects AI co-authoring (OpenAI)', () => {
  const result = git.validateCommitMessage('feat: add feature\n\nCo-Authored-By: OpenAI GPT-4');
  assert(result.valid === false, 'should reject OpenAI co-authoring');
});

test('validateCommitMessage rejects AI co-authoring (Copilot)', () => {
  const result = git.validateCommitMessage('feat: add feature\n\nCo-Authored-By: GitHub Copilot');
  assert(result.valid === false, 'should reject Copilot co-authoring');
});

test('validateCommitMessage allows human co-authoring', () => {
  const result = git.validateCommitMessage('feat: add feature\n\nCo-Authored-By: John Doe <john@example.com>');
  assert(result.valid === true, 'should allow human co-authoring');
});

test('validateCommitMessage rejects empty message', () => {
  const result = git.validateCommitMessage('');
  assert(result.valid === false, 'should reject empty message');
});

test('validateCommitMessage rejects null message', () => {
  const result = git.validateCommitMessage(null);
  assert(result.valid === false, 'should reject null message');
});

// ============================================
// Test: stageFiles
// ============================================
console.log('\n\x1b[1mstageFiles\x1b[0m');

test('stageFiles rejects empty array', () => {
  const result = git.stageFiles([]);
  assert(result.success === false, 'should reject empty array');
  assert(result.error.includes('required'), 'should mention files required');
});

test('stageFiles rejects non-array', () => {
  const result = git.stageFiles('file.js');
  assert(result.success === false, 'should reject non-array');
});

// ============================================
// Test: createCommit
// ============================================
console.log('\n\x1b[1mcreateCommit\x1b[0m');

test('createCommit rejects invalid message', () => {
  const result = git.createCommit('bad message');
  assert(result.success === false, 'should reject invalid message');
  assert(result.error.includes('conventional commit'), 'should mention format');
});

test('createCommit rejects AI co-authoring', () => {
  const result = git.createCommit('feat: add\n\nCo-Authored-By: Claude');
  assert(result.success === false, 'should reject AI co-authoring');
});

// ============================================
// Test: Function Exports
// ============================================
console.log('\n\x1b[1mFunction Exports\x1b[0m');

const expectedExports = [
  'getCurrentBranch',
  'isProtectedBranch',
  'getGitStatus',
  'isGitRepo',
  'getRepoRoot',
  'getRecentCommits',
  'hasUncommittedChanges',
  'getCurrentCommit',
  'getUncommittedFiles',
  'validateCommitMessage',
  'stageFiles',
  'createCommit'
];

for (const name of expectedExports) {
  test(`exports ${name}`, () => {
    assert(typeof git[name] === 'function', `${name} should be a function`);
  });
}

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mGit Unit Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
