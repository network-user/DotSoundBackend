import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../../lib/adminApi'
import { StatusPill } from './StatusPill'

type Mode = 'direct' | 'proxy' | 'tor' | 'hybrid'

const MODE_LABEL: Record<Mode, string> = {
  direct: 'Direct',
  proxy: 'Proxy',
  tor: 'Tor',
  hybrid: 'Hybrid',
}

const MODE_TONE: Record<Mode, 'ok' | 'warn' | 'error' | 'unknown'> = {
  direct: 'warn',
  proxy: 'ok',
  tor: 'ok',
  hybrid: 'ok',
}

function MiniBar({
  segments,
}: {
  segments: Array<{ key: string; value: number; tone: string }>
}) {
  const total = segments.reduce((acc, s) => acc + s.value, 0)
  if (total === 0) {
    return <div className="admin-outbound__bar admin-outbound__bar--empty" />
  }
  return (
    <div className="admin-outbound__bar" role="img" aria-label="response distribution">
      {segments
        .filter((s) => s.value > 0)
        .map((s) => (
          <span
            key={s.key}
            className={`admin-outbound__bar-seg admin-outbound__bar-seg--${s.tone}`}
            style={{ flex: s.value }}
            title={`${s.key}: ${s.value}`}
          />
        ))}
    </div>
  )
}

function classifyStatus(bucket: string): 'ok' | 'warn' | 'error' {
  if (bucket === '2xx' || bucket === '3xx') return 'ok'
  if (bucket === '4xx' || bucket === '401' || bucket === '403' || bucket === '404') {
    return 'warn'
  }
  return 'error'
}

function BreakerBadge({ state }: { state: string }) {
  const tone =
    state === 'open' ? 'error' : state === 'half_open' ? 'warn' : 'ok'
  return <StatusPill kind={tone}>{state}</StatusPill>
}

function formatRecentTs(ts: number): string {
  const raw = ts > 2_000_000_000_000 ? ts : ts * 1000
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return 'n/a'
  return d.toLocaleTimeString()
}

