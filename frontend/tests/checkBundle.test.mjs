import assert from 'node:assert/strict'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve, sep } from 'node:path'
import { gzipSync } from 'node:zlib'
import test from 'node:test'

import { isJavaScriptAsset, measureBundle, staticImportSpecifiers } from '../../scripts/check_bundle.mjs'

test('bundle inventory includes module workers while initial loading follows only static imports', async () => {
  const temporary = await mkdtemp(join(tmpdir(), 'cardchemy-bundle-'))
  assert.ok(resolve(temporary).startsWith(resolve(tmpdir()) + sep))
  assert.ok(basename(temporary).startsWith('cardchemy-bundle-'))
  try {
    const assets = join(temporary, 'assets')
    await mkdir(assets)
    const sources = {
      'index.js': 'import "./base.mjs"; import("./later.js");',
      'base.mjs': 'export { value } from "./shared.js";',
      'shared.js': 'export const value = 1;',
      'later.js': 'export const later = 2;',
      'pdf.worker.mjs': 'export const worker = "a large optional worker";',
    }
    await writeFile(join(temporary, 'index.html'), '<script type="module" src="/assets/index.js"></script>')
    for (const [name, source] of Object.entries(sources)) await writeFile(join(assets, name), source)

    const { metrics, files } = await measureBundle(temporary)
    const byFile = Object.fromEntries(files.map((file) => [file.file, file]))
    assert.deepEqual(Object.keys(byFile).sort(), Object.keys(sources).map((name) => `assets/${name}`).sort())
    assert.equal(byFile['assets/index.js'].initial, true)
    assert.equal(byFile['assets/base.mjs'].initial, true)
    assert.equal(byFile['assets/shared.js'].initial, true)
    assert.equal(byFile['assets/later.js'].initial, false)
    assert.equal(byFile['assets/pdf.worker.mjs'].initial, false)
    assert.equal(metrics.total_js_gzip_bytes,
      Object.values(sources).reduce((total, source) => total + gzipSync(source).length, 0))
    assert.equal(metrics.largest_js_raw_bytes,
      Math.max(...Object.values(sources).map((source) => Buffer.byteLength(source))))
  } finally {
    await rm(temporary, { recursive: true, force: true })
  }
})

test('JavaScript extension and import parser recognize .mjs without treating dynamic imports as initial', () => {
  assert.equal(isJavaScriptAsset('pdf.worker.mjs'), true)
  assert.equal(isJavaScriptAsset('index.js'), true)
  assert.equal(isJavaScriptAsset('style.css'), false)
  assert.deepEqual(staticImportSpecifiers('import "./base.mjs"; export * from "./shared.js"; import("./later.js")'),
    ['./base.mjs', './shared.js'])
})
