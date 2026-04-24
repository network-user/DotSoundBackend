import {
  ChangeEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  onComplete?: (value: string) => void
  autoFocus?: boolean
  disabled?: boolean
}

export function TotpInput({
  value,
  onChange,
  onComplete,
  autoFocus,
  disabled,
}: Props) {
  const [cells, setCells] = useState<string[]>(
    () =>
      Array.from(
        { length: 6 },
        (_, i) => value[i] || '',
      ),
  )
  const refs = useRef<
    Array<HTMLInputElement | null>
  >([])

  useEffect(() => {
    setCells(
      Array.from(
        { length: 6 },
        (_, i) => value[i] || '',
      ),
    )
  }, [value])

  useEffect(() => {
    if (autoFocus) {
      refs.current[0]?.focus()
    }
  }, [autoFocus])

  function commit(next: string[]) {
    setCells(next)
    const joined = next.join('')
    onChange(joined)
    if (joined.length === 6) {
      onComplete?.(joined)
    }
  }

  function handleChange(
    index: number,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const raw = event.target.value
      .replace(/\D/g, '')
      .slice(0, 6)
    if (raw.length > 1) {
      const filled = Array.from(
        { length: 6 },
        (_, i) => raw[i] || '',
      )
      commit(filled)
      refs.current[
        Math.min(raw.length, 5)
      ]?.focus()
      return
    }
    const next = [...cells]
    next[index] = raw
    commit(next)
    if (raw && index < 5) {
      refs.current[index + 1]?.focus()
    }
  }

  function handleKeyDown(
    index: number,
    event: KeyboardEvent<HTMLInputElement>,
  ) {
    if (event.key === 'Enter') {
      const joined = cells.join('')
      if (joined.length === 6) {
        event.preventDefault()
        onComplete?.(joined)
      }
      return
    }
    if (
      event.key === 'Backspace' &&
      !cells[index] &&
      index > 0
    ) {
      const next = [...cells]
      next[index - 1] = ''
      commit(next)
      refs.current[index - 1]?.focus()
    }
  }

  return (
    <div
      className="admin-totp-input"
      role="group"
      aria-label="Six digit code"
    >
      {cells.map((cell, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el
          }}
          inputMode="numeric"
          maxLength={1}
          value={cell}
          disabled={disabled}
          onChange={(e) => handleChange(index, e)}
          onKeyDown={(e) =>
            handleKeyDown(index, e)
          }
          autoComplete="one-time-code"
          aria-label={`Digit ${index + 1}`}
        />
      ))}
    </div>
  )
}
