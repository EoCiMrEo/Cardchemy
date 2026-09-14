import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { isAxiosError } from 'axios'

import { authService } from '@/services/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'


export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState(token ? '' : 'The reset token is missing')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!token) return
    setLoading(true)
    try {
      const result = await authService.resetPassword(token, password)
      setMessage(result.message)
      setSuccess(true)
    } catch (caught: unknown) {
      setMessage(
        isAxiosError<{ detail?: string }>(caught) && caught.response?.data.detail
          ? caught.response.data.detail
          : 'Unable to reset the password',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Choose a new password</CardTitle>
          <CardDescription>Reset links are single-use and expire quickly.</CardDescription>
        </CardHeader>
        <CardContent>
          {!success && token && (
            <form onSubmit={submit} className="space-y-4">
              <label htmlFor="new-password" className="text-sm font-medium">New password</label>
              <Input id="new-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} maxLength={128} required />
              <Button type="submit" className="w-full" disabled={loading}>{loading ? 'Resetting…' : 'Reset password'}</Button>
            </form>
          )}
          {message && <p className={`text-sm ${success ? 'text-green-700' : 'text-destructive'}`}>{message}</p>}
        </CardContent>
        <CardFooter><Link to="/login" className="text-sm text-primary hover:underline">Back to sign in</Link></CardFooter>
      </Card>
    </div>
  )
}
