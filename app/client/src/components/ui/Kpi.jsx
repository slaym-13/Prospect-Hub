import { cn } from '../../lib/cn';

export function KpiRow({ children }) {
  return <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(150px,1fr))]">{children}</div>;
}

/**
 * One headline number, set like a figure in a ledger: a mono label above, the value
 * in the display serif. `hero` makes it the wide, solid-blue one with the tile.
 */
export function Kpi({ label, value, detail, hero }) {
  return (
    <div
      className={cn(
        'rounded-card border p-4 shadow-card',
        hero
          ? 'zellige overflow-hidden border-transparent bg-accent text-accent-fg [--zellige-opacity:0.14] sm:col-span-2'
          : 'border-line bg-surface'
      )}
    >
      <div className={cn('font-mono text-[10.5px] uppercase tracking-[0.14em]', hero ? 'opacity-80' : 'text-muted')}>
        {label}
      </div>
      <div
        className={cn(
          'mt-1.5 font-display font-medium leading-none tabular-nums tracking-tight',
          hero ? 'text-[56px]' : 'text-[34px]'
        )}
      >
        {value}
      </div>
      {detail && <div className={cn('mt-2 text-xs', hero ? 'opacity-80' : 'text-muted opacity-85')}>{detail}</div>}
    </div>
  );
}
