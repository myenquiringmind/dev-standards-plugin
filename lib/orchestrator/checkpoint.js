/**
 * Checkpoint Protocol for User Approval Gates
 *
 * Manages checkpoint state and generates approval prompts.
 * Checkpoints are user approval gates that pause execution
 * after design and build phases.
 *
 * @module lib/orchestrator/checkpoint
 */

'use strict';

/**
 * Generate checkpoint prompt for user approval
 *
 * @param {Object} context - Checkpoint context
 * @param {string} context.domain - Current domain
 * @param {string} context.phase - Completed phase
 * @param {Array<string>} [context.changes] - List of changes made
 * @param {Array<{to: string, reason: string}>} [context.handoffs] - Pending handoff requests
 * @returns {string} Formatted checkpoint prompt in markdown
 *
 * @example
 * const prompt = generateCheckpointPrompt({
 *   domain: 'git',
 *   phase: 'design',
 *   changes: ['Added commit validation', 'Created lib/git/index.js'],
 *   handoffs: [{ to: 'test-standards', reason: 'Add test coverage' }]
 * });
 */
function generateCheckpointPrompt(context) {
  const { domain, phase, changes = [], handoffs = [] } = context;

  let prompt = `## Checkpoint: ${phase} Complete\n\n`;
  prompt += `**Agent**: @${domain}-standards\n`;
  prompt += `**Phase**: ${phase}\n`;
  prompt += '**Status**: Awaiting user approval\n\n';

  if (changes.length > 0) {
    prompt += '### Changes Made\n';
    changes.forEach(change => {
      prompt += `- ${change}\n`;
    });
    prompt += '\n';
  }

  if (handoffs.length > 0) {
    prompt += '### Pending Handoffs\n';
    handoffs.forEach((h, i) => {
      prompt += `${i + 1}. \u2192 @${h.to}: ${h.reason}\n`;
    });
    prompt += '\n';
  }

  prompt += '### User Action Required\n';
  prompt += '- [ ] Approve and proceed\n';
  prompt += '- [ ] Request modifications\n';
  prompt += '- [ ] Reject and rollback\n';

  return prompt;
}

/**
 * Parse user checkpoint response
 *
 * @param {string} response - User response text
 * @returns {{approved: boolean, feedback?: string}}
 *
 * @example
 * parseCheckpointResponse('approve')
 * // { approved: true }
 *
 * @example
 * parseCheckpointResponse('please add more error handling')
 * // { approved: false, feedback: 'please add more error handling' }
 */
function parseCheckpointResponse(response) {
  if (!response || typeof response !== 'string') {
    return { approved: false, feedback: 'No response provided' };
  }

  const lower = response.toLowerCase().trim();

  // Check for approval indicators
  const approvalPatterns = [
    'approve',
    'approved',
    'proceed',
    'continue',
    'yes',
    'lgtm',
    'looks good',
    'ship it',
    'go ahead'
  ];

  for (const pattern of approvalPatterns) {
    if (lower.includes(pattern) || lower === pattern) {
      return { approved: true };
    }
  }

  // Single character approvals
  if (lower === 'ok' || lower === 'y') {
    return { approved: true };
  }

  // Check for rejection indicators
  const rejectionPatterns = [
    'reject',
    'rejected',
    'rollback',
    'cancel',
    'stop',
    'abort'
  ];

  for (const pattern of rejectionPatterns) {
    if (lower.includes(pattern)) {
      return { approved: false, feedback: response };
    }
  }

  // Single character rejections
  if (lower === 'no' || lower === 'n') {
    return { approved: false, feedback: response };
  }

  // Treat as modification request
  return { approved: false, feedback: response };
}

/**
 * Create JSON checkpoint message for hook integration
 *
 * @param {Object} context - Checkpoint context
 * @param {string} context.domain - Current domain
 * @param {string} context.phase - Current phase
 * @param {Array<string>} [context.changes] - Changes made
 * @param {Array<Object>} [context.handoffs] - Pending handoffs
 * @returns {string} JSON string for hook output
 *
 * @example
 * const msg = createCheckpointMessage({ domain: 'git', phase: 'design' });
 * // JSON with type, domain, phase, status, prompt
 */
function createCheckpointMessage(context) {
  return JSON.stringify({
    type: 'checkpoint',
    domain: context.domain,
    phase: context.phase,
    status: 'pending',
    changes: context.changes || [],
    handoffs: context.handoffs || [],
    prompt: generateCheckpointPrompt(context)
  }, null, 2);
}

/**
 * Create a blocking response for hooks when checkpoint is pending
 *
 * @param {string} phase - The phase awaiting approval
 * @returns {string} JSON string with block decision
 */
function createBlockingResponse(phase) {
  return JSON.stringify({
    decision: 'block',
    reason: `Checkpoint pending for ${phase} phase. Please approve or reject before making changes.`,
    checkpoint: phase
  });
}

/**
 * Create an allow response for hooks when no checkpoint is pending
 *
 * @returns {string} JSON string with allow decision
 */
function createAllowResponse() {
  return JSON.stringify({
    decision: 'allow'
  });
}

/**
 * Validate checkpoint context
 *
 * @param {Object} context - Context to validate
 * @returns {{valid: boolean, error?: string}}
 */
function validateCheckpointContext(context) {
  if (!context || typeof context !== 'object') {
    return { valid: false, error: 'Context object required' };
  }

  if (!context.domain || typeof context.domain !== 'string') {
    return { valid: false, error: 'Domain string required' };
  }

  if (!context.phase || typeof context.phase !== 'string') {
    return { valid: false, error: 'Phase string required' };
  }

  if (context.changes && !Array.isArray(context.changes)) {
    return { valid: false, error: 'Changes must be an array' };
  }

  if (context.handoffs && !Array.isArray(context.handoffs)) {
    return { valid: false, error: 'Handoffs must be an array' };
  }

  return { valid: true };
}

module.exports = {
  generateCheckpointPrompt,
  parseCheckpointResponse,
  createCheckpointMessage,
  createBlockingResponse,
  createAllowResponse,
  validateCheckpointContext
};
