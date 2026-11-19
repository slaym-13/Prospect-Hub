/**
 * The frame every sign-in, sign-up and account-email page sits in: a blue panel that
 * says what the place is, and the form beside it. On a phone the panel becomes a band.
 */
export function AuthShell({ title, subtitle, children, footer, wide }) {
  return (
    <main className="grid min-h-screen grid-rows-[auto_1fr] lg:grid-cols-[minmax(340px,0.85fr)_minmax(0,1.15fr)] lg:grid-rows-none">
      <BrandPanel />

      <section className="grid place-items-center px-4 py-8 sm:py-12">
        <div
          className={`grid ${wide ? 'w-[min(640px,100%)]' : 'w-[min(420px,100%)]'} gap-5 rounded-card border border-line bg-surface p-6 shadow-card animate-rise sm:p-8`}
          style={{ animationDelay: '120ms' }}
        >
          <div>
            <h1 className="text-[30px] leading-[1.1]">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-muted">{subtitle}</p>}
          </div>

          {children}

          {footer && <p className="m-0 border-t border-line pt-4 text-center text-[13px] text-muted">{footer}</p>}
        </div>
      </section>
    </main>
  );
}

function BrandPanel() {
  return (
    <aside className="zellige relative flex flex-col justify-between gap-8 overflow-hidden bg-accent px-6 py-7 text-accent-fg [--zellige-opacity:0.16] sm:px-10 lg:sticky lg:top-0 lg:h-screen lg:py-12">
      {/* a glow that keeps the lattice from feeling flat */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-40 -right-32 -z-10 size-[520px] rounded-full bg-[radial-gradient(closest-side,rgb(255_255_255/0.22),transparent)] animate-fade"
      />

      <div className="flex items-center gap-2.5 font-display text-xl font-semibold tracking-tight animate-fade">
        <Mark />
        Prospect Hub
      </div>

      <div className="hidden max-w-md lg:block">
        <h2 className="text-[44px] font-medium leading-[1.04] animate-rise" style={{ animationDelay: '200ms' }}>
          Every company in Marrakech, <em className="font-normal italic opacity-90">one follow-up at a time.</em>
        </h2>
        <div className="mt-6 h-px w-24 bg-accent-fg/60 animate-draw" style={{ animationDelay: '450ms' }} />
        <ul className="mt-6 grid gap-2.5 text-[15px] opacity-90">
          {['Find the companies worth writing to', 'Send emails that sound like you', 'Never lose track of a reply'].map(
            (line, i) => (
              <li key={line} className="flex items-baseline gap-3 animate-rise" style={{ animationDelay: `${520 + i * 90}ms` }}>
                <span className="font-mono text-[11px] opacity-70">0{i + 1}</span>
                {line}
              </li>
            )
          )}
        </ul>
      </div>

      <p className="hidden font-mono text-[11px] uppercase tracking-[0.16em] opacity-70 lg:block">
        31.6295° N · 7.9811° W
      </p>
    </aside>
  );
}

/** The logo: two bars in a round mark. Drawn in the panel's colours. */
export function Mark({ inverted = true }) {
  const ring = inverted ? 'bg-accent-fg' : 'bg-accent';
  const bar = inverted ? 'bg-accent' : 'bg-accent-fg';
  return (
    <span className={`relative inline-block size-7 shrink-0 rounded-full ${ring}`} aria-hidden="true">
      <span className={`absolute left-2 top-[7px] h-3.5 w-[5px] ${bar}`} />
      <span className={`absolute left-[15px] top-[11px] h-2.5 w-[5px] ${bar}`} />
    </span>
  );
}
