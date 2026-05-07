import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { hapticSelection, haptic } from '@/lib/telegram'

interface Props {
  value: string
  query: string
  open: boolean
  searching: boolean
  results: string[]
  hasExact: boolean
  toggleHintKey: string
  inputPlaceholderKey: string
  searchProgressKey: string
  emptyHintKey: string
  createKey: string
  onToggleOpen: () => void
  onQueryChange: (next: string) => void
  onPick: (value: string) => void
  onCreate: (value: string) => void
}

export function UploadComboBox({
  value,
  query,
  open,
  searching,
  results,
  hasExact,
  toggleHintKey,
  inputPlaceholderKey,
  searchProgressKey,
  emptyHintKey,
  createKey,
  onToggleOpen,
  onQueryChange,
  onPick,
  onCreate,
}: Props) {
  const { t } = useTranslation()

  return (
    <>
      <button
        type="button"
        className="genre-search-toggle ru-up-cb__toggle"
        onClick={() => {
          onToggleOpen()
          hapticSelection()
        }}
      >
        <Icon name="search" size={16} />
        <span>{value || t(toggleHintKey)}</span>
        <Icon
          name={open ? 'chevron-up' : 'chevron-down'}
          size={16}
        />
      </button>
      {open && (
        <div
          className="genre-search-popover ru-up-cb__popover"
          role="listbox"
        >
          <input
            className="form-input genre-search-input ru-up-cb__input"
            placeholder={t(inputPlaceholderKey)}
            maxLength={256}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
          />
          {searching && (
            <p className="genre-search-note ru-up-cb__note">
              {t(searchProgressKey)}
            </p>
          )}
          {!searching && results.length > 0 && (
            <div className="genre-search-list ru-up-cb__list">
              {results.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`genre-search-item ru-up-cb__item${
                    value.toLowerCase() === item.toLowerCase()
                      ? ' active'
                      : ''
                  }`}
                  onClick={() => {
                    onPick(item)
                    hapticSelection()
                  }}
                >
                  {item}
                </button>
              ))}
            </div>
          )}
          {!searching && query.trim() && !hasExact && (
            <button
              type="button"
              className="genre-search-create ru-up-cb__create"
              onClick={() => {
                onCreate(query.trim())
                haptic('medium')
              }}
            >
              {t(createKey, { name: query.trim() })}
            </button>
          )}
          {!searching &&
            results.length === 0 &&
            !query.trim() && (
              <p className="genre-search-note ru-up-cb__note">
                {t(emptyHintKey)}
              </p>
            )}
        </div>
      )}
    </>
  )
}
