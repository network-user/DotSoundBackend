# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: bottom-nav.spec.ts >> bottom navigation dock >> stays inside the mobile viewport without overlap
- Location: e2e\bottom-nav.spec.ts:177:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Поиск' })
    - locator resolved to <button tabindex="0" type="button" aria-label="Поиск" class="mp-press mp-press--ghost rb-nav__btn">…</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div role="presentation" class="app-issue-overlay">…</div> intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div role="presentation" class="app-issue-overlay">…</div> intercepts pointer events
    - retrying click action
      - waiting 100ms
    53 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div role="presentation" class="app-issue-overlay">…</div> intercepts pointer events
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - main [ref=e4]
    - navigation "Основная навигация":
      - generic [ref=e5]:
        - button "Главная" [ref=e6] [cursor=pointer]:
          - generic:
            - generic:
              - img
            - generic: Главная
        - button "Медиатека" [ref=e8] [cursor=pointer]:
          - generic:
            - generic:
              - img
            - generic: Медиатека
        - button "Поиск" [ref=e9] [cursor=pointer]:
          - generic:
            - generic:
              - img
            - generic: Поиск
        - button "Профиль" [ref=e10] [cursor=pointer]:
          - generic:
            - generic:
              - img
            - generic: Профиль
  - alert [ref=e11]:
    - img [ref=e13]
    - heading "Что-то пошло не так" [level=1] [ref=e15]
    - paragraph [ref=e16]: На экране произошла ошибка. Можно попробовать снова или перезагрузить страницу.
    - button "Попробовать снова" [ref=e17] [cursor=pointer]
```

# Test source

```ts
  84  |       path === '/api/v1/users/me/followed-artists/tracks' ||
  85  |       path === '/api/v1/tracks/my/imported'
  86  |     ) {
  87  |       await route.fulfill({
  88  |         json: {
  89  |           items: [],
  90  |           total: 0,
  91  |           page: 1,
  92  |           size: 20,
  93  |         },
  94  |       })
  95  |       return
  96  |     }
  97  | 
  98  |     if (path === '/api/v1/playlists') {
  99  |       await route.fulfill({
  100 |         json: {
  101 |           items: [],
  102 |           total: 0,
  103 |           page: 1,
  104 |           size: 20,
  105 |         },
  106 |       })
  107 |       return
  108 |     }
  109 | 
  110 |     await route.fulfill({ json: {} })
  111 |   })
  112 | }
  113 | 
  114 | async function expectBottomNavFramed(page: Page) {
  115 |   const nav = page.locator('#nav')
  116 |   const dock = page.locator('.rb-nav__dock')
  117 |   await expect(nav).toBeVisible()
  118 |   await expect(dock).toBeVisible()
  119 | 
  120 |   const labels = await nav.locator('button').evaluateAll((buttons) =>
  121 |     buttons.map((button) => button.getAttribute('aria-label')),
  122 |   )
  123 |   expect(labels).toEqual([
  124 |     'Главная',
  125 |     'Медиатека',
  126 |     'Поиск',
  127 |     'Профиль',
  128 |   ])
  129 | 
  130 |   const box = await dock.boundingBox()
  131 |   const viewport = page.viewportSize()
  132 |   expect(box).not.toBeNull()
  133 |   expect(viewport).not.toBeNull()
  134 |   if (!box || !viewport) return
  135 | 
  136 |   expect(box.x).toBeGreaterThanOrEqual(0)
  137 |   expect(box.x + box.width).toBeLessThanOrEqual(viewport.width)
  138 |   expect(box.y + box.height).toBeLessThanOrEqual(viewport.height)
  139 |   expect(box.height).toBeLessThanOrEqual(76)
  140 | }
  141 | 
  142 | test.describe('bottom navigation dock', () => {
  143 |   test.beforeEach(async ({ page }) => {
  144 |     await page.addInitScript(() => {
  145 |       window.localStorage.setItem('i18nextLng', 'ru')
  146 |       window.localStorage.setItem('ds_consent_v1', '1')
  147 |       window.localStorage.setItem('cookie_notice_dismissed', 'v1')
  148 |     })
  149 |     await mockMiniAppApi(page)
  150 |   })
  151 | 
  152 |   test('keeps the swapped order and page transition shell on desktop', async ({
  153 |     page,
  154 |   }) => {
  155 |     await page.setViewportSize({ width: 1440, height: 900 })
  156 |     await page.goto('/mini_app/')
  157 |     await expectBottomNavFramed(page)
  158 | 
  159 |     await page.getByRole('button', { name: 'Медиатека' }).click()
  160 |     await expect(page).toHaveURL(/\/mini_app\/library/)
  161 |     await expect(
  162 |       page.getByRole('button', { name: 'Медиатека' }),
  163 |     ).toHaveClass(/is-active/)
  164 | 
  165 |     await page.getByRole('button', { name: 'Поиск' }).click()
  166 |     await expect(page).toHaveURL(/\/mini_app\/search/)
  167 |     await expect(page.getByRole('button', { name: 'Поиск' })).toHaveClass(
  168 |       /is-active/,
  169 |     )
  170 | 
  171 |     const transitionName = await page
  172 |       .locator('.rb-route-transition')
  173 |       .evaluate((element) => getComputedStyle(element).viewTransitionName)
  174 |     expect(transitionName).toBe('route-page')
  175 |   })
  176 | 
  177 |   test('stays inside the mobile viewport without overlap', async ({
  178 |     page,
  179 |   }) => {
  180 |     await page.setViewportSize({ width: 390, height: 844 })
  181 |     await page.goto('/mini_app/')
  182 |     await expectBottomNavFramed(page)
  183 | 
> 184 |     await page.getByRole('button', { name: 'Поиск' }).click()
      |                                                       ^ Error: locator.click: Test timeout of 30000ms exceeded.
  185 |     await expect(page).toHaveURL(/\/mini_app\/search/)
  186 |     await expectBottomNavFramed(page)
  187 |   })
  188 | })
  189 | 
```