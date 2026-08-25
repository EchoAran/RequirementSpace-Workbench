import React from 'react';
import { twMerge } from 'tailwind-merge';

interface GlassSurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'base' | 'elevated' | 'subtle';
  children: React.ReactNode;
}

export function GlassSurface({
  variant = 'base',
  className,
  children,
  ...props
}: GlassSurfaceProps) {
  const variantClasses = {
    subtle: 'bg-white/50 backdrop-blur-md border border-white/40 shadow-xs',
    base: 'glass-panel',
    elevated: 'glass-panel-elevated',
  };

  return (
    <div
      className={twMerge(
        'rounded-2xl transition-all duration-300',
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
