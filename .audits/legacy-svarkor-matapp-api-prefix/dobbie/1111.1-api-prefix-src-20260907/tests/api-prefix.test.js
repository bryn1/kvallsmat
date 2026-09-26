// RED test for MC 1111.1: API_BASE must be prefix-aware so api/stores works
// under /matapp/. Desired behavior:
//   * served under /matapp/  -> API_BASE == "/matapp"
//   * served under /matapp   -> API_BASE == "/matapp"
//   * served at root /       -> API_BASE == ""  (unchanged legacy behavior)
//   * empty pathname (defensive) -> API_BASE == ""
'use node:test';
const { test } = require('node:test');
const assert = require('node:assert');
const { loadApi } = require('./load-api');

test('API_BASE is "/matapp" under /matapp/ (trailing slash)', () => {
  const r = loadApi('/matapp/');
  assert.strictEqual(r.API_BASE, '/matapp');
});

test('API_BASE is "/matapp" under /matapp (no trailing slash)', () => {
  const r = loadApi('/matapp');
  assert.strictEqual(r.API_BASE, '/matapp');
});

test('API_BASE is "" when served at root / (legacy unchanged)', () => {
  const r = loadApi('/');
  assert.strictEqual(r.API_BASE, '');
});

test('API_BASE is "" for empty pathname (defensive)', () => {
  const r = loadApi('');
  assert.strictEqual(r.API_BASE, '');
});

test('resolveApiBase is a pure function of the path segment', () => {
  const r = loadApi('/matapp/');
  assert.strictEqual(typeof r.resolveApiBase, 'function');
  assert.strictEqual(r.resolveApiBase('/somepath/'), '/somepath');
  assert.strictEqual(r.resolveApiBase('/'), '');
});
