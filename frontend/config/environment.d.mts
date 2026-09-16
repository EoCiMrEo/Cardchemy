export function publicEnvironment(
  rootFile: string,
  processEnvironment?: Record<string, string | undefined>,
): { apiPort: number; apiUrl: string }
