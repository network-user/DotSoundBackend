import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import {
  cleanup,
  render,
  waitFor,
} from '@testing-library/react'
import { NotificationList } from './NotificationList'
import { api } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  api: {
    getNotifications: vi.fn(async () => []),
    markNotificationRead: vi.fn(),
    markNotificationUnread: vi.fn(),
    deleteNotification: vi.fn(),
  },
}))

vi.mock('@/lib/ws', () => ({
  onWS: vi.fn(() => () => undefined),
}))

vi.mock('@/store/PlayerContext', () => ({
  usePlayerActions: () => ({
    openTrackAtComment: vi.fn(),
  }),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'ru' },
  }),
}))

describe('NotificationList', () => {
  afterEach(() => {
    cleanup()
    document.body.innerHTML = ''
    vi.clearAllMocks()
  })

  it('renders the overlay in body outside the caller container', async () => {
    const host = document.createElement('div')
    host.className = 'profile-page-header'
    document.body.appendChild(host)

    render(
      <NotificationList
        open
        onClose={() => undefined}
      />,
      { container: host },
    )

    const overlay = document.querySelector(
      '.notification-overlay',
    )
    expect(overlay).not.toBeNull()
    expect(overlay?.parentElement).toBe(document.body)
    expect(
      host.querySelector('.notification-overlay'),
    ).toBeNull()

    await waitFor(() => {
      expect(api.getNotifications).toHaveBeenCalled()
    })
  })
})
