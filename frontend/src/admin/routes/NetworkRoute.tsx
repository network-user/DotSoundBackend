import { useTranslation } from 'react-i18next'
import { OutboundStatusPanel } from '../components/widgets/OutboundStatusPanel'

export function NetworkRoute() {
  const { t } = useTranslation()
  return (
    <div>
      <h1>
        {t('admin.network.title', {
          defaultValue: 'Network',
        })}
      </h1>
      <p className="admin-card__sub">
        {t('admin.network.subtitle', {
          defaultValue:
            'Outbound transport, proxy/Tor state, request flow and recent egress attempts.',
        })}
      </p>
      <OutboundStatusPanel />
    </div>
  )
}
