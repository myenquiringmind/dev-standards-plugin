/**
 * Parameter Parser for Agent Invocation
 *
 * Parses `@agent-name param1=value1 param2=value2` syntax used to invoke
 * agents with specific parameters.
 *
 * @module lib/orchestrator/parser
 */

'use strict';

/**
 * Valid domains for the orchestrator
 * @type {string[]}
 */
const VALID_DOMAINS = [
  'logging', 'error', 'type', 'lint', 'test',
  'validation', 'git', 'housekeeping', 'naming', 'all'
];

/**
 * Valid phases for workflow execution
 * @type {string[]}
 */
const VALID_PHASES = ['design', 'validate-design', 'build', 'test', 'validate'];

/**
 * Valid git modes for workflow
 * @type {string[]}
 */
const VALID_GIT_MODES = ['auto', 'manual', 'disabled'];

/**
 * Parse agent invocation string
 *
 * @param {string} input - Input string like "@standards-orchestrator domain=all"
 * @returns {{agent: string, params: Object}|null} Parsed result or null if invalid
 *
 * @example
 * parse('@standards-orchestrator domain=logging phase=design')
 * // { agent: 'standards-orchestrator', params: { domain: 'logging', phase: 'design' } }
 *
 * @example
 * parse('@git-standards')
 * // { agent: 'git-standards', params: {} }
 *
 * @example
 * parse('not an agent')
 * // null
 */
function parse(input) {
  if (!input || typeof input !== 'string') {
    return null;
  }

  const trimmed = input.trim();

  // Match @agent-name pattern (letters, numbers, hyphens after first letter)
  const agentMatch = trimmed.match(/^@([a-zA-Z][a-zA-Z0-9-]*)/);
  if (!agentMatch) {
    return null;
  }

  const agent = agentMatch[1];
  const remainder = trimmed.substring(agentMatch[0].length).trim();

  // Parse key=value pairs
  const params = {};

  if (remainder) {
    // Pattern matches: key=value, key="value with spaces", key='value'
    const paramPattern = /([a-zA-Z][a-zA-Z0-9_]*)=("[^"]*"|'[^']*'|[^\s]+)/g;
    let match;

    while ((match = paramPattern.exec(remainder)) !== null) {
      const [, key, value] = match;
      // Remove quotes from quoted values
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        params[key] = value.slice(1, -1);
      } else {
        params[key] = value;
      }
    }
  }

  return { agent, params };
}

/**
 * Validate orchestrator parameters
 *
 * @param {Object} params - Parsed parameters
 * @returns {{valid: boolean, error?: string}}
 *
 * @example
 * validateOrchestratorParams({ domain: 'git' })
 * // { valid: true }
 *
 * @example
 * validateOrchestratorParams({ domain: 'invalid' })
 * // { valid: false, error: 'Invalid domain: invalid. Valid: logging, error, ...' }
 */
function validateOrchestratorParams(params) {
  if (!params || typeof params !== 'object') {
    return { valid: false, error: 'Parameters object required' };
  }

  if (!params.domain) {
    return { valid: false, error: 'Missing required parameter: domain' };
  }

  if (!VALID_DOMAINS.includes(params.domain)) {
    return {
      valid: false,
      error: `Invalid domain: ${params.domain}. Valid: ${VALID_DOMAINS.join(', ')}`
    };
  }

  if (params.phase && !VALID_PHASES.includes(params.phase)) {
    return {
      valid: false,
      error: `Invalid phase: ${params.phase}. Valid: ${VALID_PHASES.join(', ')}`
    };
  }

  if (params.gitMode && !VALID_GIT_MODES.includes(params.gitMode)) {
    return {
      valid: false,
      error: `Invalid gitMode: ${params.gitMode}. Valid: ${VALID_GIT_MODES.join(', ')}`
    };
  }

  return { valid: true };
}

/**
 * Parse command line arguments into parameters object
 *
 * @param {string[]} args - Array of arguments like ['domain=all', 'phase=design']
 * @returns {Object} Parsed parameters
 *
 * @example
 * parseArgs(['domain=all', 'phase=design'])
 * // { domain: 'all', phase: 'design' }
 */
function parseArgs(args) {
  const params = {};

  for (const arg of args) {
    const match = arg.match(/^([a-zA-Z][a-zA-Z0-9_]*)=(.+)$/);
    if (match) {
      const [, key, value] = match;
      // Remove quotes if present
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        params[key] = value.slice(1, -1);
      } else {
        params[key] = value;
      }
    }
  }

  return params;
}

/**
 * Format parameters back to string format
 *
 * @param {Object} params - Parameters object
 * @returns {string} Formatted string like "domain=all phase=design"
 *
 * @example
 * formatParams({ domain: 'all', phase: 'design' })
 * // 'domain=all phase=design'
 */
function formatParams(params) {
  return Object.entries(params)
    .map(([key, value]) => {
      // Quote values with spaces
      if (typeof value === 'string' && value.includes(' ')) {
        return `${key}="${value}"`;
      }
      return `${key}=${value}`;
    })
    .join(' ');
}

module.exports = {
  VALID_DOMAINS,
  VALID_PHASES,
  VALID_GIT_MODES,
  parse,
  validateOrchestratorParams,
  parseArgs,
  formatParams
};
