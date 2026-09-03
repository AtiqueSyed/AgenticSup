/**
 * The route table, and the guard deciding what a given (role, path) may see.
 *
 * Deliberately React-free and side-effect-free: `npm test` runs it under plain node,
 * which is the only reason the redirect rules below are testable at all.
 */

export const LOGIN = '/login';
export const CHAT = '/chat';
export const ONBOARDING = '/admin/onboarding';
export const REGISTRY = '/admin/registry';

const VIEWS = {
  [LOGIN]: 'login',
  [CHAT]: 'chat',
  [ONBOARDING]: 'onboarding',
  [REGISTRY]: 'registry',
};

// The two admin screens address themselves by tab name. Rather than edit ~2000 lines
// across ACEOnboarding and MetadataRegistry, the URL becomes the source of truth and
// these two functions adapt it back into the prop API they already expect.
const TAB_PATHS = { onboarding: ONBOARDING, registry: REGISTRY, query: CHAT };

export const pathForAdminTab = (tab) => TAB_PATHS[tab] ?? CHAT;

export const adminTabForPath = (path) =>
  path === REGISTRY ? 'registry' : path === ONBOARDING ? 'onboarding' : 'query';

export const homePathFor = (role) => (role === 'admin' ? ONBOARDING : CHAT);

/**
 * Resolve a request into either `{ redirect }` or `{ view }` -- never both, never neither,
 * so the caller can never fall through to a blank screen on an unknown URL.
 */
export function resolveRoute(role, path) {
  if (!role) return path === LOGIN ? { view: 'login' } : { redirect: LOGIN };
  if (path === LOGIN || path === '/') return { redirect: homePathFor(role) };
  // Typing /admin/registry as a non-admin must not render it, even for one frame.
  if (path.startsWith('/admin') && role !== 'admin') return { redirect: CHAT };
  const view = VIEWS[path];
  return view ? { view } : { redirect: homePathFor(role) };
}
