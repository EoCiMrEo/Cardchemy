import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'

import { useAuth } from '@/context/AuthContext'
import { subjectService } from '@/services/subjects'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BrandWordmark } from '@/components/BrandWordmark'
import { apiErrorMessage } from '@/services/errors'
import { copy } from '@/i18n/en'


export default function JoinCourse() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')?.trim() || null
  const navigate = useNavigate()
  const { user, isLoading: authLoading } = useAuth()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const [courseName, setCourseName] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (authLoading) return
    if (!token) return
    if (!user) {
      navigate(`/register?token=${encodeURIComponent(token)}`, { replace: true })
      return
    }
    if (user.role !== 'student') return

    const controller = new AbortController()
    void subjectService.joinCourse(token, controller.signal).then(
      (result) => {
        if (controller.signal.aborted) return
        setStatus('success')
        setCourseName(result.subject_name)
        setMessage(result.message)
      },
      (caught: unknown) => {
        if (controller.signal.aborted) return
        setStatus('error')
        setMessage(apiErrorMessage(caught, copy.join.failed))
      },
    )
    return () => controller.abort()
  }, [attempt, authLoading, navigate, token, user])

  const blockedMessage = !token
    ? copy.join.missingToken
    : user?.role === 'instructor'
      ? copy.join.instructorBlocked
      : ''
  const displayStatus = blockedMessage ? 'error' : status
  const displayMessage = blockedMessage || message
  const retryJoin = () => {
    setStatus('loading')
    setMessage('')
    setAttempt((value) => value + 1)
  }

  if (authLoading || (!user && token) || displayStatus === 'loading') {
    return <div className="flex min-h-dvh items-center justify-center"><Loader2 className="h-10 w-10 animate-spin" /></div>
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <BrandWordmark className="mx-auto mb-3" />
          {displayStatus === 'success' ? <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto mb-4" /> : <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />}
          <CardTitle className="text-2xl">{displayStatus === 'success' ? copy.join.joinedTitle : copy.join.failedTitle}</CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          {courseName && <p className="text-lg font-medium text-green-600">{courseName}</p>}
          <p className={displayStatus === 'error' ? 'text-destructive' : 'text-muted-foreground'} role={displayStatus === 'error' ? 'alert' : 'status'}>{displayMessage}</p>
          {displayStatus === 'error' && token && user?.role === 'student' ? (
            <Button type="button" variant="outline" onClick={retryJoin} className="w-full">
              {copy.join.retry}
            </Button>
          ) : null}
          <Button onClick={() => navigate('/dashboard', { replace: true })} className="w-full">{copy.join.goToDashboard}</Button>
        </CardContent>
      </Card>
    </div>
  )
}
