/**
 * Core utilities barrel export
 *
 * @module lib/core
 */

'use strict';

const platform = require('./platform');
const config = require('./config');
const exec = require('./exec');

module.exports = {
  platform,
  config,
  exec
};
