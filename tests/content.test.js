#!/usr/bin/env node
/**
 * Content validation tests for agents, commands, and skills
 * Verifies markdown structure and required sections
 */

const fs = require('fs');
const path = require('path');

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
  if (!condition) throw new Error(message);
}

const ROOT = path.join(__dirname, '..');

// ============================================
// Test: Agent Files
// ============================================
console.log('\n\x1b[1mAgent Files\x1b[0m');

const agents = [
  'agents/standards-orchestrator.md',
  'agents/logging-standards.md',
  'agents/error-standards.md',
  'agents/type-standards.md',
  'agents/lint-standards.md',
  'agents/test-standards.md',
  'agents/validation-standards.md',
  'agents/git-standards.md',
  'agents/investigator.md',
  'agents/code-reviewer.md',
  'agents/doc-writer.md'
];

for (const agent of agents) {
  const agentName = path.basename(agent, '.md');
  const content = fs.readFileSync(path.join(ROOT, agent), 'utf8');

  test(`${agentName} has title (# heading)`, () => {
    assert(content.includes('# '), 'should have title');
  });

  test(`${agentName} has constraints section`, () => {
    assert(
      content.toLowerCase().includes('constraint') ||
      content.toLowerCase().includes('output format'),
      'should have constraints or output format'
    );
  });

  test(`${agentName} is not empty`, () => {
    assert(content.trim().length > 100, 'should have substantial content');
  });
}

// ============================================
// Test: Command Files
// ============================================
console.log('\n\x1b[1mCommand Files\x1b[0m');

const commands = [
  'commands/plan.md',
  'commands/fix.md',
  'commands/validate.md',
  'commands/review.md',
  'commands/setup.md',
  'commands/typecheck.md',
  'commands/logs.md'
];

for (const command of commands) {
  const commandName = path.basename(command, '.md');
  const content = fs.readFileSync(path.join(ROOT, command), 'utf8');

  test(`/${commandName} has title`, () => {
    assert(content.includes('# '), 'should have title');
  });

  test(`/${commandName} has usage or output section`, () => {
    assert(
      content.toLowerCase().includes('usage') ||
      content.toLowerCase().includes('output') ||
      content.toLowerCase().includes('format') ||
      content.toLowerCase().includes('report') ||
      content.toLowerCase().includes('workflow'),
      'should have usage, output, report, or workflow section'
    );
  });

  test(`/${commandName} is actionable (has steps or examples)`, () => {
    assert(
      content.includes('```') ||
      content.includes('1.') ||
      content.includes('- ['),
      'should have code blocks, numbered lists, or checkboxes'
    );
  });
}

// ============================================
// Test: Skill File
// ============================================
console.log('\n\x1b[1mSkill File\x1b[0m');

const skillPath = path.join(ROOT, 'skills/dev-workflow/SKILL.md');
const skillContent = fs.readFileSync(skillPath, 'utf8');

test('skill has YAML frontmatter', () => {
  assert(skillContent.startsWith('---'), 'should start with ---');
  const endFrontmatter = skillContent.indexOf('---', 3);
  assert(endFrontmatter > 3, 'should have closing ---');
});

test('skill frontmatter has name', () => {
  const match = skillContent.match(/^---\n([\s\S]*?)\n---/);
  assert(match, 'should have frontmatter');
  assert(match[1].includes('name:'), 'should have name field');
});

test('skill frontmatter has description', () => {
  const match = skillContent.match(/^---\n([\s\S]*?)\n---/);
  assert(match, 'should have frontmatter');
  assert(match[1].includes('description:'), 'should have description field');
});

test('skill has workflow content', () => {
  assert(skillContent.includes('# '), 'should have headings');
  assert(
    skillContent.includes('Investigate') ||
    skillContent.includes('Plan') ||
    skillContent.includes('Implement'),
    'should have workflow steps'
  );
});

test('skill mentions DRY/SOLID', () => {
  assert(
    skillContent.includes('DRY') && skillContent.includes('SOLID'),
    'should mention DRY and SOLID'
  );
});

test('skill has git commit format', () => {
  assert(
    skillContent.includes('type(scope)') ||
    skillContent.includes('feat') ||
    skillContent.includes('fix'),
    'should have git commit format guidance'
  );
});

// ============================================
// Test: Template File
// ============================================
console.log('\n\x1b[1mTemplate File\x1b[0m');

const templatePath = path.join(ROOT, 'templates/CLAUDE.md.template');
const templateContent = fs.readFileSync(templatePath, 'utf8');

test('template has Quick Reference section', () => {
  assert(templateContent.includes('Quick Reference'), 'should have Quick Reference');
});

test('template has common commands', () => {
  assert(
    templateContent.includes('Test') &&
    templateContent.includes('Lint') &&
    templateContent.includes('Build'),
    'should have Test, Lint, Build commands'
  );
});

test('template has project structure section', () => {
  assert(
    templateContent.includes('Project Structure') ||
    templateContent.includes('src/'),
    'should have project structure'
  );
});

// ============================================
// Test: Config File
// ============================================
console.log('\n\x1b[1mConfig File\x1b[0m');

const configPath = path.join(ROOT, 'config/defaults.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

test('config has protectedBranches', () => {
  assert(Array.isArray(config.protectedBranches), 'should be array');
  assert(config.protectedBranches.includes('main'), 'should include main');
  assert(config.protectedBranches.includes('master'), 'should include master');
});

test('config has formatters for common languages', () => {
  assert(config.formatters.ts, 'should have TypeScript');
  assert(config.formatters.py, 'should have Python');
  assert(config.formatters.js, 'should have JavaScript');
});

test('config has typeCheckers', () => {
  assert(config.typeCheckers.ts, 'should have TypeScript');
  assert(config.typeCheckers.py, 'should have Python');
});

test('config has linters', () => {
  assert(config.linters.ts, 'should have TypeScript');
  assert(config.linters.py, 'should have Python');
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mContent Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
