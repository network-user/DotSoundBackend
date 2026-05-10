export interface AudioMetadata {
  title?: string
  artist?: string
  album?: string
  genre?: string
  year?: string
  durationSec?: number
  cover?: { blob: Blob; mime: string }
  source: 'tags' | 'filename' | 'mixed' | 'none'
}

const HEADER_PROBE_BYTES = 10
const MAX_TAG_BYTES = 8 * 1024 * 1024
const COVER_MAX_BYTES = 2 * 1024 * 1024

export async function extractAudioMetadata(
  file: File,
): Promise<AudioMetadata> {
  let tagMeta: Partial<AudioMetadata> = {}
  try {
    tagMeta = await readId3v2(file)
  } catch {
    tagMeta = {}
  }
  const fromTags = Boolean(
    tagMeta.title || tagMeta.artist || tagMeta.album,
  )
  const fallback = fromTags ? {} : parseFilename(file.name)
  const merged: AudioMetadata = {
    ...fallback,
    ...tagMeta,
    source: fromTags
      ? Object.keys(fallback).length
        ? 'mixed'
        : 'tags'
      : Object.keys(fallback).length
        ? 'filename'
        : 'none',
  }
  return merged
}

async function readId3v2(
  file: File,
): Promise<Partial<AudioMetadata>> {
  const headerBuf = await file
    .slice(0, HEADER_PROBE_BYTES)
    .arrayBuffer()
  const header = new Uint8Array(headerBuf)
  if (
    header.length < HEADER_PROBE_BYTES ||
    header[0] !== 0x49 ||
    header[1] !== 0x44 ||
    header[2] !== 0x33
  ) {
    return {}
  }
  const major = header[3]
  if (major !== 3 && major !== 4) return {}
  const flags = header[5]
  if (flags & 0x80) return {}
  const tagSize = readSynchsafe(header, 6)
  if (tagSize <= 0 || tagSize > MAX_TAG_BYTES) return {}
  const fullBuf = await file
    .slice(0, HEADER_PROBE_BYTES + tagSize)
    .arrayBuffer()
  const bytes = new Uint8Array(fullBuf)
  let cursor = HEADER_PROBE_BYTES
  if (flags & 0x40) {
    const extSize =
      major === 4
        ? readSynchsafe(bytes, cursor)
        : readUint32BE(bytes, cursor)
    cursor += extSize
  }
  const out: Partial<AudioMetadata> = {}
  while (cursor + 10 <= bytes.length) {
    const id = String.fromCharCode(
      bytes[cursor],
      bytes[cursor + 1],
      bytes[cursor + 2],
      bytes[cursor + 3],
    )
    if (!/^[A-Z0-9]{4}$/.test(id)) break
    const frameSize =
      major === 4
        ? readSynchsafe(bytes, cursor + 4)
        : readUint32BE(bytes, cursor + 4)
    if (frameSize <= 0) break
    if (cursor + 10 + frameSize > bytes.length) break
    const payload = bytes.subarray(
      cursor + 10,
      cursor + 10 + frameSize,
    )
    applyFrame(id, payload, out)
    cursor += 10 + frameSize
  }
  return out
}

function applyFrame(
  id: string,
  payload: Uint8Array,
  out: Partial<AudioMetadata>,
): void {
  if (id === 'TIT2') out.title = readTextFrame(payload)
  else if (id === 'TPE1') out.artist = readTextFrame(payload)
  else if (id === 'TALB') out.album = readTextFrame(payload)
  else if (id === 'TYER' || id === 'TDRC') {
    const raw = readTextFrame(payload)
    out.year = raw?.slice(0, 4)
  } else if (id === 'TCON') {
    const raw = readTextFrame(payload)
    if (raw) out.genre = stripGenreRefs(raw)
  } else if (id === 'APIC' && !out.cover) {
    const cover = readApicFrame(payload)
    if (cover) out.cover = cover
  }
}

function readTextFrame(payload: Uint8Array): string | undefined {
  if (payload.length < 1) return undefined
  const encoding = payload[0]
  const slice = payload.subarray(1)
  const text = decodeText(slice, encoding)
  const trimmed = text.replace(/\0+$/, '').trim()
  return trimmed.length ? trimmed : undefined
}

