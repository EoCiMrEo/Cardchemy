import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import process from 'node:process'

const appOrigin = 'http://127.0.0.1:4175'
const apiOrigin = `${appOrigin}/api`
const frontendRoot = fileURLToPath(new URL('../..', import.meta.url))
const viteCli = join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const playwrightCli = join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js')

function childExit(child) {
  return new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code, signal) => resolve({ code, signal }))
  })
}

async function originIsAvailable() {
  try {
    const response = await fetch(appOrigin, { method: 'HEAD' })
    return response.ok
  } catch {
    return false
  }
}

async function waitForServer(serverExit) {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    if (await originIsAvailable()) return
    const outcome = await Promise.race([
      serverExit.then((result) => ({ type: 'exit', result })),
      new Promise((resolve) => setTimeout(() => resolve({ type: 'retry' }), 250)),
    ])
    if (outcome.type === 'exit') {
      throw new Error(`Vite exited before becoming ready (${JSON.stringify(outcome.result)}).`)
    }
  }
  throw new Error(`Vite did not become ready at ${appOrigin} within 30 seconds.`)
}

if (await originIsAvailable()) {
  throw new Error(`${appOrigin} is already in use; stop that process before running browser tests.`)
}

const server = spawn(
  process.execPath,
  [viteCli, '--host', '127.0.0.1', '--port', '4175', '--strictPort'],
  {
    cwd: frontendRoot,
    env: { ...process.env, VITE_API_URL: apiOrigin },
    stdio: 'inherit',
  },
)
const serverExit = childExit(server)
let testExitCode = 1

try {
  await waitForServer(serverExit)
  const tests = spawn(
    process.execPath,
    [playwrightCli, 'test', ...process.argv.slice(2)],
    {
      cwd: frontendRoot,
      env: { ...process.env, PLAYWRIGHT_MANAGED_SERVER: '1' },
      stdio: 'inherit',
    },
  )
  const result = await childExit(tests)
  testExitCode = result.code ?? 1
} finally {
  if (server.exitCode === null && server.signalCode === null) server.kill()
  await Promise.race([
    serverExit,
    new Promise((resolve) => setTimeout(resolve, 5_000)),
  ])
}

process.exitCode = testExitCode
