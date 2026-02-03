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
const git = require('../git');

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
  history: [],
  changedFiles: [],

  // Git workflow tracking
  git: {
    enabled: false,                   // Whether git workflow is active
    mode: 'auto',                     // 'auto' | 'manual' | 'disabled'
    workflowBranch: null,             // Created branch name
    baseBranch: null,                 // Branch we branched from
    baseCommit: null,                 // Commit hash at workflow start
    phaseCommits: [],                 // [{domain, phase, hash, timestamp}]
    rollbackPoints: {},               // {phase: commitHash}
    prRequired: false,                // Whether PR is required
    platform: null,                   // 'github' | 'gitlab' | null
    finalizationMode: 'pr'            // 'pr' | 'merge' | 'manual'
  }
};

/**
 * Setup git workflow for orchestrator
 *
 * @param {string} domain - Primary domain being worked on
 * @param {string} [gitMode='auto'] - Git mode: 'auto', 'manual', or 'disabled'
 * @returns {{success: boolean, gitState?: Object, error?: string}}
 * @private
 */
function setupGitWorkflow(domain, gitMode = 'auto') {
  // Skip if disabled
  if (gitMode === 'disabled') {
    return {
      success: true,
      gitState: {
        enabled: false,
        mode: 'disabled',
        workflowBranch: null,
        baseBranch: null,
        baseCommit: null,
        phaseCommits: [],
        rollbackPoints: {},
        prRequired: false,
        platform: null,
        finalizationMode: 'manual'
      }
    };
  }

  // Check if we're in a git repo
  if (!git.isGitRepo()) {
    return {
      success: true,
      gitState: {
        enabled: false,
        mode: 'disabled',
        workflowBranch: null,
        baseBranch: null,
        baseCommit: null,
        phaseCommits: [],
        rollbackPoints: {},
        prRequired: false,
        platform: null,
        finalizationMode: 'manual'
      }
    };
  }

  // Check we're not on protected branch
  const currentBranch = git.getCurrentBranch();
  if (git.isProtectedBranch(currentBranch)) {
    return {
      success: false,
      error: `Cannot start orchestrator on protected branch (${currentBranch}). Create a feature branch first: git checkout -b feature/your-feature`
    };
  }

  // Check for uncommitted changes
  if (git.hasUncommittedChanges()) {
    return {
      success: false,
      error: 'Uncommitted changes detected. Please commit or stash before starting orchestrator: git stash push -m "pre-orchestrator"'
    };
  }

  // Detect PR requirements
  const prInfo = git.detectPRRequirements();

  // Create workflow branch
  const branchName = git.generateOrchestratorBranchName(domain);
  const createResult = git.createBranch(branchName);
  if (!createResult.success) {
    return { success: false, error: `Failed to create branch: ${createResult.error}` };
  }

  const baseCommit = git.getHeadCommit();

  return {
    success: true,
    gitState: {
      enabled: true,
      mode: gitMode,
      workflowBranch: branchName,
      baseBranch: currentBranch,
      baseCommit: baseCommit,
      phaseCommits: [],
      rollbackPoints: {},
      prRequired: prInfo.prRequired || false,
      platform: prInfo.platform || null,
      finalizationMode: prInfo.prRequired ? 'pr' : 'merge'
    }
  };
}

/**
 * Commit changes for the current phase
 *
 * @returns {{success: boolean, hash?: string, noChanges?: boolean, error?: string}}
 * @private
 */
function commitPhaseChanges() {
  if (!state.git.enabled || state.git.mode !== 'auto') {
    return { success: true, noChanges: true };
  }

  if (!git.hasUncommittedChanges()) {
    return {
      success: true,
      hash: git.getCurrentCommit(),
      noChanges: true
    };
  }

  const result = git.createPhaseCommit(
    state.currentDomain,
    state.currentPhase,
    ['.']  // Stage all changes
  );

  if (result.success) {
    state.git.phaseCommits.push({
      domain: state.currentDomain,
      phase: state.currentPhase,
      hash: result.hash,
      timestamp: new Date().toISOString()
    });
  }

  return result;
}

/**
 * Initialize orchestrator for a domain
 *
 * @param {Object} params - Parsed parameters
 * @param {string} params.domain - Domain to orchestrate (or 'all')
 * @param {string} [params.phase] - Specific phase to run (optional)
 * @param {string} [params.gitMode='auto'] - Git mode: 'auto', 'manual', 'disabled'
 * @returns {{success: boolean, error?: string, state?: Object}}
 *
 * @example
 * const result = initialize({ domain: 'git' });
 * if (result.success) {
 *   console.log(`Starting ${result.state.currentDomain} at ${result.state.currentPhase}`);
 * }
 */
