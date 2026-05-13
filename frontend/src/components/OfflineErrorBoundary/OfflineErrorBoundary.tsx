import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State {
  error: Error | null
}

interface Props {
  children: ReactNode
}

function isLikelyNetworkError(err: Error): boolean {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return true
  }
  const msg = (err.message || '').toLowerCase()
  return /network|fetch|load|chunk/.test(msg)
}

export class OfflineErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (typeof console !== 'undefined') {
      console.error('[OfflineErrorBoundary]', error)
      console.error(
        '[OfflineErrorBoundary] component stack:',
        info.componentStack,
      )
    }
  }

  private handleRetry = (): void => {
    this.setState({ error: null })
  }

  private handleOpenLibrary = (): void => {
    if (typeof window !== 'undefined') {
      window.location.assign('/mini_app/profile?tab=offline')
    }
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children
    const offlineLike = isLikelyNetworkError(error)
    return (
      <div
        role="alert"
        style={{
          minHeight: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          gap: '12px',
          textAlign: 'center',
          background: '#000',
          color: '#fff',
          fontFamily:
            'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        }}
      >
        <div
          style={{
            width: '56px',
            height: '56px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            opacity: 0.9,
          }}
          aria-hidden
        >
          {offlineLike ? (
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M1.42 9a16 16 0 0 1 21.16 0" />
              <path d="M5 12.55a11 11 0 0 1 14.08 0" />
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
              <line x1="12" y1="20" x2="12.01" y2="20" />
              <line x1="2" y1="2" x2="22" y2="22" />
            </svg>
          ) : (
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          )}
        </div>
        <h1
          style={{
            fontSize: '20px',
            fontWeight: 600,
            margin: 0,
          }}
        >
          {offlineLike
            ? 'Похоже, нет связи'
            : 'Что-то пошло не так'}
        </h1>
        <p
          style={{
            fontSize: '14px',
            opacity: 0.7,
            maxWidth: '320px',
            margin: 0,
          }}
        >
          {offlineLike
            ? 'Можно слушать сохранённые треки оффлайн.'
            : 'Попробуйте перезагрузить страницу.'}
        </p>
        <div
          style={{
            display: 'flex',
            gap: '8px',
            marginTop: '12px',
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}
        >
          <button
            type="button"
            onClick={this.handleRetry}
            style={{
              padding: '10px 16px',
              borderRadius: '999px',
              border: '1px solid rgba(255,255,255,0.2)',
              background: 'transparent',
              color: '#fff',
              fontSize: '14px',
              cursor: 'pointer',
            }}
          >
            Повторить
          </button>
          {offlineLike ? (
            <button
              type="button"
              onClick={this.handleOpenLibrary}
              style={{
                padding: '10px 16px',
                borderRadius: '999px',
                border: 'none',
                background: '#fff',
                color: '#000',
                fontSize: '14px',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Открыть оффлайн-библиотеку
            </button>
          ) : (
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: '10px 16px',
                borderRadius: '999px',
                border: 'none',
                background: '#fff',
                color: '#000',
                fontSize: '14px',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Перезагрузить
            </button>
          )}
        </div>
      </div>
    )
  }
}
