import {
  m,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import { Icon } from '@/components/Icon/Icon'

export interface MorphIconProps {
  name: string
  filled?: boolean
  size?: number
  className?: string
}

interface MorphPair {
  outline: string
  filled: string
}

const PAIRS: Record<string, MorphPair> = {
  heart: {
    outline:
      'M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 000-7.78z',
    filled:
      'M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 000-7.78z',
  },
  play: {
    outline: 'M7 4.5v15l13-7.5L7 4.5z',
    filled: 'M7 4.5v15l13-7.5L7 4.5z',
  },
  pause: {
    outline: 'M7 4h4v16H7zm6 0h4v16h-4z',
    filled: 'M7 4h4v16H7zm6 0h4v16h-4z',
  },
  star: {
    outline:
      'M12 2.5l3 6.1 6.7 1-4.85 4.7 1.15 6.7L12 17.8 5.99 21l1.16-6.7L2.3 9.6l6.7-1L12 2.5z',
    filled:
      'M12 2.5l3 6.1 6.7 1-4.85 4.7 1.15 6.7L12 17.8 5.99 21l1.16-6.7L2.3 9.6l6.7-1L12 2.5z',
  },
  bookmark: {
    outline:
      'M6 3h12v18l-6-4-6 4V3z',
    filled:
      'M6 3h12v18l-6-4-6 4V3z',
  },
  home: {
    outline:
      'M3 11l9-8 9 8v9a2 2 0 01-2 2h-3v-7H8v7H5a2 2 0 01-2-2v-9z',
    filled:
      'M3 11l9-8 9 8v9a2 2 0 01-2 2h-3v-7H8v7H5a2 2 0 01-2-2v-9z',
  },
  search: {
    outline:
      'M21 21l-5.4-5.4M16 10.5A5.5 5.5 0 115 10.5a5.5 5.5 0 0111 0z',
    filled:
      'M21 21l-5.4-5.4M16 10.5A5.5 5.5 0 115 10.5a5.5 5.5 0 0111 0z',
  },
  library: {
    outline:
      'M4 4h3v16H4zM10 4h3v16h-3zM16 5l3-1 3 17-3 1-3-17z',
    filled:
      'M4 4h3v16H4zM10 4h3v16h-3zM16 5l3-1 3 17-3 1-3-17z',
  },
  chats: {
    outline:
      'M21 11.5A8.5 8.5 0 0112.5 20a8.4 8.4 0 01-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 01-.9-3.8A8.5 8.5 0 0121 11.5z',
    filled:
      'M21 11.5A8.5 8.5 0 0112.5 20a8.4 8.4 0 01-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 01-.9-3.8A8.5 8.5 0 0121 11.5z',
  },
  profile: {
    outline:
      'M12 12a4 4 0 100-8 4 4 0 000 8zm-7 9a7 7 0 0114 0H5z',
    filled:
      'M12 12a4 4 0 100-8 4 4 0 000 8zm-7 9a7 7 0 0114 0H5z',
  },
  radio: {
    outline:
      'M12 12a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM8 12a4 4 0 018 0M5 12a7 7 0 0114 0M3 12a9 9 0 0118 0',
    filled:
      'M12 12a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM8 12a4 4 0 018 0M5 12a7 7 0 0114 0M3 12a9 9 0 0118 0',
  },
  'users-following': {
    outline:
      'M9 11a4 4 0 100-8 4 4 0 000 8zM1 21a8 8 0 0116 0H1zM18 7l2 2 4-4',
    filled:
      'M9 11a4 4 0 100-8 4 4 0 000 8zM1 21a8 8 0 0116 0H1zM18 7l2 2 4-4',
  },
  flame: {
    outline:
      'M12 2c1 4 5 5 5 10a5 5 0 11-10 0c0-2 1-3 1-5 0-3-2-3-2-5 2 0 3 1 3 1 0-1 1-2 3-1z',
    filled:
      'M12 2c1 4 5 5 5 10a5 5 0 11-10 0c0-2 1-3 1-5 0-3-2-3-2-5 2 0 3 1 3 1 0-1 1-2 3-1z',
  },
  'thumbs-down': {
    outline:
      'M10 15v4a3 3 0 003 3l4-9V2H5.72a2 2 0 00-2 1.7l-1.38 9A2 2 0 004.32 15H10zm10-13h2a2 2 0 012 2v7a2 2 0 01-2 2h-2',
    filled:
      'M10 15v4a3 3 0 003 3l4-9V2H5.72a2 2 0 00-2 1.7l-1.38 9A2 2 0 004.32 15H10zm10-13h2a2 2 0 012 2v7a2 2 0 01-2 2h-2',
  },
  calendar: {
    outline:
      'M7 2v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7zM5 10h14v10H5V10z',
    filled:
      'M7 2v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7zM5 10h14v10H5V10z',
  },
}

export function MorphIcon({
  name,
  filled = false,
  size = 20,
  className,
}: MorphIconProps) {
  const reduce = useReducedMotion()
  const pair = PAIRS[name]

  if (!pair) {
    return (
      <Icon
        name={filled ? `${name}-fill` : name}
        size={size}
        className={className}
      />
    )
  }

  const target = filled ? pair.filled : pair.outline

  return (
    <m.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ fill: 'currentColor', stroke: 'currentColor' }}
      animate={{
        fillOpacity: filled ? 1 : 0,
        strokeOpacity: filled ? 0 : 1,
        strokeWidth: filled ? 0 : 2,
      }}
      transition={reduce ? { duration: 0 } : TWEEN_FAST}
    >
      <m.path
        key={name}
        animate={{ d: target }}
        initial={false}
        transition={
          reduce
            ? { duration: 0 }
            : { duration: 0.24, ease: [0.22, 0.61, 0.36, 1] }
        }
        d={target}
      />
    </m.svg>
  )
}
