import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import { useApp } from '../../store/AppContext';
import { useTheme } from '../../hooks/useTheme';
import { Toasts, Message, Spinner } from '../ui/Feedback';
import { preloadPages } from '../../pages';
import { Icon } from '../ui/Icon';
import { JobBar } from './JobBar';
import { AssistantPanel } from '../../features/assistant/AssistantPanel';
import { ContactAdminPanel } from '../../features/messages/ContactAdminPanel';
import { CommandPalette } from '../../features/search/CommandPalette';
import { Mark } from '../../features/auth/AuthShell';
import { cn } from '../../lib/cn';
import { today } from '../../lib/format';

/** The daily work. Everything else lives in the menu under your name. */
const TABS = [
  ['/', 'Dashboard', 'dashboard'],
  ['/today', 'Today', 'today'],
  ['/companies', 'Companies', 'companies'],
  ['/pipeline', 'Pipeline', 'pipeline'],
  ['/outbox', 'Outbox', 'outbox']
];

/** Pages that use the whole width of the window instead of the reading column. */
const FULL_WIDTH = ['/pipeline'];

export function AppLayout() {
  const { config, toasts, leads } = useApp();
  const { pathname } = useLocation();
  const [askOpen, setAskOpen] = useState(false);
  const [askWith, setAskWith] = useState('');
  const [contactOpen, setContactOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => preloadPages(), []);

  // Ctrl+K (Cmd+K on a Mac) opens the search from anywhere.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((o) => !o);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const ask = useCallback((question = '') => {
    setAskWith(question);
    setAskOpen(true);
  }, []);

  const now = today();
  const dueCount = leads.filter(
    (l) => l.nextStep && l.nextStep <= now && !['won', 'lost', 'optout'].includes(l.status)
  ).length;
  const badge = (to) => (to === '/today' && dueCount > 0 ? dueCount : 0);
  const wide = FULL_WIDTH.includes(pathname);

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-surface/80 backdrop-blur-md backdrop-saturate-150">
        <div className={cn('mx-auto flex items-center gap-3 px-4 py-2.5', wide ? 'max-w-none' : 'max-w-[1240px]')}>
          <Link to="/" className="flex shrink-0 items-center gap-2.5 font-display text-[19px] font-semibold tracking-tight text-fg no-underline">
            <Mark inverted={false} />
            <span className="hidden sm:inline">Prospect Hub</span>
          </Link>

          {/* On a phone these move to the bar at the bottom of the screen. */}
          <nav aria-label="Sections" className="ml-2 hidden gap-1 md:flex">
            {TABS.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 text-sm font-medium no-underline transition-colors duration-200',
                    isActive ? 'bg-accent-soft font-semibold text-accent' : 'text-muted hover:bg-surface-2 hover:text-fg'
                  )
                }
              >
                {label}
                {badge(to) > 0 && (
                  <span className="rounded-full bg-warn-soft px-1.5 font-casual text-[11px] font-semibold text-warn">{badge(to)}</span>
                )}
              </NavLink>
            ))}
          </nav>

          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="ml-auto flex min-w-0 items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-muted transition-colors hover:border-accent hover:text-accent lg:w-64"
            aria-label="Search (Ctrl+K)"
          >
            <Icon name="search" size={15} />
            <span className="hidden truncate lg:inline">Search or ask…</span>
            <kbd className="ml-auto hidden rounded-md border border-line px-1.5 font-mono text-[10px] lg:inline">Ctrl K</kbd>
          </button>

          <UserMenu onAsk={() => ask()} onContact={() => setContactOpen(true)} />
        </div>
      </header>

      <main
        className={cn(
          'mx-auto grid grid-cols-[minmax(0,1fr)] gap-4 px-4 pb-28 pt-6 md:pb-16',
          wide ? 'max-w-none' : 'max-w-[1240px]'
        )}
      >
        <JobBar />
        {config && !config.profileComplete && (
          <Message>
            Your profile is incomplete: your emails and CV need your full name, phone number and who you are.{' '}
            <Link to="/settings">Complete it in Settings</Link>.
          </Message>
        )}
        {/* keyed by the route, so each page plays its entrance once when it opens */}
        <div key={pathname} className="stagger grid grid-cols-[minmax(0,1fr)] gap-4">
          <Suspense fallback={<Spinner />}>
            <Outlet />
          </Suspense>
        </div>
      </main>

      <BottomBar badge={badge} />

      {searchOpen && <CommandPalette onClose={() => setSearchOpen(false)} onAsk={ask} />}
      {askOpen && (
        <AssistantPanel
          key={askWith}
          initialQuestion={askWith}
          onClose={() => {
            setAskOpen(false);
            setAskWith('');
          }}
        />
      )}
      {contactOpen && <ContactAdminPanel onClose={() => setContactOpen(false)} />}
      <Toasts items={toasts} />
    </>
  );
}

