/**
 * ChiRAG brand mark — three connected nodes.
 *
 * The product is a knowledge graph with retrieval over it, so the mark is a
 * small constellation rather than a letterform. Deliberately not two crossing
 * strokes: at small sizes that reads as a close button.
 */
export default function BrandMark({ size = 18, tone = 'currentColor' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <g stroke={tone} strokeWidth="1.5" strokeLinecap="round" opacity="0.55">
        <line x1="6.4" y1="8.6" x2="17.6" y2="6.2" />
        <line x1="6.4" y1="8.6" x2="12.8" y2="18.2" />
        <line x1="17.6" y1="6.2" x2="12.8" y2="18.2" />
      </g>
      <circle cx="6.4" cy="8.6" r="2.6" fill={tone} />
      <circle cx="17.6" cy="6.2" r="2" fill={tone} />
      <circle cx="12.8" cy="18.2" r="2" fill={tone} />
    </svg>
  );
}
