#!/usr/bin/env node
/**
 * Test suite for dev-standards plugin
 * Run with: node tests/hooks.test.js
 *
 * Tests validate:
 * - JSON syntax validity
 * - Required sections exist
 * - Matcher patterns are valid regex
 * - PostToolUse includes Edit tool
 * - All command hooks have timeouts
 * - Version consistency between files
 */

const fs = require('fs');
const path = require('path');

const HOOKS_PATH = path.join(__dirname, '..', 'hooks', 'hooks.json');
const PLUGIN_PATH = path.join(__dirname, '..', '.claude-plugin', 'plugin.json');
const MARKETPLACE_PATH = path.join(__dirname, '..', '.claude-plugin', 'marketplace.json');
const CONFIG_PATH = path.join(__dirname, '..', 'config', 'defaults.json');
const CONFIG_SCHEMA_PATH = path.join(__dirname, '..', 'schemas', 'config.schema.json');

let passed = 0;
let failed = 0;

/**
 * Test assertion helper
 */
function assert(condition, message) {
  if (condition) {
    console.log(`  \x1b[32m✓\x1b[0m ${message}`);
    passed++;
  } else {
    console.log(`  \x1b[31m✗\x1b[0m ${message}`);
    failed++;
  }
}

/**
 * Test group helper
 */
function describe(name, fn) {
  console.log(`\n\x1b[1m${name}\x1b[0m`);
  fn();
}

// ============================================
// Test: hooks.json validity
// ============================================
describe('hooks.json', () => {
  let hooks;

  // Test: Valid JSON
  try {
    const content = fs.readFileSync(HOOKS_PATH, 'utf8');
    hooks = JSON.parse(content);
    assert(true, 'is valid JSON');
  } catch (e) {
    assert(false, `is valid JSON: ${e.message}`);
    return;
  }

  // Test: Has required sections
  const requiredSections = [
    'SessionStart',
    'UserPromptSubmit',
    'PreToolUse',
    'PostToolUse',
    'Stop',
    'SubagentStop',
    'PreCompact'
  ];

  for (const section of requiredSections) {
    assert(
      Array.isArray(hooks[section]),
      `has ${section} section`
    );
  }

  // Test: Has _meta with version
  assert(
    hooks._meta && typeof hooks._meta.version === 'string',
    'has _meta.version'
  );

  // Test: All matchers are valid regex
  let matchersValid = true;
  for (const [section, entries] of Object.entries(hooks)) {
    if (section === '_meta') continue;
    if (!Array.isArray(entries)) continue;

    for (const entry of entries) {
      if (entry.matcher && entry.matcher !== '*') {
        try {
          new RegExp(entry.matcher);
        } catch (e) {
          matchersValid = false;
          console.log(`    Invalid regex in ${section}: ${entry.matcher}`);
        }
      }
    }
  }
  assert(matchersValid, 'all matchers are valid regex patterns');

  // Test: PostToolUse matchers include Edit
  const postToolUseEntries = hooks.PostToolUse || [];
  const formatHook = postToolUseEntries.find(e =>
    e.description?.toLowerCase().includes('format') ||
    e.description?.toLowerCase().includes('auto-format')
  );
  const typeCheckHook = postToolUseEntries.find(e =>
    e.description?.toLowerCase().includes('type check')
  );
  const lintHook = postToolUseEntries.find(e =>
    e.description?.toLowerCase().includes('lint')
  );

  assert(
    formatHook && formatHook.matcher?.includes('Edit'),
    'auto-format hook matches Edit tool'
  );
  assert(
    typeCheckHook && typeCheckHook.matcher?.includes('Edit'),
    'type check hook matches Edit tool'
  );
  assert(
    lintHook && lintHook.matcher?.includes('Edit'),
    'lint hook matches Edit tool'
  );

  // Test: All command hooks have timeouts
  let allHaveTimeouts = true;
  for (const [section, entries] of Object.entries(hooks)) {
    if (section === '_meta') continue;
    if (!Array.isArray(entries)) continue;

    for (const entry of entries) {
      for (const hook of entry.hooks || []) {
        if (hook.type === 'command') {
          if (typeof hook.timeout !== 'number' || hook.timeout <= 0) {
            allHaveTimeouts = false;
            console.log(`    Missing timeout in ${section}: ${entry.description}`);
          }
        }
      }
    }
  }
  assert(allHaveTimeouts, 'all command hooks have valid timeouts');

  // Test: No bash-only commands (cross-platform)
  let noBashOnly = true;
  for (const [section, entries] of Object.entries(hooks)) {
    if (section === '_meta') continue;
    if (!Array.isArray(entries)) continue;

    for (const entry of entries) {
      for (const hook of entry.hooks || []) {
        if (hook.type === 'command' && hook.command) {
          // Check for bash-only patterns
          if (hook.command.startsWith('bash -c') ||
              hook.command.includes('~/.claude') ||
              hook.command.includes('$(date ')) {
            noBashOnly = false;
            console.log(`    Bash-only command in ${section}: ${entry.description}`);
          }
        }
      }
    }
  }
  assert(noBashOnly, 'all hooks are cross-platform (no bash-only commands)');
});

