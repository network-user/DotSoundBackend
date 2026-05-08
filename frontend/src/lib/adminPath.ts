type AdminRuntimeConfig = {
  panelPath: string | null
  apiPath: string | null
}

const runtimeConfig: AdminRuntimeConfig = {
  panelPath: null,
  apiPath: null,
}

export function normalizeAdminPathSegment(
  value: string | null | undefined,
): string {
  const raw = (value || '').trim().replace(/^\/+|\/+$/g, '')
  if (!raw) return 'admin'
  const cleaned = raw.replace(/[^A-Za-z0-9_-]/g, '')
  return cleaned || 'admin'
}

export function setAdminRuntimeConfig(config: {
  panelPath?: string | null
  apiPath?: string | null
}): void {
  if (config.panelPath !== undefined) {
    runtimeConfig.panelPath = config.panelPath
      ? normalizeAdminPathSegment(config.panelPath)
      : null
  }
  if (config.apiPath !== undefined) {
    const raw = (config.apiPath || '').trim()
    runtimeConfig.apiPath = raw
      ? raw.replace(/\/+$/g, '')
      : null
  }
}

export function getConfiguredAdminPanelPath(): string | null {
  return runtimeConfig.panelPath
}

export function getAdminPanelPath(): string {
  return runtimeConfig.panelPath || 'admin'
}

export function getAdminPanelRoute(suffix = ''): string {
  const base = `/${getAdminPanelPath()}`
  if (!suffix) return base
  const normalized = suffix.startsWith('/')
    ? suffix
    : `/${suffix}`
  return `${base}${normalized}`
}

export function getAdminApiBasePath(): string {
  return runtimeConfig.apiPath || `/api/v1/${getAdminPanelPath()}`
}

export function getAdminApiPath(path = ''): string {
  const base = getAdminApiBasePath()
  if (!path) return base
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${base}${normalized}`
}
