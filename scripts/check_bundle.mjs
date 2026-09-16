import { readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

// Measure final emitted assets. Static imports count toward initial loading;
// dynamic route imports count toward total bytes but not the initial graph.
const root = fileURLToPath(new URL('..', import.meta.url))
const dist = join(root, 'frontend', 'dist')
const budget = JSON.parse(await readFile(join(root, '.github', 'bundle-budget.json'), 'utf8'))
const html = await readFile(join(dist, 'index.html'), 'utf8')
const entries = [...html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)=["']([^"']+\.js)["'][^>]*>/g)]
  .map((match) => match[1])
if (entries.length === 0) throw new Error('No emitted JavaScript entries found in dist/index.html.')

async function allJs(directory) {
  const result = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) result.push(...await allJs(path))
    else if (entry.name.endsWith('.js')) result.push(path)
  }
  return result
}
const assets = new Map()
for (const path of await allJs(dist)) {
  const data = await readFile(path)
  assets.set(resolve(path), { raw: data.length, gzip: gzipSync(data).length, source: data.toString('utf8') })
}
const initial = new Set()
async function visit(path) {
  path = resolve(path)
  if (initial.has(path)) return
  if (!path.startsWith(resolve(dist) + sep)) throw new Error('Initial asset escaped the dist directory.')
  const asset = assets.get(path)
  if (!asset) throw new Error('Referenced JavaScript asset is missing: ' + path)
  initial.add(path)
  // Vite emits compact import/export clauses; this excludes import(...).
  const imports = /(?:\bimport\s*(?:[^;()]*?\bfrom\s*)?|\bexport\s*[^;()]*?\bfrom\s*)["']([^"']+\.js)["']/g
  for (const match of asset.source.matchAll(imports)) {
    if (match[1].startsWith('.')) await visit(resolve(dirname(path), match[1]))
  }
}
for (const entry of entries) await visit(resolve(dist, entry.replace(/^\//, '')))

const files = [...assets].map(([path, bytes]) => ({
  file: relative(dist, path).replaceAll('\\', '/'),
  raw_bytes: bytes.raw,
  gzip_bytes: bytes.gzip,
  initial: initial.has(path),
})).sort((a, b) => b.raw_bytes - a.raw_bytes)
const metrics = {
  initial_js_gzip_bytes: files.filter((file) => file.initial).reduce((sum, file) => sum + file.gzip_bytes, 0),
  largest_js_raw_bytes: Math.max(...files.map((file) => file.raw_bytes)),
  total_js_gzip_bytes: files.reduce((sum, file) => sum + file.gzip_bytes, 0),
}
const report = { metrics, budgets: budget.limits, files }
await writeFile(join(root, 'frontend', 'bundle-report.json'), JSON.stringify(report, null, 2) + '\n')
const failures = []
for (const [name, value] of Object.entries(metrics)) {
  const limit = budget.limits[name]
  console.log(name + ': ' + value.toLocaleString() + ' bytes (limit ' + limit.toLocaleString() + ')')
  if (value > limit) failures.push(name)
}
if (failures.length) throw new Error('Production bundle budget exceeded: ' + failures.join(', '))
