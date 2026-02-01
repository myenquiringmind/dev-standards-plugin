#!/usr/bin/env node
/**
 * Hook Runner - Unified entry point for all plugin hooks
 *
 * This follows SOLID principles:
 * - Single Responsibility: Each hook action is a separate function
 * - Open/Closed: New hooks can be added without modifying existing code
 * - Dependency Inversion: Uses the shared utils module
 *
 * Usage: node hook-runner.js <action> [args...]
 *
 * Actions:
 *   log <event> [details]     - Log to session.log
 *   session-start             - SessionStart hook
 *   check-branch              - Check if on protected branch (blocks if true)
 *   check-command             - Check if command is dangerous (reads from stdin)
 *   format <file>             - Format a file
 *   typecheck <file>          - Type check a file
 *   lint <file>               - Lint a file
 *   post-edit                 - Full post-edit pipeline (reads file from stdin JSON)
 */

const fs = require('fs');
const path = require('path');

// Try to load logging module, fall back to console
let logging;
try {
  logging = require('./logging');
} catch {
  // Fallback to console-based logging for standalone use
  logging = {
    debug: (...args) => { if (process.env.DEBUG === 'true') console.error('[DEBUG]', ...args); },
    info: (...args) => console.error('[dev-standards]', ...args),
    warn: (...args) => console.error('[dev-standards] WARNING:', ...args),
    error: (...args) => console.error('[dev-standards] ERROR:', ...args)
  };
}

// Try to load utils from plugin lib, fall back to inline implementation
let utils;
try {
  // When installed as plugin, utils is in same directory
  utils = require('./utils');
} catch {
  // Fallback inline implementation for standalone use
  utils = createInlineUtils();
}

