import { expect, test, type Page } from '@playwright/test'

const token = [
  'eyJhbGciOiJub25lIn0',
  'eyJleHAiOjQxMDI0NDQ4MDAsImlzX2FkbWluIjpmYWxzZX0',
  'sig',
].join('.')

const PUBLIC_USER_ID = 2

const PROFILE_WEB_URL = `http://127.0.0.1:5173/mini_app/profile/${PUBLIC_USER_ID}`

async function mockProfileShareApi(page: Page) {
  await page.route('**/api/v1/ws**', (route) => route.abort())

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

    if (path === `/api/v1/users/${PUBLIC_USER_ID}`) {
      await route.fulfill({
        json: {
          id: PUBLIC_USER_ID,
          telegram_id: PUBLIC_USER_ID,
          username: 'publicuser',
          display_name: 'Public User',
          is_admin: false,
          is_artist: false,
          profile_visibility: 'public',
          profile_access: 'full',
          created_at: '2026-05-21T00:00:00Z',
        },
      })
      return
    }

    if (path === `/api/v1/users/${PUBLIC_USER_ID}/share-card`) {
      await route.fulfill({
        json: {
          user_id: PUBLIC_USER_ID,
          display_name: 'Public User',
          username: 'publicuser',
          avatar_url: null,
          profile_url: PROFILE_WEB_URL,
          deep_link: null,
          total_tracks: 2,
          total_plays: 10,
          total_likes: 3,
          followers_count: 1,
          top_track_titles: ['Track A'],
        },
      })
      return
    }

    if (path === `/api/v1/users/${PUBLIC_USER_ID}/stats`) {
      await route.fulfill({
        json: {
          user_id: PUBLIC_USER_ID,
          total_tracks: 2,
          total_plays: 10,
          total_likes: 3,
          followers_count: 1,
          following_count: 0,
          top_tracks: [],
        },
      })
      return
    }

    if (path === `/api/v1/users/${PUBLIC_USER_ID}/avatar`) {
      await route.fulfill({ json: { avatar_url: null } })
      return
    }

    if (path === `/api/v1/users/${PUBLIC_USER_ID}/follow/status`) {
      await route.fulfill({ json: { following: false } })
      return
    }

    if (path === `/api/v1/users/${PUBLIC_USER_ID}/tracks`) {
      await route.fulfill({
        json: {
          items: [
            {
              id: 101,
              title: 'Track A',
              artist: 'Public User',
              genre: null,
              description: null,
              duration_seconds: 180,
              cover_key: null,
              play_count: 3,
              is_active: true,
              is_public: true,
              source: 'internal',
              catalog_type: 'ugc',
              access_mode: 'internal_stream',
              source_platform: null,
              imported_from: null,
              sc_url: null,
              sc_uri: null,
              source_url: null,
              canonical_source_url: null,
              source_name: null,
              uploaded_by_id: PUBLIC_USER_ID,
              video_key: null,
              created_at: '2026-05-21T00:00:00Z',
              waveform_data: null,
            },
          ],
          total: 1,
          page: 1,
          size: 20,
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

    if (path.startsWith(`/api/v1/likes/${PUBLIC_USER_ID}`)) {
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

    await route.fulfill({ json: {} })
  })
}

test.describe('profile share flow', () => {
  test.setTimeout(60_000)

  test.beforeEach(async ({ page, context }) => {
    await context.grantPermissions([
      'clipboard-read',
      'clipboard-write',
    ])
    await page.addInitScript(() => {
      window.localStorage.setItem('i18nextLng', 'ru')
      window.localStorage.setItem('ds_consent_v1', '1')
      window.localStorage.setItem('cookie_notice_dismissed', 'v1')
      window.localStorage.setItem('auth-user-id', '1')
      window.localStorage.setItem('auth-token', 'test-token')
    })
    await mockProfileShareApi(page)
  })

  test('copies web profile link and opens public profile', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`/mini_app/profile/${PUBLIC_USER_ID}`)
    await expect(page.locator('#view-public-profile')).toBeAttached({
      timeout: 15_000,
    })
    await expect(
      page.getByRole('heading', { name: 'Public User' }),
    ).toBeVisible({
      timeout: 15_000,
    })

    const shareCardResponse = page.waitForResponse(
      (res) =>
        res.url().includes('/share-card') && res.ok(),
    )
    await page.getByTestId('public-profile-share-open').click()
    await shareCardResponse
    await expect(page.locator('.rp-share-modal')).toBeVisible({
      timeout: 10_000,
    })
    await page.getByTestId('profile-share-copy').click()

    const copied = await page.evaluate(async () =>
      navigator.clipboard.readText(),
    )
    expect(copied).toContain(`/mini_app/profile/${PUBLIC_USER_ID}`)

    await page.goto(copied)
    await expect(page).toHaveURL(
      new RegExp(`/mini_app/profile/${PUBLIC_USER_ID}`),
    )
    await expect(
      page.getByRole('heading', { name: 'Public User' }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Треки' }),
    ).toBeVisible()
  })
})
