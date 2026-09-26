// Harness: load a copy of the REAL api.js as a plain (non-module) script,
// driving it through node:vm with a stubbed `window`, and capture the global
// bindings a browser would have (API_BASE, resolveApiBase). This lets tests
// assert the actual shipped frontend, not a re-implementation.
'use strict';
const fs = require('fs');
const vm = require('vm');

function loadApi(pathname) {
  const src = fs.readFileSync(__dirname + '/api.js', 'utf8');
  // api.js references `window` at load time only to compute API_BASE; stub it.
  const sandbox = {
    window: { location: { pathname: pathname, href: 'https://x' + pathname } },
    console: console,
    fetch: function () {},
  };
  sandbox.globalThis = sandbox;
  const capture = [
    ';__result = { API_BASE, resolveApiBase, _typeof_apiBase: typeof API_BASE };',
  ].join('\n');
  const script = new vm.Script('(function(module){ ' + src + '\n' + capture +
    ' })({exports:{}});');
  const ctx = vm.createContext(sandbox);
  script.runInContext(ctx);
  return ctx.__result;
}

module.exports = { loadApi };
