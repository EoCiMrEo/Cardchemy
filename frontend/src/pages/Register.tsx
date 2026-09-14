import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { isAxiosError } from 'axios'

import { authService } from '@/services/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'


export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const inviteToken = searchParams.get('token')

  if (!inviteToken) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader>
            <CardTitle className="text-2xl text-center">Invitation Required</CardTitle>
            <CardDescription className="text-center">
              Student registration requires a single-use instructor invitation. Instructor accounts are created by the deployment operator.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button asChild className="w-full"><Link to="/login">Return to sign in</Link></Button>
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
      setError(
        isAxiosError<{ detail?: string }>(caught) && caught.response?.data.detail
          ? caught.response.data.detail
          : 'Registration failed',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl text-center">Join Course</CardTitle>
          <CardDescription className="text-center">Create a student account using your invitation.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">{error}</div>}
            <div className="space-y-2">
              <label htmlFor="full-name" className="text-sm font-medium">Full Name</label>
              <Input id="full-name" value={fullName} onChange={(event) => setFullName(event.target.value)} maxLength={255} />
            </div>
            <div className="space-y-2">
              <label htmlFor="registration-email" className="text-sm font-medium">Email</label>
              <Input id="registration-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <label htmlFor="registration-password" className="text-sm font-medium">Password</label>
              <Input id="registration-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} maxLength={128} />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Student Account
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center text-sm text-muted-foreground">
          Already registered? <Link to="/login" className="ml-1 text-primary hover:underline font-medium">Sign in</Link>
        </CardFooter>
      </Card>
    </div>
  )
}
