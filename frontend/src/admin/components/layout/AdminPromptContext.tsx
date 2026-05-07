import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'

type ConfirmOpts = {
  title?: string
  danger?: boolean
}

type AlertOpts = {
  title?: string
}

type PromptState =
  | {
      kind: 'confirm'
      body: string
      title?: string
      danger: boolean
      onFinish: (v: boolean) => void
    }
  | {
      kind: 'alert'
      body: string
      title?: string
      onFinish: () => void
    }

interface Ctx {
  showConfirm: (
    body: string,
    opts?: ConfirmOpts,
  ) => Promise<boolean>
  showAlert: (
    body: string,
    opts?: AlertOpts,
  ) => Promise<void>
}

const AdminPromptCtx = createContext<Ctx | null>(null)

export function useAdminPrompt(): Ctx {
  const c = useContext(AdminPromptCtx)
  if (!c) {
    throw new Error(
      'useAdminPrompt requires AdminPromptProvider',
    )
  }
  return c
}

function PromptHost({ state }: { state: PromptState | null }) {
  const { t } = useTranslation()
  const titleId = useId()
  const firstBtnRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!state) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      if (state.kind === 'confirm') {
        state.onFinish(false)
      } else {
        state.onFinish()
      }
    }
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [state])

  useEffect(() => {
    if (!state) return
    firstBtnRef.current?.focus()
  }, [state])

  if (!state) return null

  const isConfirm = state.kind === 'confirm'
  return (
    <div
      className="admin-modal-overlay"
      style={{ zIndex: 10001 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          if (isConfirm) {
            state.onFinish(false)
          } else {
            state.onFinish()
          }
        }
      }}
    >
      <div
        className="admin-modal admin-prompt"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={state.title ? titleId : undefined}
        aria-label={
          state.title
            ? undefined
            : t('admin.prompt.dialogLabel')
        }
        onClick={(e) => e.stopPropagation()}
      >
        {state.title ? (
          <h3 id={titleId} className="admin-prompt__title">
            {state.title}
          </h3>
        ) : null}
        <p className="admin-prompt__body">{state.body}</p>
        <div className="admin-prompt__actions">
          {isConfirm ? (
            <>
              <MotionPress
                ref={firstBtnRef}
                variant="ghost"
                onClick={() => state.onFinish(false)}
              >
                {t('admin.common.cancel')}
              </MotionPress>
              <MotionPress
                variant="primary"
                className={
                  state.danger
                    ? 'admin-prompt__btn--danger'
                    : undefined
                }
                onClick={() => state.onFinish(true)}
              >
                {t('admin.common.confirm')}
              </MotionPress>
            </>
          ) : (
            <MotionPress
              ref={firstBtnRef}
              variant="primary"
              onClick={() => state.onFinish()}
            >
              {t('admin.common.ok')}
            </MotionPress>
          )}
        </div>
      </div>
    </div>
  )
}

export function AdminPromptProvider({
  children,
}: {
  children: ReactNode
}) {
  const [state, setState] = useState<PromptState | null>(null)

  const showConfirm = useCallback(
    (body: string, opts?: ConfirmOpts) => {
      return new Promise<boolean>((outerResolve) => {
        setState({
          kind: 'confirm',
          body,
          title: opts?.title,
          danger: opts?.danger ?? false,
          onFinish: (v) => {
            setState(null)
            outerResolve(v)
          },
        })
      })
    },
    [],
  )

  const showAlert = useCallback(
    (body: string, opts?: AlertOpts) => {
      return new Promise<void>((outerResolve) => {
        setState({
          kind: 'alert',
          body,
          title: opts?.title,
          onFinish: () => {
            setState(null)
            outerResolve()
          },
        })
      })
    },
    [],
  )

  return (
    <AdminPromptCtx.Provider
      value={{ showConfirm, showAlert }}
    >
      {children}
      <PromptHost state={state} />
    </AdminPromptCtx.Provider>
  )
}
