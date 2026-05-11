import { Component, type ReactNode } from 'react'

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

  componentDidCatch(error: Error): void {
    if (typeof console !== 'undefined') {
      console.error('[OfflineErrorBoundary]', error)
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
        <div style={{ fontSize: '48px', lineHeight: 1 }}>
          {offlineLike ? '📡' : '⚠️'}
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
          {offlineLike && (
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
          )}
        </div>
      </div>
    )
  }
}