/** Thumb-reach navigation on a phone: the same five sections, with icons. */
function BottomBar({ badge }) {
  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
    >
      {TABS.map(([to, label, icon]) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            cn(
              'relative grid justify-items-center gap-0.5 py-2 text-[10.5px] font-medium no-underline transition-colors',
              isActive ? 'text-accent' : 'text-muted'
            )
          }
        >
          {({ isActive }) => (
            <>
              <span className={cn('rounded-full px-4 py-1 transition-colors', isActive && 'bg-accent-soft')}>
                <Icon name={icon} size={20} />
              </span>
              {label}
              {badge(to) > 0 && (
                <span className="absolute right-[18%] top-1 rounded-full bg-warn px-1.5 font-casual text-[10px] font-bold leading-4 text-white">
                  {badge(to)}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

/** Your name, and behind it everything that is not daily work. */
function UserMenu({ onAsk, onContact }) {
  const { config } = useApp();
  const { theme, cycleTheme } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  const name = config?.name || config?.user || '';
  const initials =
    name
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0].toUpperCase())
      .join('') || '?';

  async function signOut() {
    await api.logout();
    navigate('/login', { replace: true });
  }

  const go = (to) => () => {
    setOpen(false);
    navigate(to);
  };
  const run = (fn) => () => {
    setOpen(false);
    fn();
  };

  const item = 'flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm text-fg no-underline hover:bg-surface-2';

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-2.5 text-[13px] transition-colors hover:border-accent"
      >
        <span className="grid size-7 place-items-center rounded-full bg-accent font-casual text-[11px] font-bold text-accent-fg">
          {initials}
        </span>
        <span className="hidden max-w-36 truncate sm:inline">{name}</span>
        <Icon name="chevron" size={14} className={cn('text-muted transition-transform', open && 'rotate-180')} />
        {config?.isAdmin && config?.openMessages > 0 && (
          <span className="absolute -right-1 -top-1 size-2.5 rounded-full bg-warn ring-2 ring-surface" aria-label="Messages waiting" />
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+8px)] z-40 grid w-60 gap-0.5 rounded-2xl border border-line bg-surface p-1.5 shadow-[0_16px_48px_-12px_rgb(8_10_30/0.35)] animate-rise [animation-duration:0.2s]"
        >
          <div className="truncate px-3 pb-2 pt-1.5 text-xs text-muted" title={config?.user}>
            {config?.user}
          </div>
          <button type="button" role="menuitem" className={item} onClick={run(onAsk)}>
            Ask about the app
            {!config?.ai && <span className="text-[11px] text-muted">needs a key</span>}
          </button>
          <button type="button" role="menuitem" className={item} onClick={go('/cv')}>
            My CV
          </button>
          <button type="button" role="menuitem" className={item} onClick={go('/settings')}>
            Settings
          </button>
          {config?.isAdmin ? (
            <button type="button" role="menuitem" className={item} onClick={go('/admin')}>
              Admin
              {config.openMessages > 0 && (
                <span className="rounded-full bg-warn-soft px-1.5 font-casual text-[11px] font-semibold text-warn">
                  {config.openMessages}
                </span>
              )}
            </button>
          ) : (
            <button type="button" role="menuitem" className={item} onClick={run(onContact)}>
              Contact an administrator
            </button>
          )}
          <div className="my-1 border-t border-line" />
          <button type="button" role="menuitem" className={item} onClick={cycleTheme}>
            Theme
            <span className="text-xs text-muted">{theme === 'system' ? 'Auto' : theme === 'dark' ? 'Dark' : 'Light'}</span>
          </button>
          <button type="button" role="menuitem" className={cn(item, 'text-bad')} onClick={signOut}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
