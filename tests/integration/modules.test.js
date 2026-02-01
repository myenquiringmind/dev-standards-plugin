#!/usr/bin/env node
/**
 * Integration tests for module interactions
 * Tests that modules work together correctly
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

// ============================================
// Test: Module Loading
// ============================================
console.log('\n\x1b[1mModule Loading\x1b[0m');

test('core module loads all submodules', () => {
  const core = require('../../lib/core');
  assert(core.platform, 'Should have platform');
  assert(core.config, 'Should have config');
  assert(core.exec, 'Should have exec');
});

test('utils re-exports work', () => {
  const utils = require('../../lib/utils');
  // Check key exports
  assert(utils.PLUGIN_VERSION, 'Should have PLUGIN_VERSION');
  assert(typeof utils.getVenvPython === 'function', 'Should have getVenvPython');
  assert(typeof utils.isDangerousCommand === 'function', 'Should have isDangerousCommand');
});

test('all domain modules load', () => {
  const venv = require('../../lib/venv');
  const git = require('../../lib/git');
  const logging = require('../../lib/logging');
  const validation = require('../../lib/validation');
  const tools = require('../../lib/tools');
  const version = require('../../lib/version');

  assert(venv.getVenvPython, 'venv should export getVenvPython');
  assert(git.getCurrentBranch, 'git should export getCurrentBranch');
  assert(logging.log, 'logging should export log');
  assert(validation.isDangerousCommand, 'validation should export isDangerousCommand');
  assert(tools.formatFile, 'tools should export formatFile');
  assert(version.checkForUpdates, 'version should export checkForUpdates');
});

// ============================================
// Test: Cross-Module Integration
// ============================================
console.log('\n\x1b[1mCross-Module Integration\x1b[0m');

test('venv uses platform module correctly', () => {
  const venv = require('../../lib/venv');
  const platform = require('../../lib/core/platform');

  const pythonPath = venv.getVenvPython('/test/.venv');

  if (platform.isWindows) {
    assert(pythonPath.includes('Scripts'), 'Windows should use Scripts');
    assert(pythonPath.includes('.exe'), 'Windows should use .exe');
  } else {
    assert(pythonPath.includes('bin'), 'Unix should use bin');
    assert(!pythonPath.includes('.exe'), 'Unix should not use .exe');
  }
});

test('venv uses config module correctly', () => {
  const venv = require('../../lib/venv');
  const config = require('../../lib/core/config');

  // findVenv uses VENV_NAMES from config
  assert(config.VENV_NAMES.length > 0, 'Config should have VENV_NAMES');

  // This just verifies the function runs without error
  const result = venv.findVenv('/nonexistent/path');
  assert(result === null, 'Should return null for nonexistent path');
});

test('validation uses config for patterns', () => {
  const validation = require('../../lib/validation');
  const config = require('../../lib/core/config');

  // Validation uses patterns from config
  assert(config.DANGEROUS_PATTERNS.length > 0, 'Config should have patterns');

  // Verify patterns are used
  const dangerous = validation.isDangerousCommand('rm -rf /');
  assert(dangerous === true, 'Should detect dangerous command');
});

test('tools uses venv and exec modules', () => {
  const tools = require('../../lib/tools');

  // Test getExt function
  assert(tools.getExt('file.js') === 'js');
  assert(tools.getExt('file.py') === 'py');
  assert(tools.getExt('file.test.js') === 'js');
});

test('version uses config for plugin info', () => {
  const version = require('../../lib/version');
  const config = require('../../lib/core/config');

  const pluginVersion = version.getPluginVersion();
  assert(pluginVersion === config.PLUGIN_VERSION, 'Versions should match');
});

// ============================================
// Test: Error Propagation
// ============================================
console.log('\n\x1b[1mError Propagation\x1b[0m');

test('venv.validatePackageName throws on invalid', () => {
  const venv = require('../../lib/venv');
  let threw = false;
  try {
    venv.validatePackageName('invalid; rm -rf /');
  } catch (e) {
    threw = true;
    assert(e.message.includes('Invalid'), 'Error should mention invalid');
  }
  assert(threw, 'Should throw on invalid package name');
});

test('exec.escapeShellArg throws on non-string', () => {
  const exec = require('../../lib/core/exec');
  let threw = false;
  try {
    exec.escapeShellArg(123);
  } catch (e) {
    threw = true;
    assert(e instanceof TypeError, 'Should throw TypeError');
  }
  assert(threw, 'Should throw on non-string');
});

// ============================================
// Test: Config Consistency
// ============================================
console.log('\n\x1b[1mConfig Consistency\x1b[0m');

test('all timeout keys are used', () => {
  const config = require('../../lib/core/config');

  const timeoutKeys = Object.keys(config.TIMEOUTS);
  assert(timeoutKeys.includes('QUICK'), 'Should have QUICK timeout');
  assert(timeoutKeys.includes('STANDARD'), 'Should have STANDARD timeout');
  assert(timeoutKeys.includes('EXTENDED'), 'Should have EXTENDED timeout');
  assert(timeoutKeys.includes('INSTALL'), 'Should have INSTALL timeout');
});

test('formatters and linters cover same languages', () => {
  const config = require('../../lib/core/config');

  // Python should have both formatter and linter
  assert(config.FORMATTERS.py, 'Should have Python formatter');
  assert(config.LINTERS.py, 'Should have Python linter');

  // JS should have both
  assert(config.FORMATTERS.js, 'Should have JS formatter');
  assert(config.LINTERS.js, 'Should have JS linter');
});

// ============================================
// Test: Async Operations
// ============================================
console.log('\n\x1b[1mAsync Operations\x1b[0m');

test('version.checkForUpdates returns promise', async () => {
  const version = require('../../lib/version');

  const result = version.checkForUpdates();
  assert(result instanceof Promise, 'Should return promise');

  // Wait for result
  const updateInfo = await result;
  assert(typeof updateInfo === 'object', 'Should return object');
  assert('currentVersion' in updateInfo, 'Should have currentVersion');
});

// ============================================
// Test: Compatibility Layer (utils.js)
// ============================================
console.log('\n\x1b[1mCompatibility Layer\x1b[0m');

test('utils exports match module functions', () => {
  const utils = require('../../lib/utils');
  const venv = require('../../lib/venv');
  const git = require('../../lib/git');
  const validation = require('../../lib/validation');

  // Check that utils re-exports work correctly
  assert(utils.getVenvPython === venv.getVenvPython);
  assert(utils.findVenv === venv.findVenv);
  assert(utils.isProtectedBranch === git.isProtectedBranch);
  assert(utils.isDangerousCommand === validation.isDangerousCommand);
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mIntegration Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
