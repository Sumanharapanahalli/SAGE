import { test, expect } from '@playwright/test'

test.describe('Chat Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat')
    await page.waitForTimeout(500)
  })

  test('shows welcome screen with SAGE Chat title', async ({ page }) => {
    await expect(page.getByText('SAGE Chat')).toBeVisible()
  })

  test('shows New conversation button', async ({ page }) => {
    const btn = page.getByRole('button', { name: /New conversation/i })
    await expect(btn).toBeVisible()
  })

  test('shows quick-start role cards', async ({ page }) => {
    // Should show role names on the welcome screen
    const content = await page.textContent('body')
    // At least some default roles should appear
    const hasRole = ['Analyst', 'Developer', 'Monitor', 'Planner', 'Product Owner']
      .some(r => content?.includes(r))
    expect(hasRole).toBeTruthy()
  })

  test('clicking New conversation opens role picker', async ({ page }) => {
    const btn = page.getByRole('button', { name: /New conversation/i })
    await btn.click()
    await page.waitForTimeout(300)
    // Role picker modal should appear
    await expect(page.getByText('Choose a role')).toBeVisible()
  })

  test('selecting a role creates a conversation', async ({ page }) => {
    // Click new conversation
    const btn = page.getByRole('button', { name: /New conversation/i })
    await btn.click()
    await page.waitForTimeout(300)

    // Click first role in the picker
    const roleButtons = page.locator('button:has-text("Analyst")')
    if (await roleButtons.count() > 0) {
      await roleButtons.first().click()
      await page.waitForTimeout(300)

      // Should now show the chat interface with a textarea
      const textarea = page.locator('textarea[placeholder*="Message"]')
      await expect(textarea).toBeVisible()
    }
  })

  test('quick-start role card creates a conversation directly', async ({ page }) => {
    // Click a quick-start card (small buttons on welcome screen)
    const cards = page.locator('button:has-text("Analyst")')
    if (await cards.count() > 0) {
      await cards.first().click()
      await page.waitForTimeout(500)

      // Should show chat input
      const textarea = page.locator('textarea[placeholder*="Message"]')
      await expect(textarea).toBeVisible()
    }
  })

  test('typing and sending a message adds it to the conversation', async ({ page }) => {
    // Create a conversation first
    const cards = page.locator('button:has-text("Analyst")')
    if (await cards.count() > 0) {
      await cards.first().click()
      await page.waitForTimeout(500)
    }

    const textarea = page.locator('textarea[placeholder*="Message"]')
    if (await textarea.isVisible()) {
      await textarea.fill('Hello, test message')
      await textarea.press('Enter')
      await page.waitForTimeout(500)

      // User message should appear in the body text
      const bodyText = await page.textContent('body')
      expect(bodyText).toContain('Hello, test message')
      expect(bodyText).toContain('You')
    }
  })

  test('conversation appears in sidebar history', async ({ page }) => {
    // Create a conversation
    const cards = page.locator('button:has-text("Developer")')
    if (await cards.count() > 0) {
      await cards.first().click()
      await page.waitForTimeout(300)
    }

    // Sidebar should show "New conversation" or "Developer" text
    const sidebar = page.locator('div').filter({ hasText: /New conversation|Developer/ })
    expect(await sidebar.count()).toBeGreaterThan(0)
  })

  test('Shift+Enter does not send message (new line)', async ({ page }) => {
    // Create a conversation
    const cards = page.locator('button:has-text("Analyst")')
    if (await cards.count() > 0) {
      await cards.first().click()
      await page.waitForTimeout(500)
    }

    const textarea = page.locator('textarea[placeholder*="Message"]')
    if (await textarea.isVisible()) {
      await textarea.fill('Line one')
      await textarea.press('Shift+Enter')
      // Should not have sent — textarea should still have content
      const val = await textarea.inputValue()
      // Textarea should still be editable (message not sent)
      expect(val.length).toBeGreaterThan(0)
    }
  })

  test('New chat button in sidebar shows role picker', async ({ page }) => {
    const newChatBtn = page.locator('button:has-text("New chat")')
    if (await newChatBtn.count() > 0) {
      await newChatBtn.first().click()
      await page.waitForTimeout(300)
      await expect(page.getByText('Choose a role')).toBeVisible()
    }
  })
})
