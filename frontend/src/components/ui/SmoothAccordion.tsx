import React from 'react';
import { twMerge } from 'tailwind-merge';

interface SmoothAccordionProps {
  isOpen: boolean;
  children: React.ReactNode;
  className?: string;
  durationMs?: number;
}

/**
 * High-performance smooth accordion using CSS grid-template-rows
 * Eliminates layout thrashing (CLS) and provides natural spring easing.
 */
export function SmoothAccordion({
  isOpen,
  children,
  className,
}: SmoothAccordionProps) {
  return (
    <div
      className={twMerge(
        'grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
        isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
        className,
      )}
    >
      <div className="overflow-hidden min-h-0">
        {children}
      </div>
    </div>
  );
}
