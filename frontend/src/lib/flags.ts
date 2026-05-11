type FlagName = 'uploadV2' | 'trackEditPage'

function readEnvFlag(name: string): boolean | null {
  try {
    const value = import.meta.env[name as keyof ImportMetaEnv] as
      | string
      | undefined
    if (value === undefined) return null
    return value === '1' || value === 'true'
  } catch {
    return null
  }
}

function readQueryFlag(name: string): boolean | null {
  if (typeof window === 'undefined') return null
  try {
    const usp = new URLSearchParams(window.location.search)
    const v = usp.get(name)
    if (v === null) return null
    return v === '1' || v === 'true'
  } catch {
    return null
  }
}

function readLocalFlag(name: string): boolean | null {
  try {
    const v = window.localStorage.getItem(`dotsound:flag:${name}`)
    if (v === null) return null
    return v === '1' || v === 'true'
  } catch {
    return null
  }
}

const defaults: Record<FlagName, boolean> = {
  uploadV2: false,
  trackEditPage: true,
}

const envMap: Record<FlagName, string> = {
  uploadV2: 'VITE_UPLOAD_V2',
  trackEditPage: 'VITE_TRACK_EDIT_PAGE',
}

export function flag(name: FlagName): boolean {
  return (
    readQueryFlag(envMap[name].replace(/^VITE_/, '').toLowerCase()) ??
    readLocalFlag(name) ??
    readEnvFlag(envMap[name]) ??
    defaults[name]
  )
}

export const flagUploadV2 = (): boolean => flag('uploadV2')
export const flagTrackEditPage = (): boolean => flag('trackEditPage')
