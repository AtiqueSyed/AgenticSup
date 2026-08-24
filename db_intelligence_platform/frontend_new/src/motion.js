/**
 * Motion primitives.
 *
 * Everything here is registered through gsap.matchMedia(), so a user with
 * `prefers-reduced-motion: reduce` gets the end state immediately and no
 * animation at all. Durations and easing mirror the --d-* / --ease-* tokens
 * in index.css.
 */
import { gsap } from 'gsap';

gsap.defaults({ duration: 0.32, ease: 'power2.out' });

const REDUCED = '(prefers-reduced-motion: reduce)';

function prefersReduced() {
  return typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia(REDUCED).matches;
}

/** Staggered entrance for a list of siblings. */
export function listEnter(targets, { each = 0.045, y = 8, delay = 0 } = {}) {
  if (!targets || prefersReduced()) return null;
  return gsap.fromTo(
    targets,
    { autoAlpha: 0, y },
    {
      autoAlpha: 1,
      y: 0,
      duration: 0.4,
      delay,
      ease: 'power3.out',
      stagger: { each, from: 'start' },
      clearProps: 'all',
    }
  );
}

/** A single chat message arriving. */
export function messageEnter(target) {
  if (!target || prefersReduced()) return null;
  return gsap.fromTo(
    target,
    { autoAlpha: 0, y: 12 },
    { autoAlpha: 1, y: 0, duration: 0.4, ease: 'power3.out', clearProps: 'all' }
  );
}