// ============================================
// Test: plugin.json validity
// ============================================
describe('plugin.json', () => {
  let plugin;

  try {
    const content = fs.readFileSync(PLUGIN_PATH, 'utf8');
    plugin = JSON.parse(content);
    assert(true, 'is valid JSON');
  } catch (e) {
    assert(false, `is valid JSON: ${e.message}`);
    return;
  }

  // Test: Has required fields
  assert(typeof plugin.name === 'string' && plugin.name.length > 0, 'has name');
  assert(typeof plugin.version === 'string' && plugin.version.length > 0, 'has version');
  assert(typeof plugin.description === 'string' && plugin.description.length > 0, 'has description');

  // Test: No placeholder values
  assert(
    !plugin.author?.includes('Your Team') &&
    !plugin.author?.includes('YOUR_'),
    'author has no placeholder values'
  );
  assert(
    !plugin.repository?.includes('YOUR_ORG') &&
    !plugin.repository?.includes('YOUR_'),
    'repository has no placeholder values'
  );

  // Test: Components reference existing files
  const agents = plugin.components?.agents || [];
  for (const agent of agents) {
    const agentPath = path.join(__dirname, '..', agent);
    assert(fs.existsSync(agentPath), `agent exists: ${agent}`);
  }

  const commands = plugin.components?.commands || [];
  for (const command of commands) {
    const commandPath = path.join(__dirname, '..', command);
    assert(fs.existsSync(commandPath), `command exists: ${command}`);
  }
});

// ============================================
// Test: Version consistency
// ============================================
describe('Version Consistency', () => {
  let hooks, plugin;

  try {
    hooks = JSON.parse(fs.readFileSync(HOOKS_PATH, 'utf8'));
    plugin = JSON.parse(fs.readFileSync(PLUGIN_PATH, 'utf8'));
  } catch (e) {
    assert(false, `Could not parse files: ${e.message}`);
    return;
  }

  assert(
    hooks._meta?.version === plugin.version,
    `hooks version (${hooks._meta?.version}) matches plugin version (${plugin.version})`
  );

  // Test: SessionStart VERSION constant matches plugin version
  const sessionStartHook = hooks.SessionStart?.[0]?.hooks?.[0]?.command || '';
  const versionMatch = sessionStartHook.match(/VERSION='(\d+\.\d+\.\d+)'/);
  if (versionMatch) {
    assert(
      versionMatch[1] === plugin.version,
      `SessionStart VERSION constant (${versionMatch[1]}) matches plugin version (${plugin.version})`
    );
  } else {
    assert(false, 'SessionStart hook contains VERSION constant');
  }
});

