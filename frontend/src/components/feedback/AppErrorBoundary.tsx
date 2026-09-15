import { Component, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { copy } from '@/i18n/en'

interface AppErrorBoundaryProps {
  children: ReactNode
}

interface AppErrorBoundaryState {
  failed: boolean
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true }
  }

  componentDidCatch() {
    // Phase 9 will connect this boundary to opt-in structured error reporting.
  }

  private recover = () => {
    window.location.assign('/dashboard')
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
          <div className="max-w-md rounded-lg border bg-white p-8 text-center shadow-sm" role="alert">
            <h1 className="text-2xl font-bold">{copy.routing.errorTitle}</h1>
            <p className="mt-2 text-muted-foreground">{copy.routing.errorDescription}</p>
            <Button type="button" className="mt-6" onClick={this.recover}>
              {copy.routing.tryAgain}
            </Button>
          </div>
        </main>
      )
    }

    return this.props.children
  }
}
