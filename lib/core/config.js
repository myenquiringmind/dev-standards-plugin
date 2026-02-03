/**
 * Centralized configuration
 *
 * Single source of truth for all constants, timeouts, and configurable values.
 * Eliminates magic numbers and duplicated constants across files.
 *
 * @module lib/core/config
 */

'use strict';

// ============================================
// Plugin Metadata
// ============================================

/**
 * Current plugin version (must match plugin.json and hooks.json)
 * @type {string}
 */
const PLUGIN_VERSION = '1.4.0';

/**
 * GitHub repository in org/repo format
 * @type {string}
 */
const PLUGIN_REPO = 'myenquiringmind/dev-standards-plugin';

/**
 * Cache filename for version checks
 * @type {string}
 */
const VERSION_CACHE_FILE = '.claude-plugin-version-cache.json';

// ============================================
// Timeouts (in milliseconds)
// ============================================

const TIMEOUTS = {
  /** Quick commands like `which`, `git status` */
  QUICK: 3000,

  /** Standard commands like formatting a file */
  STANDARD: 10000,

  /** Longer commands like type checking */
  EXTENDED: 30000,

  /** Very long commands like venv creation */
  LONG: 60000,

  /** Package installation */
  INSTALL: 120000,

  /** Version check network request */
  VERSION_CHECK: 5000,

  /** Version check cache duration (24 hours) */
  VERSION_CACHE_MS: 24 * 60 * 60 * 1000
};

// ============================================
// Venv Configuration
// ============================================

/**
 * Virtual environment directory names to search for
 * @type {string[]}
 */
const VENV_NAMES = ['.venv', 'venv', '.uv'];

/**
 * Python dependencies required by the plugin
 * @type {string[]}
 */
const PYTHON_DEPS = ['ruff', 'mypy'];

// ============================================
// Git Configuration
// ============================================

/**
 * Branches that should not allow direct edits
 * @type {string[]}
 */
const PROTECTED_BRANCHES = ['main', 'master', 'production', 'develop', 'staging', 'release'];

// ============================================
// Tool Configuration
// ============================================

/**
 * Formatters by file extension
 * @type {Object<string, string>}
 */
const FORMATTERS = {
  js: 'npx prettier --write',
  jsx: 'npx prettier --write',
  ts: 'npx prettier --write',
  tsx: 'npx prettier --write',
  json: 'npx prettier --write',
  css: 'npx prettier --write',
  scss: 'npx prettier --write',
  html: 'npx prettier --write',
  md: 'npx prettier --write',
  py: 'ruff format',
  go: 'gofmt -w',
  rs: 'rustfmt'
};

/**
 * Type checkers by file extension
 * @type {Object<string, {cmd: string, errorPattern: string}>}
 */
const TYPE_CHECKERS = {
  ts: { cmd: 'npx tsc --noEmit', errorPattern: 'error TS' },
  tsx: { cmd: 'npx tsc --noEmit', errorPattern: 'error TS' },
  py: { cmd: 'mypy --ignore-missing-imports', errorPattern: 'error:' }
};

/**
 * Linters by file extension
 * @type {Object<string, {cmd: string, errorPattern?: RegExp, successPattern?: string}>}
 */
const LINTERS = {
  js: { cmd: 'npx eslint --format compact', errorPattern: /(error|warning)/ },
  jsx: { cmd: 'npx eslint --format compact', errorPattern: /(error|warning)/ },
  ts: { cmd: 'npx eslint --format compact', errorPattern: /(error|warning)/ },
  tsx: { cmd: 'npx eslint --format compact', errorPattern: /(error|warning)/ },
  py: { cmd: 'ruff check', successPattern: 'All checks passed' }
};

// ============================================
// Security Configuration
// ============================================

/**
 * Dangerous command patterns that should be blocked
 * @type {RegExp[]}
 */