function readApicFrame(
  payload: Uint8Array,
): { blob: Blob; mime: string } | undefined {
  if (payload.length < 4) return undefined
  const encoding = payload[0]
  let cursor = 1
  const mimeEnd = payload.indexOf(0, cursor)
  if (mimeEnd < 0) return undefined
  const mime = decodeText(
    payload.subarray(cursor, mimeEnd),
    0,
  ).trim()
  cursor = mimeEnd + 1
  if (cursor >= payload.length) return undefined
  cursor += 1
  const descEnd = findNullTerm(payload, cursor, encoding)
  if (descEnd < 0) return undefined
  cursor =
    descEnd + (encoding === 1 || encoding === 2 ? 2 : 1)
  if (cursor >= payload.length) return undefined
  const data = payload.subarray(cursor)
  if (!data.length || data.length > COVER_MAX_BYTES) {
    return undefined
  }
  const finalMime = mime || guessMimeFromBytes(data) || 'image/jpeg'
  const owned = new ArrayBuffer(data.byteLength)
  new Uint8Array(owned).set(data)
  const blob = new Blob([owned], {
    type: finalMime,
  })
  return { blob, mime: finalMime }
}

function decodeText(
  bytes: Uint8Array,
  encoding: number,
): string {
  if (encoding === 0) {
    return new TextDecoder('iso-8859-1').decode(bytes)
  }
  if (encoding === 1) {
    if (bytes.length < 2) return ''
    const bom0 = bytes[0]
    const bom1 = bytes[1]
    const isBE = bom0 === 0xfe && bom1 === 0xff
    const isLE = bom0 === 0xff && bom1 === 0xfe
    const decoder = new TextDecoder(
      isBE ? 'utf-16be' : 'utf-16le',
    )
    return decoder.decode(
      isBE || isLE ? bytes.subarray(2) : bytes,
    )
  }
  if (encoding === 2) {
    return new TextDecoder('utf-16be').decode(bytes)
  }
  return new TextDecoder('utf-8').decode(bytes)
}

function findNullTerm(
  bytes: Uint8Array,
  start: number,
  encoding: number,
): number {
  if (encoding === 1 || encoding === 2) {
    for (let i = start; i + 1 < bytes.length; i += 2) {
      if (bytes[i] === 0 && bytes[i + 1] === 0) return i
    }
    return -1
  }
  for (let i = start; i < bytes.length; i++) {
    if (bytes[i] === 0) return i
  }
  return -1
}

function readSynchsafe(bytes: Uint8Array, offset: number): number {
  return (
    ((bytes[offset] & 0x7f) << 21) |
    ((bytes[offset + 1] & 0x7f) << 14) |
    ((bytes[offset + 2] & 0x7f) << 7) |
    (bytes[offset + 3] & 0x7f)
  )
}

function readUint32BE(bytes: Uint8Array, offset: number): number {
  return (
    (bytes[offset] << 24) |
    (bytes[offset + 1] << 16) |
    (bytes[offset + 2] << 8) |
    bytes[offset + 3]
  ) >>> 0
}

function stripGenreRefs(value: string): string {
  return value
    .replace(/\((\d+)\)/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function guessMimeFromBytes(data: Uint8Array): string | null {
  if (
    data.length >= 3 &&
    data[0] === 0xff &&
    data[1] === 0xd8 &&
    data[2] === 0xff
  ) {
    return 'image/jpeg'
  }
  if (
    data.length >= 8 &&
    data[0] === 0x89 &&
    data[1] === 0x50 &&
    data[2] === 0x4e &&
    data[3] === 0x47
  ) {
    return 'image/png'
  }
  return null
}

const FILENAME_SEPARATORS = /\s+[-–—]\s+/

function parseFilename(name: string): Partial<AudioMetadata> {
  const stem = name.replace(/\.[a-z0-9]+$/i, '').trim()
  if (!stem) return {}
  const cleaned = stem.replace(/^\d+[\s._-]+/, '')
  const parts = cleaned.split(FILENAME_SEPARATORS)
  if (parts.length >= 2) {
    const artist = parts[0].trim()
    const title = parts.slice(1).join(' - ').trim()
    if (artist && title) return { artist, title }
  }
  return cleaned.length ? { title: cleaned } : {}
}

export async function coverBlobToFile(
  cover: { blob: Blob; mime: string },
  baseName = 'cover',
): Promise<File> {
  const ext =
    cover.mime === 'image/png'
      ? 'png'
      : cover.mime === 'image/webp'
        ? 'webp'
        : 'jpg'
  return new File([cover.blob], `${baseName}.${ext}`, {
    type: cover.mime,
  })
}