function initialize(params) {
  const { domain, phase, gitMode = 'auto' } = params;

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

  // Setup git workflow
  const gitSetup = setupGitWorkflow(state.domains[0], gitMode);
  if (!gitSetup.success) {
    return { success: false, error: gitSetup.error };
  }

  state.currentDomain = state.domains[0];
  state.currentPhase = phase || PHASES[0];
  state.completedPhases = [];
  state.pendingHandoffs = [];
  state.checkpointStatus = 'none';
  state.history = [];
  state.changedFiles = [];
  state.git = gitSetup.gitState;

  state.history.push({
    type: 'init',
    domain: state.currentDomain,
    phase: state.currentPhase,
    gitBranch: state.git.workflowBranch,
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

  // Create phase commit if git enabled
  if (state.git.enabled && state.git.mode === 'auto') {
    const commitResult = commitPhaseChanges();
    if (!commitResult.success) {
      return { success: false, error: `Git commit failed: ${commitResult.error}` };
    }

    // Record rollback point at checkpoint phases
    if (state.currentPhase === 'design' || state.currentPhase === 'build') {
      state.git.rollbackPoints[state.currentPhase] = commitResult.hash || git.getCurrentCommit();
    }
  }

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
      rollbackPoint: state.git.rollbackPoints[state.currentPhase] || null,
      timestamp: new Date().toISOString()
    });
    return {
      success: true,
      needsCheckpoint: true,
      checkpointPhase: state.currentPhase,
      rollbackPoint: state.git.rollbackPoints[state.currentPhase] || null
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
    rollbackAvailable: state.git.enabled && Object.keys(state.git.rollbackPoints).length > 0,
    state: getState()
  };
}

/**
 * Rollback to a previous checkpoint
 *
 * @param {string} [toPhase] - Phase to rollback to (default: last checkpoint)
 * @returns {{success: boolean, rolledBack?: boolean, toPhase?: string, toCommit?: string, error?: string}}
 *
 * @example
 * // Rollback to last checkpoint
 * const result = rollback();
 *
 * // Rollback to specific phase
 * const result = rollback('design');
 */
function rollback(toPhase) {
  if (!state.git.enabled) {
    return { success: false, error: 'Git workflow not enabled' };
  }

  // Determine target phase
  const checkpointPhases = ['design', 'build'];
  let targetPhase = toPhase;

  if (!targetPhase) {
    // Find the most recent checkpoint
    for (let i = checkpointPhases.length - 1; i >= 0; i--) {
      if (state.git.rollbackPoints[checkpointPhases[i]]) {
        targetPhase = checkpointPhases[i];
        break;
      }
    }
  }

  if (!targetPhase) {
    return { success: false, error: 'No rollback points available' };
  }

  const targetCommit = state.git.rollbackPoints[targetPhase];
  if (!targetCommit) {
    return { success: false, error: `No rollback point for ${targetPhase}` };
  }

  // Stash any uncommitted changes first (safety)
  if (git.hasUncommittedChanges()) {
    git.stashChanges(`Pre-rollback stash for ${state.currentDomain}/${state.currentPhase}`);
  }

  // Perform the rollback
  const result = git.rollbackToCommit(targetCommit, 'hard');
  if (!result.success) {
    return { success: false, error: `Rollback failed: ${result.error}` };
  }

  // Update orchestrator state
  state.currentPhase = targetPhase;
  state.checkpointStatus = 'none';

  // Remove completed phases after the rollback point
  const targetPhaseIndex = PHASES.indexOf(targetPhase);
  state.completedPhases = state.completedPhases.filter(cp => {
    if (cp.domain !== state.currentDomain) return true;
    const cpIndex = PHASES.indexOf(cp.phase);
    return cpIndex < targetPhaseIndex;
  });

  // Remove phase commits after rollback
  const rollbackTimestamp = new Date().toISOString();
  state.git.phaseCommits = state.git.phaseCommits.filter(pc => {
    if (pc.domain !== state.currentDomain) return true;
    const pcIndex = PHASES.indexOf(pc.phase);
    return pcIndex < targetPhaseIndex;
  });

  // Clear rollback points after the target
  for (const phase of checkpointPhases) {
    const phaseIndex = PHASES.indexOf(phase);
    if (phaseIndex > targetPhaseIndex) {
      delete state.git.rollbackPoints[phase];
    }
  }

  state.history.push({
    type: 'rollback',
    toPhase: targetPhase,
    toCommit: targetCommit,
    timestamp: rollbackTimestamp
  });

  return {
    success: true,
    rolledBack: true,
    toPhase: targetPhase,
    toCommit: targetCommit,
    state: getState()
  };
}