const DANGEROUS_PATTERNS = [
  // Unix destructive commands
  /rm\s+-rf\s+\/(?!tmp)/,           // rm -rf / (except /tmp)
  /rm\s+-rf\s+~/,                   // rm -rf ~
  /rm\s+-rf\s+\*/,                  // rm -rf *
  /rm\s+-rf\s+\.\.\//,              // rm -rf ../

  // SQL injection
  /DROP\s+(DATABASE|TABLE)/i,
  /TRUNCATE\s+TABLE/i,
  /DELETE\s+FROM\s+\w+\s*;?$/i,
  /;\s*DROP\s+/i,                   // ; DROP ...

  // Fork bombs and system damage
  /:\(\)\s*\{.*\}.*;\s*:/,          // :(){ :|:& };:
  />\s*\/dev\/sd[a-z]/,             // > /dev/sda
  /mkfs\./,                         // mkfs.ext4 etc
  /dd\s+if=.*of=\/dev/,             // dd to device

  // Permission changes
  /chmod\s+-R\s+777\s+\//,          // chmod -R 777 /

  // Remote code execution
  /curl.*\|\s*(bash|sh)/,           // curl | bash
  /wget.*\|\s*(bash|sh)/,           // wget | sh

  // Windows destructive commands
  /format\s+[cdefgh]:/i,            // format C:
  /Remove-Item.*-Recurse.*-Force.*[A-Z]:\\/i,  // PowerShell rm

  // Environment variable expansion attacks
  /\$\(.*rm\s/,                     // $(rm ...)
  /`.*rm\s/                         // `rm ...`
];

/**
 * Maximum stdin size for hook processing (10MB)
 * @type {number}
 */
const MAX_STDIN_SIZE = 10 * 1024 * 1024;

/**
 * Valid package name pattern
 * @type {RegExp}
 */
const VALID_PACKAGE_NAME = /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/;

// ============================================
// Housekeeping Configuration
// ============================================

/**
 * Files allowed in root directory (whitelist)
 * @type {string[]}
 */
const ROOT_WHITELIST = [
  // Package managers
  'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
  // Git
  '.gitignore', '.gitattributes', '.editorconfig',
  // Documentation
  'LICENSE', 'LICENSE.md', 'LICENSE.txt',
  'README.md', 'README.txt', 'readme.md',
  'CHANGELOG.md', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md',
  // Linting & formatting
  '.eslintrc.json', '.eslintrc.js', '.eslintrc', '.eslintrc.cjs',
  '.prettierrc', '.prettierrc.json', '.prettierrc.js',
  'commitlint.config.js', '.commitlintrc.json',
  // TypeScript
  'tsconfig.json', 'jsconfig.json',
  // Python
  'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt',
  // Environment
  '.env.example', '.nvmrc', '.node-version', '.python-version',
  // Build
  'Makefile', 'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
  // Claude
  '.claudeignore', 'CLAUDE.md'
];

/**
 * Files blocked in root directory (blacklist)
 * @type {RegExp[]}
 */
const ROOT_BLACKLIST = [
  /^\.?nul$/i, /^\.tmp$/i, /\.bak$/i, /\.swp$/i, /^~.*$/,
  /^Thumbs\.db$/i, /^\.DS_Store$/i, /^desktop\.ini$/i,
  /^npm-debug\.log/, /^yarn-error\.log/, /^\.eslintcache$/,
  /^\.cache$/, /^\.parcel-cache$/
];

/**
 * Directories allowed in project root
 * @type {string[]}
 */
const ROOT_DIRECTORIES = [
  // Git and CI/CD
  '.git',
  '.github',
  '.gitlab',
  '.circleci',
  '.husky',
  // Plugin configuration
  '.claude-plugin',
  // IDE (optional, often gitignored)
  '.vscode',
  '.idea',
  // Source code
  'src',
  'lib',
  'bin',
  'scripts',
  // Tests and docs
  'tests',
  'test',
  '__tests__',
  'docs',
  'doc',
  // Configuration
  'config',
  'configs',
  // Assets
  'public',
  'static',
  'assets',
  // Build output (typically gitignored)
  'dist',
  'build',
  'out',
  // Dependencies (gitignored but present locally)
  'node_modules',
  // Coverage (gitignored)
  'coverage',
  // Local temp (gitignored)
  'tmp',
  // Plugin-specific directories
  'agents',
  'commands',
  'skills',
  'hooks'
];

/**
 * System temp directory patterns to detect and block
 * @type {RegExp[]}
 */
const SYSTEM_TEMP_PATTERNS = [
  // Node.js
  /os\.tmpdir\s*\(\)/,
  /os\.temp\b/,
  /process\.env\.TMPDIR\b/,
  /process\.env\.TMP\b/,
  /process\.env\.TEMP\b/,

  // Unix paths
  /['"`]\/tmp\//,
  /['"`]\/var\/tmp\//,

  // Windows paths
  /%TEMP%/i,
  /%TMP%/i,
  /\\Temp\\/i,
  /\\Local\\Temp/i,

  // Python
  /tempfile\.gettempdir\s*\(\)/,
  /tempfile\.mktemp/,
  /tempfile\.NamedTemporaryFile/
];

/**
 * Allowed local temp patterns
 * @type {RegExp[]}
 */
const LOCAL_TEMP_ALLOWED = [
  /\.\/tmp\//,
  /path\.join\s*\([^)]*['"`]tmp['"`]/,
  /\$\{?projectRoot\}?\/tmp/,
  /__dirname.*['"`]tmp['"`]/
];

// ============================================
// Naming Convention Configuration
// ============================================

/**
 * Naming conventions by language
 * @type {Object}
 */
const NAMING_CONVENTIONS = {
  javascript: {
    files: /^[a-z][a-z0-9]*(-[a-z0-9]+)*\.(js|mjs|cjs|ts|tsx|jsx)$/,
    functions: /^[a-z][a-zA-Z0-9]*$/,  // camelCase
    classes: /^[A-Z][a-zA-Z0-9]*$/,     // PascalCase
    constants: /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$/,  // SCREAMING_SNAKE
    tests: /\.(test|spec)\.(js|ts|jsx|tsx)$/
  },
  python: {
    files: /^[a-z][a-z0-9]*(_[a-z0-9]+)*\.py$/,
    functions: /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/,  // snake_case
    classes: /^[A-Z][a-zA-Z0-9]*$/,               // PascalCase
    constants: /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$/,  // SCREAMING_SNAKE
    tests: /^test_.*\.py$|_test\.py$/
  }
};

/**
 * File extensions by language
 * @type {Object}
 */
const LANGUAGE_EXTENSIONS = {
  javascript: ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx'],
  python: ['.py', '.pyw']
};

// ============================================
// Gitignore Pattern Configuration
// ============================================

/**
 * Comprehensive .gitignore patterns by category
 * Used by @git-standards agent for .gitignore rectification
 * @type {Object<string, string[]>}
 */
const GITIGNORE_PATTERNS = {
  // OS-generated files
  os: [
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
    '*.swp',
    '*.swo',
    '*~',
    '.nul',
    'nul'
  ],

  // IDE and editor files
  ide: [
    '.idea/',
    '.vscode/',
    '*.sublime-*',
    '.project',
    '.classpath',
    '.settings/'
  ],

  // Node.js
  node: [
    'node_modules/',
    'npm-debug.log*',
    'yarn-debug.log*',
    'yarn-error.log*',
    '.npm',
    '.yarn/',
    '.pnpm-store/'
  ],

  // Python
  python: [
    '__pycache__/',
    '*.py[cod]',
    '*$py.class',
    '.venv/',
    'venv/',
    '.uv/',
    '.mypy_cache/',
    '.ruff_cache/',
    '.pytest_cache/',
    '*.egg-info/',
    '.eggs/'
  ],

  // Test coverage
  coverage: [
    'coverage/',
    '.nyc_output/',
    'htmlcov/',
    '.coverage',
    '*.lcov'
  ],

  // Build outputs
  build: [
    'dist/',
    'build/',
    'out/',
    '.next/',
    '.nuxt/',
    '.output/'
  ],

  // Cache directories
  cache: [
    '.cache/',
    '.parcel-cache/',
    '.eslintcache',
    '.stylelintcache',
    '*.tsbuildinfo'
  ],

  // Secrets and credentials (CRITICAL)
  secrets: [
    '.env',
    '.env.local',
    '.env.*.local',
    '*.pem',
    '*.key',
    '*.p12',
    'credentials.json',
    'secrets.json',
    '.secrets/'
  ],

  // Logs
  logs: [
    '*.log',
    'logs/',
    '*.log.*'
  ],

  // Temporary files
  temp: [
    'tmp/',
    'temp/',
    '.tmp/',
    '*.tmp'
  ],

  // Local plugin state
  plugin: [
    'tmp/.orchestrator-state.json'
  ]
};

/**
 * Project type detection patterns
 * @type {Object<string, string[]>}
 */
const PROJECT_TYPE_PATTERNS = {
  node: ['package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml'],
  python: ['pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile'],
  rust: ['Cargo.toml'],
  go: ['go.mod'],
  java: ['pom.xml', 'build.gradle']
};

// ============================================
// Orchestrator Domain Configuration
// ============================================

/**
 * Domain dependencies - which domains must complete BEFORE each domain
 * Used to determine execution order when running domain=all
 *
 * Design rationale for cycle-breaking:
 * - error before logging: Error patterns must exist before logging can integrate
 * - housekeeping before git: Project structure must be clean before git tracking
 * - lint before type: Linting is more fundamental than type annotations
 *
 * @type {Object<string, string[]>}
 */
const DOMAIN_DEPENDENCIES = {
  // Tier 1: No dependencies (run first)
  naming: [],
  validation: [],

  // Tier 2: Foundation
  error: [],  // Foundation - no deps but runs after Tier 1 for logical grouping
  logging: ['error'],  // Logging needs error patterns first

  // Tier 3: Code quality
  lint: ['error', 'logging'],
  type: ['error', 'lint'],

  // Tier 4: Project structure
  housekeeping: ['error'],
  git: ['housekeeping', 'validation', 'error', 'type'],

  // Tier 5: Hub (runs last - receives handoffs from all)
  test: ['error', 'logging', 'type', 'lint', 'validation', 'naming', 'git', 'housekeeping']
};

/**
 * Pre-computed execution order based on DOMAIN_DEPENDENCIES
 * Topologically sorted to ensure dependencies are satisfied
 * @type {string[]}
 */
const DOMAIN_EXECUTION_ORDER = [
  'naming',       // Tier 1 - No dependencies
  'validation',   // Tier 1 - No dependencies
  'error',        // Tier 2 - Foundation for error handling
  'logging',      // Tier 2 - Depends on error
  'lint',         // Tier 3 - Depends on error, logging
  'type',         // Tier 3 - Depends on error, lint
  'housekeeping', // Tier 4 - Depends on error
  'git',          // Tier 4 - Depends on housekeeping, validation, error, type
  'test'          // Tier 5 - Hub, runs last
];

// ============================================
// Logging Configuration
// ============================================

/**
 * Whether debug logging is enabled
 * @type {boolean}
 */
const DEBUG = process.env.DEBUG === 'true' || process.env.DEBUG === '1';

/**
 * Log directory name under home
 * @type {string}
 */
const LOG_DIR = '.claude/logs';

/**
 * Session log filename
 * @type {string}
 */
const SESSION_LOG = 'session.log';

// ============================================
// Exports
// ============================================

module.exports = {
  // Plugin metadata
  PLUGIN_VERSION,
  PLUGIN_REPO,
  VERSION_CACHE_FILE,

  // Timeouts
  TIMEOUTS,

  // Venv
  VENV_NAMES,
  PYTHON_DEPS,

  // Git
  PROTECTED_BRANCHES,

  // Tools
  FORMATTERS,
  TYPE_CHECKERS,
  LINTERS,

  // Security
  DANGEROUS_PATTERNS,
  MAX_STDIN_SIZE,
  VALID_PACKAGE_NAME,

  // Housekeeping
  ROOT_WHITELIST,
  ROOT_BLACKLIST,
  ROOT_DIRECTORIES,
  SYSTEM_TEMP_PATTERNS,
  LOCAL_TEMP_ALLOWED,

  // Naming conventions
  NAMING_CONVENTIONS,
  LANGUAGE_EXTENSIONS,

  // Gitignore
  GITIGNORE_PATTERNS,
  PROJECT_TYPE_PATTERNS,

  // Orchestrator
  DOMAIN_DEPENDENCIES,
  DOMAIN_EXECUTION_ORDER,

  // Logging
  DEBUG,
  LOG_DIR,
  SESSION_LOG
};
