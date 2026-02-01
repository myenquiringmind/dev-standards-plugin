/**
 * Handoff Tracker for Agent-to-Agent Delegation
 *
 * Tracks dependencies between agents and manages handoff queue.
 * Handoffs represent work that needs to be passed from one agent
 * to another (e.g., error-standards creating catch blocks that
 * need logging-standards to add proper logging).
 *
 * @module lib/orchestrator/handoff
 */

'use strict';

/**
 * Known handoff dependencies between agents.
 * Maps source agent to array of typical target agents.
 * @type {Object<string, string[]>}
 */
const HANDOFF_GRAPH = {
  'error-standards': ['logging-standards', 'test-standards'],
  'logging-standards': ['test-standards'],
  'type-standards': ['lint-standards', 'test-standards'],
  'validation-standards': ['error-standards', 'test-standards'],
  'housekeeping-standards': ['git-standards', 'test-standards'],
  'naming-standards': ['test-standards', 'type-standards'],
  'git-standards': ['test-standards'],
  'lint-standards': ['test-standards']
};

/**
 * Handoff queue
 * @type {Array<Object>}
 */
let queue = [];

/**
 * Register a handoff request
 *
 * @param {Object} handoff - Handoff details
 * @param {string} handoff.from - Source agent
 * @param {string} handoff.to - Target agent
 * @param {string} handoff.reason - Why handoff is needed
 * @param {string[]} [handoff.files] - Affected files
 * @param {string} [handoff.context] - Additional context
 * @returns {{success: boolean, id: string, position: number}}
 *
 * @example
 * register({
 *   from: 'error-standards',
 *   to: 'logging-standards',
 *   reason: 'New catch blocks require logging',
 *   files: ['lib/venv/index.js', 'lib/tools/index.js']
 * });
 */
