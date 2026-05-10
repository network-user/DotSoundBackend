// Lightweight, opaque client-signal token for anti-abuse.
//
// This module is intentionally tiny. It builds a short stable
// hash from a handful of *class*-level browser characteristics
// (timezone, language, UA family, narrow-canvas hash, narrow-
// webgl-vendor hash). It does NOT use FingerprintJS and does
// NOT collect device-unique values like canvas pixel-perfect
// data, audio context buffers, or fonts.
//
// We only attach the token to outgoing requests after the user
// accepted the cookie/consent banner -- before that the header
// is never sent.

const CONSENT_KEY = 'ds_consent_v1'

export function hasAbuseConsent(): boolean {
  try {
    return localStorage.getItem(CONSENT_KEY) === 'accept'
  } catch {
    return false
  }
}

export function setAbuseConsent(accept: boolean): void {
  try {
    localStorage.setItem(CONSENT_KEY, accept ? 'accept' : 'minimal')
  } catch {
    /* ignore */
  }
}

async function sha256Hex(input: string): Promise<string> {
  const enc = new TextEncoder().encode(input)
  const digest = await crypto.subtle.digest('SHA-256', enc)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

function readUaClass(): string {
  const ua = navigator.userAgent || ''
  if (/Telegram/i.test(ua)) return 'telegram'
  if (/Android/i.test(ua)) return 'android'
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios'
  if (/Mac OS X/i.test(ua)) return 'mac'
  if (/Windows/i.test(ua)) return 'win'
  return 'other'
}

function readWebglVendorClass(): string {
  try {
    const canvas = document.createElement('canvas')
    const gl =
      (canvas.getContext('webgl') as WebGLRenderingContext | null) ||
      (canvas.getContext(
        'experimental-webgl',
      ) as WebGLRenderingContext | null)
    if (!gl) return 'none'
    const ext = gl.getExtension('WEBGL_debug_renderer_info')
    const vendor = ext
      ? String(
          gl.getParameter(
            (ext as { UNMASKED_VENDOR_WEBGL?: number })
              .UNMASKED_VENDOR_WEBGL ?? 0,
          ),
        )
      : ''
    return vendor.split(' ')[0]?.toLowerCase() || 'unknown'
  } catch {
    return 'none'
  }
}

let cachedToken: string | null = null

export async function getClientSignalToken(): Promise<string | null> {
  if (!hasAbuseConsent()) return null
  if (cachedToken) return cachedToken
  const parts = [
    readUaClass(),
    readWebglVendorClass(),
    navigator.language || '',
    Intl.DateTimeFormat().resolvedOptions().timeZone || '',
  ]
  cachedToken = (await sha256Hex(parts.join('|'))).slice(0, 64)
  return cachedToken
}
