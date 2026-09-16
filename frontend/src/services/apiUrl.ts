const INVALID_API_URL_CHARACTERS = /[\\\s]/

function hasAsciiControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0
    return codePoint < 32 || codePoint === 127
  })
}

export function normalizeApiBaseUrl(value: string): string {
  if (
    !value
    || value !== value.trim()
    || INVALID_API_URL_CHARACTERS.test(value)
    || hasAsciiControlCharacter(value)
  ) {
    throw new Error('invalid whitespace or control character')
  }

  if (value.startsWith('/')) {
    if (value === '/' || value.startsWith('//') || value.includes('?') || value.includes('#')) {
      throw new Error('invalid root-relative URL')
    }
    return value.replace(/\/+$/, '')
  }

  const parsed = new URL(value)
  if (
    !['http:', 'https:'].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || parsed.search
    || parsed.hash
  ) {
    throw new Error('invalid absolute URL')
  }
  return parsed.toString().replace(/\/+$/, '')
}
