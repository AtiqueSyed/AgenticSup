import assert from 'node:assert/strict';
import {
  resolveRoute, adminTabForPath, pathForAdminTab,
  LOGIN, CHAT, ONBOARDING, REGISTRY,
} from './routes.js';

// Signed out: only the login screen is reachable, everything else bounces.
assert.deepEqual(resolveRoute(null, LOGIN), { view: 'login' });
assert.deepEqual(resolveRoute(null, REGISTRY), { redirect: LOGIN });
assert.deepEqual(resolveRoute(null, '/'), { redirect: LOGIN });

// Signed in: '/' and '/login' land on the role's home instead of showing login again.
assert.deepEqual(resolveRoute('user', '/'), { redirect: CHAT });
assert.deepEqual(resolveRoute('admin', '/'), { redirect: ONBOARDING });
assert.deepEqual(resolveRoute('admin', LOGIN), { redirect: ONBOARDING });

// A plain user cannot reach an admin screen by typing its URL.
assert.deepEqual(resolveRoute('user', ONBOARDING), { redirect: CHAT });
assert.deepEqual(resolveRoute('user', REGISTRY), { redirect: CHAT });
assert.deepEqual(resolveRoute('admin', REGISTRY), { view: 'registry' });
assert.deepEqual(resolveRoute('admin', ONBOARDING), { view: 'onboarding' });

// Unknown URLs redirect rather than rendering nothing.
assert.deepEqual(resolveRoute('user', '/nope'), { redirect: CHAT });
assert.deepEqual(resolveRoute('admin', '/admin'), { redirect: ONBOARDING });

// The admin tab <-> path adapter round-trips, so the admin screens' nav still works.
for (const tab of ['onboarding', 'registry', 'query']) {
  assert.equal(adminTabForPath(pathForAdminTab(tab)), tab);
}

console.log('routes: all assertions passed');

// --- navigate(): history semantics, with a stub window ---------------------
// Not ceremony: a wrong push/replace or a missing event breaks back/forward
// silently -- the page keeps rendering, it just stops responding to the URL.
const calls = [];
const events = [];
globalThis.window = {
  location: { pathname: '/login' },
  history: {
    pushState: (_s, _t, to) => { calls.push(['push', to]); globalThis.window.location.pathname = to; },
    replaceState: (_s, _t, to) => { calls.push(['replace', to]); globalThis.window.location.pathname = to; },
  },
  dispatchEvent: (e) => events.push(e.type),
  addEventListener: () => {},
  removeEventListener: () => {},
};
globalThis.Event = class { constructor(type) { this.type = type; } };

const { navigate } = await import('./router.js');

navigate(CHAT);
assert.deepEqual(calls.at(-1), ['push', CHAT]);
assert.equal(events.at(-1), 'app:navigate', 'pushState fires no popstate; without our event nothing re-renders');

// Redirecting to where we already are must not stack a duplicate history entry.
const before = calls.length;
navigate(CHAT);
assert.equal(calls.length, before, 'navigate to the current path must be a no-op');

navigate(ONBOARDING, { replace: true });
assert.deepEqual(calls.at(-1), ['replace', ONBOARDING]);

// subscribe(): the back/forward path itself, exercised through router.js's own
// wiring. The stub at the top no-ops addEventListener, so nothing above this line
// proves a popstate ever reaches React -- and that is the whole feature.
const listeners = {};
globalThis.window.addEventListener = (type, fn) => { (listeners[type] ??= []).push(fn); };
globalThis.window.removeEventListener = (type, fn) => {
  listeners[type] = (listeners[type] ?? []).filter((f) => f !== fn);
};

const { subscribe } = await import('./router.js');
let notified = 0;
const unsubscribe = subscribe(() => { notified += 1; });

// A browser Back fires popstate. React is only told because subscribe() listened.
listeners['popstate'].forEach((fn) => fn());
assert.equal(notified, 1, 'popstate must notify React -- this is the back button');

// navigate() dispatches its own event, since pushState fires no popstate.
listeners['app:navigate'].forEach((fn) => fn());
assert.equal(notified, 2, 'navigate() must notify React');

unsubscribe();
assert.equal(listeners['popstate'].length, 0, 'cleanup must detach, or listeners leak every render');
assert.equal(listeners['app:navigate'].length, 0, 'cleanup must detach both listeners');

console.log('router: all assertions passed');
