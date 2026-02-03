#!/usr/bin/env node
/**
 * Orchestrator CLI
 *
 * Command-line interface for the orchestrator runtime.
 * Used by hooks and skills to invoke orchestrator functions.
 *
 * Usage:
 *   node lib/orchestrator/cli.js init domain=all
 *   node lib/orchestrator/cli.js status
 *   node lib/orchestrator/cli.js advance
 *   node lib/orchestrator/cli.js checkpoint approve
 *   node lib/orchestrator/cli.js checkpoint reject "feedback"
 *   node lib/orchestrator/cli.js prompt
 *   node lib/orchestrator/cli.js handoff register '{"to":"test-standards","reason":"..."}'
 *   node lib/orchestrator/cli.js handoff status
 *   node lib/orchestrator/cli.js reset
 *
 * @module lib/orchestrator/cli
 */

'use strict';

const fs = require('fs');
const path = require('path');
const orchestrator = require('./index');
const parser = require('./parser');
const handoff = require('./handoff');

/**
 * Validate handoff ID format
 * Expected format: handoff-<timestamp>-<alphanumeric>
 *
 * @param {string} id - Handoff ID to validate
 * @returns {{valid: boolean, error?: string}}
 */
function validateHandoffId(id) {
  if (!id || typeof id !== 'string') {
    return { valid: false, error: 'Handoff ID must be a non-empty string' };
  }

  // Format: handoff-<timestamp>-<9 char alphanumeric>
  const pattern = /^handoff-\d+-[a-z0-9]{9}$/;
  if (!pattern.test(id)) {
    return {
      valid: false,
      error: `Invalid handoff ID format: "${id}". Expected: handoff-<timestamp>-<alphanumeric>`
    };
  }

  return { valid: true };
}

/**
 * Validate handoff registration data structure
 *
 * @param {Object} data - Handoff data to validate
 * @returns {{valid: boolean, error?: string}}
 */
function validateHandoffData(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { valid: false, error: 'Handoff data must be a JSON object' };
  }

  if (!data.to || typeof data.to !== 'string') {
    return { valid: false, error: 'Missing required field: "to" (target agent)' };
  }

  if (!data.reason || typeof data.reason !== 'string') {
    return { valid: false, error: 'Missing required field: "reason"' };
  }

  // Validate target agent format (should end with -standards)
  if (!data.to.endsWith('-standards')) {
    return {
      valid: false,
      error: `Invalid target agent: "${data.to}". Must end with -standards`
    };
  }

  // Optional: validate files array if present
  if (data.files !== undefined) {
    if (!Array.isArray(data.files)) {
      return { valid: false, error: '"files" must be an array of file paths' };
    }
    for (const file of data.files) {
      if (typeof file !== 'string') {
        return { valid: false, error: 'All entries in "files" must be strings' };
      }
    }
  }

  // Optional: validate context if present
  if (data.context !== undefined && typeof data.context !== 'string') {
    return { valid: false, error: '"context" must be a string' };
  }

  return { valid: true };
}

/**
 * State file location - stored in project tmp directory
 */
const STATE_FILE = path.join(process.cwd(), 'tmp', '.orchestrator-state.json');

/**
 * Ensure tmp directory exists
 */
function ensureTmpDir() {
  const dir = path.dirname(STATE_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/**
 * Load state from file
 *
 * @returns {Object|null} Loaded state or null if not found
 */
function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      const data = fs.readFileSync(STATE_FILE, 'utf8');
      const parsed = JSON.parse(data);
      // Restore orchestrator state
      orchestrator.setState(parsed.orchestrator || {});
      // Restore handoff queue
      handoff.setQueue(parsed.handoffs || []);
      return parsed;
    }
  } catch (e) {
    console.error(JSON.stringify({ error: `Failed to load state: ${e.message}` }));
  }
  return null;
}

/**
 * Save state to file
 */