export function OutboundStatusPanel() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'outbound-status'],
    queryFn: () => adminApi.outboundStatus(),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })

  if (isLoading) {
    return (
      <section className="admin-card admin-outbound">
        <h2>{t('admin.dashboard.outbound.title', 'Outbound layer')}</h2>
        <div className="admin-skeleton admin-skeleton--card" />
      </section>
    )
  }

  if (error || !data) {
    return (
      <section className="admin-card admin-outbound">
        <h2>{t('admin.dashboard.outbound.title', 'Outbound layer')}</h2>
        <div className="admin-log-empty">
          {t('admin.dashboard.outbound.unavailable', 'Status unavailable')}
        </div>
      </section>
    )
  }

  if (!data.available) {
    return (
      <section className="admin-card admin-outbound">
        <h2>{t('admin.dashboard.outbound.title', 'Outbound layer')}</h2>
        <div className="admin-log-empty">
          {t(
            'admin.dashboard.outbound.notInstalled',
            'Outbound module is not installed in this deployment',
          )}
        </div>
      </section>
    )
  }

  const mode = (data.mode ?? 'direct') as Mode
  const services = data.services ?? []
  const burned = data.quarantine?.active_total ?? 0
  const totalRequests = services.reduce(
    (acc, s) => acc + (s.requests ?? 0),
    0,
  )
  const maxRequests = services.reduce(
    (acc, s) => Math.max(acc, s.requests ?? 0),
    1,
  )
  const rotationEvents = data.rotation_events ?? {}
  const rotationsTotal = Object.values(rotationEvents).reduce(
    (acc, v) => acc + Number(v ?? 0),
    0,
  )
  const recentRequests = data.recent_requests ?? []

  return (
    <section className="admin-card admin-outbound">
      <div className="admin-outbound__head">
        <div>
          <h2>{t('admin.dashboard.outbound.title', 'Outbound layer')}</h2>
          <p className="admin-card__sub">
            {t(
              'admin.dashboard.outbound.subtitle',
              'Internal anti-ban posture: transport mode, identity rotation, per-service health.',
            )}
          </p>
        </div>
        <div className={`admin-outbound__mode admin-outbound__mode--${mode}`}>
          <span
            className={`admin-outbound__mode-dot admin-outbound__mode-dot--${MODE_TONE[mode]}`}
            aria-hidden="true"
          />
          <span className="admin-outbound__mode-label">
            {MODE_LABEL[mode]}
          </span>
        </div>
      </div>

      <div className="admin-outbound__topology">
        <article
          className={`admin-outbound__node admin-outbound__node--${
            data.tor?.available ? 'on' : 'off'
          }`}
          title="Tor circuit transport"
        >
          <div className="admin-outbound__node-name">Tor</div>
          <div className="admin-outbound__node-state">
            {data.tor?.available
              ? t('admin.dashboard.outbound.on', 'on')
              : t('admin.dashboard.outbound.off', 'off')}
          </div>
          <div className="admin-outbound__node-meta">
            {data.tor?.available
              ? t('admin.dashboard.outbound.torDetail', {
                  defaultValue:
                    'NEWNYM every {{interval}}s · max {{cap}} uses',
                  interval: data.tor.newnym_min_interval_s,
                  cap: data.tor.circuit_uses_cap,
                })
              : t(
                  'admin.dashboard.outbound.torOffHint',
                  'control-port unreachable',
                )}
          </div>
        </article>
        <article
          className={`admin-outbound__node admin-outbound__node--${
            (data.proxies?.configured ?? 0) > 0 ? 'on' : 'off'
          }`}
          title="Static proxy pool"
        >
          <div className="admin-outbound__node-name">Proxy pool</div>
          <div className="admin-outbound__node-state">
            {data.proxies?.configured ?? 0}
          </div>
          <div className="admin-outbound__node-meta">
            {data.proxies?.prefer_tor
              ? t(
                  'admin.dashboard.outbound.proxyHintTorFirst',
                  'Tor first · proxies as fallback',
                )
              : t(
                  'admin.dashboard.outbound.proxyHintMix',
                  'mixed selection',
                )}
          </div>
        </article>
        <article
          className={`admin-outbound__node admin-outbound__node--${
            burned > 0 ? 'warn' : 'on'
          }`}
          title="Burned identities currently in quarantine"
        >
          <div className="admin-outbound__node-name">
            {t('admin.dashboard.outbound.quarantine', 'Quarantine')}
          </div>
          <div className="admin-outbound__node-state">{burned}</div>
          <div className="admin-outbound__node-meta">
            {t('admin.dashboard.outbound.quarantineDetail', {
              defaultValue: '{{tor}} circuits · {{proxy}} proxies',
              tor: data.quarantine?.active_tor_circuits ?? 0,
              proxy: data.quarantine?.active_proxies ?? 0,
            })}
          </div>
        </article>
        <article
          className="admin-outbound__node admin-outbound__node--neutral"
          title="Total outbound requests since process start"
        >
          <div className="admin-outbound__node-name">
            {t('admin.dashboard.outbound.requests', 'Requests')}
          </div>
          <div className="admin-outbound__node-state">{totalRequests}</div>
          <div className="admin-outbound__node-meta">
            {t('admin.dashboard.outbound.rotations', {
              defaultValue: '{{count}} rotations',
              count: rotationsTotal,
            })}
          </div>
        </article>
      </div>

      <div className="admin-outbound__topo-graph" aria-hidden="true">
        <svg viewBox="0 0 480 120" className="admin-outbound__svg">
          <defs>
            <linearGradient id="adm-out-link" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.05" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0.6" />
            </linearGradient>
          </defs>
          <g className="admin-outbound__svg-links">
            <line x1="60" y1="60" x2="220" y2="30" />
            <line x1="60" y1="60" x2="220" y2="90" />
            <line x1="220" y1="30" x2="420" y2="60" />
            <line x1="220" y1="90" x2="420" y2="60" />
          </g>
          <g>
            <circle cx="60" cy="60" r="22" className="admin-outbound__svg-node admin-outbound__svg-node--src" />
            <text x="60" y="63" textAnchor="middle" className="admin-outbound__svg-text">
              core
            </text>
            <circle cx="220" cy="30" r="18" className={`admin-outbound__svg-node ${data.tor?.available ? 'admin-outbound__svg-node--on' : 'admin-outbound__svg-node--off'}`} />
            <text x="220" y="33" textAnchor="middle" className="admin-outbound__svg-text">
              tor
            </text>
            <circle cx="220" cy="90" r="18" className={`admin-outbound__svg-node ${(data.proxies?.configured ?? 0) > 0 ? 'admin-outbound__svg-node--on' : 'admin-outbound__svg-node--off'}`} />
            <text x="220" y="93" textAnchor="middle" className="admin-outbound__svg-text">
              pool
            </text>
            <circle cx="420" cy="60" r="22" className="admin-outbound__svg-node admin-outbound__svg-node--dst" />
            <text x="420" y="63" textAnchor="middle" className="admin-outbound__svg-text">
              www
            </text>
          </g>
        </svg>
      </div>

      <div className="admin-outbound__services">
        <div className="admin-outbound__services-head">
          <h3>{t('admin.dashboard.outbound.servicesTitle', 'Per-service traffic')}</h3>
          <span className="admin-outbound__backend">
            {t('admin.dashboard.outbound.backend', 'backend')}: {data.backend}
          </span>
        </div>
        {services.length === 0 ? (
          <div className="admin-log-empty">
            {t(
              'admin.dashboard.outbound.noTraffic',
              'No outbound traffic recorded yet.',
            )}
          </div>
        ) : (
          <div className="admin-outbound__services-rows">
            {services.map((svc) => {
              const segments = Object.entries(svc.by_status).map(
                ([bucket, value]) => ({
                  key: bucket,
                  value: Number(value),
                  tone: classifyStatus(bucket),
                }),
              )
              const share = (svc.requests / maxRequests) * 100
              return (
                <div
                  key={svc.service}
                  className="admin-outbound__service-row"
                >
                  <div className="admin-outbound__service-name">
                    {svc.service}
                  </div>
                  <div
                    className="admin-outbound__service-volume"
                    aria-label={`${svc.requests} requests`}
                  >
                    <span
                      className="admin-outbound__service-volume-fill"
                      style={{ width: `${share}%` }}
                    />
                    <span className="admin-outbound__service-volume-count">
                      {svc.requests}
                    </span>
                  </div>
                  <div className="admin-outbound__service-bar">
                    <MiniBar segments={segments} />
                  </div>
                  <div className="admin-outbound__service-breaker">
                    <BreakerBadge state={svc.breaker} />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="admin-outbound__recent">
        <div className="admin-outbound__services-head">
          <h3>
            {t(
              'admin.dashboard.outbound.recentTitle',
              'Recent requests',
            )}
          </h3>
          <span className="admin-outbound__backend">
            {t(
              'admin.dashboard.outbound.recentHint',
              'query strings and secrets are stripped',
            )}
          </span>
        </div>
        {recentRequests.length === 0 ? (
          <div className="admin-log-empty">
            {t(
              'admin.dashboard.outbound.noRecent',
              'No recent request trace yet.',
            )}
          </div>
        ) : (
          <div className="admin-outbound__recent-table">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>{t('admin.common.time', 'Time')}</th>
                  <th>{t('admin.common.service', 'Service')}</th>
                  <th>{t('admin.dashboard.outbound.transport', 'Mode')}</th>
                  <th>{t('admin.dashboard.outbound.identity', 'Identity')}</th>
                  <th>{t('admin.dashboard.outbound.request', 'Request')}</th>
                  <th>{t('admin.common.status', 'Status')}</th>
                  <th>{t('admin.common.duration', 'Duration')}</th>
                </tr>
              </thead>
              <tbody>
                {recentRequests.slice(0, 40).map((item, idx) => {
                  const status =
                    item.status_code === null
                      ? item.error || 'error'
                      : item.status_code
                  return (
                    <tr key={`${item.ts}-${idx}`}>
                      <td className="admin-mono">
                        {formatRecentTs(Number(item.ts))}
                      </td>
                      <td className="admin-mono">{item.service}</td>
                      <td>
                        <StatusPill
                          kind={
                            item.transport === 'direct'
                              ? 'warn'
                              : 'ok'
                          }
                        >
                          {item.transport}
                        </StatusPill>
                      </td>
                      <td className="admin-mono">
                        {item.identity || 'direct'}
                      </td>
                      <td className="admin-mono">
                        {item.method} {item.host}
                        {item.path}
                      </td>
                      <td className="admin-mono">{status}</td>
                      <td className="admin-mono">
                        {item.duration_ms === null
                          ? 'n/a'
                          : `${item.duration_ms.toFixed(1)} ms`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {rotationsTotal > 0 && (
        <div className="admin-outbound__rotations">
          <h3>{t('admin.dashboard.outbound.rotationReasons', 'Recent rotation reasons')}</h3>
          <div className="admin-outbound__rotation-list">
            {Object.entries(rotationEvents)
              .sort((a, b) => (b[1] as number) - (a[1] as number))
              .slice(0, 8)
              .map(([reason, count]) => (
                <span
                  key={reason}
                  className="admin-outbound__rotation-pill"
                  title={reason}
                >
                  <span className="admin-outbound__rotation-reason">
                    {reason}
                  </span>
                  <span className="admin-outbound__rotation-count">
                    {count as number}
                  </span>
                </span>
              ))}
          </div>
        </div>
      )}
    </section>
  )
}
