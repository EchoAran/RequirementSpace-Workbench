import { useEffect, useRef } from 'react';
import gsap from 'gsap';

/**
 * Hook to safely use GSAP animations with automatic React cleanup.
 * Prevents memory leaks, stale refs, and animation conflicts on unmount.
 */
export function useGsapContext(
  callback: (context: gsap.Context) => void,
  dependencies: any[] = [],
) {
  const scopeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      callback(ctx);
    }, scopeRef);

    return () => {
      ctx.revert();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  return scopeRef;
}

/**
 * Smoothly animates drawer opening / closing with backdrop synchronization.
 */
export function animateDrawerTransition(
  drawerEl: HTMLElement | null,
  overlayEl: HTMLElement | null,
  isOpen: boolean,
  onComplete?: () => void,
) {
  if (!drawerEl) return;

  const tl = gsap.timeline({
    onComplete,
  });

  if (isOpen) {
    if (overlayEl) {
      tl.fromTo(
        overlayEl,
        { opacity: 0 },
        { opacity: 1, duration: 0.2, ease: 'power2.out' },
        0,
      );
    }
    tl.fromTo(
      drawerEl,
      { x: '100%', opacity: 0.8 },
      { x: '0%', opacity: 1, duration: 0.35, ease: 'power3.out' },
      0,
    );
  } else {
    if (overlayEl) {
      tl.to(
        overlayEl,
        { opacity: 0, duration: 0.2, ease: 'power2.in' },
        0,
      );
    }
    tl.to(
      drawerEl,
      { x: '100%', opacity: 0.8, duration: 0.25, ease: 'power3.in' },
      0,
    );
  }

  return tl;
}
