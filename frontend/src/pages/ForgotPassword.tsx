import { useState } from 'react'
import { Link } from 'react-router-dom'
import { isAxiosError } from 'axios'

import { authService } from '@/services/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'


export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true)
    try {
      const result = await authService.forgotPassword(email)
      setMessage(result.message)
    } catch (caught: unknown) {
      setMessage(
        isAxiosError<{ detail?: string }>(caught) && caught.response?.data.detail
          ? caught.response.data.detail
          : 'Unable to request a reset right now',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Reset your password</CardTitle>
          <CardDescription>We will email a single-use reset link if the account exists.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <label htmlFor="reset-email" className="text-sm font-medium">Email</label>
            <Input id="reset-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            {message && <p className="text-sm text-muted-foreground">{message}</p>}
            <Button type="submit" className="w-full" disabled={loading}>{loading ? 'Sending…' : 'Send reset link'}</Button>
          </form>
        </CardContent>
        <CardFooter><Link to="/login" className="text-sm text-primary hover:underline">Back to sign in</Link></CardFooter>
      </Card>
    </div>
  )
}
