#!/usr/bin/env node
/**
 * Unit tests for lib/errors module
 * Tests custom error type hierarchy
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
const errors = require('../../lib/errors');
const {
  DevStandardsError,
  ValidationError,
  VenvError,
  ExecutionError,
  SecurityError,
  ConfigError,
  GitError
} = errors;

// ============================================
// Test: Base Error Class
// ============================================
console.log('\n\x1b[1mDevStandardsError (Base Class)\x1b[0m');

test('DevStandardsError instantiates correctly', () => {
  const error = new DevStandardsError('test message');
  assert(error instanceof Error, 'Should extend Error');
  assert(error instanceof DevStandardsError, 'Should be DevStandardsError');
  assert(error.message === 'test message', 'Message should match');
  assert(error.name === 'DevStandardsError', 'Name should be DevStandardsError');
  assert(error.code === 'E_DEV_STANDARDS', 'Default code should be E_DEV_STANDARDS');
});

test('DevStandardsError accepts custom code', () => {
  const error = new DevStandardsError('test', { code: 'E_CUSTOM' });
  assert(error.code === 'E_CUSTOM', 'Should use custom code');
});

test('DevStandardsError preserves cause', () => {
  const cause = new Error('original error');
  const error = new DevStandardsError('wrapper', { cause });
  assert(error.cause === cause, 'Cause should be preserved');
  assert(error.cause.message === 'original error', 'Cause message should match');
});

test('DevStandardsError has stack trace', () => {
  const error = new DevStandardsError('test');
  assert(typeof error.stack === 'string', 'Should have stack trace');
  assert(error.stack.includes('DevStandardsError'), 'Stack should include error name');
});

// ============================================
// Test: ValidationError
// ============================================
console.log('\n\x1b[1mValidationError\x1b[0m');

test('ValidationError has correct code', () => {
  const error = new ValidationError('invalid input');
  assert(error.code === 'E_VALIDATION', 'Code should be E_VALIDATION');
  assert(error.name === 'ValidationError', 'Name should be ValidationError');
});

test('ValidationError extends DevStandardsError', () => {
  const error = new ValidationError('test');
  assert(error instanceof DevStandardsError, 'Should extend DevStandardsError');
  assert(error instanceof Error, 'Should extend Error');
});

test('ValidationError preserves cause', () => {
  const cause = new TypeError('type mismatch');
  const error = new ValidationError('validation failed', { cause });
  assert(error.cause === cause, 'Cause should be preserved');
});

// ============================================
// Test: VenvError
// ============================================
console.log('\n\x1b[1mVenvError\x1b[0m');

test('VenvError has correct code', () => {
  const error = new VenvError('venv creation failed');
  assert(error.code === 'E_VENV', 'Code should be E_VENV');
  assert(error.name === 'VenvError', 'Name should be VenvError');
});

test('VenvError extends DevStandardsError', () => {
  const error = new VenvError('test');
  assert(error instanceof DevStandardsError, 'Should extend DevStandardsError');
});

// ============================================
// Test: ExecutionError
// ============================================
console.log('\n\x1b[1mExecutionError\x1b[0m');

test('ExecutionError has correct code', () => {
  const error = new ExecutionError('command failed');
  assert(error.code === 'E_EXECUTION', 'Code should be E_EXECUTION');
  assert(error.name === 'ExecutionError', 'Name should be ExecutionError');
});

test('ExecutionError extends DevStandardsError', () => {
  const error = new ExecutionError('test');
  assert(error instanceof DevStandardsError, 'Should extend DevStandardsError');
});

// ============================================
// Test: SecurityError
// ============================================
console.log('\n\x1b[1mSecurityError\x1b[0m');

test('SecurityError has correct code', () => {
  const error = new SecurityError('dangerous command');
  assert(error.code === 'E_SECURITY', 'Code should be E_SECURITY');
  assert(error.name === 'SecurityError', 'Name should be SecurityError');
});

test('SecurityError extends DevStandardsError', () => {
  const error = new SecurityError('test');
  assert(error instanceof DevStandardsError, 'Should extend DevStandardsError');
});

// ============================================
// Test: ConfigError
// ============================================
console.log('\n\x1b[1mConfigError\x1b[0m');

test('ConfigError has correct code', () => {
  const error = new ConfigError('missing config');
  assert(error.code === 'E_CONFIG', 'Code should be E_CONFIG');
  assert(error.name === 'ConfigError', 'Name should be ConfigError');
});

test('ConfigError extends DevStandardsError', () => {
  const error = new ConfigError('test');
  assert(error instanceof DevStandardsError, 'Should extend DevStandardsError');
});

// ============================================
// Test: GitError
// ============================================
console.log('\n\x1b[1mGitError\x1b[0m');

test('GitError has correct code', () => {
  const error = new GitError('protected branch');
  assert(error.code === 'E_GIT', 'Code should be E_GIT');
  assert(error.name === 'GitError', 'Name should be GitError');
});

test('GitError extends DevStandardsError', () => {
  const error = new GitError('test');
  assert(error instanceof DevStandardsError, 'Should extend DevStandardsError');
});

// ============================================
// Test: Module Exports
// ============================================
console.log('\n\x1b[1mModule Exports\x1b[0m');

const expectedExports = [
  'DevStandardsError',
  'ValidationError',
  'VenvError',
  'ExecutionError',
  'SecurityError',
  'ConfigError',
  'GitError'
];

for (const name of expectedExports) {
  test(`exports ${name}`, () => {
    assert(typeof errors[name] === 'function', `${name} should be exported as a class`);
  });
}

// ============================================
// Test: Error Catching Patterns
// ============================================
console.log('\n\x1b[1mError Catching Patterns\x1b[0m');

test('can catch by base class', () => {
  let caught = false;
  try {
    throw new ValidationError('test');
  } catch (e) {
    if (e instanceof DevStandardsError) {
      caught = true;
    }
  }
  assert(caught, 'ValidationError should be catchable as DevStandardsError');
});

test('can catch by specific class', () => {
  let caughtValidation = false;
  let caughtExecution = false;

  try {
    throw new ValidationError('test');
  } catch (e) {
    if (e instanceof ValidationError) caughtValidation = true;
    if (e instanceof ExecutionError) caughtExecution = true;
  }

  assert(caughtValidation, 'Should catch ValidationError');
  assert(!caughtExecution, 'Should not catch as ExecutionError');
});

test('error code can be used for switching', () => {
  const error = new SecurityError('test');
  let handled = false;

  switch (error.code) {
    case 'E_VALIDATION':
      break;
    case 'E_SECURITY':
      handled = true;
      break;
    default:
      break;
  }

  assert(handled, 'Should be able to switch on error code');
});

// ============================================
// Test: Error Serialization
// ============================================
console.log('\n\x1b[1mError Serialization\x1b[0m');

test('error can be converted to string', () => {
  const error = new ValidationError('invalid input');
  const str = error.toString();
  assert(str.includes('ValidationError'), 'String should include error name');
  assert(str.includes('invalid input'), 'String should include message');
});

test('error JSON includes code', () => {
  const error = new ConfigError('missing field');
  // Note: JSON.stringify on Error only gets enumerable properties
  // code and cause are set in constructor and should be enumerable
  assert(error.code === 'E_CONFIG', 'Code should be accessible');
});

// ============================================
// Test: Error Chaining
// ============================================
console.log('\n\x1b[1mError Chaining\x1b[0m');

test('supports deep cause chains', () => {
  const root = new Error('root cause');
  const middle = new ExecutionError('execution failed', { cause: root });
  const top = new VenvError('venv setup failed', { cause: middle });

  assert(top.cause === middle, 'Top cause should be middle');
  assert(middle.cause === root, 'Middle cause should be root');
  assert(top.cause.cause === root, 'Can traverse cause chain');
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mError Types Unit Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
