import { readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

// Measure final emitted assets. Static imports count toward initial loading;
// dynamic route imports count toward total bytes but not the initial graph.
const root = fileURLToPath(new URL('..', import.meta.url))
const dist = join(root, 'frontend', 'dist')
const jsExtension = /\.(?:m?js)$/
const staticImport = /(?:\bimport\s*(?:[^;()]*?\bfrom\s*)?|\bexport\s*[^;()]*?\bfrom\s*)["']([^"']+\.(?:m?js))["']/g

export function isJavaScriptAsset(name) {
  return jsExtension.test(name)
}

export function staticImportSpecifiers(source) {
  return [...source.matchAll(staticImport)].map((match) => match[1])
}

async function allJs(directory) {
  const result = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) result.push(...await allJs(path))
    else if (isJavaScriptAsset(entry.name)) result.push(path)
  }
  return result
}
export async function measureBundle(directory) {
  const html = await readFile(join(directory, 'index.html'), 'utf8')
  const entries = [...html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)=["']([^"']+\.(?:m?js))["'][^>]*>/g)]
    .map((match) => match[1])
  if (entries.length === 0) throw new Error('No emitted JavaScript entries found in dist/index.html.')

  const assets = new Map()
  for (const path of await allJs(directory)) {
    const data = await readFile(path)
    assets.set(resolve(path), { raw: data.length, gzip: gzipSync(data).length, source: data.toString('utf8') })
  }
  const initial = new Set()
  async function visit(path) {
    path = resolve(path)
    if (initial.has(path)) return
    if (!path.startsWith(resolve(directory) + sep)) throw new Error('Initial asset escaped the dist directory.')
    const asset = assets.get(path)
    if (!asset) throw new Error('Referenced JavaScript asset is missing: ' + path)
    initial.add(path)
    // Follow static imports, including .mjs; dynamic imports remain outside initial loading.
    for (const specifier of staticImportSpecifiers(asset.source)) {
      if (specifier.startsWith('.')) await visit(resolve(dirname(path), specifier))
    }
  }
  for (const entry of entries) await visit(resolve(directory, entry.replace(/^\//, '')))

  const files = [...assets].map(([path, bytes]) => ({
    file: relative(directory, path).replaceAll('\\', '/'),
    raw_bytes: bytes.raw,
    gzip_bytes: bytes.gzip,
    initial: initial.has(path),
  })).sort((a, b) => b.raw_bytes - a.raw_bytes)
  const metrics = {
    initial_js_gzip_bytes: files.filter((file) => file.initial).reduce((sum, file) => sum + file.gzip_bytes, 0),
    largest_js_raw_bytes: Math.max(...files.map((file) => file.raw_bytes)),
    total_js_gzip_bytes: files.reduce((sum, file) => sum + file.gzip_bytes, 0),
  }
  return { metrics, files }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const budget = JSON.parse(await readFile(join(root, '.github', 'bundle-budget.json'), 'utf8'))
  const { metrics, files } = await measureBundle(dist)
  const report = { metrics, budgets: budget.limits, files }
  await writeFile(join(root, 'frontend', 'bundle-report.json'), JSON.stringify(report, null, 2) + '\n')
  const failures = []
  for (const [name, value] of Object.entries(metrics)) {
    const limit = budget.limits[name]
    console.log(name + ': ' + value.toLocaleString() + ' bytes (limit ' + limit.toLocaleString() + ')')
    if (value > limit) failures.push(name)
  }
  if (failures.length) throw new Error('Production bundle budget exceeded: ' + failures.join(', '))
}
