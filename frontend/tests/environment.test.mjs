import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { publicEnvironment } from '../config/environment.mjs'

test('one root file, process precedence, public allowlist, and validated defaults', () => {
  const directory = mkdtempSync(join(tmpdir(), 'flashcard-env-'))
  const rootFile = join(directory, '.env')
  try {
    writeFileSync(rootFile, 'VITE_API_URL=/root-api\nAPI_PORT=18000\nAI_API_KEY=private-test-value\n')
    writeFileSync(join(directory, '.env.local'), 'VITE_API_URL=/unsupported-fallback\n')
    assert.deepEqual(publicEnvironment(rootFile, {}), { apiUrl: '/root-api', apiPort: 18000 })
    assert.deepEqual(publicEnvironment(rootFile, { VITE_API_URL: '/process', API_PORT: '8001' }), {
      apiUrl: '/process', apiPort: 8001,
    })
    assert.deepEqual(publicEnvironment(join(directory, 'absent'), {}), { apiUrl: '/api', apiPort: 8000 })
    assert.throws(() => publicEnvironment(rootFile, { API_PORT: '0' }), /API_PORT/)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
