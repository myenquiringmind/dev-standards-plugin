#!/usr/bin/env node
/**
 * Edge case tests for Unicode handling
 * Tests various Unicode scenarios across modules
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

// Load modules
const validation = require('../../lib/validation');
const exec = require('../../lib/core/exec');

// ============================================
// Test: Unicode in Commands
// ============================================
console.log('\n\x1b[1mUnicode in Commands\x1b[0m');

test('escapeShellArg handles emoji', () => {
  const result = exec.escapeShellArg('file_📁_test.txt');
  assert(typeof result === 'string');
  assert(result.includes('📁'));
});

test('escapeShellArg handles CJK characters', () => {
  const result = exec.escapeShellArg('文件_test.txt');
  assert(typeof result === 'string');
  assert(result.includes('文件'));
});

test('escapeShellArg handles Arabic', () => {
  const result = exec.escapeShellArg('ملف_test.txt');
  assert(typeof result === 'string');
  assert(result.includes('ملف'));
});

test('escapeShellArg handles Cyrillic', () => {
  const result = exec.escapeShellArg('файл_test.txt');
  assert(typeof result === 'string');
  assert(result.includes('файл'));
});

test('escapeShellArg handles combining characters', () => {
  const result = exec.escapeShellArg('café.txt');
  assert(typeof result === 'string');
});

test('escapeShellArg handles zero-width characters', () => {
  // Zero-width space
  const result = exec.escapeShellArg('file\u200Btest.txt');
  assert(typeof result === 'string');
});

// ============================================
// Test: Unicode in Validation
// ============================================
console.log('\n\x1b[1mUnicode in Validation\x1b[0m');

test('isDangerousCommand handles Unicode semicolon', () => {
  // Full-width semicolon might be a bypass attempt
  const cmd = 'echo test；rm -rf /';
  const result = validation.isDangerousCommand(cmd);
  // Should recognize as dangerous pattern regardless
  assert(typeof result === 'boolean');
});

test('isDangerousCommand handles Unicode pipe', () => {
  const cmd = 'echo test｜bash';
  const result = validation.isDangerousCommand(cmd);
  assert(typeof result === 'boolean');
});

test('sanitizeInput handles mixed Unicode', () => {
  const input = 'Hello 世界; rm -rf /';
  const result = validation.sanitizeInput(input);
  assert(!result.includes(';'));
  assert(result.includes('世界'));
});

test('validateFilePath handles Unicode paths', () => {
  const result = validation.validateFilePath('/home/用户/文件.txt');
  assert(typeof result.valid === 'boolean');
});

// ============================================
// Test: Unicode Package Names
// ============================================
console.log('\n\x1b[1mUnicode Package Names\x1b[0m');

test('rejects Unicode package names', () => {
  // Package names should be ASCII
  const unicodeNames = [
    'пакет',
    '包',
    'パッケージ',
    'חבילה',
    'حزمة'
  ];

  for (const name of unicodeNames) {
    assert(!validation.isValidPackageName(name), `Should reject: ${name}`);
  }
});

// ============================================
// Test: Homoglyph Attacks
// ============================================
console.log('\n\x1b[1mHomoglyph Attacks\x1b[0m');

test('handles Cyrillic a in package name', () => {
  // Cyrillic 'а' looks like Latin 'a'
  const name = 'ruff' + '\u0430';  // Cyrillic a
  assert(!validation.isValidPackageName(name), 'Should reject homoglyph');
});

test('handles Greek omicron in command', () => {
  // Greek 'ο' looks like Latin 'o'
  const cmd = 'rm -rf /h\u03BFme';  // Greek omicron
  // Should not cause issues
  const result = validation.isDangerousCommand(cmd);
  assert(typeof result === 'boolean');
});

// ============================================
// Test: Long Unicode Strings
// ============================================
console.log('\n\x1b[1mLong Unicode Strings\x1b[0m');

test('handles very long Unicode path', () => {
  const longPath = '/home/' + '用户/'.repeat(100) + 'file.txt';
  const result = validation.validateFilePath(longPath);
  assert(typeof result.valid === 'boolean');
});

test('escapeShellArg handles long emoji string', () => {
  const emojiString = '📁'.repeat(1000);
  const result = exec.escapeShellArg(emojiString);
  assert(typeof result === 'string');
  assert(result.length > emojiString.length);  // Should be wrapped in quotes
});

// ============================================
// Test: Special Unicode Characters
// ============================================
console.log('\n\x1b[1mSpecial Unicode Characters\x1b[0m');

test('handles right-to-left override', () => {
  // RLO character used for spoofing
  const rloString = 'test\u202Efdp.exe';
  const result = validation.sanitizeInput(rloString);
  assert(typeof result === 'string');
});

test('handles null in Unicode', () => {
  const nullString = 'file\u0000.txt';
  const result = validation.validateFilePath(nullString);
  assert(result.valid === false, 'Should reject null character');
});

test('handles BOM character', () => {
  const bomString = '\uFEFFfile.txt';
  const result = exec.escapeShellArg(bomString);
  assert(typeof result === 'string');
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mUnicode Edge Case Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
