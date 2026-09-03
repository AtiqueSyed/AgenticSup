import { useSyncExternalStore } from 'react';

/**
 * History-API glue -- the whole router.
 *
 * Four flat routes, no params, no nested layouts: react-router would be another
 * dependency and an order of magnitude more code for exactly this behaviour.
 * ponytail: swap in react-router the day routes gain params (/chat/:id) or nesting.
 */

const PUSH = 'app:navigate';

export function subscribe(onChange) {
  window.addEventListener('popstate', onChange); // browser back / forward
  window.addEventListener(PUSH, onChange); // our own navigate()
  return () => {
    window.removeEventListener('popstate', onChange);
    window.removeEventListener(PUSH, onChange);
  };
}

export function navigate(to, { replace = false } = {}) {
  if (to === window.location.pathname) return;
  window.history[replace ? 'replaceState' : 'pushState']({}, '', to);
  // pushState does not fire popstate, so nothing would re-render without this.
  window.dispatchEvent(new Event(PUSH));
}

export const usePath = () =>
  useSyncExternalStore(subscribe, () => window.location.pathname);