function register(handoff) {
  if (!handoff || typeof handoff !== 'object') {
    return { success: false, error: 'Handoff object required' };
  }

  if (!handoff.to || typeof handoff.to !== 'string') {
    return { success: false, error: 'Target agent (to) required' };
  }

  if (!handoff.reason || typeof handoff.reason !== 'string') {
    return { success: false, error: 'Reason required' };
  }

  const id = `handoff-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const entry = {
    id,
    from: handoff.from || 'unknown',
    to: handoff.to,
    reason: handoff.reason,
    files: handoff.files || [],
    context: handoff.context || '',
    status: 'pending',
    registeredAt: new Date().toISOString()
  };

  queue.push(entry);
  return { success: true, id, position: queue.length };
}

/**
 * Get next pending handoff
 *
 * @returns {Object|null} Next handoff or null if queue is empty
 *
 * @example
 * const next = getNext();
 * if (next) {
 *   console.log(`Processing handoff to ${next.to}: ${next.reason}`);
 * }
 */
function getNext() {
  return queue.find(h => h.status === 'pending') || null;
}

/**
 * Get a specific handoff by ID
 *
 * @param {string} id - Handoff ID
 * @returns {Object|null} Handoff or null if not found
 */
function getById(id) {
  return queue.find(h => h.id === id) || null;
}

/**
 * Mark handoff as in progress
 *
 * @param {string} id - Handoff ID
 * @returns {{success: boolean, error?: string}}
 */
function start(id) {
  const handoff = queue.find(h => h.id === id);
  if (!handoff) {
    return { success: false, error: 'Handoff not found' };
  }
  if (handoff.status !== 'pending') {
    return { success: false, error: `Handoff is ${handoff.status}, not pending` };
  }
  handoff.status = 'in_progress';
  handoff.startedAt = new Date().toISOString();
  return { success: true };
}

/**
 * Mark handoff as complete
 *
 * @param {string} id - Handoff ID
 * @param {string} [summary] - Optional completion summary
 * @returns {{success: boolean, error?: string}}
 *
 * @example
 * complete(handoff.id, 'Added logging.error() to 3 catch blocks');
 */
function complete(id, summary) {
  const handoff = queue.find(h => h.id === id);
  if (!handoff) {
    return { success: false, error: 'Handoff not found' };
  }
  handoff.status = 'complete';
  handoff.completedAt = new Date().toISOString();
  if (summary) {
    handoff.summary = summary;
  }
  return { success: true };
}

/**
 * Mark handoff as failed
 *
 * @param {string} id - Handoff ID
 * @param {string} reason - Failure reason
 * @returns {{success: boolean, error?: string}}
 */
function fail(id, reason) {
  const handoff = queue.find(h => h.id === id);
  if (!handoff) {
    return { success: false, error: 'Handoff not found' };
  }
  handoff.status = 'failed';
  handoff.failedAt = new Date().toISOString();
  handoff.failureReason = reason;
  return { success: true };
}

/**
 * Get suggested handoffs for an agent based on known dependencies
 *
 * @param {string} fromAgent - Agent that just completed work
 * @returns {string[]} List of agents that typically need handoffs
 *
 * @example
 * getSuggestedHandoffs('error-standards')
 * // ['logging-standards', 'test-standards']
 */
function getSuggestedHandoffs(fromAgent) {
  return HANDOFF_GRAPH[fromAgent] || [];
}

/**
 * Get all handoffs for a specific target agent
 *
 * @param {string} targetAgent - Target agent name
 * @returns {Array<Object>} Handoffs for this agent
 */
function getForAgent(targetAgent) {
  return queue.filter(h => h.to === targetAgent);
}

/**
 * Get all pending handoffs for a specific target agent
 *
 * @param {string} targetAgent - Target agent name
 * @returns {Array<Object>} Pending handoffs for this agent
 */
function getPendingForAgent(targetAgent) {
  return queue.filter(h => h.to === targetAgent && h.status === 'pending');
}

/**
 * Get queue status
 *
 * @returns {{pending: number, inProgress: number, complete: number, failed: number, queue: Object[]}}
 *
 * @example
 * const status = getStatus();
 * console.log(`${status.pending} handoffs waiting, ${status.complete} done`);
 */
function getStatus() {
  return {
    pending: queue.filter(h => h.status === 'pending').length,
    inProgress: queue.filter(h => h.status === 'in_progress').length,
    complete: queue.filter(h => h.status === 'complete').length,
    failed: queue.filter(h => h.status === 'failed').length,
    queue: [...queue]
  };
}

/**
 * Get all pending handoffs
 *
 * @returns {Array<Object>} All pending handoffs
 */
function getAllPending() {
  return queue.filter(h => h.status === 'pending');
}

/**
 * Clear the handoff queue
 */
function clear() {
  queue = [];
}

/**
 * Remove completed handoffs from queue
 *
 * @returns {number} Number of handoffs removed
 */
function pruneCompleted() {
  const before = queue.length;
  queue = queue.filter(h => h.status !== 'complete');
  return before - queue.length;
}

/**
 * Format handoff for display
 *
 * @param {Object} handoff - Handoff to format
 * @returns {string} Formatted handoff string
 */
function formatHandoff(handoff) {
  let str = `[${handoff.status.toUpperCase()}] ${handoff.from} \u2192 ${handoff.to}\n`;
  str += `  Reason: ${handoff.reason}\n`;
  if (handoff.files && handoff.files.length > 0) {
    str += `  Files: ${handoff.files.join(', ')}\n`;
  }
  return str;
}

/**
 * Set queue state (for restoring from persistence)
 *
 * @param {Array<Object>} newQueue - Queue to restore
 * @returns {{success: boolean}}
 */
function setQueue(newQueue) {
  if (!Array.isArray(newQueue)) {
    return { success: false, error: 'Queue must be an array' };
  }
  queue = newQueue;
  return { success: true };
}

/**
 * Get raw queue (for persistence)
 *
 * @returns {Array<Object>} Copy of queue
 */
function getQueue() {
  return [...queue];
}

module.exports = {
  HANDOFF_GRAPH,
  register,
  getNext,
  getById,
  start,
  complete,
  fail,
  getSuggestedHandoffs,
  getForAgent,
  getPendingForAgent,
  getStatus,
  getAllPending,
  clear,
  pruneCompleted,
  formatHandoff,
  setQueue,
  getQueue
};
