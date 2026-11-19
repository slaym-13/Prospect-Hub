/** A few line icons, drawn on a 24px grid. Inline, so no icon font or extra request. */
const PATHS = {
  dashboard: 'M4 13h6V4H4zM14 20h6v-9h-6zM14 4v4h6V4zM4 20h6v-3H4z',
  today: 'M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  companies: 'M3 21h18M5 21V7l7-4 7 4v14M9 10h1M14 10h1M9 14h1M14 14h1M10 21v-3h4v3',
  pipeline: 'M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v6h-4z',
  outbox: 'M21 3 10 14M21 3l-7 18-4-7-7-4z',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14',
  table: 'M3 5h18v14H3zM3 10h18M3 15h18M9 5v14',
  chevron: 'm6 9 6 6 6-6',
  ask: 'M12 21a9 9 0 1 0-8-4.9L3 21l4.9-1A9 9 0 0 0 12 21zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.1M12 17h.01',
  arrow: 'M5 12h14M13 6l6 6-6 6'
};

export function Icon({ name, size = 18, className, strokeWidth = 1.8 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
