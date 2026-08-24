/**
 * JS mirror of the CSS custom properties in index.css.
 *
 * Roughly 120 sites across the admin screens style themselves inline with
 * `theme === 'light' ? ... : ...`, and inline styles beat any stylesheet rule.
 * Those sites read from here so the JS and CSS palettes cannot drift.
 *
 * If you change a value here, change it in index.css too.
 */

const light = {
  surface0: '#f6f8fa',
  surface1: '#ffffff',
  surface2: '#eef1f5',
  surface3: '#e0e4ea',
  surfaceSunken: '#f4f6f9',
  surfaceInverse: '#1a1f36',

  text: '#1a1f36',
  textSecondary: '#4f566b',
  textMuted: '#8792a2',
  textInverse: '#ffffff',

  border: 'rgba(26, 31, 54, 0.10)',
  borderStrong: 'rgba(26, 31, 54, 0.20)',
  borderHairline: 'rgba(26, 31, 54, 0.06)',

  accent: '#5381e6',
  accentHover: '#6a92ea',
  accentInk: '#ffffff',
  accentText: '#3d68cc',
  accentSoft: 'rgba(83, 129, 230, 0.10)',
  accentRing: 'rgba(83, 129, 230, 0.40)',

  ok: '#0e7c5a',
  okSoft: 'rgba(14, 124, 90, 0.10)',
  warn: '#a8620a',
  warnSoft: 'rgba(168, 98, 10, 0.11)',
  danger: '#cf3a35',
  dangerSoft: 'rgba(207, 58, 53, 0.10)',

  graphDb: '#4a6fc9',
  graphTable: '#0f7b6c',
  graphColumn: '#a2622a',
  graphEntity: '#7c5bbf',
  graphEdge: 'rgba(26, 31, 54, 0.18)',
  graphEdgeActive: '#5381e6',

  seal: '#5c6470',
  scrim: 'rgba(26, 31, 54, 0.28)',

  e1: '0 1px 2px rgba(26, 31, 54, 0.05)',
  e2: '0 1px 3px rgba(26, 31, 54, 0.06), 0 1px 2px rgba(26, 31, 54, 0.04)',
  e3: '0 12px 32px -12px rgba(26, 31, 54, 0.22), 0 2px 6px rgba(26, 31, 54, 0.05)',
};

const dark = {
  surface0: '#16181d',
  surface1: '#1c1f26',
  surface2: '#262a33',
  surface3: '#333844',
  surfaceSunken: '#101216',
  surfaceInverse: '#f2f4f8',

  text: '#eceef3',
  textSecondary: '#a3abba',
  textMuted: '#7b8493',
  textInverse: '#16181d',

  border: 'rgba(236, 238, 243, 0.11)',
  borderStrong: 'rgba(236, 238, 243, 0.22)',
  borderHairline: 'rgba(236, 238, 243, 0.06)',

  accent: '#5381e6',
  accentHover: '#6f96ec',
  accentInk: '#ffffff',
  accentText: '#8caaf5',
  accentSoft: 'rgba(83, 129, 230, 0.16)',
  accentRing: 'rgba(83, 129, 230, 0.45)',

  ok: '#45b98c',
  okSoft: 'rgba(69, 185, 140, 0.14)',
  warn: '#d6963f',
  warnSoft: 'rgba(214, 150, 63, 0.14)',
  danger: '#ef7b74',
  dangerSoft: 'rgba(239, 123, 116, 0.14)',

  graphDb: '#8aa9f0',
  graphTable: '#4fb3a0',
  graphColumn: '#d59a63',
  graphEntity: '#af95e0',
  graphEdge: 'rgba(236, 238, 243, 0.18)',
  graphEdgeActive: '#5381e6',

  seal: '#9aa2b1',
  scrim: 'rgba(8, 9, 12, 0.60)',

  e1: '0 1px 2px rgba(0, 0, 0, 0.40)',
  e2: '0 1px 3px rgba(0, 0, 0, 0.45), 0 1px 2px rgba(0, 0, 0, 0.30)',
  e3: '0 12px 32px -12px rgba(0, 0, 0, 0.70), 0 2px 6px rgba(0, 0, 0, 0.35)',
};

/** Shared, theme-independent scales. */
export const radius = {
  xs: '4px', sm: '6px', md: '8px', lg: '10px',
  xl: '14px', xxl: '18px', full: '999px',
};

export const space = {
  1: '4px', 2: '8px', 3: '12px', 4: '16px', 5: '20px', 6: '24px',
  7: '32px', 8: '40px', 9: '48px', 10: '56px', 11: '64px', 12: '80px',
};

export const fontSize = {
  1: '11px', 2: '12px', 3: '14px', 4: '15px',
  5: '19px', 6: '24px', 7: '32px', 8: '44px',
};

export const motion = {
  d1: '120ms', d2: '200ms', d3: '320ms', d4: '550ms',
  ease: 'cubic-bezier(0.4, 0, 0.2, 1)',
  easeOut: 'cubic-bezier(0.22, 1, 0.36, 1)',
  easeInOut: 'cubic-bezier(0.65, 0, 0.35, 1)',
};

export const fontStack = {
  sans: "'General Sans', -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, Roboto, Helvetica, Arial, sans-serif",
  mono: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Monaco, 'Cascadia Code', 'Roboto Mono', monospace",
};

/** Palette for a theme name. Anything not 'light' resolves to dark. */
export function palette(theme) {
  return theme === 'light' ? light : dark;
}

export default palette;