// ============================================
// Test: marketplace.json validity
// ============================================
describe('marketplace.json', () => {
  let marketplace;

  try {
    const content = fs.readFileSync(MARKETPLACE_PATH, 'utf8');
    marketplace = JSON.parse(content);
    assert(true, 'is valid JSON');
  } catch (e) {
    assert(false, `is valid JSON: ${e.message}`);
    return;
  }

  // Test: No placeholder values
  assert(
    !marketplace.name?.includes('your-org') &&
    !marketplace.name?.includes('YOUR_'),
    'name has no placeholder values'
  );

  // Test: Plugins use 'source' field (not 'path')
  const plugins = marketplace.plugins || [];
  for (const plugin of plugins) {
    assert(
      plugin.source !== undefined,
      `plugin "${plugin.name}" has 'source' field (not 'path')`
    );
    assert(
      plugin.path === undefined,
      `plugin "${plugin.name}" does not use deprecated 'path' field`
    );
  }
});

// ============================================
// Test: config/defaults.json validity
// ============================================
describe('config/defaults.json', () => {
  if (!fs.existsSync(CONFIG_PATH)) {
    assert(false, 'file exists');
    return;
  }

  let config;
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf8');
    config = JSON.parse(content);
    assert(true, 'is valid JSON');
  } catch (e) {
    assert(false, `is valid JSON: ${e.message}`);
    return;
  }

  // Test: Has protected branches
  assert(
    Array.isArray(config.protectedBranches) && config.protectedBranches.length > 0,
    'has protectedBranches array'
  );

  // Test: Has formatters
  assert(
    typeof config.formatters === 'object' && Object.keys(config.formatters).length > 0,
    'has formatters object'
  );

  // Test: Has type checkers
  assert(
    typeof config.typeCheckers === 'object' && Object.keys(config.typeCheckers).length > 0,
    'has typeCheckers object'
  );
});

// ============================================
// Test: config.schema.json validity
// ============================================
describe('schemas/config.schema.json', () => {
  if (!fs.existsSync(CONFIG_SCHEMA_PATH)) {
    assert(false, 'file exists');
    return;
  }

  let schema;
  try {
    const content = fs.readFileSync(CONFIG_SCHEMA_PATH, 'utf8');
    schema = JSON.parse(content);
    assert(true, 'is valid JSON');
  } catch (e) {
    assert(false, `is valid JSON: ${e.message}`);
    return;
  }

  // Test: Has required schema properties
  assert(
    schema.properties?.protectedBranches,
    'defines protectedBranches property'
  );
  assert(
    schema.properties?.formatters,
    'defines formatters property'
  );
  assert(
    schema.properties?.typeCheckers,
    'defines typeCheckers property'
  );
  assert(
    schema.properties?.linters,
    'defines linters property'
  );
  assert(
    schema.properties?.dangerousPatterns,
    'defines dangerousPatterns property'
  );

  // Test: Schema reference in config matches
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  assert(
    config.$schema?.includes('config.schema.json'),
    'config/defaults.json references config.schema.json'
  );
});

// ============================================
// Test: Required files exist
// ============================================
describe('Required Files', () => {
  const requiredFiles = [
    'LICENSE',
    'README.md',
    'CHANGELOG.md',
    'CONTRIBUTING.md',
    '.gitignore',
    'skills/dev-workflow/SKILL.md',
    'templates/CLAUDE.md.template',
    'lib/utils.js',
    'lib/hook-runner.js',
    'requirements.txt',
    // Schemas
    'schemas/hooks.schema.json',
    'schemas/config.schema.json',
    // New modular structure
    'lib/core/index.js',
    'lib/core/platform.js',
    'lib/core/config.js',
    'lib/core/exec.js',
    'lib/venv/index.js',
    'lib/git/index.js',
    'lib/logging/index.js',
    'lib/validation/index.js',
    'lib/tools/index.js',
    'lib/version/index.js'
  ];

  for (const file of requiredFiles) {
    const filePath = path.join(__dirname, '..', file);
    assert(fs.existsSync(filePath), `${file} exists`);
  }
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mTest Results:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
