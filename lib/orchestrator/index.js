/**
 * Agent Orchestrator Runtime
 *
 * Executes agent workflows with phase sequencing, checkpoints, and handoffs.
 * This is the execution engine that makes agents actionable rather than
 * just documentation.
 *
 * @module lib/orchestrator
 */

'use strict';

const { DOMAIN_EXECUTION_ORDER } = require('../core/config');

/**
 * Workflow phases in execution order
 * @type {string[]}
 */
const PHASES = ['design', 'validate-design', 'build', 'test', 'validate'];

/**
 * Available domains and their agent mappings
 * @type {Object<string, string>}
 */
const DOMAINS = {
  logging: 'logging-standards',
  error: 'error-standards',
  type: 'type-standards',
  lint: 'lint-standards',
  test: 'test-standards',
  validation: 'validation-standards',
  git: 'git-standards',
  housekeeping: 'housekeeping-standards',
  naming: 'naming-standards'
};

/**
 * Orchestrator state
 * @type {Object}
 */
let state = {
  domains: [],
  currentDomain: null,
  currentPhase: null,
  completedPhases: [],
  pendingHandoffs: [],
  checkpointStatus: 'none', // none, pending, approved, rejected
  history: []
};

/**
 * Initialize orchestrator for a domain
 *
 * @param {Object} params - Parsed parameters
 * @param {string} params.domain - Domain to orchestrate (or 'all')
 * @param {string} [params.phase] - Specific phase to run (optional)
 * @returns {{success: boolean, error?: string, state?: Object}}
 *
 * @example
 * const result = initialize({ domain: 'git' });
 * if (result.success) {
 *   console.log(`Starting ${result.state.currentDomain} at ${result.state.currentPhase}`);
 * }
 */
function initialize(params) {
  const { domain, phase } = params;

  if (domain === 'all') {
    // Use dependency-sorted order instead of arbitrary Object.keys() order
    state.domains = [...DOMAIN_EXECUTION_ORDER];
  } else if (DOMAINS[domain]) {
    state.domains = [domain];
  } else {
    return {
      success: false,
      error: `Unknown domain: ${domain}. Valid domains: ${Object.keys(DOMAINS).join(', ')}, all`
    };
  }

  if (phase && !PHASES.includes(phase)) {
    return {
      success: false,
      error: `Unknown phase: ${phase}. Valid phases: ${PHASES.join(', ')}`
    };
  }

  state.currentDomain = state.domains[0];
  state.currentPhase = phase || PHASES[0];
  state.completedPhases = [];
  state.pendingHandoffs = [];
  state.checkpointStatus = 'none';
  state.history = [];

  state.history.push({
    type: 'init',
    domain: state.currentDomain,
    phase: state.currentPhase,
    timestamp: new Date().toISOString()
  });

  return { success: true, state: getState() };
}

/**
 * Get the agent prompt for current domain/phase
 *
 * @returns {string} Agent context prompt in @agent phase=X format
 *
 * @example
 * const prompt = getAgentPrompt();
 * // Returns: '@git-standards phase=design'
 */
function getAgentPrompt() {
  if (!state.currentDomain) {
    return '';
  }
  const agentName = DOMAINS[state.currentDomain];
  return `@${agentName} phase=${state.currentPhase}`;
}

/**
 * Advance to next phase, requesting checkpoint if needed
 *
 * @returns {{success: boolean, needsCheckpoint?: boolean, checkpointPhase?: string, nextPhase?: string, newDomain?: string, complete?: boolean}}
 *
 * @example
 * const result = advancePhase();
 * if (result.needsCheckpoint) {
 *   // Wait for user approval before continuing
 * } else if (result.complete) {
 *   // All phases and domains complete
 * }
 */
