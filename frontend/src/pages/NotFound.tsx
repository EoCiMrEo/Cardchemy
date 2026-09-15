import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { copy } from '@/i18n/en'

export default function NotFound() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md text-center">
        <h1 className="text-3xl font-bold">{copy.routing.notFoundTitle}</h1>
        <p className="mt-3 text-muted-foreground">{copy.routing.notFoundDescription}</p>
        <Button asChild className="mt-6">
          <Link to="/dashboard">{copy.routing.returnToDashboard}</Link>
        </Button>
      </div>
    </main>
  )
}
