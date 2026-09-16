import assert from 'node:assert/strict'
import { test } from 'node:test'

import { normalizeApiBaseUrl } from '../src/services/apiUrl.ts'

test('accepts same-origin root-relative and absolute HTTP(S) API bases', () => {
  assert.equal(normalizeApiBaseUrl('/api'), '/api')
  assert.equal(normalizeApiBaseUrl('/api/'), '/api')
  assert.equal(normalizeApiBaseUrl('/api/v1/'), '/api/v1')
  assert.equal(normalizeApiBaseUrl('https://cards.example.test/api/'), 'https://cards.example.test/api')
  assert.equal(normalizeApiBaseUrl('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000')
})

test('rejects protocol-relative, credential-bearing, ambiguous, and unsafe API bases', () => {
  const invalidValues = [
    '',
    '/',
    '//attacker.example/api',
    '/\\attacker.example/api',
    '/api?tenant=unsafe',
    '/api#fragment',
    '/api path',
    'api',
    'javascript:alert(1)',
    'https://user:password@cards.example.test/api',
    'https://cards.example.test/api?tenant=unsafe',
    'https://cards.example.test/api#fragment',
    ' https://cards.example.test/api',
  ]

  for (const value of invalidValues) {
    assert.throws(() => normalizeApiBaseUrl(value), undefined, value)
  }
})

