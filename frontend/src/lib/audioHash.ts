/**
 * Compound SHA-256 over (head 4 MiB || tail 4 MiB || size LE-8B).
 *
 * Hashing the whole file is too expensive on mobile for 100 MB uploads.
 * Head+tail+size keeps the collision probability negligible in practice
 * while staying under ~50ms on a mid-tier phone.
 */

const HEAD_BYTES = 4 * 1024 * 1024
const TAIL_BYTES = 4 * 1024 * 1024

function toHex(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let out = ''
  for (let i = 0; i < bytes.length; i++) {
    out += bytes[i].toString(16).padStart(2, '0')
  }
  return out
}

function sizeAsLE8(size: number): Uint8Array {
  const buf = new ArrayBuffer(8)
  const view = new DataView(buf)
  view.setBigUint64(0, BigInt(size), true)
  return new Uint8Array(buf)
}

export async function computeAudioHash(file: Blob): Promise<string> {
  const size = file.size
  let headBytes: ArrayBuffer
  let tailBytes: ArrayBuffer

  if (size <= HEAD_BYTES + TAIL_BYTES) {
    headBytes = await file.arrayBuffer()
    tailBytes = new ArrayBuffer(0)
  } else {
    headBytes = await file.slice(0, HEAD_BYTES).arrayBuffer()
    tailBytes = await file
      .slice(size - TAIL_BYTES, size)
      .arrayBuffer()
  }

  const sizeBytes = sizeAsLE8(size)
  const merged = new Uint8Array(
    headBytes.byteLength + tailBytes.byteLength + sizeBytes.byteLength,
  )
  merged.set(new Uint8Array(headBytes), 0)
  merged.set(new Uint8Array(tailBytes), headBytes.byteLength)
  merged.set(
    sizeBytes,
    headBytes.byteLength + tailBytes.byteLength,
  )

  const digest = await crypto.subtle.digest('SHA-256', merged)
  return toHex(digest)
}
