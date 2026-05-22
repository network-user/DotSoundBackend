import { memo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { HomeMixShortcutIcon } from '@/components/home/HomeMixShortcutIcon'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  HOME_QUICK_VISIBLE_COUNT,
  MIX_SHORTCUT_TILES,
  type MixShortcutTile,
} from '@/lib/homeShortcuts'

interface HomeQuickShortcutsProps {
  onStartRadio: () => void
}

function ShortcutTile({
  item,
  label,
  onActivate,
}: {
  item: MixShortcutTile
  label: string
  onActivate: (path: string) => void
}) {
  return (
    <MotionPress
      variant="subtle"
      className="dh-shortcut"
      onClick={() => onActivate(item.path)}
      ariaLabel={label}
    >
      <span className="dh-shortcut__icon" aria-hidden>
        <HomeMixShortcutIcon id={item.shortcutIcon} size={20} />
      </span>
      <span className="dh-shortcut__label">{label}</span>
      <span className="dh-shortcut__chev" aria-hidden>
        <Icon name="chevron-right" size={14} />
      </span>
    </MotionPress>
  )
}

export const HomeQuickShortcuts = memo(function HomeQuickShortcuts({
  onStartRadio,
}: HomeQuickShortcutsProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const tiles = MIX_SHORTCUT_TILES.slice(0, HOME_QUICK_VISIBLE_COUNT)

  const handleActivate = useCallback(
    (path: string) => {
      if (path === '/radio') {
        onStartRadio()
        return
      }
      navigate(path)
    },
    [navigate, onStartRadio],
  )

  return (
    <section
      className="dh-shortcuts"
      aria-label={t('redesign.home.shortcutsAria')}
    >
      <div className="dh-shortcuts__grid">
        {tiles.map((item) => (
          <ShortcutTile
            key={item.path}
            item={item}
            label={t(`redesign.home.${item.labelKey}`)}
            onActivate={handleActivate}
          />
        ))}
      </div>
    </section>
  )
})
