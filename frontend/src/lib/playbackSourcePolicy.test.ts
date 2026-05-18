import { describe, expect, it } from 'vitest'

import { shouldUseInternalHlsPlayback } from './playbackSourcePolicy'

describe('shouldUseInternalHlsPlayback', () => {
  it('routes ready UGC tracks through HLS', () => {
    expect(
      shouldUseInternalHlsPlayback({
        access_mode: 'internal_stream',
        is_public: true,
        has_hls: true,
        hls_manifest_key: 'hls/123/master.m3u8',
      }),
    ).toBe(true)
  })

  it('skips HLS for UGC tracks still mid-transcode', () => {
    expect(
      shouldUseInternalHlsPlayback({
        access_mode: 'internal_stream',
        is_public: true,
        has_hls: false,
        hls_manifest_key: null,
      }),
    ).toBe(false)
  })

  it('skips HLS for third-party streams', () => {
    expect(
      shouldUseInternalHlsPlayback({
        access_mode: 'third_party_stream',
        is_public: true,
        has_hls: true,
        hls_manifest_key: 'hls/123/master.m3u8',
      }),
    ).toBe(false)
  })

  it('skips HLS for private (non-public) tracks', () => {
    expect(
      shouldUseInternalHlsPlayback({
        access_mode: 'internal_stream',
        is_public: false,
        has_hls: true,
        hls_manifest_key: 'hls/123/master.m3u8',
      }),
    ).toBe(false)
  })

  it('treats an empty manifest key the same as has_hls=false', () => {
    expect(
      shouldUseInternalHlsPlayback({
        access_mode: 'internal_stream',
        is_public: true,
        has_hls: true,
        hls_manifest_key: '',
      }),
    ).toBe(false)
  })
})
