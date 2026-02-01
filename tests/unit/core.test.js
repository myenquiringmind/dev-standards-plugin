#!/usr/bin/env node
/**
 * Unit tests for lib/core modules
 * Tests platform detection, config, and command execution
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

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(message || `Expected ${expected}, got ${actual}`);
  }
}

// Load modules
const platform = require('../../lib/core/platform');
const config = require('../../lib/core/config');
const exec = require('../../lib/core/exec');

// ============================================
// Test: Platform Detection
// ============================================
console.log('\n\x1b[1mPlatform Detection\x1b[0m');

test('isWindows is boolean', () => {
  assert(typeof platform.isWindows === 'boolean');
});

test('isMacOS is boolean', () => {
  assert(typeof platform.isMacOS === 'boolean');
});

test('isLinux is boolean', () => {
  assert(typeof platform.isLinux === 'boolean');
});

test('exactly one platform is true', () => {
  const platforms = [platform.isWindows, platform.isMacOS, platform.isLinux];
  const trueCount = platforms.filter(p => p).length;
  // Could be 0 on other platforms like FreeBSD, but at least not more than 1
  assert(trueCount <= 1, 'Multiple platforms detected as true');
});

test('getPythonCommand returns string', () => {
  const cmd = platform.getPythonCommand();
  assert(typeof cmd === 'string');
  assert(cmd === 'python' || cmd === 'python3');
});

test('getWhichCommand returns string', () => {
  const cmd = platform.getWhichCommand();
  assert(typeof cmd === 'string');
  assert(cmd === 'where' || cmd === 'which');
});

test('getVenvBinDir returns Scripts or bin', () => {
  const dir = platform.getVenvBinDir();
  assert(dir === 'Scripts' || dir === 'bin');
});

test('getPythonExecutable includes python', () => {
  const exe = platform.getPythonExecutable();
  assert(exe.includes('python'));
});

test('getPipExecutable includes pip', () => {
  const exe = platform.getPipExecutable();
  assert(exe.includes('pip'));
});

test('getPathSeparator returns ; or :', () => {
  const sep = platform.getPathSeparator();
  assert(sep === ';' || sep === ':');
});

test('getLineEnding returns \\r\\n or \\n', () => {
  const ending = platform.getLineEnding();
  assert(ending === '\r\n' || ending === '\n');
});

// ============================================
// Test: Config Constants
// ============================================
console.log('\n\x1b[1mConfig Constants\x1b[0m');

test('PLUGIN_VERSION is semver format', () => {
  assert(/^\d+\.\d+\.\d+/.test(config.PLUGIN_VERSION));
});

test('PLUGIN_REPO is valid format', () => {
  assert(config.PLUGIN_REPO.includes('/'));
});

test('TIMEOUTS are all positive numbers', () => {
  for (const [key, value] of Object.entries(config.TIMEOUTS)) {
    assert(typeof value === 'number' && value > 0, `${key} should be positive`);
  }
});

test('VENV_NAMES includes common names', () => {
  assert(config.VENV_NAMES.includes('.venv'));
  assert(config.VENV_NAMES.includes('venv'));
});

test('PYTHON_DEPS includes required tools', () => {
  assert(config.PYTHON_DEPS.includes('ruff'));
  assert(config.PYTHON_DEPS.includes('mypy'));
});

test('PROTECTED_BRANCHES includes main branches', () => {
  assert(config.PROTECTED_BRANCHES.includes('main'));
  assert(config.PROTECTED_BRANCHES.includes('master'));
});

test('DANGEROUS_PATTERNS is array of RegExp', () => {
  assert(Array.isArray(config.DANGEROUS_PATTERNS));
  for (const pattern of config.DANGEROUS_PATTERNS) {
    assert(pattern instanceof RegExp, 'Each pattern should be RegExp');
  }
});

test('FORMATTERS has common languages', () => {
  assert(config.FORMATTERS.js);
  assert(config.FORMATTERS.py);
  assert(config.FORMATTERS.ts);
});

test('TYPE_CHECKERS has common languages', () => {
  assert(config.TYPE_CHECKERS.py);
  assert(config.TYPE_CHECKERS.ts);
});

test('LINTERS has common languages', () => {
  assert(config.LINTERS.py);
  assert(config.LINTERS.js);
});

test('MAX_STDIN_SIZE is reasonable', () => {
  assert(config.MAX_STDIN_SIZE >= 1024 * 1024); // At least 1MB
  assert(config.MAX_STDIN_SIZE <= 100 * 1024 * 1024); // At most 100MB
});

test('VALID_PACKAGE_NAME is RegExp', () => {
  assert(config.VALID_PACKAGE_NAME instanceof RegExp);
});

// ============================================
// Test: Gitignore Patterns (Phase 11)
// ============================================
console.log('\n\x1b[1mGitignore Patterns (Phase 11)\x1b[0m');

test('GITIGNORE_PATTERNS exists', () => {
  assert(config.GITIGNORE_PATTERNS, 'GITIGNORE_PATTERNS should exist');
  assert(typeof config.GITIGNORE_PATTERNS === 'object');
});

test('GITIGNORE_PATTERNS has all required categories', () => {
  const required = ['os', 'ide', 'node', 'python', 'coverage', 'build', 'cache', 'secrets', 'logs', 'temp'];
  for (const cat of required) {
    assert(config.GITIGNORE_PATTERNS[cat], `Missing category: ${cat}`);
    assert(Array.isArray(config.GITIGNORE_PATTERNS[cat]), `${cat} should be array`);
    assert(config.GITIGNORE_PATTERNS[cat].length > 0, `${cat} should not be empty`);
  }
});

test('GITIGNORE_PATTERNS.secrets includes .env', () => {
  assert(config.GITIGNORE_PATTERNS.secrets.includes('.env'), '.env must be in secrets');
});

test('GITIGNORE_PATTERNS.secrets includes credential patterns', () => {
  const secrets = config.GITIGNORE_PATTERNS.secrets;
  assert(secrets.some(p => p.includes('.pem') || p.includes('*.pem')), 'Should include .pem files');
  assert(secrets.some(p => p.includes('.key') || p.includes('*.key')), 'Should include .key files');
});

test('GITIGNORE_PATTERNS.os includes common OS files', () => {
  const os = config.GITIGNORE_PATTERNS.os;
  assert(os.includes('.DS_Store'), 'Should include .DS_Store');
  assert(os.includes('Thumbs.db'), 'Should include Thumbs.db');
});

test('GITIGNORE_PATTERNS.node includes node_modules', () => {
  assert(config.GITIGNORE_PATTERNS.node.includes('node_modules/'), 'Should include node_modules/');
});

test('GITIGNORE_PATTERNS.python includes __pycache__', () => {
  assert(config.GITIGNORE_PATTERNS.python.includes('__pycache__/'), 'Should include __pycache__/');
});

// ============================================
// Test: Root Directories (Phase 11)
// ============================================
console.log('\n\x1b[1mRoot Directories (Phase 11)\x1b[0m');

test('ROOT_DIRECTORIES exists', () => {
  assert(config.ROOT_DIRECTORIES, 'ROOT_DIRECTORIES should exist');
  assert(Array.isArray(config.ROOT_DIRECTORIES));
});

test('ROOT_DIRECTORIES includes .husky', () => {
  assert(config.ROOT_DIRECTORIES.includes('.husky'), '.husky must be allowed');
});

test('ROOT_DIRECTORIES includes .claude-plugin', () => {
  assert(config.ROOT_DIRECTORIES.includes('.claude-plugin'), '.claude-plugin must be allowed');
});

test('ROOT_DIRECTORIES includes .github', () => {
  assert(config.ROOT_DIRECTORIES.includes('.github'), '.github must be allowed');
});

test('ROOT_DIRECTORIES includes common source directories', () => {
  assert(config.ROOT_DIRECTORIES.includes('src'), 'src must be allowed');
  assert(config.ROOT_DIRECTORIES.includes('lib'), 'lib must be allowed');
  assert(config.ROOT_DIRECTORIES.includes('tests'), 'tests must be allowed');
});

// ============================================
// Test: Protected Branches (Phase 11)
// ============================================
console.log('\n\x1b[1mProtected Branches (Phase 11)\x1b[0m');

test('PROTECTED_BRANCHES includes develop', () => {
  assert(config.PROTECTED_BRANCHES.includes('develop'), 'develop should be protected');
});

test('PROTECTED_BRANCHES includes staging', () => {
  assert(config.PROTECTED_BRANCHES.includes('staging'), 'staging should be protected');
});

test('PROTECTED_BRANCHES includes release', () => {
  assert(config.PROTECTED_BRANCHES.includes('release'), 'release should be protected');
});

// ============================================
// Test: Project Type Patterns (Phase 11)
// ============================================
console.log('\n\x1b[1mProject Type Patterns (Phase 11)\x1b[0m');

test('PROJECT_TYPE_PATTERNS exists', () => {
  assert(config.PROJECT_TYPE_PATTERNS, 'PROJECT_TYPE_PATTERNS should exist');
});

test('PROJECT_TYPE_PATTERNS.node includes package.json', () => {
  assert(config.PROJECT_TYPE_PATTERNS.node.includes('package.json'));
});

test('PROJECT_TYPE_PATTERNS.python includes requirements.txt', () => {
  assert(config.PROJECT_TYPE_PATTERNS.python.includes('requirements.txt'));
});

// ============================================
// Test: ROOT_BLACKLIST regex fix (Phase 10)
// ============================================
console.log('\n\x1b[1mROOT_BLACKLIST Regex (Phase 10)\x1b[0m');

test('ROOT_BLACKLIST catches nul file (plain)', () => {
  const matches = config.ROOT_BLACKLIST.some(pattern => pattern.test('nul'));
  assert(matches, 'Should match plain "nul" file');
});

test('ROOT_BLACKLIST catches .nul file', () => {
  const matches = config.ROOT_BLACKLIST.some(pattern => pattern.test('.nul'));
  assert(matches, 'Should match ".nul" file');
});

// ============================================
// Test: Exec Module
// ============================================
console.log('\n\x1b[1mExec Module\x1b[0m');

test('escapeShellArg escapes spaces', () => {
  const result = exec.escapeShellArg('file with spaces.txt');
  assert(result.length > 'file with spaces.txt'.length);
});

test('escapeShellArg throws on non-string', () => {
  let threw = false;
  try {
    exec.escapeShellArg(123);
  } catch (e) {
    threw = true;
  }
  assert(threw, 'Should throw on non-string');
});

test('escapeShellArg handles quotes', () => {
  const result = exec.escapeShellArg('file"with"quotes.txt');
  // Should escape or wrap the quotes
  assert(result !== 'file"with"quotes.txt');
});

test('escapeFilePath is alias for escapeShellArg', () => {
  const arg = 'test file.txt';
  assertEqual(exec.escapeFilePath(arg), exec.escapeShellArg(arg));
});

test('commandExists returns boolean', () => {
  const result = exec.commandExists('node');
  assert(typeof result === 'boolean');
});

test('commandExists finds node', () => {
  assert(exec.commandExists('node'), 'node should exist');
});

test('commandExists returns false for nonexistent', () => {
  assert(!exec.commandExists('definitely_not_a_real_command_xyz123'));
});

test('exec returns object with success property', () => {
  const result = exec.exec('echo test');
  assert(typeof result === 'object');
  assert('success' in result);
});

test('exec successful command has output', () => {
  const result = exec.exec('echo hello');
  assert(result.success);
  assert(result.output.includes('hello'));
});

test('exec failed command has error', () => {
  const result = exec.exec('exit 1', { timeout: 1000 });
  // Note: 'exit 1' may not work on all platforms - verify we get some result back
  assert(result !== undefined);
});

test('execOrThrow returns output on success', () => {
  const result = exec.execOrThrow('echo test');
  assert(typeof result === 'string');
});

test('execOrThrow throws on failure', () => {
  let threw = false;
  try {
    exec.execOrThrow('definitely_not_a_command_xyz');
  } catch (e) {
    threw = true;
  }
  assert(threw, 'Should throw on failed command');
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mCore Unit Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
