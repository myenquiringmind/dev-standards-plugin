#!/usr/bin/env node
/**
 * Unit tests for lib/logging module
 * Tests session logging and debug output
 */

const os = require('os');

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
const logging = require('../../lib/logging');

// ============================================
// Test: Path Functions
// ============================================
console.log('\n\x1b[1mPath Functions\x1b[0m');

test('getLogDir returns path in home directory', () => {
  const logDir = logging.getLogDir();
  assert(logDir.includes(os.homedir()), 'Should be in home dir');
  assert(logDir.includes('.claude'), 'Should be in .claude dir');
});

test('getLogFile returns session.log path', () => {
  const logFile = logging.getLogFile();
  assert(logFile.includes('session.log'), 'Should be session.log');
});

test('ensureLogDir returns path', () => {
  const logDir = logging.ensureLogDir();
  assert(typeof logDir === 'string');
});

// ============================================
// Test: Logging Functions
// ============================================
console.log('\n\x1b[1mLogging Functions\x1b[0m');

test('log function exists', () => {
  assert(typeof logging.log === 'function');
});

test('debug function exists', () => {
  assert(typeof logging.debug === 'function');
});

test('info function exists', () => {
  assert(typeof logging.info === 'function');
});

test('warn function exists', () => {
  assert(typeof logging.warn === 'function');
});

test('error function exists', () => {
  assert(typeof logging.error === 'function');
});

test('log writes to file', () => {
  // Write a unique test entry
  const testId = `TEST_${Date.now()}`;
  logging.log('TEST_EVENT', testId);

  // Read back and verify
  const logs = logging.readRecentLogs(10);
  const found = logs.some(line => line.includes(testId));
  assert(found, 'Log entry should be written');
});

// ============================================
// Test: Log Reading
// ============================================
console.log('\n\x1b[1mLog Reading\x1b[0m');

test('readRecentLogs returns array', () => {
  const logs = logging.readRecentLogs();
  assert(Array.isArray(logs));
});

test('readRecentLogs respects limit', () => {
  // Write some entries first
  for (let i = 0; i < 5; i++) {
    logging.log('LIMIT_TEST', `entry_${i}`);
  }

  const logs = logging.readRecentLogs(3);
  assert(logs.length <= 3, 'Should respect limit');
});

test('clearLog returns boolean', () => {
  const result = logging.clearLog();
  assert(typeof result === 'boolean');
});

// ============================================
// Test: Function Exports
// ============================================
console.log('\n\x1b[1mFunction Exports\x1b[0m');

const expectedExports = [
  'getLogDir',
  'getLogFile',
  'ensureLogDir',
  'log',
  'debug',
  'info',
  'warn',
  'error',
  'readRecentLogs',
  'clearLog'
];

for (const name of expectedExports) {
  test(`exports ${name}`, () => {
    assert(typeof logging[name] === 'function', `${name} should be a function`);
  });
}

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mLogging Unit Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
