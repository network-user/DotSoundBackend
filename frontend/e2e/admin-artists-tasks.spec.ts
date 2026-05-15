import { expect, test } from '@playwright/test'

const adminManifest = {
  capabilities: ['tasks.manage', 'tasks.run', 'artists.enrich'],
  menu: [
    {
      id: 'artists',
      label: 'Artists',
      route: '/admin/artists',
      capability: null,
    },
    {
      id: 'tasks',
      label: 'Tasks',
      route: '/admin/tasks',
      capability: null,
    },
  ],
  slots: {},
  adminBundleUrl: '/mini_app/assets/admin.js',
  issuedAt: Date.now(),
  expiresIn: 3600,
  locale: 'en',
}

async function mockAdminApi(page: import('@playwright/test').Page) {
  await page.route('**/api/v1/auth/config', async (route) => {
    await route.fulfill({
      json: {
        admin_panel_path: 'admin',
        admin_api_path: '/api/v1/admin',
      },
    })
  })
  await page.route('**/api/v1/admin/auth/csrf', async (route) => {
    await route.fulfill({ json: { csrf_token: 'csrf' } })
  })
  await page.route('**/api/v1/admin/auth/metadata', async (route) => {
    await route.fulfill({
      json: {
        is_admin: true,
        admin_init: true,
        admin_totp_enabled: true,
        has_backup_codes: true,
      },
    })
  })
  await page.route('**/api/v1/admin/auth/refresh', async (route) => {
    await route.fulfill({
      json: {
        access_token: 'admin-token',
        refresh_token: 'refresh-token',
        expires_in: 3600,
      },
    })
  })
  await page.route('**/api/v1/admin/manifest**', async (route) => {
    await route.fulfill({ json: adminManifest })
  })
  await page.route('**/api/v1/admin/artists**', async (route) => {
    await route.fulfill({
      json: {
        total: 2,
        items: [
          {
            id: 1,
            name: 'Needle Artist',
            image_key: null,
            image_url: null,
            source: 'internal',
            bio: null,
            birth_date: null,
            birthplace: null,
            country: 'US',
            website_url: null,
            enrichment_status: 'done',
            enrichment_confidence: 0.93,
            enriched_at: '2026-05-15T00:00:00Z',
            created_at: '2026-05-15T00:00:00Z',
            updated_at: '2026-05-15T00:00:00Z',
            monthly_listeners: 0,
            catalog_sync_state: 'running',
            catalog_sync_mode: 'full',
            catalog_sync_updated_at: '2026-05-15T00:00:00Z',
          },
          {
            id: 2,
            name: 'Idle Artist',
            image_key: null,
            image_url: null,
            source: 'internal',
            bio: null,
            birth_date: null,
            birthplace: null,
            country: null,
            website_url: null,
            enrichment_status: 'pending',
            enrichment_confidence: null,
            enriched_at: null,
            created_at: '2026-05-15T00:00:00Z',
            updated_at: null,
            monthly_listeners: 0,
            catalog_sync_state: 'idle',
            catalog_sync_mode: null,
            catalog_sync_updated_at: null,
          },
        ],
      },
    })
  })
  await page.route('**/api/v1/admin/tasks/overview', async (route) => {
    await route.fulfill({
      json: {
        queues: [{ name: 'taskiq:default', length: 1 }],
        background_jobs: { queued: 1, running: 1, failed_terminal: 0 },
        compute_jobs: { pending: 0, claimed: 0 },
        lyrics_jobs: { queued: 0, running: 0 },
        upcoming_schedules: [],
      },
    })
  })
  await page.route('**/api/v1/admin/tasks/jobs**', async (route) => {
    await route.fulfill({
      json: {
        total: 1,
        page: 1,
        size: 50,
        items: [
          {
            id: 'job-catalog-1',
            name: 'sync_artist_catalog_task',
            queue: 'default',
            status: 'running',
            payload: { artist_id: 1 },
            attempts: 1,
            max_attempts: 3,
            duration_ms: 1200,
            scheduled_job_id: null,
            parent_job_id: null,
            error: null,
            created_at: '2026-05-15T00:00:00Z',
            started_at: '2026-05-15T00:00:01Z',
            finished_at: null,
          },
        ],
      },
    })
  })
  await page.route('**/api/v1/admin/tasks/queues', async (route) => {
    await route.fulfill({
      json: { items: [{ name: 'taskiq:default', length: 1 }] },
    })
  })
  await page.route('**/api/v1/admin/tasks/compute-jobs**', async (route) => {
    await route.fulfill({ json: { total: 0, page: 1, size: 50, items: [] } })
  })
  await page.route('**/api/v1/admin/tasks/lyrics-jobs**', async (route) => {
    await route.fulfill({ json: { total: 0, page: 1, size: 50, items: [] } })
  })
}

test('admin artists and tasks sync workflow renders', async ({ page }) => {
  await mockAdminApi(page)

  await page.goto('/mini_app/admin/artists')
  await expect(page.getByRole('heading', { name: /artists/i })).toBeVisible()
  await expect(page.getByText('Catalog sync')).toBeVisible()
  await expect(page.getByText('running')).toBeVisible()
  await expect(page.getByText('Enrich selected')).toBeVisible()
  await page.screenshot({
    path: 'test-results/admin-artists-sync-workflow.png',
    fullPage: true,
  })

  await page.goto('/mini_app/admin/tasks?bgName=sync_artist_catalog')
  await expect(page.getByRole('heading', { name: /tasks/i })).toBeVisible()
  await expect(page.getByText('Catalog sync')).toBeVisible()
  await expect(page.getByText('artist:1')).toBeVisible()
  await page.screenshot({
    path: 'test-results/admin-tasks-catalog-sync.png',
    fullPage: true,
  })
})
