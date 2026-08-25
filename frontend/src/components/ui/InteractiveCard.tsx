import React from 'react';
import { twMerge } from 'tailwind-merge';

export interface InteractiveCardProps extends React.HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  interactive?: boolean;
  elevation?: 'flat' | 'raised' | 'floating';
  children: React.ReactNode;
}

export function InteractiveCard({
  selected = false,
  interactive = true,
  elevation = 'raised',
  className,
  children,
  ...props
}: InteractiveCardProps) {
  const elevationClasses = {
    flat: 'bg-white/70 border border-slate-200/60 shadow-none',
    raised: 'bg-white/90 border border-slate-200/80 shadow-xs',
    floating: 'glass-panel shadow-md',
  };

  const selectedClasses = selected
    ? 'ring-2 ring-indigo-500/80 border-indigo-300 bg-indigo-50/20'
    : '';

  const interactiveClasses = interactive
    ? 'interactive-card cursor-pointer hover:border-indigo-200 hover:shadow-md'
    : '';

  return (
    <div
      className={twMerge(
        'rounded-2xl p-4',
        elevationClasses[elevation],
        interactiveClasses,
        selectedClasses,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
