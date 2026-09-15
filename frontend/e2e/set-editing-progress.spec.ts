import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'

test('validates multiple-choice edits, preserves approval, and keeps other card controls', async ({
  page,
}) => {
  let updateBody: unknown
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
        return { json: fixtures.set }
      }
      if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
        return { json: fixtures.cards }
      }
      if (call.method === 'PUT' && call.path === '/flashcards/card-1') {
        updateBody = call.body
        if (callNumber === 1) {
          return { status: 503, json: { detail: 'Card update temporarily unavailable' } }
        }
        const update = call.body as Record<string, unknown>
        return {
          json: {
            ...fixtures.cards[0],
            ...update,
            is_approved: false,
          },
        }
      }
      return undefined
    },
  })

  await page.goto('/sets/set-1')
  await page
    .getByRole('button', { name: `Edit ${fixtures.cards[0].front_content}`, exact: true })
    .click()

  await expect(page.getByRole('radio')).toHaveCount(4)
  await expect(page.getByRole('textbox', { name: 'Front' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: /^Option [1-4]$/ })).toHaveCount(4)
  await expect(
    page.getByRole('button', { name: `Edit ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Delete ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Approve ${fixtures.cards[0].front_content}`, exact: true }),
  ).toBeVisible()

  const front = page.getByRole('textbox', { name: 'Front' })
  const firstOption = page.getByRole('textbox', { name: 'Option 1' })
  const secondOption = page.getByRole('textbox', { name: 'Option 2' })
  const save = page.getByRole('button', { name: 'Save' })

  await front.fill('   ')
  await save.click()
  await expect(page.getByRole('alert')).toContainText(/question/i)
  expect(api.count('PUT', '/flashcards/card-1')).toBe(0)

  await front.fill(fixtures.cards[0].front_content)
  await secondOption.fill('Nucleus')
  await save.click()
  await expect(page.getByRole('alert')).toContainText(/unique/i)
  expect(api.count('PUT', '/flashcards/card-1')).toBe(0)

  await secondOption.fill('Mitochondrion')
  await firstOption.fill('')
  await save.click()
  await expect(page.getByRole('alert')).toContainText(/option|required|empty/i)
  expect(api.count('PUT', '/flashcards/card-1')).toBe(0)

  await firstOption.fill('Nucleus')
  await page.getByRole('radio', { name: 'Mark option 3 as correct' }).check()
  await save.click()

  await expect(page.getByRole('alert')).toContainText('Card update temporarily unavailable')
  const updateCallsBeforeRetry = api.count('PUT', '/flashcards/card-1')
  await save.click()
  await expect.poll(() => api.count('PUT', '/flashcards/card-1')).toBe(updateCallsBeforeRetry + 1)
  const submitted = updateBody as Record<string, unknown>
  expect(submitted).not.toHaveProperty('is_approved')
  expect(submitted.back_content).toBe('Ribosome')
  await expect(page.getByText('Needs Review')).toBeVisible()
})

test('keeps per-card actions and the newer editor stable while another save is pending', async ({
  page,
}) => {
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
        return { json: fixtures.set }
      }
      if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
        return { json: fixtures.cards }
      }
      if (call.method === 'PUT' && call.path === '/flashcards/card-1') {
        return { delayMs: 300, json: { ...fixtures.cards[0], ...(call.body as object) } }
      }
      return undefined
    },
  })

  await page.goto('/sets/set-1')
  await page
    .getByRole('button', { name: `Edit ${fixtures.cards[0].front_content}`, exact: true })
    .click()
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(() => api.count('PUT', '/flashcards/card-1')).toBe(1)

  await expect(
    page.getByRole('button', { name: `Delete ${fixtures.cards[0].front_content}`, exact: true }),
  ).toBeDisabled()
  await expect(
    page.getByRole('button', { name: `Delete ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeEnabled()
  await page
    .getByRole('button', { name: `Edit ${fixtures.cards[1].front_content}`, exact: true })
    .click()
  await expect(page.getByRole('textbox', { name: 'Front' })).toHaveValue(
    fixtures.cards[1].front_content,
  )

  await page.waitForTimeout(350)
  await expect(page.getByRole('textbox', { name: 'Front' })).toHaveValue(
    fixtures.cards[1].front_content,
  )
})

test('renders completion and mastery from the server-authoritative progress response', async ({
  page,
}) => {
  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') {
        return { json: fixtures.subject }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
        return { json: [fixtures.set] }
      }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') {
        return { json: fixtures.progress }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')

  await expect(page.getByText('2/4')).toBeVisible()
  await expect(page.getByText('37% complete')).toBeVisible()
  await expect(page.getByText('63% mastery')).toBeVisible()
})
