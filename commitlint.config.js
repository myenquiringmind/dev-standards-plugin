/**
 * Commitlint configuration
 *
 * Enforces conventional commit format:
 * type(scope): subject
 *
 * @see https://www.conventionalcommits.org/
 */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Allowed commit types
    'type-enum': [2, 'always', [
      'feat',     // New feature
      'fix',      // Bug fix
      'docs',     // Documentation only
      'style',    // Code style (formatting, semicolons, etc.)
      'refactor', // Code change that neither fixes a bug nor adds a feature
      'test',     // Adding or modifying tests
      'chore',    // Maintenance tasks
      'perf',     // Performance improvement
      'ci',       // CI configuration
      'build'     // Build system or external dependencies
    ]],

    // Subject must be lowercase
    'subject-case': [2, 'never', ['start-case', 'pascal-case', 'upper-case']],

    // Subject max length
    'header-max-length': [2, 'always', 72],

    // Subject must not end with period
    'subject-full-stop': [2, 'never', '.'],

    // Type must be lowercase
    'type-case': [2, 'always', 'lower-case'],

    // Scope must be lowercase
    'scope-case': [2, 'always', 'lower-case']
  }
};
