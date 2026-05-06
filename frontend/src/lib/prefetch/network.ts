interface NetInfo {
  effectiveType?: string
  saveData?: boolean
  downlink?: number
  addEventListener?: (
    type: 'change',
    cb: () => void,
  ) => void
  removeEventListener?: (
    type: 'change',
    cb: () => void,
  ) => void
}

export interface NetworkSnapshot {
  effectiveType: string | null
  saveData: boolean
  downlinkMbps: number | null
}

function _readNetInfo(): NetInfo | null {
  const nav = navigator as Navigator & {
    connection?: NetInfo
    mozConnection?: NetInfo
    webkitConnection?: NetInfo
  }
  return (
    nav.connection ||
    nav.mozConnection ||
    nav.webkitConnection ||
    null
  )
}

export function readNetworkSnapshot(): NetworkSnapshot {
  const info = _readNetInfo()
  if (!info) {
    return {
      effectiveType: null,
      saveData: false,
      downlinkMbps: null,
    }
  }
  return {
    effectiveType: info.effectiveType ?? null,
    saveData: Boolean(info.saveData),
    downlinkMbps:
      typeof info.downlink === 'number' && info.downlink >= 0
        ? info.downlink
        : null,
  }
}

export function subscribeToNetworkChanges(
  cb: (snapshot: NetworkSnapshot) => void,
): () => void {
  const info = _readNetInfo()
  if (!info?.addEventListener) {
    return () => {}
  }
  const listener = () => cb(readNetworkSnapshot())
  info.addEventListener('change', listener)
  return () => {
    info.removeEventListener?.('change', listener)
  }
}
