import { expect, test } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'


type MailpitAddress = { Address?: string }
type MailpitMessage = {
  ID?: string
  Id?: string
  id?: string
  Subject?: string
  To?: MailpitAddress[]
}

const liveEmail = process.env.PHASE7_LIVE_EMAIL
const oldPassword = process.env.PHASE7_LIVE_OLD_PASSWORD
const newPassword = process.env.PHASE7_LIVE_NEW_PASSWORD
const mailpitUrl = process.env.PHASE7_LIVE_MAILPIT_URL

async function waitForResetMessage(
  request: APIRequestContext,
  recipient: string,
): Promise<MailpitMessage> {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    const response = await request.get(`${mailpitUrl}/api/v1/messages`)
    expect(response.ok()).toBe(true)
    const payload = await response.json() as { messages?: MailpitMessage[] }
    const message = payload.messages?.find((candidate) =>
      candidate.Subject?.startsWith('Reset your')
      && candidate.To?.some((address) => address.Address?.toLowerCase() === recipient.toLowerCase()),
    )
    if (message) return message
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error('Mailpit did not capture the password-reset message within 20 seconds')
}

function messageId(message: MailpitMessage): string {
  const id = message.ID ?? message.Id ?? message.id
  if (!id) throw new Error('Mailpit returned a message without an ID')
  return id
}

test('live request -> captured email -> reset page -> password and token semantics', async ({ page, request }) => {
  test.skip(
    !liveEmail || !oldPassword || !newPassword || !mailpitUrl,
    'Set PHASE7_LIVE_EMAIL, PHASE7_LIVE_OLD_PASSWORD, PHASE7_LIVE_NEW_PASSWORD, and PHASE7_LIVE_MAILPIT_URL',
  )
  if (!liveEmail || !oldPassword || !newPassword || !mailpitUrl) return

  const cleared = await request.delete(`${mailpitUrl}/api/v1/messages`)
  expect(cleared.ok()).toBe(true)

  await page.goto('/forgot-password')
  await page.getByRole('textbox', { name: 'Email' }).fill(liveEmail)
  await page.getByRole('button', { name: 'Send reset link' }).click()
  await expect(page.getByRole('status')).toContainText(
    'If that account exists, a password-reset email has been sent',
  )

  const summary = await waitForResetMessage(request, liveEmail)
  const detailResponse = await request.get(`${mailpitUrl}/api/v1/message/${messageId(summary)}`)
  expect(detailResponse.ok()).toBe(true)
  const detail = await detailResponse.json() as { Text?: string; HTML?: string }
  expect(detail.Text).toContain('/reset-password?token=')
  expect(detail.HTML).toContain('/reset-password?token=')
  const link = detail.Text?.match(/https?:\/\/[^\s<>]+\/reset-password\?token=[^\s<>]+/)?.[0]
  if (!link) throw new Error('The captured text email did not contain a reset link')

  await page.goto(link)
  await page.getByLabel('New password').fill(newPassword)
  await page.getByRole('button', { name: 'Reset password' }).click()
  await expect(page.getByText('Password reset successfully. Sign in again on every device')).toBeVisible()

  await page.goto(link)
  await page.getByLabel('New password').fill(`${newPassword}-reuse`)
  await page.getByRole('button', { name: 'Reset password' }).click()
  await expect(page.getByText(/invalid|expired|already used/i)).toBeVisible()

  await page.goto('/login')
  await page.getByLabel('Email').fill(liveEmail)
  await page.getByLabel('Password').fill(oldPassword)
  await page.getByRole('button', { name: 'Sign In' }).click()
  await expect(page.getByRole('alert')).toBeVisible()

  await page.getByLabel('Password').fill(newPassword)
  await page.getByRole('button', { name: 'Sign In' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
})
