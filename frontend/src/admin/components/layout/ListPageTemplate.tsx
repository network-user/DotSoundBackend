import { ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
  kpis?: ReactNode
  filters?: ReactNode
  toolbarHint?: ReactNode
  pagination?: ReactNode
  children: ReactNode
}

export function ListPageTemplate({
  title,
  subtitle,
  actions,
  kpis,
  filters,
  toolbarHint,
  pagination,
  children,
}: Props) {
  return (
    <section className="admin-list-page">
      <header className="admin-list-page__head">
        <div className="admin-list-page__head-text">
          <h1 className="admin-list-page__title">{title}</h1>
          {subtitle ? (
            <p className="admin-list-page__subtitle">{subtitle}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="admin-list-page__actions">{actions}</div>
        ) : null}
      </header>

      {kpis ? <div className="admin-list-page__kpis">{kpis}</div> : null}

      {filters || toolbarHint ? (
        <div className="admin-list-page__toolbar">
          {filters ? (
            <div className="admin-list-page__filters">{filters}</div>
          ) : null}
          {toolbarHint ? (
            <div className="admin-list-page__hint">{toolbarHint}</div>
          ) : null}
        </div>
      ) : null}

      <div className="admin-list-page__body">{children}</div>

      {pagination ? (
        <div className="admin-list-page__pagination">{pagination}</div>
      ) : null}
    </section>
  )
}
