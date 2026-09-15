import { useState } from "react"
import { useAuth } from "@/context/AuthContext"
import { authService } from "@/services/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { apiErrorMessage } from "@/services/errors"
import { copy } from "@/i18n/en"

export default function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const inviteToken = searchParams.get('token')?.trim() || null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const data = await authService.login({ email, password })
      await login(data.access_token)
      navigate(inviteToken ? `/join?token=${encodeURIComponent(inviteToken)}` : "/dashboard")
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.auth.loginFailed))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl text-center">{copy.auth.welcomeBack}</CardTitle>
          <CardDescription className="text-center">
            {copy.auth.loginDescription}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md" role="alert">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="login-email" className="text-sm font-medium">{copy.auth.email}</label>
              <Input
                id="login-email"
                type="email"
                placeholder={copy.auth.emailPlaceholder}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="login-password" className="text-sm font-medium">{copy.auth.password}</label>
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {loading ? copy.auth.signingIn : copy.auth.signIn}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center text-sm text-muted-foreground">
          <Link to="/forgot-password" className="text-primary hover:underline font-medium">
            {copy.auth.forgotPassword}
          </Link>
        </CardFooter>
      </Card>
    </div>
  )
}
