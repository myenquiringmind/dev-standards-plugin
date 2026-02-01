#!/usr/bin/env node
/**
 * Test runner - runs all test suites
 *
 * Usage: node tests/run-all.js
 *
 * Test categories:
 * - Unit tests: Individual module testing
 * - Integration tests: Cross-module interactions
 * - Security tests: Attack vector prevention
 * - Edge cases: Unicode, large files, etc.
 * - Content tests: Agent/command markdown validation
 * - Hook tests: JSON structure validation
 */

const { execSync } = require('child_process');
const path = require('path');

const ROOT = path.join(__dirname, '..');

console.log('\x1b[1m' + '='.repeat(60) + '\x1b[0m');
console.log('\x1b[1m         DEV-STANDARDS PLUGIN TEST SUITE\x1b[0m');
console.log('\x1b[1m' + '='.repeat(60) + '\x1b[0m');

const testSuites = [
  // Existing tests (renamed to follow *.test.js convention)
  { name: 'Hooks Configuration', file: 'hooks.test.js' },
  { name: 'Venv Utilities', file: 'venv.test.js' },
  { name: 'Content Validation', file: 'content.test.js' },

  // New unit tests
  { name: 'Core Modules (Unit)', file: 'unit/core.test.js' },
  { name: 'Validation Module (Unit)', file: 'unit/validation.test.js' },
  { name: 'Git Module (Unit)', file: 'unit/git.test.js' },
  { name: 'Logging Module (Unit)', file: 'unit/logging.test.js' },
  { name: 'Error Types (Unit)', file: 'unit/errors.test.js' },

  // Integration tests
  { name: 'Module Integration', file: 'integration/modules.test.js' },

  // Security tests
  { name: 'Command Injection Security', file: 'security/injection.test.js' },

  // Edge case tests
  { name: 'Unicode Edge Cases', file: 'edge-cases/unicode.test.js' },
];

let totalPassed = 0;
let totalFailed = 0;
const failedSuites = [];

for (const suite of testSuites) {
  console.log(`\n\x1b[36m▶ Running: ${suite.name}\x1b[0m`);
  console.log('-'.repeat(50));

  try {
    const testPath = path.join(__dirname, suite.file);
    execSync(`node "${testPath}"`, {
      stdio: 'inherit',
      cwd: ROOT
    });
    totalPassed++;
  } catch (e) {
    totalFailed++;
    failedSuites.push(suite.name);
  }
}

// Final summary
console.log('\n\n' + '='.repeat(60));
console.log('\x1b[1m                    FINAL SUMMARY\x1b[0m');
console.log('='.repeat(60));

console.log(`\nTest Suites: \x1b[32m${totalPassed} passed\x1b[0m, \x1b[31m${totalFailed} failed\x1b[0m, ${testSuites.length} total`);

if (failedSuites.length > 0) {
  console.log('\n\x1b[31mFailed Suites:\x1b[0m');
  for (const suite of failedSuites) {
    console.log(`  ✗ ${suite}`);
  }
}

console.log('\n' + '='.repeat(60));

process.exit(totalFailed > 0 ? 1 : 0);