/**
 * Finalize the orchestrator workflow (push branch, create PR)
 *
 * @param {Object} [options] - Finalization options
 * @param {string} [options.mode] - Override finalization mode ('pr', 'merge', 'manual')
 * @returns {{success: boolean, prUrl?: string, branch?: string, message?: string, error?: string}}
 *
 * @example
 * const result = finalize();
 * if (result.prUrl) {
 *   console.log(`PR created: ${result.prUrl}`);
 * }
 */
function finalize(options = {}) {
  if (!state.git.enabled) {
    return { success: true, message: 'Git workflow not enabled, nothing to finalize' };
  }

  // Commit any remaining changes
  if (git.hasUncommittedChanges()) {
    const commitResult = git.createPhaseCommit(
      state.currentDomain,
      'final',
      ['.']
    );
    if (!commitResult.success && !commitResult.noChanges) {
      return { success: false, error: `Final commit failed: ${commitResult.error}` };
    }
    if (commitResult.hash) {
      state.git.phaseCommits.push({
        domain: state.currentDomain,
        phase: 'final',
        hash: commitResult.hash,
        timestamp: new Date().toISOString()
      });
    }
  }

  // Push branch to remote
  const remote = git.getRemoteInfo();
  if (remote.exists) {
    const pushResult = git.pushBranch(state.git.workflowBranch);
    if (!pushResult.success) {
      return { success: false, error: `Failed to push: ${pushResult.error}` };
    }
  }

  // Determine finalization mode
  const mode = options.mode || state.git.finalizationMode;

  // Create PR if requested and GitHub CLI available
  if (mode === 'pr' && git.hasGitHubCLI()) {
    const prBody = generatePRBody();
    const prResult = git.createPullRequest({
      title: `feat(${state.domains.join(',')}): orchestrator workflow completion`,
      body: prBody,
      base: state.git.baseBranch
    });

    state.history.push({
      type: 'finalize',
      mode: 'pr',
      prUrl: prResult.prUrl,
      timestamp: new Date().toISOString()
    });

    return {
      success: prResult.success,
      prUrl: prResult.prUrl,
      branch: state.git.workflowBranch,
      error: prResult.error
    };
  }

  // Manual or merge mode - just report status
  state.history.push({
    type: 'finalize',
    mode: mode,
    branch: state.git.workflowBranch,
    timestamp: new Date().toISOString()
  });

  return {
    success: true,
    branch: state.git.workflowBranch,
    message: remote.exists
      ? `Branch ${state.git.workflowBranch} pushed. Create PR manually or merge locally.`
      : `Branch ${state.git.workflowBranch} ready. No remote configured.`
  };
}

/**
 * Generate PR body from orchestrator state
 *
 * @returns {string} PR body markdown
 * @private
 */
function generatePRBody() {
  let body = '## Orchestrator Workflow Summary\n\n';
  body += `**Domains**: ${state.domains.join(', ')}\n`;
  body += `**Phases completed**: ${state.completedPhases.length}\n`;
  body += `**Base branch**: ${state.git.baseBranch}\n\n`;

  if (state.git.phaseCommits.length > 0) {
    body += '### Phase Commits\n';
    state.git.phaseCommits.forEach(pc => {
      body += `- \`${pc.hash}\` ${pc.domain}/${pc.phase}\n`;
    });
    body += '\n';
  }

  if (state.changedFiles.length > 0) {
    body += '### Files Changed\n';
    state.changedFiles.slice(0, 20).forEach(f => {
      body += `- ${f}\n`;
    });
    if (state.changedFiles.length > 20) {
      body += `- ... and ${state.changedFiles.length - 20} more\n`;
    }
    body += '\n';
  }

  body += '---\n';
  body += 'Generated by dev-standards orchestrator\n';

  return body;
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
    history: [...state.history],
    changedFiles: [...state.changedFiles],
    git: state.git ? { ...state.git, phaseCommits: [...state.git.phaseCommits], rollbackPoints: { ...state.git.rollbackPoints } } : null
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
    history: newState.history || [],
    changedFiles: newState.changedFiles || [],
    git: newState.git || {
      enabled: false,
      mode: 'disabled',
      workflowBranch: null,
      baseBranch: null,
      baseCommit: null,
      phaseCommits: [],
      rollbackPoints: {},
      prRequired: false,
      platform: null,
      finalizationMode: 'manual'
    }
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
    history: [],
    changedFiles: [],
    git: {
      enabled: false,
      mode: 'disabled',
      workflowBranch: null,
      baseBranch: null,
      baseCommit: null,
      phaseCommits: [],
      rollbackPoints: {},
      prRequired: false,
      platform: null,
      finalizationMode: 'manual'
    }
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
  getProgress,

  // Git workflow functions
  rollback,
  finalize,
  commitPhaseChanges
};