function createInlineUtils() {
  const os = require('os');
  const { execSync } = require('child_process');

  return {
    getLogDir: () => path.join(os.homedir(), '.claude', 'logs'),
    getLogFile: function() { return path.join(this.getLogDir(), 'session.log'); },
    ensureLogDir: function() {
      try { fs.mkdirSync(this.getLogDir(), { recursive: true }); } catch { /* Directory may already exist - ignore */ }
    },
    log: function(event, details = '') {
      this.ensureLogDir();
      const entry = `[${new Date().toISOString()}] ${event}${details ? ' ' + details : ''}\n`;
      try { fs.appendFileSync(this.getLogFile(), entry); } catch { /* Log file write failure - silent fallback */ }
    },
    getGitStatus: () => {
      try {
        return execSync('git status --short', { encoding: 'utf8', timeout: 3000 }).trim() || 'Working tree clean';
      } catch { return 'Not a git repo'; }
    },
    getCurrentBranch: () => {
      try {
        return execSync('git branch --show-current', { encoding: 'utf8', timeout: 3000 }).trim();
      } catch { return null; }
    },
    isProtectedBranch: function(branch) {
      return ['main', 'master', 'production'].includes(branch || this.getCurrentBranch());
    },
    isDangerousCommand: (cmd) => {
      const patterns = [
        /rm\s+-rf\s+\/(?!tmp)/, /rm\s+-rf\s+~/, /rm\s+-rf\s+\*/,
        /DROP\s+(DATABASE|TABLE)/i, /TRUNCATE\s+TABLE/i,
        /curl.*\|\s*(bash|sh)/, /wget.*\|\s*(bash|sh)/,
        /format\s+[cdefgh]:/i
      ];
      return patterns.some(p => p.test(cmd));
    },
    getExt: (f) => path.extname(f).slice(1).toLowerCase(),
    findVenv: (dir) => {
      for (const n of ['.venv', 'venv', '.uv']) {
        const py = path.join(dir, n, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
        if (fs.existsSync(py)) return path.join(dir, n);
      }
      return null;
    },
    formatFile: () => ({ success: true }),
    typeCheckFile: () => null,
    lintFile: () => null
  };
}

// ============================================
// Hook Actions
// ============================================

const actions = {
  /**
   * Log an event to session.log
   */
  log: (args) => {
    const [event, ...details] = args;
    utils.log(event, details.join(' '));
  },

  /**
   * SessionStart hook - show context and log
   */
  'session-start': () => {
    const cwd = process.cwd();
    utils.log('SESSION_START', `in ${cwd}`);
    logging.debug('Session starting in:', cwd);

    // Use console.log for output that goes to stdout (for Claude to see)
    console.log('--- Project Context ---');
    console.log(utils.getGitStatus());
    console.log('---');

    // Show TODO.md or TASKS.md if exists
    for (const name of ['TODO.md', 'TASKS.md']) {
      const filePath = path.join(cwd, name);
      if (fs.existsSync(filePath)) {
        try {
          const content = fs.readFileSync(filePath, 'utf8');
          console.log(content.split('\n').slice(0, 20).join('\n'));
          logging.debug('Displayed', name);
        } catch {
          logging.debug('Failed to read', name);
        }
        break;
      }
    }
  },

  /**
   * Check if on protected branch - outputs block JSON if true
   */
  'check-branch': () => {
    const branch = utils.getCurrentBranch();
    logging.debug('Checking branch protection for:', branch);
    if (utils.isProtectedBranch(branch)) {
      logging.warn('Blocked edit on protected branch:', branch);
      console.log(JSON.stringify({
        decision: 'block',
        reason: `Cannot edit directly on protected branch (${branch}). Create a feature branch first: git checkout -b feature/your-feature`
      }));
      process.exit(0);
    }
    // Pass through stdin to stdout
    passThrough();
  },

  /**
   * Check if command is dangerous - reads from stdin
   */
  'check-command': () => {
    readStdin((data) => {
      try {
        const input = JSON.parse(data);
        const cmd = input?.tool_input?.command || '';
        logging.debug('Checking command:', cmd.substring(0, 50));

        if (cmd && utils.isDangerousCommand(cmd)) {
          logging.warn('Blocked dangerous command:', cmd.substring(0, 50));
          console.log(JSON.stringify({
            decision: 'block',
            reason: `Potentially destructive command blocked: ${cmd.substring(0, 50)}`
          }));
          return;
        }
      } catch {
        logging.debug('JSON parse error in check-command, passing through');
      }
      console.log(data);
    });
  },

  /**
   * Format a single file
   */
  format: (args) => {
    const [filePath] = args;
    if (!filePath || !fs.existsSync(filePath)) {
      logging.error('File not found:', filePath);
      process.exit(1);
    }
    logging.debug('Formatting file:', filePath);
    const result = utils.formatFile(filePath);
    if (result && !result.success) {
      logging.error('[Format]', result.error);
    }
  },

  /**
   * Type check a single file
   */
  typecheck: (args) => {
    const [filePath] = args;
    if (!filePath) {
      logging.error('File path required');
      process.exit(1);
    }
    logging.debug('Type checking file:', filePath);
    const result = utils.typeCheckFile(filePath);
    if (result && !result.success) {
      logging.error('[Type Check]', result.error);
      process.exit(1);
    }
  },

  /**
   * Lint a single file
   */
  lint: (args) => {
    const [filePath] = args;
    if (!filePath) {
      logging.error('File path required');
      process.exit(1);
    }
    logging.debug('Linting file:', filePath);
    const result = utils.lintFile(filePath);
    if (result && !result.success) {
      logging.warn('[Lint]', result.warning);
    }
  },

  /**
   * Full post-edit pipeline - format, typecheck, lint
   * Reads file path from stdin JSON
   */
  'post-edit': (args) => {
    const [action] = args; // 'format', 'typecheck', or 'lint'
    logging.debug('Post-edit action:', action);

    readStdin((data) => {
      try {
        const input = JSON.parse(data);
        const filePath = input?.tool_input?.file_path || input?.tool_input?.files?.[0]?.file_path;

        if (!filePath || typeof filePath !== 'string') {
          logging.debug('No file path in input, passing through');
          console.log(data);
          return;
        }

        const resolved = path.resolve(filePath);
        if (!fs.existsSync(resolved)) {
          logging.debug('File does not exist:', resolved);
          console.log(data);
          return;
        }

        logging.debug('Processing post-edit for:', resolved);
        if (action === 'format') {
          utils.formatFile(resolved);
        } else if (action === 'typecheck') {
          const result = utils.typeCheckFile(resolved);
          if (result && !result.success) {
            logging.error('[Type Check]', result.error);
          }
        } else if (action === 'lint') {
          const result = utils.lintFile(resolved);
          if (result && !result.success) {
            logging.warn('[Lint]', result.warning);
          }
        }

        console.log(data);
      } catch {
        logging.debug('Post-edit parse error, passing through');
        console.log(data || '');
      }
    });
  }
};

// ============================================
// Helpers
// ============================================

/**
 * Read all data from stdin and call callback with the result
 *
 * @param {function(string): void} callback - Function to call with stdin data
 *
 * @example
 * readStdin((data) => {
 *   const parsed = JSON.parse(data);
 *   console.log(parsed);
 * });
 */
function readStdin(callback) {
  let data = '';
  process.stdin.on('data', chunk => data += chunk);
  process.stdin.on('end', () => callback(data));
}

/**
 * Pass stdin through to stdout unchanged
 * Used for hooks that need to not block but don't modify the data
 *
 * @example
 * // In a hook that just logs but doesn't transform:
 * utils.log('SOME_EVENT');
 * passThrough();
 */
function passThrough() {
  readStdin(data => console.log(data));
}

// ============================================
// Main
// ============================================

const [,, action, ...args] = process.argv;

if (!action || !actions[action]) {
  logging.error('Usage: hook-runner.js <action> [args...]');
  logging.info('Actions:', Object.keys(actions).join(', '));
  process.exit(1);
}

logging.debug('Running action:', action, 'with args:', args);
actions[action](args);
