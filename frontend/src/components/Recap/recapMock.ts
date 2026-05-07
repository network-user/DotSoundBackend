/**
 * TODO(redesign-2026): replace with API payload when recap endpoint ships.
 * UI only; no PrivateCore internals.
 */

export interface RecapMockArtist {
  name: string
  plays: number
}

export interface RecapMockTrack {
  title: string
  artist: string
  bpm: number
  cover: string
}

export interface RecapMockGenre {
  label: string
  pct: number
}

export interface RecapMockMoodSlice {
  labelKey: string
  value: number
}

export const RECAP_MOCK_COVERS: readonly string[] = [
  'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect fill="#242424" width="320" height="320"/><circle cx="160" cy="140" r="56" fill="#3a3a3a"/></svg>',
    ),
  'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect fill="#1e1e1e" width="320" height="320"/><rect x="72" y="96" width="176" height="120" rx="8" fill="#353535"/></svg>',
    ),
  'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect fill="#2c2c2c" width="320" height="320"/><path d="M80 200 L240 200 L160 88 Z" fill="#454545"/></svg>',
    ),
  'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect fill="#222" width="320" height="320"/><ellipse cx="160" cy="150" rx="90" ry="72" fill="#3d3d3d"/></svg>',
    ),
  'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect fill="#262626" width="320" height="320"/><line x1="64" y1="220" x2="256" y2="96" stroke="#4a4a4a" stroke-width="24"/></svg>',
    ),
]

export const RECAP_MOCK: {
  totalMinutes: number
  artists: RecapMockArtist[]
  tracks: RecapMockTrack[]
  mostPlayed: RecapMockTrack
  genres: RecapMockGenre[]
  mood: RecapMockMoodSlice[]
} = {
  totalMinutes: 12_480,
  artists: [
    { name: 'North Echo', plays: 412 },
    { name: 'Glass Horizon', plays: 305 },
    { name: 'Mono Relay', plays: 268 },
  ],
  tracks: [
    {
      title: 'Parallel Lines',
      artist: 'North Echo',
      bpm: 118,
      cover: RECAP_MOCK_COVERS[0]!,
    },
    {
      title: 'Signal Drift',
      artist: 'Glass Horizon',
      bpm: 128,
      cover: RECAP_MOCK_COVERS[1]!,
    },
    {
      title: 'Quiet Static',
      artist: 'Mono Relay',
      bpm: 92,
      cover: RECAP_MOCK_COVERS[2]!,
    },
    {
      title: 'Bloom Fade',
      artist: 'North Echo',
      bpm: 110,
      cover: RECAP_MOCK_COVERS[3]!,
    },
    {
      title: 'Veil',
      artist: 'Glass Horizon',
      bpm: 104,
      cover: RECAP_MOCK_COVERS[4]!,
    },
  ],
  mostPlayed: {
    title: 'Parallel Lines',
    artist: 'North Echo',
    bpm: 118,
    cover: RECAP_MOCK_COVERS[0]!,
  },
  genres: [
    { label: 'Electronic', pct: 0.34 },
    { label: 'Ambient', pct: 0.22 },
    { label: 'Indie', pct: 0.18 },
    { label: 'Hip-hop', pct: 0.14 },
    { label: 'Other', pct: 0.12 },
  ],
  mood: [
    { labelKey: 'night', value: 38 },
    { labelKey: 'morning', value: 18 },
    { labelKey: 'day', value: 28 },
    { labelKey: 'evening', value: 16 },
  ],
}

export interface RecapSnapshotArtist {
  name: string
  plays: number
  coverUrl: string
}

export interface RecapSnapshotTrack {
  title: string
  artist: string
  coverUrl: string
  bpm: number
}

export interface RecapSnapshotGenre {
  label: string
  share01: number
}

export interface RecapSnapshotMood {
  labelKey: string
  hours: number
}

export interface RecapSnapshotMock {
  yearLabel: string
  totalMinutes: number
  topArtists: RecapSnapshotArtist[]
  topTracks: RecapSnapshotTrack[]
  mostPlayed: RecapSnapshotTrack
  genres: RecapSnapshotGenre[]
  moodByDaypart: RecapSnapshotMood[]
  friendsHeadlineKey: string
  friendsYouHours: number
  friendsAvgHours: number
  shareCoverUrls: string[]
}

export function getRecapSnapshotMock(): RecapSnapshotMock {
  const nCov = RECAP_MOCK_COVERS.length
  const topArtists: RecapSnapshotArtist[] =
    RECAP_MOCK.artists.map((a, i) => ({
      name: a.name,
      plays: a.plays,
      coverUrl:
        RECAP_MOCK_COVERS[i % nCov] ?? RECAP_MOCK_COVERS[0]!,
    }))
  const mapTrack = (t: RecapMockTrack): RecapSnapshotTrack => ({
    title: t.title,
    artist: t.artist,
    coverUrl: t.cover,
    bpm: t.bpm,
  })
  return {
    yearLabel: 'DotSound',
    totalMinutes: RECAP_MOCK.totalMinutes,
    topArtists,
    topTracks: RECAP_MOCK.tracks.map(mapTrack),
    mostPlayed: mapTrack(RECAP_MOCK.mostPlayed),
    genres: RECAP_MOCK.genres.map((g) => ({
      label: g.label,
      share01: g.pct,
    })),
    moodByDaypart: RECAP_MOCK.mood.map((row) => ({
      labelKey: row.labelKey,
      hours: row.value,
    })),
    friendsHeadlineKey: 'friendsBenchmark',
    friendsYouHours: 214,
    friendsAvgHours: 168,
    shareCoverUrls: RECAP_MOCK.tracks
      .slice(0, 4)
      .map((row) => row.cover),
  }
}