function advancePhase() {
  if (!state.currentDomain || !state.currentPhase) {
    return { success: false, error: 'Orchestrator not initialized' };
  }

  const currentIndex = PHASES.indexOf(state.currentPhase);

  // Record completion
  state.completedPhases.push({
    domain: state.currentDomain,
    phase: state.currentPhase,
    timestamp: new Date().toISOString()
  });

  // Check if we need a checkpoint before advancing
  // Checkpoints required after design and build phases
  if (state.currentPhase === 'design' || state.currentPhase === 'build') {
    state.checkpointStatus = 'pending';
    state.history.push({
      type: 'checkpoint_requested',
      domain: state.currentDomain,
      phase: state.currentPhase,
      timestamp: new Date().toISOString()
    });
    return {
      success: true,
      needsCheckpoint: true,
      checkpointPhase: state.currentPhase
    };
  }

  // Advance to next phase
  if (currentIndex < PHASES.length - 1) {
    state.currentPhase = PHASES[currentIndex + 1];
    state.history.push({
      type: 'phase_advance',
      domain: state.currentDomain,
      phase: state.currentPhase,
      timestamp: new Date().toISOString()
    });
    return { success: true, needsCheckpoint: false, nextPhase: state.currentPhase };
  }

  // Domain complete, move to next domain
  const domainIndex = state.domains.indexOf(state.currentDomain);
  if (domainIndex < state.domains.length - 1) {
    state.currentDomain = state.domains[domainIndex + 1];
    state.currentPhase = PHASES[0];
    state.history.push({
      type: 'domain_advance',
      domain: state.currentDomain,
      phase: state.currentPhase,
      timestamp: new Date().toISOString()
    });
    return {
      success: true,
      needsCheckpoint: false,
      nextPhase: state.currentPhase,
      newDomain: state.currentDomain
    };
  }

  // All complete
  state.history.push({
    type: 'complete',
    timestamp: new Date().toISOString()
  });
  return { success: true, complete: true };
}

/**
 * Process checkpoint approval/rejection
 *
 * @param {boolean} approved - Whether user approved
 * @param {string} [feedback] - User feedback if rejected or modification requested
 * @returns {{success: boolean, error?: string, rejected?: boolean, feedback?: string, nextPhase?: string, state?: Object}}
 *
 * @example
 * // User approves
 * const result = processCheckpoint(true);
 *
 * // User rejects with feedback
 * const result = processCheckpoint(false, 'Need more error handling');
 */
function processCheckpoint(approved, feedback) {
  if (state.checkpointStatus !== 'pending') {
    return { success: false, error: 'No pending checkpoint' };
  }

  state.checkpointStatus = approved ? 'approved' : 'rejected';
  state.history.push({
    type: 'checkpoint_response',
    phase: state.currentPhase,
    domain: state.currentDomain,
    approved,
    feedback: feedback || null,
    timestamp: new Date().toISOString()
  });

  if (approved) {
    // Clear checkpoint status
    state.checkpointStatus = 'none';

    // Advance to next phase
    const currentIndex = PHASES.indexOf(state.currentPhase);
    if (currentIndex < PHASES.length - 1) {
      state.currentPhase = PHASES[currentIndex + 1];
      return {
        success: true,
        nextPhase: state.currentPhase,
        state: getState()
      };
    }

    // Check for next domain
    const domainIndex = state.domains.indexOf(state.currentDomain);
    if (domainIndex < state.domains.length - 1) {
      state.currentDomain = state.domains[domainIndex + 1];
      state.currentPhase = PHASES[0];
      return {
        success: true,
        nextPhase: state.currentPhase,
        newDomain: state.currentDomain,
        state: getState()
      };
    }

    return { success: true, complete: true, state: getState() };
  }

  return {
    success: true,
    rejected: true,
    feedback,
    state: getState()
  };
}

/**
 * Detect if a handoff would create a cycle based on domain dependencies
 *
 * A cycle occurs when the target domain would eventually hand back to
 * a domain that's already in the current execution chain.
 *
 * @param {string} fromDomain - Source domain (e.g., 'error')
 * @param {string} toDomain - Target domain (e.g., 'logging')
 * @param {string[]} completedDomains - Domains already completed in this run
 * @returns {{cycle: boolean, reason?: string}}
 *
 * @example
 * const check = detectHandoffCycle('error', 'logging', ['naming', 'validation']);
 * if (check.cycle) {
 *   console.warn(check.reason);
 * }
 */
function detectHandoffCycle(fromDomain, toDomain, completedDomains = []) {
  // If target domain already completed, it's a backward handoff (potential cycle)
  if (completedDomains.includes(toDomain)) {
    return {
      cycle: true,
      reason: `${toDomain} already completed - backward handoff would create cycle`
    };
  }

  // Check if handoff would violate dependency order
  const fromIndex = DOMAIN_EXECUTION_ORDER.indexOf(fromDomain);
  const toIndex = DOMAIN_EXECUTION_ORDER.indexOf(toDomain);

  if (toIndex !== -1 && fromIndex !== -1 && toIndex < fromIndex) {
    // Handoff goes backward in execution order - potential cycle
    return {
      cycle: true,
      reason: `${toDomain} (index ${toIndex}) comes before ${fromDomain} (index ${fromIndex}) in execution order`
    };
  }

  return { cycle: false };
}

