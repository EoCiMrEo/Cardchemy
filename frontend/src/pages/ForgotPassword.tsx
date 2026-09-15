import { useState } from 'react'
import { Link } from 'react-router-dom'

import { authService } from '@/services/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { apiErrorMessage } from '@/services/errors'
import { copy } from '@/i18n/en'


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
      setMessage(apiErrorMessage(caught, copy.auth.resetRequestFailed))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{copy.auth.resetPasswordTitle}</CardTitle>
          <CardDescription>{copy.auth.resetPasswordDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <label htmlFor="reset-email" className="text-sm font-medium">{copy.auth.email}</label>
            <Input id="reset-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            {message && <p className="text-sm text-muted-foreground" role="status">{message}</p>}
            <Button type="submit" className="w-full" disabled={loading}>{loading ? copy.auth.sending : copy.auth.sendResetLink}</Button>
          </form>
        </CardContent>
        <CardFooter><Link to="/login" className="text-sm text-primary hover:underline">{copy.auth.backToSignIn}</Link></CardFooter>
      </Card>
    </div>
  )
}
