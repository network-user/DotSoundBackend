export function decodeAdminJwtHint(
  token: string | null,
): string | null {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded =
      b64 + '='.repeat((4 - (b64.length % 4)) % 4)
    const json = JSON.parse(
      atob(padded),
    ) as Record<string, unknown>
    const email =
      typeof json.email === 'string'
        ? json.email
        : typeof json.sub === 'string'
          ? json.sub
          : null
    return email
  } catch {
    return null
  }
}
