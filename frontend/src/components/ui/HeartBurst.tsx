import { m, useReducedMotion } from '@/lib/motion'

interface Props {
  active: boolean
  size?: number
}

const SPARK_COUNT = 6

const SPARKS = Array.from(
  { length: SPARK_COUNT },
  (_, i) => {
    const angle =
      (i / SPARK_COUNT) * Math.PI * 2 - Math.PI / 2
    return {
      x: Math.cos(angle),
      y: Math.sin(angle),
    }
  },
)

export function HeartBurst({
  active,
  size = 18,
}: Props) {
  const reduce = useReducedMotion()
  if (!active || reduce) return null
  const distance = size * 1.55
  return (
    <span
      className="heart-burst"
      aria-hidden="true"
    >
      {SPARKS.map((s, i) => (
        <m.span
          key={i}
          className="heart-burst__spark"
          initial={{
            x: 0,
            y: 0,
            opacity: 0.9,
            scale: 0.5,
          }}
          animate={{
            x: s.x * distance,
            y: s.y * distance,
            opacity: 0,
            scale: 1,
          }}
          transition={{
            duration: 0.46,
            ease: [0.16, 1, 0.3, 1],
          }}
        />
      ))}
    </span>
  )
}