/**
 * Register a handoff request from current agent
 *
 * @param {Object} handoffRequest - Handoff details
 * @param {string} handoffRequest.to - Target agent
 * @param {string} handoffRequest.reason - Why handoff is needed
 * @param {string[]} [handoffRequest.files] - Affected files
 * @param {string} [handoffRequest.context] - Additional context
 * @returns {{success: boolean, id?: string, skipped?: boolean, cycleReason?: string}}
 *
 * @example
 * registerHandoff({
 *   to: 'logging-standards',
 *   reason: 'New catch blocks need logging',
 *   files: ['lib/venv/index.js']
 * });
 */
function registerHandoff(handoffRequest) {
  // Extract domain from agent name (e.g., 'logging-standards' → 'logging')
  const toDomain = handoffRequest.to.replace('-standards', '');

  // Get list of completed domains
  const completedDomains = [...new Set(state.completedPhases.map(p => p.domain))];

  // Check for cycle
  const cycleCheck = detectHandoffCycle(state.currentDomain, toDomain, completedDomains);
  if (cycleCheck.cycle) {
    state.history.push({
      type: 'handoff_skipped',
      from: DOMAINS[state.currentDomain],
      to: handoffRequest.to,
      reason: cycleCheck.reason,
      timestamp: new Date().toISOString()
    });
    return {
      success: true,
      skipped: true,
      cycleReason: cycleCheck.reason
    };
  }

  const id = `handoff-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const entry = {
    id,
    from: DOMAINS[state.currentDomain],
    ...handoffRequest,
    status: 'pending',
    registeredAt: new Date().toISOString()
  };

  state.pendingHandoffs.push(entry);
  state.history.push({
    type: 'handoff_registered',
    id,
    from: entry.from,
    to: handoffRequest.to,
    timestamp: new Date().toISOString()
  });

  return { success: true, id };
}

/**
 * Get orchestrator state for inspection
 *
 * @returns {Object} Copy of current state
 */
function getState() {
  return {
    domains: [...state.domains],
    currentDomain: state.currentDomain,
    currentPhase: state.currentPhase,
    completedPhases: [...state.completedPhases],
    pendingHandoffs: [...state.pendingHandoffs],
    checkpointStatus: state.checkpointStatus,
    history: [...state.history]
  };
}

/**
 * Set orchestrator state (used for restoring from persistence)
 *
 * @param {Object} newState - State to restore
 * @returns {{success: boolean}}
 */
function setState(newState) {
  if (!newState || typeof newState !== 'object') {
    return { success: false, error: 'Invalid state object' };
  }

  state = {
    domains: newState.domains || [],
    currentDomain: newState.currentDomain || null,
    currentPhase: newState.currentPhase || null,
    completedPhases: newState.completedPhases || [],
    pendingHandoffs: newState.pendingHandoffs || [],
    checkpointStatus: newState.checkpointStatus || 'none',
    history: newState.history || []
  };

  return { success: true };
}

/**
 * Reset orchestrator state to initial values
 */
function reset() {
  state = {
    domains: [],
    currentDomain: null,
    currentPhase: null,
    completedPhases: [],
    pendingHandoffs: [],
    checkpointStatus: 'none',
    history: []
  };
}

/**
 * Get progress summary
 *
 * @returns {{totalPhases: number, completedCount: number, currentDomain: string, currentPhase: string, percentage: number}}
 */
function getProgress() {
  const totalPhases = state.domains.length * PHASES.length;
  const completedCount = state.completedPhases.length;
  const percentage = totalPhases > 0 ? Math.round((completedCount / totalPhases) * 100) : 0;

  return {
    totalPhases,
    completedCount,
    currentDomain: state.currentDomain,
    currentPhase: state.currentPhase,
    percentage
  };
}

module.exports = {
  PHASES,
  DOMAINS,
  DOMAIN_EXECUTION_ORDER,
  initialize,
  getAgentPrompt,
  advancePhase,
  processCheckpoint,
  registerHandoff,
  detectHandoffCycle,
  getState,
  setState,
  reset,
  getProgress
};
