import React from 'react';
import { twMerge } from 'tailwind-merge';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'card' | 'row' | 'badge' | 'avatar' | 'rect';
  count?: number;
}

export function SkeletonPreset({
  variant = 'card',
  count = 1,
  className,
  ...props
}: SkeletonProps) {
  const items = Array.from({ length: count }, (_, i) => i);

  if (variant === 'card') {
    return (
      <div className="space-y-3 w-full">
        {items.map((i) => (
          <div
            key={i}
            className={twMerge(
              'rounded-2xl border border-slate-200/50 bg-white/60 p-5 space-y-3 shadow-xs',
              className,
            )}
            {...props}
          >
            <div className="flex items-center justify-between">
              <div className="h-4 w-1/3 rounded-lg skeleton-shimmer" />
              <div className="h-4 w-16 rounded-full skeleton-shimmer" />
            </div>
            <div className="h-3 w-3/4 rounded-md skeleton-shimmer" />
            <div className="h-3 w-1/2 rounded-md skeleton-shimmer" />
            <div className="pt-2 flex gap-2">
              <div className="h-6 w-20 rounded-md skeleton-shimmer" />
              <div className="h-6 w-16 rounded-md skeleton-shimmer" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'row') {
    return (
      <div className="space-y-2 w-full">
        {items.map((i) => (
          <div
            key={i}
            className={twMerge(
              'h-10 w-full rounded-xl skeleton-shimmer border border-slate-100',
              className,
            )}
            {...props}
          />
        ))}
      </div>
    );
  }

  if (variant === 'avatar') {
    return (
      <div
        className={twMerge('h-9 w-9 rounded-full skeleton-shimmer shrink-0', className)}
        {...props}
      />
    );
  }

  return (
    <div
      className={twMerge('h-4 rounded-md skeleton-shimmer', className)}
      {...props}
    />
  );
}
