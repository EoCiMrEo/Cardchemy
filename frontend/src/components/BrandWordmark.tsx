import { copy } from '@/i18n/en'
import { cn } from '@/lib/utils'

export function BrandWordmark({ className }: { className?: string }) {
  return (
    <img
      src="/brand/cardchemy-wordmark.png"
      alt={copy.common.appName}
      width={480}
      height={166}
      decoding="async"
      className={cn('block h-auto w-40 max-w-full sm:w-44', className)}
    />
  )
}
