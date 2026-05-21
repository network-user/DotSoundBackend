import { expect, test, type Page } from '@playwright/test'

const token = [
  'eyJhbGciOiJub25lIn0',
  'eyJleHAiOjQxMDI0NDQ4MDAsImlzX2FkbWluIjpmYWxzZX0',
  'sig',
].join('.')

async function mockMiniAppApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/v1/auth/session') {
      await route.fulfill({
        json: {
          user_id: 1,
          is_admin: false,
          access_token: token,
        },
      })
      return
    }

    if (path === '/api/v1/auth/config') {
      await route.fulfill({
        json: {
          admin_panel_path: 'admin',
          admin_api_path: '/api/v1/admin',
        },
      })
      return
    }

    if (path === '/api/v1/users/1') {
      await route.fulfill({
        json: {
          id: 1,
          telegram_id: 1,
          username: 'listener',
          display_name: 'Listener',
          is_admin: false,
          is_artist: false,
          profile_visibility: 'public',
          created_at: '2026-05-21T00:00:00Z',
        },
      })
      return
    }

    if (path === '/api/v1/onboarding/status') {
      await route.fulfill({
        json: {
          onboarding_completed: true,
          tutorial_seen: true,
        },
      })
      return
    }

    if (path === '/api/v1/recommendations/home-highlight') {
      await route.fulfill({ json: null })
      return
    }

    if (path === '/api/v1/recommendations/genre-mixes') {
      await route.fulfill({ json: { mixes: [] } })
      return
    }

    if (path === '/api/v1/recommendations/discover') {
      await route.fulfill({
        json: {
          trending_tracks: [],
          suggested_artists: [],
          genre_cards: [],
          recent_genres: [],
        },
      })
      return
    }

    if (path.startsWith('/api/v1/recommendations/home/sections/')) {
      await route.fulfill({
        json: {
          section_type: 'continue',
          title: 'Continue',
          subtitle: null,
          tracks: [],
          has_more: false,
          next_cursor: null,
        },
      })
      return
    }

    if (
      path === '/api/v1/promotions/hero' ||
      path === '/api/v1/promotions/section'
    ) {
      await route.fulfill({ json: { items: [] } })
      return
    }

    if (path === '/api/v1/artists/followed') {
      await route.fulfill({ json: { items: [], total: 0 } })
      return
    }

    if (path === '/api/v1/playlists/featured') {
      await route.fulfill({ json: [] })
      return
    }

    if (path === '/api/v1/tracks/genres') {
      await route.fulfill({ json: [] })
      return
    }

    if (path === '/api/v1/tracks') {
      await route.fulfill({
        json: {
          items: [],
          total: 0,
          page: 1,
          size: 20,
        },
      })
      return
    }

    if (path === '/api/v1/import/active') {
      await route.fulfill({ json: null })
      return
    }

    if (
      path === '/api/v1/users/me/listen-history' ||
      path === '/api/v1/users/me/library' ||
      path === '/api/v1/users/me/collection' ||
      path === '/api/v1/users/me/followed-artists/tracks' ||
      path === '/api/v1/tracks/my/imported'
    ) {
      await route.fulfill({
        json: {
          items: [],
          total: 0,
          page: 1,
          size: 20,
        },
      })
      return
    }

    if (path === '/api/v1/playlists') {
      await route.fulfill({
        json: {
          items: [],
          total: 0,
          page: 1,
          size: 20,
        },
      })
      return
    }

    if (/^\/api\/v1\/likes\/\d+$/.test(path)) {
      await route.fulfill({
        json: {
          items: [],
          total: 0,
          page: 1,
          size: 20,
        },
      })
      return
    }

    await route.fulfill({ json: {} })
  })
}

async function expectBottomNavFramed(page: Page) {
  const nav = page.locator('#nav')
  const dock = page.locator('.rb-nav__dock')
  await expect(nav).toBeVisible()
  await expect(dock).toBeVisible()

  const labels = await nav.locator('button').evaluateAll((buttons) =>
    buttons.map((button) => button.getAttribute('aria-label')),
  )
  expect(labels).toEqual([
    'Главная',
    'Медиатека',
    'Поиск',
    'Профиль',
  ])

  const box = await dock.boundingBox()
  const viewport = page.viewportSize()
  expect(box).not.toBeNull()
  expect(viewport).not.toBeNull()
  if (!box || !viewport) return

  expect(box.x).toBeGreaterThanOrEqual(0)
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width)
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height)
  expect(box.height).toBeLessThanOrEqual(76)
}

test.describe('bottom navigation dock', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('i18nextLng', 'ru')
      window.localStorage.setItem('ds_consent_v1', '1')
      window.localStorage.setItem('cookie_notice_dismissed', 'v1')
    })
    await mockMiniAppApi(page)
  })

  test('keeps the swapped order and page transition shell on desktop', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/mini_app/')
    await expectBottomNavFramed(page)

    await page.getByRole('button', { name: 'Медиатека' }).click()
    await expect(page).toHaveURL(/\/mini_app\/library/)
    await expect(
      page.getByRole('button', { name: 'Медиатека' }),
    ).toHaveClass(/is-active/)

    await page.getByRole('button', { name: 'Поиск' }).click()
    await expect(page).toHaveURL(/\/mini_app\/search/)
    await expect(page.getByRole('button', { name: 'Поиск' })).toHaveClass(
      /is-active/,
    )

    const transitionName = await page
      .locator('.rb-route-transition')
      .evaluate((element) => getComputedStyle(element).viewTransitionName)
    expect(transitionName).toBe('route-page')
  })

  test('stays inside the mobile viewport without overlap', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/mini_app/')
    await expectBottomNavFramed(page)

    await page.getByRole('button', { name: 'Поиск' }).click()
    await expect(page).toHaveURL(/\/mini_app\/search/)
    await expectBottomNavFramed(page)
  })
})
