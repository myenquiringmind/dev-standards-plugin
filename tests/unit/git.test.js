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

// Only test branches that are actually in config
const protectedBranches = ['main', 'master', 'production'];
const safeBranches = ['feature/test', 'fix/bug', 'dev', 'develop', 'staging', 'prod', 'release'];

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
  'getCurrentCommit'
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
