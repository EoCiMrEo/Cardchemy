import { expect, test, type Page } from '@playwright/test'

import { expectNoSeriousOrCriticalViolations } from './support/a11y'
import { fixtures, installMockApi, type MockResponse } from './support/mockApi'

const root = '/subjects/subject-1/published-knowledge'
const doc1 = { id: 'lecture-1', title: 'Lecture One', page_count: 3, has_original_pdf: true }
const doc2 = { id: 'lecture-2', title: 'Lecture Two', page_count: 2, has_original_pdf: true }

async function setup(page: Page, { revoke = false }: { revoke?: boolean } = {}) {
  let listReads = 0
  let pageReads = 0
  let revoked = false
  const api = await installMockApi(page, { auth: 'student', resolver: (call): MockResponse | undefined => {
    if (call.path === '/subjects/subject-1') return { json: fixtures.subject }
    if (call.path === '/subjects/subject-1/sets') return { json: [] }
    if (call.path === `${root}/documents`) {
      listReads += 1
      return { json: { documents: revoked ? [doc2] : [doc1, doc2] } }
    }
    if (call.path === `${root}/search`) return { json: { pages: [
      { document_id: doc1.id, document_title: doc1.title, page_number: 2 },
    ] } }
    if (call.path === `${root}/documents/${doc1.id}/pages/2`) {
      pageReads += 1
      if (revoked) return { status: 404, json: { detail: 'Unavailable' } }
      return { json: { document_title: doc1.title, page_number: 2,
        page_content: 'Synthetic text on a published page.', truncated: false } }
    }
    if (call.path === `${root}/documents/${doc1.id}/original-pdf` && call.method === 'HEAD') {
      if (revoke) revoked = true
      return { status: 404, body: '' }
    }
    return undefined
  } })
  await page.goto('/subjects/subject-1')
  return { api, listReads: () => listReads, pageReads: () => pageReads }
}

test('students browse and search published pages even when Ask is unavailable', async ({ page }) => {
  const { api } = await setup(page)
  await page.setViewportSize({ width: 360, height: 780 })
  const section = page.getByRole('region', { name: 'Published lectures' })
  await expect(section.getByRole('button', { name: 'Lecture One · 3 pages · open page 1' })).toBeVisible()
  await section.getByRole('textbox', { name: 'Search published lectures' }).fill('synthetic topic')
  await section.getByRole('button', { name: 'Search pages' }).click()
  const result = section.getByRole('button', { name: 'Lecture One · page 2' })
  await expect(result).toBeVisible()
  await result.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Published lecture page' })
  await expect(dialog.getByText('Opened from Lecture One · page 2', { exact: true })).toBeVisible()
  await expect(dialog.getByText('The original PDF is unavailable. Read the extracted page text below.')).toBeVisible()
  await dialog.getByText('Extracted text for opened page 2', { exact: true }).click()
  await expect(dialog).toContainText('Synthetic text on a published page.')
  await expectNoSeriousOrCriticalViolations(page)
  expect(await page.evaluate(() => document.body.scrollWidth <= innerWidth)).toBe(true)
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(result).toBeFocused()
  expect(api.callsFor('GET', `${root}/search`)[0].headers.authorization).toBe('Bearer boot-access-token')
})

test('revoked published page clears stale search links and restores safe focus', async ({ page }) => {
  const { listReads, pageReads } = await setup(page, { revoke: true })
  const section = page.getByRole('region', { name: 'Published lectures' })
  await section.getByRole('textbox', { name: 'Search published lectures' }).fill('synthetic topic')
  await section.getByRole('button', { name: 'Search pages' }).click()
  await section.getByRole('button', { name: 'Lecture One · page 2' }).click()
  await expect(page.getByRole('dialog', { name: 'Published lecture page' })).not.toBeVisible()
  await expect.poll(listReads).toBeGreaterThanOrEqual(2)
  await expect.poll(pageReads).toBeGreaterThanOrEqual(2)
  await expect(section.getByRole('button', { name: 'Lecture One · page 2' })).toHaveCount(0)
  await expect(section.getByRole('button', { name: 'Lecture One · 3 pages · open page 1' })).toHaveCount(0)
  await expect(section.getByRole('button', { name: 'Lecture Two · 2 pages · open page 1' })).toBeVisible()
  await expect(section).toBeFocused()
})
