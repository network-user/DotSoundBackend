interface Props {
  name: string
  size?: number
  className?: string
}

const PATHS: Record<string, string> = {
  play: 'M6 4l12 8-12 8V4z',
  pause: 'M6 4h4v16H6zm8 0h4v16h-4z',
  'skip-back':
    'M19 20L9 12l10-8v16zM5 4v16',
  'skip-forward':
    'M5 4l10 8-10 8V4zM19 4v16',
  heart:
    'M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 000-7.78z',
  'heart-outline':
    'M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 000-7.78z',
  'thumbs-down':
    'M10 15v4a3 3 0 003 3l4-9V2H5.72a2 2 0 00-2 1.7l-1.38 9A2 2 0 004.32 15H10zm10-13h2.67A2.31 2.31 0 0125 4.31v7.38',
  music: 'M9 18V5l12-2v13M9 18a3 3 0 11-6 0 3 3 0 016 0zm12-2a3 3 0 11-6 0 3 3 0 016 0z',
  search:
    'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  home: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0v-6m-2 0h4',
  upload:
    'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m14-7l-5-5-5 5m5-5v12',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  user: 'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2m8-10a4 4 0 100-8 4 4 0 000 8z',
  settings:
    'M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z',
  x: 'M18 6L6 18M6 6l12 12',
  share:
    'M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8m-4-6l-4-4-4 4m4-4v13',
  link: 'M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71',
  image:
    'M21 19V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2zM8.5 10a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM21 15l-5-5L5 21',
  sparkle:
    'M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74L12 2z',
  video:
    'M23 7l-7 5 7 5V7zM14 5H3a2 2 0 00-2 2v10a2 2 0 002 2h11a2 2 0 002-2V7a2 2 0 00-2-2z',
  flag: 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zm0 7v-7',
  lock: 'M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zm-3-4V7a4 4 0 10-8 0v4',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 100 6 3 3 0 000-6z',
  trash:
    'M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2',
  chevron:
    'M9 18l6-6-6-6',
  maximize:
    'M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3',
  'volume-off': 'M11 5L6 9H2v6h4l5 4V5z M23 9l-6 6m0-6l6 6',
  'volume-low':
    'M11 5L6 9H2v6h4l5 4V5z M15.54 8.46a5 5 0 010 7.07',
  'volume-high':
    'M11 5L6 9H2v6h4l5 4V5z M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07',
  eq: 'M4 21V14m0-4V3m8 18v-7m0-4V3m8 18v-3m0-4V3M1 14h6M9 10h6M17 17h6',
  edit: 'M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7 M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z',
  text: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
  undo: 'M3 10h10a5 5 0 010 10H7 M3 10l4-4m-4 4l4 4',
  'rewind-5':
    'M1 4v6h6 M3.51 15a9 9 0 105.66-8.49L3 10',
  'forward-5':
    'M23 4v6h-6 M20.49 15a9 9 0 11-5.66-8.49L21 10',
  info: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 16v-4m0-4h.01',
  'log-out':
    'M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4m7 14l5-5-5-5m5 5H9',
}

const FILLED_ICONS = new Set(['heart', 'play'])

export function Icon({
  name,
  size = 20,
  className,
}: Props) {
  const d = PATHS[name]
  if (!d) return null
  const isFilled = FILLED_ICONS.has(name)

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={isFilled ? 'currentColor' : 'none'}
      stroke={
        isFilled ? 'none' : 'currentColor'
      }
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {d.split(' M').map((seg, i) => (
        <path
          key={i}
          d={i === 0 ? seg : `M${seg}`}
        />
      ))}
    </svg>
  )
}
