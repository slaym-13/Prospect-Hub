import { cn } from '../../lib/cn';

const TONES = {
  info: 'bg-warn-soft text-warn',
  good: 'bg-good-soft text-good',
  bad: 'bg-bad-soft text-bad',
  plain: 'bg-surface-2 text-muted'
};

/** Inline message: the result of an action, shown where the action happened. */
export function Message({ tone = 'info', className, children }) {
  if (!children) return null;
  return (
    <div role="status" className={cn('rounded-xl px-3 py-2 text-[13px]', TONES[tone], className)}>
      {children}
    </div>
  );
}

/**
 * An empty place that says what to do next. `title` is the short headline, children
 * the explanation, `action` a button or link that does the next step.
 */
export function Empty({ title, action, children, compact }) {
  return (
    <div
      className={cn(
        'grid justify-items-center gap-2 rounded-card border border-dashed border-line text-center',
        compact ? 'p-4' : 'px-5 py-8'
      )}
    >
      {!compact && (
        <svg width="34" height="34" viewBox="0 0 56 56" aria-hidden="true" className="text-accent opacity-60">
          <g fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="17" y="17" width="22" height="22" />
            <rect x="17" y="17" width="22" height="22" transform="rotate(45 28 28)" />
            <circle cx="28" cy="28" r="4.5" />
          </g>
        </svg>
      )}
      {title && <p className="m-0 font-display text-[17px] font-semibold text-fg">{title}</p>}
      {children && <p className="m-0 max-w-sm text-[13px] text-muted">{children}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function Spinner({ label = 'Loading…' }) {
  return <div className="p-8 text-center text-muted">{label}</div>;
}

/** Stacked notifications, rendered once by the layout. */
export function Toasts({ items }) {
  if (!items.length) return null;
  return (
    <div className="pointer-events-none fixed bottom-24 left-1/2 md:bottom-5 z-60 grid -translate-x-1/2 gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          role="status"
          className={cn(
            'pointer-events-auto max-w-[90vw] rounded-full px-4 py-2.5 text-sm shadow-lg',
            t.tone === 'bad' ? 'bg-bad text-white' : 'bg-fg text-bg'
          )}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}
