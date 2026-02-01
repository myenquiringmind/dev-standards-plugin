#!/usr/bin/env node
/**
 * Validates hooks.json against the JSON schema and best practices.
 * Run with: node scripts/validate-hooks.js
 *
 * Exit codes:
 *   0 - Validation passed
 *   1 - Validation failed
 */

const fs = require('fs');
const path = require('path');

const HOOKS_PATH = path.join(__dirname, '..', 'hooks', 'hooks.json');
const SCHEMA_PATH = path.join(__dirname, '..', 'schemas', 'hooks.schema.json');

const errors = [];
const warnings = [];

/**
 * Add an error
 */
function error(message) {
  errors.push(message);
  console.log(`\x1b[31m  ERROR:\x1b[0m ${message}`);
}

/**
 * Add a warning
 */
function warn(message) {
  warnings.push(message);
  console.log(`\x1b[33m  WARN:\x1b[0m ${message}`);
}

/**
 * Validate hooks.json structure and content
 */
function validate() {
  console.log('\n\x1b[1mValidating hooks.json\x1b[0m\n');

  // Check file exists
  if (!fs.existsSync(HOOKS_PATH)) {
    error(`hooks.json not found at ${HOOKS_PATH}`);
    return;
  }

  // Parse JSON
  let hooks;
  try {
    const content = fs.readFileSync(HOOKS_PATH, 'utf8');
    hooks = JSON.parse(content);
    console.log('  \x1b[32m✓\x1b[0m Valid JSON syntax');
  } catch (e) {
    error(`Invalid JSON: ${e.message}`);
    return;
  }

  // Check _meta section
  if (!hooks._meta) {
    error('Missing _meta section');
  } else {
    if (!hooks._meta.version) {
      error('Missing _meta.version');
    } else if (!/^\d+\.\d+\.\d+$/.test(hooks._meta.version)) {
      error(`Invalid version format: ${hooks._meta.version} (expected semver)`);
    } else {
      console.log(`  \x1b[32m✓\x1b[0m Version: ${hooks._meta.version}`);
    }
  }

  // Check required sections
  const requiredSections = [
    'SessionStart',
    'PreToolUse',
    'PostToolUse',
    'Stop'
  ];

  const optionalSections = [
    'UserPromptSubmit',
    'SubagentStop',
    'PreCompact'
  ];

  for (const section of requiredSections) {
    if (!hooks[section]) {
      error(`Missing required section: ${section}`);
    } else if (!Array.isArray(hooks[section])) {
      error(`${section} must be an array`);
    } else {
      console.log(`  \x1b[32m✓\x1b[0m Has ${section} section`);
    }
  }

  for (const section of optionalSections) {
    if (hooks[section] && !Array.isArray(hooks[section])) {
      error(`${section} must be an array if present`);
    }
  }

  // Validate each hook entry
  const allSections = [...requiredSections, ...optionalSections];
  let hookCount = 0;

  for (const section of allSections) {
    const entries = hooks[section];
    if (!Array.isArray(entries)) continue;

    entries.forEach((entry, i) => {
      const prefix = `${section}[${i}]`;

      // Check matcher
      if (!entry.matcher) {
        error(`${prefix}: missing 'matcher'`);
      } else if (entry.matcher !== '*') {
        try {
          new RegExp(entry.matcher);
        } catch (e) {
          error(`${prefix}: invalid regex matcher: ${entry.matcher}`);
        }
      }

      // Check hooks array
      if (!entry.hooks || !Array.isArray(entry.hooks)) {
        error(`${prefix}: missing or invalid 'hooks' array`);
      } else {
        entry.hooks.forEach((hook, j) => {
          const hookPrefix = `${prefix}.hooks[${j}]`;
          hookCount++;

          if (!hook.type) {
            error(`${hookPrefix}: missing 'type'`);
          } else if (hook.type === 'command') {
            if (!hook.command) {
              error(`${hookPrefix}: command type missing 'command'`);
            }
            if (typeof hook.timeout !== 'number' || hook.timeout <= 0) {
              error(`${hookPrefix}: command type missing or invalid 'timeout'`);
            }
            if (hook.timeout > 60) {
              warn(`${hookPrefix}: timeout > 60s may cause issues`);
            }

            // Check for cross-platform compatibility
            if (hook.command) {
              if (hook.command.startsWith('bash -c')) {
                warn(`${hookPrefix}: 'bash -c' may not work on Windows`);
              }
              if (hook.command.includes('~/.claude')) {
                warn(`${hookPrefix}: '~/' path may not work on Windows`);
              }
              if (hook.command.includes('$(date ')) {
                warn(`${hookPrefix}: '$(date)' may not work on Windows`);
              }
            }
          } else if (hook.type === 'prompt') {
            if (!hook.prompt) {
              error(`${hookPrefix}: prompt type missing 'prompt'`);
            }
          } else {
            error(`${hookPrefix}: invalid type '${hook.type}' (expected 'command' or 'prompt')`);
          }
        });
      }

      // Check description (optional but recommended)
      if (!entry.description) {
        warn(`${prefix}: missing 'description'`);
      }
    });
  }

  console.log(`\n  Total hooks validated: ${hookCount}`);

  // Check for unknown sections
  const validSections = ['_meta', ...allSections];
  for (const key of Object.keys(hooks)) {
    if (!validSections.includes(key)) {
      warn(`Unknown section: ${key}`);
    }
  }
}

// Run validation
validate();

// Summary
console.log('\n' + '='.repeat(50));
if (errors.length === 0 && warnings.length === 0) {
  console.log('\x1b[32m✓ Validation passed with no issues\x1b[0m');
} else if (errors.length === 0) {
  console.log(`\x1b[33m⚠ Validation passed with ${warnings.length} warning(s)\x1b[0m`);
} else {
  console.log(`\x1b[31m✗ Validation failed: ${errors.length} error(s), ${warnings.length} warning(s)\x1b[0m`);
}
console.log('='.repeat(50) + '\n');

process.exit(errors.length > 0 ? 1 : 0);
