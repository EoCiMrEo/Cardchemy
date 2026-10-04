import { Button } from '@/components/ui/button'
import { coreCopy } from '@/i18n/enCore'

interface PageErrorProps {
  message: string
  onRetry: () => void
}

export function PageError({ message, onRetry }: PageErrorProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center" role="alert">
      <p className="text-sm text-red-800">{message}</p>
      <Button type="button" variant="outline" className="mt-4" onClick={onRetry}>
        {coreCopy.common.retry}
      </Button>
    </div>
  )
}
