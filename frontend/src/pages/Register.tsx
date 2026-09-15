import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import { authService } from '@/services/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { apiErrorMessage } from '@/services/errors'
import { copy } from '@/i18n/en'


export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const inviteToken = searchParams.get('token')?.trim() || null
  const loginPath = inviteToken ? `/login?token=${encodeURIComponent(inviteToken)}` : '/login'

  if (!inviteToken) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-gray-50 px-4">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader>
            <CardTitle className="text-2xl text-center">{copy.auth.invitationRequired}</CardTitle>
            <CardDescription className="text-center">
              {copy.auth.invitationRequiredDescription}
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button asChild className="w-full"><Link to="/login">{copy.auth.returnToSignIn}</Link></Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authService.register({
        email,
        password,
        full_name: fullName || undefined,
        invite_token: inviteToken,
      })
      navigate('/login', { replace: true })
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.auth.registrationFailed))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl text-center">{copy.auth.joinCourse}</CardTitle>
          <CardDescription className="text-center">{copy.auth.registrationDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md" role="alert">{error}</div>}
            <div className="space-y-2">
              <label htmlFor="full-name" className="text-sm font-medium">{copy.auth.fullName}</label>
              <Input id="full-name" value={fullName} onChange={(event) => setFullName(event.target.value)} maxLength={255} />
            </div>
            <div className="space-y-2">
              <label htmlFor="registration-email" className="text-sm font-medium">{copy.auth.email}</label>
              <Input id="registration-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <label htmlFor="registration-password" className="text-sm font-medium">{copy.auth.password}</label>
              <Input id="registration-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} maxLength={128} />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {loading ? copy.auth.creatingAccount : copy.auth.createStudentAccount}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center text-sm text-muted-foreground">
          {copy.auth.alreadyRegistered} <Link to={loginPath} className="ml-1 text-primary hover:underline font-medium">{copy.auth.signInLink}</Link>
        </CardFooter>
      </Card>
    </div>
  )
}
