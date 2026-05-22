import { memo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { HomeMixShortcutIcon } from '@/components/home/HomeMixShortcutIcon'
import { HorizontalSnap } from '@/components/ui/HorizontalSnap'
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
      className={`rh-home-shortcut rh-home-shortcut--${item.shortcutIcon}`}
      onClick={() => onActivate(item.path)}
    >
      <span className="rh-home-shortcut__frame" aria-hidden>
        <span className="rh-home-shortcut__glyph">
          <HomeMixShortcutIcon id={item.shortcutIcon} size={24} />
        </span>
      </span>
      <span className="rh-home-shortcut__label">{label}</span>
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
      className="rh-home-shortcuts rh-home-shortcuts--deck"
      aria-label={t('redesign.home.shortcutsAria')}
    >
      <div className="rh-home-shortcuts__intro">
        <span className="rh-home-shortcuts__eyebrow">
          {t('redesign.home.shortcutsEyebrow')}
        </span>
        <h2 className="rh-home-shortcuts__title">
          {t('redesign.home.shortcutsTitle')}
        </h2>
      </div>
      <HorizontalSnap
        items={tiles}
        renderItem={(item) => (
          <ShortcutTile
            item={item}
            label={t(`redesign.home.${item.labelKey}`)}
            onActivate={handleActivate}
          />
        )}
        showArrows="never"
        parallax={false}
        className="rh-home-shortcuts-snap"
        ariaLabel={t('redesign.home.shortcutsAria')}
      />
    </section>
  )
})
