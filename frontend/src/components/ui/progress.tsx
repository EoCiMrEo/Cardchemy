"use client"

import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"

import { cn } from "@/lib/utils"

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root>
>(({ className, value, max = 100, ...props }, ref) => {
  const safeMax = Number.isFinite(max) && max > 0 ? max : 100
  const safeValue = value === null || value === undefined || !Number.isFinite(value)
    ? null
    : Math.min(safeMax, Math.max(0, value))
  const percentage = safeValue === null ? 0 : (safeValue / safeMax) * 100

  return (
    <ProgressPrimitive.Root
      ref={ref}
      value={safeValue}
      max={safeMax}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-slate-200",
        className
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className="h-full flex-1 bg-blue-500 transition-[width] duration-1000 ease-linear motion-reduce:transition-none"
        style={{ width: `${percentage}%` }}
        aria-hidden="true"
      />
    </ProgressPrimitive.Root>
  )
})
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
