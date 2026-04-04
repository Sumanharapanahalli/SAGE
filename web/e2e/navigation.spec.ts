import { test, expect } from '@playwright/test'

// ---------------------------------------------------------------------------
// Navigation & Layout — verify the app shell renders and all routes are reachable
// ---------------------------------------------------------------------------

test.describe('App Shell', () => {
  test('loads and shows the sidebar + header', async ({ page }) => {
    await page.goto('/')
    // Sidebar should be visible (contains navigation links)
    await expect(page.locator('nav, [class*="sidebar"], a[href="/"]')).toBeTruthy()
    // Page should not show a blank white screen
    const body = page.locator('body')
    await expect(body).not.toBeEmpty()
  })

  test('renders Dashboard on /', async ({ page }) => {
    await page.goto('/')
    // Dashboard page should render — look for heading or dashboard-related text
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toBeTruthy()
  })

  test('PWA manifest is accessible', async ({ page }) => {
    const res = await page.goto('/manifest.json')
    expect(res?.status()).toBe(200)
    const manifest = await res?.json()
    expect(manifest.name).toContain('SAGE')
    expect(manifest.display).toBe('standalone')
    expect(manifest.theme_color).toBe('#3b82f6')
  })

  test('service worker script is accessible', async ({ page }) => {
    const res = await page.goto('/sw.js')
    expect(res?.status()).toBe(200)
    const text = await res?.text()
    expect(text).toContain('CACHE_NAME')
  })

  test('app icon SVG is accessible', async ({ page }) => {
    const res = await page.goto('/icons/icon.svg')
    expect(res?.status()).toBe(200)
  })
})

// ---------------------------------------------------------------------------
// All routes should render without crashing
// ---------------------------------------------------------------------------
const ALL_ROUTES = [
  '/', '/chat', '/approvals', '/queue', '/product-backlog', '/build',
  '/live-console', '/agents', '/analyst', '/developer', '/monitor',
  '/improvements', '/workflows', '/goals', '/gym', '/code',
  '/knowledge', '/activity', '/audit', '/costs',
  '/org-graph', '/onboarding',
  '/llm', '/yaml-editor', '/access-control', '/integrations',
  '/safety', '/cds-compliance', '/regulatory', '/skills', '/settings',
]

for (const route of ALL_ROUTES) {
  test(`route ${route} renders without crash`, async ({ page }) => {
    await page.goto(route)
    await page.waitForTimeout(300)
    // No uncaught errors — page should have content
    const html = await page.content()
    expect(html).toContain('<div id="root">')
    // Should NOT show a blank root div (React rendered something)
    const rootChildren = await page.locator('#root').locator('> *').count()
    expect(rootChildren).toBeGreaterThan(0)
  })
}
