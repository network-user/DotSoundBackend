import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useState,
} from 'react'
import { Press } from '@/components/ui/Press'
import { Sheet } from '@/components/ui/Sheet'
import { adminApi } from '../../lib/adminApi'
import { TotpInput } from './TotpInput'

interface StepUpRequest {
  action: string
  resolve: (ok: boolean) => void
}

interface StepUpContextValue {
  request: (action: string) => Promise<boolean>
}

const Ctx = createContext<StepUpContextValue>({
  request: async () => false,
})

export function useStepUp() {
  return useContext(Ctx)
}

export function StepUpProvider({
  children,
}: {
  children: ReactNode
}) {
  const [pending, setPending] =
    useState<StepUpRequest | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] =
    useState<string | null>(null)

  const request = useCallback(
    (action: string) =>
      new Promise<boolean>((resolve) => {
        setCode('')
        setError(null)
        setPending({ action, resolve })
      }),
    [],
  )

  function close(ok: boolean) {
    pending?.resolve(ok)
    setPending(null)
    setCode('')
    setError(null)
  }

  async function handleConfirm() {
    if (!pending || code.length < 6) return
    setBusy(true)
    setError(null)
    try {
      await adminApi.stepUp({
        code,
        action: pending.action,
      })
      close(true)
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : String(err)
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Ctx.Provider value={{ request }}>
      {children}
      <Sheet
        open={pending !== null}
        onClose={() => close(false)}
        ariaLabel="Step-up authentication"
      >
        <div className="admin-stepup">
          <h3>Confirm action</h3>
          <p className="admin-auth-hint">
            Action <code>{pending?.action}</code>{' '}
            requires a fresh authenticator code.
          </p>
          <TotpInput
            value={code}
            onChange={setCode}
            onComplete={handleConfirm}
            autoFocus
            disabled={busy}
          />
          {error && (
            <div className="admin-auth-error">
              {error}
            </div>
          )}
          <div className="admin-stepup-actions">
            <Press
              variant="ghost"
              onClick={() => close(false)}
              disabled={busy}
            >
              Cancel
            </Press>
            <Press
              variant="primary"
              onClick={handleConfirm}
              disabled={
                busy || code.length < 6
              }
            >
              {busy ? 'Confirming…' : 'Confirm'}
            </Press>
          </div>
        </div>
      </Sheet>
    </Ctx.Provider>
  )
}
