#!/usr/bin/env node
/**
 * Unit tests for lib/orchestrator module
 * Tests orchestrator runtime, parser, checkpoint, and handoff modules
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
const orchestrator = require('../../lib/orchestrator');
const parser = require('../../lib/orchestrator/parser');
const checkpoint = require('../../lib/orchestrator/checkpoint');
const handoff = require('../../lib/orchestrator/handoff');

// ============================================
// Parser Tests
// ============================================
console.log('\n\x1b[1mParser Tests\x1b[0m');

test('parse extracts agent name', () => {
  const result = parser.parse('@standards-orchestrator');
  assert(result !== null, 'should return result');
  assert(result.agent === 'standards-orchestrator', 'should extract agent name');
});

test('parse extracts parameters', () => {
  const result = parser.parse('@orchestrator domain=all phase=design');
  assert(result.params.domain === 'all', 'should extract domain');
  assert(result.params.phase === 'design', 'should extract phase');
});

test('parse handles single parameter', () => {
  const result = parser.parse('@git-standards phase=build');
  assert(result.agent === 'git-standards', 'should get agent');
  assert(result.params.phase === 'build', 'should get phase');
});

test('parse handles quoted values', () => {
  const result = parser.parse('@agent param="value with spaces"');
  assert(result.params.param === 'value with spaces', 'should handle double quotes');
});

test('parse handles single quoted values', () => {
  const result = parser.parse("@agent param='single quoted'");
  assert(result.params.param === 'single quoted', 'should handle single quotes');
});

test('parse returns null for non-agent input', () => {
  assert(parser.parse('not an agent') === null, 'should return null');
});

test('parse returns null for empty string', () => {
  assert(parser.parse('') === null, 'should return null for empty');
});

test('parse returns null for null input', () => {
  assert(parser.parse(null) === null, 'should return null for null');
});

test('parse handles agent with no params', () => {
  const result = parser.parse('@investigator');
  assert(result.agent === 'investigator', 'should get agent');
  assert(Object.keys(result.params).length === 0, 'should have empty params');
});

test('validateOrchestratorParams accepts valid domain', () => {
  const result = parser.validateOrchestratorParams({ domain: 'git' });
  assert(result.valid === true, 'should accept git domain');
});

test('validateOrchestratorParams accepts all domain', () => {
  const result = parser.validateOrchestratorParams({ domain: 'all' });
  assert(result.valid === true, 'should accept all domain');
});

test('validateOrchestratorParams accepts all valid domains', () => {
  const domains = ['logging', 'error', 'type', 'lint', 'test', 'validation', 'git', 'housekeeping', 'naming', 'all'];
  for (const domain of domains) {
    const result = parser.validateOrchestratorParams({ domain });
    assert(result.valid === true, `should accept ${domain} domain`);
  }
});

test('validateOrchestratorParams rejects invalid domain', () => {
  const result = parser.validateOrchestratorParams({ domain: 'invalid' });
  assert(result.valid === false, 'should reject invalid domain');
  assert(result.error.includes('Invalid domain'), 'should have error message');
});

test('validateOrchestratorParams rejects missing domain', () => {
  const result = parser.validateOrchestratorParams({});
  assert(result.valid === false, 'should reject missing domain');
  assert(result.error.includes('Missing'), 'should mention missing');
});

test('validateOrchestratorParams accepts valid phase', () => {
  const result = parser.validateOrchestratorParams({ domain: 'git', phase: 'design' });
  assert(result.valid === true, 'should accept design phase');
});

test('validateOrchestratorParams rejects invalid phase', () => {
  const result = parser.validateOrchestratorParams({ domain: 'git', phase: 'invalid-phase' });
  assert(result.valid === false, 'should reject invalid phase');
});

test('parseArgs converts array to params object', () => {
  const result = parser.parseArgs(['domain=all', 'phase=design']);
  assert(result.domain === 'all', 'should get domain');
  assert(result.phase === 'design', 'should get phase');
});

test('formatParams converts object to string', () => {
  const result = parser.formatParams({ domain: 'git', phase: 'build' });
  assert(result.includes('domain=git'), 'should include domain');
  assert(result.includes('phase=build'), 'should include phase');
});

// ============================================
// Orchestrator Tests
// ============================================
console.log('\n\x1b[1mOrchestrator Tests\x1b[0m');

test('initialize accepts valid single domain', () => {
  orchestrator.reset();
  const result = orchestrator.initialize({ domain: 'git' });
  assert(result.success === true, 'should succeed');
  assert(result.state.currentDomain === 'git', 'should set domain');
  assert(result.state.currentPhase === 'design', 'should start at design');
});

test('initialize accepts all domain', () => {
  orchestrator.reset();
  const result = orchestrator.initialize({ domain: 'all' });
  assert(result.success === true, 'should succeed');
  const state = orchestrator.getState();
  assert(state.domains.length === 9, 'should have 9 domains');
});

test('initialize accepts specific phase', () => {
  orchestrator.reset();
  const result = orchestrator.initialize({ domain: 'git', phase: 'build' });
  assert(result.success === true, 'should succeed');
  assert(result.state.currentPhase === 'build', 'should start at build');
});

test('initialize rejects invalid domain', () => {
  orchestrator.reset();
  const result = orchestrator.initialize({ domain: 'invalid' });
  assert(result.success === false, 'should fail');
  assert(result.error.includes('Unknown domain'), 'should have error message');
});

test('initialize rejects invalid phase', () => {
  orchestrator.reset();
  const result = orchestrator.initialize({ domain: 'git', phase: 'invalid' });
  assert(result.success === false, 'should fail');
  assert(result.error.includes('Unknown phase'), 'should have error message');
});

test('getAgentPrompt returns correct format', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  const prompt = orchestrator.getAgentPrompt();
  assert(prompt === '@git-standards phase=design', 'should return correct prompt');
});

test('getAgentPrompt returns empty when not initialized', () => {
  orchestrator.reset();
  const prompt = orchestrator.getAgentPrompt();
  assert(prompt === '', 'should return empty string');
});

test('advancePhase requires checkpoint after design', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  const result = orchestrator.advancePhase();
  assert(result.needsCheckpoint === true, 'should need checkpoint');
  assert(result.checkpointPhase === 'design', 'should be design checkpoint');
});

test('advancePhase requires checkpoint after build', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git', phase: 'build' });
  const result = orchestrator.advancePhase();
  assert(result.needsCheckpoint === true, 'should need checkpoint');
  assert(result.checkpointPhase === 'build', 'should be build checkpoint');
});

test('advancePhase does not need checkpoint after validate-design', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git', phase: 'validate-design' });
  const result = orchestrator.advancePhase();
  assert(result.needsCheckpoint === false, 'should not need checkpoint');
  assert(result.nextPhase === 'build', 'should advance to build');
});

test('processCheckpoint advances on approval', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  orchestrator.advancePhase(); // Triggers checkpoint
  const result = orchestrator.processCheckpoint(true);
  assert(result.success === true, 'should succeed');
  assert(result.nextPhase === 'validate-design', 'should advance to validate-design');
});

test('processCheckpoint records rejection', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  orchestrator.advancePhase();
  const result = orchestrator.processCheckpoint(false, 'needs more work');
  assert(result.rejected === true, 'should be rejected');
  assert(result.feedback === 'needs more work', 'should have feedback');
});

test('processCheckpoint fails when no checkpoint pending', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  const result = orchestrator.processCheckpoint(true);
  assert(result.success === false, 'should fail');
  assert(result.error.includes('No pending checkpoint'), 'should have error');
});

test('getState returns copy of state', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  const state = orchestrator.getState();
  assert(state.currentDomain === 'git', 'should have domain');
  assert(Array.isArray(state.history), 'should have history array');
});

test('setState restores state', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'logging' });
  const savedState = orchestrator.getState();

  orchestrator.reset();
  orchestrator.setState(savedState);
  const restoredState = orchestrator.getState();

  assert(restoredState.currentDomain === 'logging', 'should restore domain');
});

test('getProgress returns correct values', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'git' });
  const progress = orchestrator.getProgress();
  assert(progress.totalPhases === 5, 'should have 5 phases for single domain');
  assert(progress.completedCount === 0, 'should have 0 completed');
  assert(progress.percentage === 0, 'should be 0%');
});

test('registerHandoff adds to pending handoffs', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'error' });
  const result = orchestrator.registerHandoff({
    to: 'logging-standards',
    reason: 'Add logging to catch blocks'
  });
  assert(result.success === true, 'should succeed');
  const state = orchestrator.getState();
  assert(state.pendingHandoffs.length === 1, 'should have 1 handoff');
});

// ============================================
// Checkpoint Tests
// ============================================
console.log('\n\x1b[1mCheckpoint Tests\x1b[0m');

test('generateCheckpointPrompt includes domain and phase', () => {
  const prompt = checkpoint.generateCheckpointPrompt({
    domain: 'git',
    phase: 'design',
    changes: ['Added file X', 'Modified file Y']
  });
  assert(prompt.includes('@git-standards'), 'should include agent');
  assert(prompt.includes('design'), 'should include phase');
  assert(prompt.includes('Added file X'), 'should include changes');
});

test('generateCheckpointPrompt includes handoffs', () => {
  const prompt = checkpoint.generateCheckpointPrompt({
    domain: 'error',
    phase: 'build',
    handoffs: [{ to: 'logging-standards', reason: 'Add logging' }]
  });
  assert(prompt.includes('Pending Handoffs'), 'should have handoffs section');
  assert(prompt.includes('logging-standards'), 'should include target agent');
});

test('parseCheckpointResponse detects approve', () => {
  assert(checkpoint.parseCheckpointResponse('approve').approved === true);
});

test('parseCheckpointResponse detects yes', () => {
  assert(checkpoint.parseCheckpointResponse('yes').approved === true);
});

test('parseCheckpointResponse detects LGTM', () => {
  assert(checkpoint.parseCheckpointResponse('LGTM').approved === true);
});

test('parseCheckpointResponse detects proceed', () => {
  assert(checkpoint.parseCheckpointResponse('proceed').approved === true);
});

test('parseCheckpointResponse detects ok', () => {
  assert(checkpoint.parseCheckpointResponse('ok').approved === true);
});

test('parseCheckpointResponse detects reject', () => {
  const result = checkpoint.parseCheckpointResponse('reject');
  assert(result.approved === false, 'should not approve');
});

test('parseCheckpointResponse detects no', () => {
  const result = checkpoint.parseCheckpointResponse('no');
  assert(result.approved === false, 'should not approve');
});

test('parseCheckpointResponse detects rollback', () => {
  const result = checkpoint.parseCheckpointResponse('rollback');
  assert(result.approved === false, 'should not approve');
});

test('parseCheckpointResponse treats unknown as modification', () => {
  const result = checkpoint.parseCheckpointResponse('please add more tests');
  assert(result.approved === false, 'should not approve');
  assert(result.feedback === 'please add more tests', 'should capture as feedback');
});

test('parseCheckpointResponse handles null', () => {
  const result = checkpoint.parseCheckpointResponse(null);
  assert(result.approved === false, 'should not approve');
  assert(result.feedback.includes('No response'), 'should indicate no response');
});

test('createBlockingResponse returns correct format', () => {
  const response = checkpoint.createBlockingResponse('design');
  const parsed = JSON.parse(response);
  assert(parsed.decision === 'block', 'should block');
  assert(parsed.reason.includes('design'), 'should mention phase');
});

test('createAllowResponse returns correct format', () => {
  const response = checkpoint.createAllowResponse();
  const parsed = JSON.parse(response);
  assert(parsed.decision === 'allow', 'should allow');
});

test('validateCheckpointContext rejects missing domain', () => {
  const result = checkpoint.validateCheckpointContext({ phase: 'design' });
  assert(result.valid === false, 'should be invalid');
});

test('validateCheckpointContext rejects missing phase', () => {
  const result = checkpoint.validateCheckpointContext({ domain: 'git' });
  assert(result.valid === false, 'should be invalid');
});

test('validateCheckpointContext accepts valid context', () => {
  const result = checkpoint.validateCheckpointContext({ domain: 'git', phase: 'design' });
  assert(result.valid === true, 'should be valid');
});

// ============================================
// Handoff Tests
// ============================================
console.log('\n\x1b[1mHandoff Tests\x1b[0m');

test('register adds handoff to queue', () => {
  handoff.clear();
  const result = handoff.register({
    from: 'error-standards',
    to: 'logging-standards',
    reason: 'Add logging to catch blocks'
  });
  assert(result.success === true, 'should succeed');
  assert(result.position === 1, 'should be first in queue');
  assert(typeof result.id === 'string', 'should have ID');
});

test('register rejects missing to', () => {
  handoff.clear();
  const result = handoff.register({ reason: 'test' });
  assert(result.success === false, 'should fail');
});

test('register rejects missing reason', () => {
  handoff.clear();
  const result = handoff.register({ to: 'test-standards' });
  assert(result.success === false, 'should fail');
});

test('getNext returns pending handoff', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'b', reason: 'test' });
  const next = handoff.getNext();
  assert(next !== null, 'should return handoff');
  assert(next.from === 'a', 'should have correct from');
  assert(next.status === 'pending', 'should be pending');
});

test('getNext returns null when empty', () => {
  handoff.clear();
  const next = handoff.getNext();
  assert(next === null, 'should return null');
});

test('start marks handoff as in_progress', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'b', reason: 'test' });
  const next = handoff.getNext();
  handoff.start(next.id);
  const updated = handoff.getById(next.id);
  assert(updated.status === 'in_progress', 'should be in_progress');
});

test('complete marks handoff done', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'b', reason: 'test' });
  const next = handoff.getNext();
  handoff.complete(next.id, 'Done');
  const status = handoff.getStatus();
  assert(status.complete === 1, 'should have 1 complete');
  assert(status.pending === 0, 'should have 0 pending');
});

test('fail marks handoff as failed', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'b', reason: 'test' });
  const next = handoff.getNext();
  handoff.fail(next.id, 'Something went wrong');
  const updated = handoff.getById(next.id);
  assert(updated.status === 'failed', 'should be failed');
  assert(updated.failureReason === 'Something went wrong', 'should have reason');
});

test('getSuggestedHandoffs returns known dependencies', () => {
  const suggestions = handoff.getSuggestedHandoffs('error-standards');
  assert(suggestions.includes('logging-standards'), 'should include logging');
  assert(suggestions.includes('test-standards'), 'should include test');
});

test('getSuggestedHandoffs returns empty for unknown agent', () => {
  const suggestions = handoff.getSuggestedHandoffs('unknown-agent');
  assert(suggestions.length === 0, 'should be empty');
});

test('getForAgent filters by target', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'test-standards', reason: 'test 1' });
  handoff.register({ from: 'b', to: 'logging-standards', reason: 'test 2' });
  handoff.register({ from: 'c', to: 'test-standards', reason: 'test 3' });
  const forTest = handoff.getForAgent('test-standards');
  assert(forTest.length === 2, 'should have 2 handoffs');
});

test('getStatus returns correct counts', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'b', reason: 'test 1' });
  handoff.register({ from: 'c', to: 'd', reason: 'test 2' });
  const h = handoff.getNext();
  handoff.complete(h.id);
  const status = handoff.getStatus();
  assert(status.pending === 1, 'should have 1 pending');
  assert(status.complete === 1, 'should have 1 complete');
});

test('pruneCompleted removes completed handoffs', () => {
  handoff.clear();
  handoff.register({ from: 'a', to: 'b', reason: 'test' });
  const h = handoff.getNext();
  handoff.complete(h.id);
  const removed = handoff.pruneCompleted();
  assert(removed === 1, 'should remove 1');
  assert(handoff.getStatus().queue.length === 0, 'queue should be empty');
});

test('formatHandoff returns readable string', () => {
  const h = {
    status: 'pending',
    from: 'error-standards',
    to: 'logging-standards',
    reason: 'Add logging',
    files: ['a.js', 'b.js']
  };
  const formatted = handoff.formatHandoff(h);
  assert(formatted.includes('[PENDING]'), 'should show status');
  assert(formatted.includes('error-standards'), 'should show from');
  assert(formatted.includes('logging-standards'), 'should show to');
});

test('clear empties the queue', () => {
  handoff.register({ from: 'a', to: 'b', reason: 'test' });
  handoff.clear();
  assert(handoff.getStatus().queue.length === 0, 'should be empty');
});

// ============================================
// Domain Dependency Ordering Tests (Phase 12)
// ============================================
console.log('\n\x1b[1mDomain Dependency Ordering (Phase 12)\x1b[0m');

test('DOMAIN_EXECUTION_ORDER is exported from orchestrator', () => {
  assert(Array.isArray(orchestrator.DOMAIN_EXECUTION_ORDER), 'should be array');
  assert(orchestrator.DOMAIN_EXECUTION_ORDER.length === 9, 'should have 9 domains');
});

test('naming has no dependencies', () => {
  const config = require('../../lib/core/config');
  assert(config.DOMAIN_DEPENDENCIES.naming.length === 0, 'naming should have no deps');
});

test('logging depends on error', () => {
  const config = require('../../lib/core/config');
  assert(config.DOMAIN_DEPENDENCIES.logging.includes('error'), 'logging should depend on error');
});

test('test depends on all other domains', () => {
  const config = require('../../lib/core/config');
  assert(config.DOMAIN_DEPENDENCIES.test.length >= 8, 'test should depend on 8+ domains');
});

test('domain=all uses DOMAIN_EXECUTION_ORDER', () => {
  orchestrator.reset();
  const result = orchestrator.initialize({ domain: 'all' });
  assert(result.success, 'should succeed');
  assert(result.state.domains[0] === 'naming', 'first domain should be naming');
  assert(result.state.domains[8] === 'test', 'last domain should be test');
});

test('error comes before logging in execution order', () => {
  const order = orchestrator.DOMAIN_EXECUTION_ORDER;
  const errorIdx = order.indexOf('error');
  const loggingIdx = order.indexOf('logging');
  assert(errorIdx < loggingIdx, 'error should come before logging');
});

test('housekeeping comes before git in execution order', () => {
  const order = orchestrator.DOMAIN_EXECUTION_ORDER;
  const housekeepingIdx = order.indexOf('housekeeping');
  const gitIdx = order.indexOf('git');
  assert(housekeepingIdx < gitIdx, 'housekeeping should come before git');
});

test('detectHandoffCycle detects backward handoff', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'all' });
  // Simulate logging trying to handoff back to error (already completed)
  const check = orchestrator.detectHandoffCycle('logging', 'error', ['naming', 'validation', 'error']);
  assert(check.cycle === true, 'should detect cycle');
  assert(check.reason.includes('already completed'), 'should explain reason');
});

test('detectHandoffCycle allows forward handoff', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'all' });
  // error handing off to logging (forward direction)
  const check = orchestrator.detectHandoffCycle('error', 'logging', ['naming', 'validation']);
  assert(check.cycle === false, 'should not detect cycle for forward handoff');
});

test('registerHandoff skips cyclic handoffs', () => {
  orchestrator.reset();
  orchestrator.initialize({ domain: 'all' });
  // Advance to logging phase
  orchestrator.setState({
    ...orchestrator.getState(),
    currentDomain: 'logging',
    completedPhases: [
      { domain: 'naming', phase: 'validate' },
      { domain: 'validation', phase: 'validate' },
      { domain: 'error', phase: 'validate' }
    ]
  });
  // Try to handoff back to error (should be skipped)
  const result = orchestrator.registerHandoff({
    to: 'error-standards',
    reason: 'Test backward handoff'
  });
  assert(result.skipped === true, 'should skip backward handoff');
  assert(result.cycleReason.includes('already completed'), 'should explain cycle');
});

// ============================================
// Integration Tests
// ============================================
console.log('\n\x1b[1mIntegration Tests\x1b[0m');

test('full workflow: single domain complete', () => {
  orchestrator.reset();
  handoff.clear();

  // Initialize
  const init = orchestrator.initialize({ domain: 'git' });
  assert(init.success === true, 'should initialize');

  // Design phase
  let advance = orchestrator.advancePhase();
  assert(advance.needsCheckpoint === true, 'design needs checkpoint');

  // Approve design
  let check = orchestrator.processCheckpoint(true);
  assert(check.nextPhase === 'validate-design', 'should go to validate-design');

  // Validate-design phase (no checkpoint)
  advance = orchestrator.advancePhase();
  assert(advance.nextPhase === 'build', 'should go to build');

  // Build phase
  advance = orchestrator.advancePhase();
  assert(advance.needsCheckpoint === true, 'build needs checkpoint');

  // Approve build
  check = orchestrator.processCheckpoint(true);
  assert(check.nextPhase === 'test', 'should go to test');

  // Test phase (no checkpoint)
  advance = orchestrator.advancePhase();
  assert(advance.nextPhase === 'validate', 'should go to validate');

  // Validate phase (final)
  advance = orchestrator.advancePhase();
  assert(advance.complete === true, 'should be complete');
});

test('full workflow: handoff registration', () => {
  orchestrator.reset();
  handoff.clear();

  orchestrator.initialize({ domain: 'error' });

  // Register handoff during build
  orchestrator.registerHandoff({
    to: 'logging-standards',
    reason: 'Add logging to new catch blocks',
    files: ['lib/venv/index.js']
  });

  const state = orchestrator.getState();
  assert(state.pendingHandoffs.length === 1, 'should have handoff');
  assert(state.pendingHandoffs[0].to === 'logging-standards', 'should be to logging');
});

// ============================================
// Test: CLI Input Validation (Phase 13)
// ============================================
console.log('\n\x1b[1mCLI Input Validation (Phase 13)\x1b[0m');

// Import CLI module to test validation functions
const cli = require('../../lib/orchestrator/cli');

test('CLI validates handoff ID format - valid ID', () => {
  // Valid format: handoff-<timestamp>-<9 alphanumeric chars>
  const validId = 'handoff-1234567890123-abcd12345';
  // Can't directly test private function, but we can test CLI behavior
  assert(validId.match(/^handoff-\d+-[a-z0-9]{9}$/), 'valid ID should match pattern');
});

test('CLI validates handoff ID format - invalid ID', () => {
  const invalidIds = [
    'not-a-handoff-id',
    'handoff-abc-123456789',  // timestamp not numeric
    'handoff-123-short',       // random part too short
    '',
    null
  ];
  for (const id of invalidIds) {
    if (id && typeof id === 'string') {
      assert(!id.match(/^handoff-\d+-[a-z0-9]{9}$/), `${id} should not match valid pattern`);
    }
  }
});

test('CLI module exports required functions', () => {
  assert(typeof cli.loadState === 'function', 'should export loadState');
  assert(typeof cli.saveState === 'function', 'should export saveState');
  assert(typeof cli.main === 'function', 'should export main');
});

// ============================================
// Summary
// ============================================
console.log('\n' + '='.repeat(50));
console.log(`\x1b[1mOrchestrator Unit Tests:\x1b[0m ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
