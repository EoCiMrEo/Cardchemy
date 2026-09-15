import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { authService } from '@/services/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { apiErrorMessage } from '@/services/errors'
import { copy } from '@/i18n/en'


export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState(token ? '' : copy.auth.resetTokenMissing)
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
      setMessage(apiErrorMessage(caught, copy.auth.resetFailed))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{copy.auth.chooseNewPassword}</CardTitle>
          <CardDescription>{copy.auth.resetLinkDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          {!success && token && (
            <form onSubmit={submit} className="space-y-4">
              <label htmlFor="new-password" className="text-sm font-medium">{copy.auth.newPassword}</label>
              <Input id="new-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} maxLength={128} required />
              <Button type="submit" className="w-full" disabled={loading}>{loading ? copy.auth.resetting : copy.auth.resetPassword}</Button>
            </form>
          )}
          {message && <p className={`text-sm ${success ? 'text-green-700' : 'text-destructive'}`}>{message}</p>}
        </CardContent>
        <CardFooter><Link to="/login" className="text-sm text-primary hover:underline">{copy.auth.backToSignIn}</Link></CardFooter>
      </Card>
    </div>
  )
}
