import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { isAxiosError } from 'axios'

import { useAuth } from '@/context/AuthContext'
import { subjectService } from '@/services/subjects'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'


export default function JoinCourse() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const navigate = useNavigate()
  const { user, isLoading: authLoading } = useAuth()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const [courseName, setCourseName] = useState('')

  useEffect(() => {
    if (authLoading) return
    if (!token) return
    if (!user) {
      navigate(`/register?token=${encodeURIComponent(token)}`, { replace: true })
      return
    }
    if (user.role !== 'student') return

    let active = true
    void subjectService.joinCourse(token).then(
      (result) => {
        if (!active) return
        setStatus('success')
        setCourseName(result.subject_name)
        setMessage(result.message)
      },
      (caught: unknown) => {
        if (!active) return
        setStatus('error')
        setMessage(
          isAxiosError<{ detail?: string }>(caught) && caught.response?.data.detail
            ? caught.response.data.detail
            : 'Failed to join course',
        )
      },
    )
    return () => { active = false }
  }, [authLoading, navigate, token, user])

  const blockedMessage = !token
    ? 'No invitation token was provided'
    : user?.role === 'instructor'
      ? 'Only student accounts can accept course invitations'
      : ''
  const displayStatus = blockedMessage ? 'error' : status
  const displayMessage = blockedMessage || message

  if (authLoading || (!user && token) || displayStatus === 'loading') {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="h-10 w-10 animate-spin" /></div>
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          {displayStatus === 'success' ? <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto mb-4" /> : <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />}
          <CardTitle className="text-2xl">{displayStatus === 'success' ? 'Course Joined' : 'Join Failed'}</CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          {courseName && <p className="text-lg font-medium text-green-600">{courseName}</p>}
          <p className={displayStatus === 'error' ? 'text-destructive' : 'text-muted-foreground'}>{displayMessage}</p>
          <Button onClick={() => navigate('/dashboard', { replace: true })} className="w-full">Go to Dashboard</Button>
        </CardContent>
      </Card>
    </div>
  )
}
