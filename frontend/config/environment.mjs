import { existsSync, readFileSync } from 'node:fs'
import { parseEnv } from 'node:util'

// Read exactly one file. Vite's normal .env.local/.env.<mode> fallbacks are
// intentionally disabled so native and container builds have one contract.
export function publicEnvironment(rootFile, processEnvironment = process.env) {
  const file = existsSync(rootFile) ? parseEnv(readFileSync(rootFile, 'utf8')) : {}
  const value = (key, fallback) => processEnvironment[key] || file[key] || fallback
  const apiPort = Number(value('API_PORT', '8000'))
  if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535) {
    throw new Error('API_PORT must be an integer between 1 and 65535')
  }
  return { apiPort, apiUrl: value('VITE_API_URL', '/api') }
}