function saveState() {
  ensureTmpDir();
  const state = {
    orchestrator: orchestrator.getState(),
    handoffs: handoff.getQueue(),
    savedAt: new Date().toISOString()
  };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Output JSON result
 *
 * @param {Object} result - Result to output
 */
function output(result) {
  console.log(JSON.stringify(result, null, 2));
}

/**
 * Handle init command
 *
 * @param {string[]} args - Command arguments
 */
function handleInit(args) {
  const params = parser.parseArgs(args);
  const validation = parser.validateOrchestratorParams(params);

  if (!validation.valid) {
    output({ success: false, error: validation.error });
    process.exit(1);
  }

  const result = orchestrator.initialize(params);
  if (result.success) {
    handoff.clear(); // Clear any existing handoffs
    saveState();
  }
  output(result);
}

/**
 * Handle status command
 */
function handleStatus() {
  const loaded = loadState();
  if (!loaded) {
    output({ status: 'not_initialized', message: 'Orchestrator not initialized. Run: init domain=<domain>' });
    return;
  }

  const state = orchestrator.getState();
  const progress = orchestrator.getProgress();
  const handoffStatus = handoff.getStatus();

  output({
    status: 'active',
    ...state,
    progress,
    handoffs: handoffStatus
  });
}

/**
 * Handle advance command
 */
function handleAdvance() {
  const loaded = loadState();
  if (!loaded) {
    output({ success: false, error: 'Orchestrator not initialized' });
    process.exit(1);
  }

  const result = orchestrator.advancePhase();
  saveState();
  output(result);
}

/**
 * Handle checkpoint command
 *
 * @param {string[]} args - Command arguments [action, feedback?]
 */
function handleCheckpoint(args) {
  const action = args[0];
  const feedback = args.slice(1).join(' ');

  if (!action || !['approve', 'reject', 'status'].includes(action)) {
    output({
      success: false,
      error: 'Usage: checkpoint <approve|reject|status> [feedback]'
    });
    process.exit(1);
  }

  const loaded = loadState();
  if (!loaded) {
    output({ success: false, error: 'Orchestrator not initialized' });
    process.exit(1);
  }

  if (action === 'status') {
    const state = orchestrator.getState();
    output({
      checkpointStatus: state.checkpointStatus,
      currentPhase: state.currentPhase,
      currentDomain: state.currentDomain
    });
    return;
  }

  const result = orchestrator.processCheckpoint(action === 'approve', feedback || undefined);
  saveState();
  output(result);
}

/**
 * Handle prompt command
 */
function handlePrompt() {
  const loaded = loadState();
  if (!loaded) {
    output({ prompt: null, error: 'Not initialized' });
    return;
  }

  output({ prompt: orchestrator.getAgentPrompt() });
}

/**
 * Handle progress command
 */
function handleProgress() {
  const loaded = loadState();
  if (!loaded) {
    output({ error: 'Not initialized' });
    return;
  }

  output(orchestrator.getProgress());
}

/**
 * Handle handoff command
 *
 * @param {string[]} args - Command arguments
 */
function handleHandoff(args) {
  const subCommand = args[0];

  loadState(); // Load state for handoff context

  switch (subCommand) {
    case 'register': {
      const jsonStr = args.slice(1).join(' ');
      if (!jsonStr || !jsonStr.trim()) {
        output({ success: false, error: 'Handoff JSON data required' });
        process.exit(1);
      }
      let data;
      try {
        data = JSON.parse(jsonStr);
      } catch (e) {
        output({ success: false, error: `Invalid JSON syntax: ${e.message}` });
        process.exit(1);
      }
      // Validate handoff data structure
      const validation = validateHandoffData(data);
      if (!validation.valid) {
        output({ success: false, error: validation.error });
        process.exit(1);
      }
      const state = orchestrator.getState();
      data.from = data.from || (state.currentDomain ? `${state.currentDomain}-standards` : 'unknown');
      const result = handoff.register(data);
      saveState();
      output(result);
      break;
    }

    case 'next': {
      const next = handoff.getNext();
      output(next ? { success: true, handoff: next } : { success: true, handoff: null, message: 'No pending handoffs' });
      break;
    }

    case 'complete': {
      const id = args[1];
      const summary = args.slice(2).join(' ');
      const idValidation = validateHandoffId(id);
      if (!idValidation.valid) {
        output({ success: false, error: idValidation.error });
        process.exit(1);
      }
      const result = handoff.complete(id, summary || undefined);
      saveState();
      output(result);
      break;
    }

    case 'start': {
      const id = args[1];
      const idValidation = validateHandoffId(id);
      if (!idValidation.valid) {
        output({ success: false, error: idValidation.error });
        process.exit(1);
      }
      const result = handoff.start(id);
      saveState();
      output(result);
      break;
    }

    case 'fail': {
      const id = args[1];
      const reason = args.slice(2).join(' ');
      const idValidation = validateHandoffId(id);
      if (!idValidation.valid) {
        output({ success: false, error: idValidation.error });
        process.exit(1);
      }
      const result = handoff.fail(id, reason || 'No reason provided');
      saveState();
      output(result);
      break;
    }

    case 'status': {
      output(handoff.getStatus());
      break;
    }

    case 'suggest': {
      const agent = args[1];
      if (!agent) {
        output({ success: false, error: 'Agent name required' });
        process.exit(1);
      }
      const suggestions = handoff.getSuggestedHandoffs(agent);
      output({ agent, suggestions });
      break;
    }

    case 'clear': {
      handoff.clear();
      saveState();
      output({ success: true, message: 'Handoff queue cleared' });
      break;
    }

    default:
      output({
        success: false,
        error: 'Usage: handoff <register|next|complete|start|fail|status|suggest|clear> [args]'
      });
      process.exit(1);
  }
}

/**
 * Handle reset command
 */
function handleReset() {
  if (fs.existsSync(STATE_FILE)) {
    fs.unlinkSync(STATE_FILE);
  }
  orchestrator.reset();
  handoff.clear();
  output({ success: true, message: 'Orchestrator reset' });
}

/**
 * Handle git command
 *
 * @param {string[]} args - Command arguments
 */
function handleGit(args) {
  const subCommand = args[0];
  const loaded = loadState();

  switch (subCommand) {
    case 'status': {
      if (!loaded || !loaded.orchestrator?.git) {
        output({ git: { enabled: false }, message: 'Git workflow not active' });
        return;
      }
      const state = orchestrator.getState();
      const git = require('../git');
      output({
        git: state.git,
        currentBranch: git.getCurrentBranch(),
        uncommittedFiles: git.getUncommittedFiles(),
        hasChanges: git.hasUncommittedChanges()
      });
      break;
    }

    case 'commit': {
      if (!loaded) {
        output({ success: false, error: 'Orchestrator not initialized' });
        process.exit(1);
      }
      const result = orchestrator.commitPhaseChanges();
      saveState();
      output(result);
      break;
    }

    case 'enable': {
      if (!loaded) {
        output({ success: false, error: 'Orchestrator not initialized' });
        process.exit(1);
      }
      // Can't enable mid-session easily - would need branch creation
      output({
        success: false,
        error: 'Cannot enable git workflow mid-session. Re-initialize with: init domain=X gitMode=auto'
      });
      break;
    }

    case 'disable': {
      if (!loaded) {
        output({ success: false, error: 'Orchestrator not initialized' });
        process.exit(1);
      }
      const state = orchestrator.getState();
      if (state.git) {
        state.git.enabled = false;
        state.git.mode = 'disabled';
        orchestrator.setState(state);
        saveState();
        output({ success: true, message: 'Git workflow disabled' });
      } else {
        output({ success: true, message: 'Git workflow was not enabled' });
      }
      break;
    }

    default:
      output({
        error: 'Usage: git <status|commit|enable|disable>',
        subcommands: {
          status: 'Show git workflow state and uncommitted files',
          commit: 'Manually commit current phase changes',
          enable: 'Enable git workflow (requires re-init)',
          disable: 'Disable git workflow'
        }
      });
      process.exit(1);
  }
}

/**
 * Handle rollback command
 *
 * @param {string[]} args - Command arguments
 */
function handleRollback(args) {
  const loaded = loadState();
  if (!loaded) {
    output({ success: false, error: 'Orchestrator not initialized' });
    process.exit(1);
  }

  const toPhase = args[0]; // Optional phase to rollback to
  const result = orchestrator.rollback(toPhase);
  saveState();
  output(result);
}

/**
 * Handle finalize command
 *
 * @param {string[]} args - Command arguments
 */
function handleFinalize(args) {
  const loaded = loadState();
  if (!loaded) {
    output({ success: false, error: 'Orchestrator not initialized' });
    process.exit(1);
  }

  const params = parser.parseArgs(args);
  const result = orchestrator.finalize(params);
  saveState();
  output(result);
}

/**
 * Handle help command
 */
function handleHelp() {
  const help = `
Orchestrator CLI - Agent Workflow Execution Runtime

Commands:
  init <domain=X> [phase=Y] [gitMode=X]  Initialize orchestrator for a domain
  status                      Show current orchestrator state
  advance                     Advance to next phase
  checkpoint <action> [msg]   Handle checkpoint (approve/reject/status)
  prompt                      Get current agent prompt
  progress                    Show progress summary
  handoff <subcommand>        Manage handoffs
  git <subcommand>            Git workflow management
  rollback [phase]            Rollback to checkpoint (design or build)
  finalize [mode=X]           Finalize workflow (push branch, create PR)
  reset                       Reset orchestrator state
  help                        Show this help

Git Subcommands:
  status                      Show git workflow state and uncommitted files
  commit                      Manually commit current phase changes
  disable                     Disable git workflow

Git Modes (for init):
  auto                        Auto-create branch and commit at phases (default)
  manual                      Track state but don't auto-commit
  disabled                    No git workflow integration

Handoff Subcommands:
  register '{"to":"X","reason":"Y"}'  Register a handoff
  next                                Get next pending handoff
  start <id>                          Mark handoff as in progress
  complete <id> [summary]             Mark handoff as complete
  fail <id> <reason>                  Mark handoff as failed
  status                              Show handoff queue status
  suggest <agent>                     Get suggested handoffs for agent
  clear                               Clear handoff queue

Examples:
  node cli.js init domain=git
  node cli.js init domain=all phase=design gitMode=auto
  node cli.js advance
  node cli.js checkpoint approve
  node cli.js checkpoint reject "Need more tests"
  node cli.js git status
  node cli.js rollback design
  node cli.js finalize
  node cli.js handoff register '{"to":"test-standards","reason":"Add tests"}'
`;
  console.log(help);
}

/**
 * Main CLI handler
 */
function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command) {
    handleHelp();
    return;
  }

  switch (command) {
    case 'init':
      handleInit(args.slice(1));
      break;

    case 'status':
      handleStatus();
      break;

    case 'advance':
      handleAdvance();
      break;

    case 'checkpoint':
      handleCheckpoint(args.slice(1));
      break;

    case 'prompt':
      handlePrompt();
      break;

    case 'progress':
      handleProgress();
      break;

    case 'handoff':
      handleHandoff(args.slice(1));
      break;

    case 'git':
      handleGit(args.slice(1));
      break;

    case 'rollback':
      handleRollback(args.slice(1));
      break;

    case 'finalize':
      handleFinalize(args.slice(1));
      break;

    case 'reset':
      handleReset();
      break;

    case 'help':
    case '--help':
    case '-h':
      handleHelp();
      break;

    default:
      output({
        error: `Unknown command: ${command}`,
        usage: 'Commands: init, status, advance, checkpoint, prompt, progress, handoff, git, rollback, finalize, reset, help'
      });
      process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}

module.exports = {
  loadState,
  saveState,
  main
};
