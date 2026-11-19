import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../store/AppContext';
import { Icon } from '../../components/ui/Icon';
import { STATUS_LABEL } from '../../lib/format';
import { cn } from '../../lib/cn';

const PAGES = [
  ['Dashboard', '/', 'dashboard'],
  ['Today', '/today', 'today'],
  ['Companies', '/companies', 'companies'],
  ['Map of the companies', '/companies?view=map', 'map'],
  ['Pipeline board', '/pipeline', 'pipeline'],
  ['Outbox', '/outbox', 'outbox'],
  ['CV', '/cv', 'table'],
  ['Settings', '/settings', 'dashboard'],
  ['Admin', '/admin', 'dashboard', 'admin']
];

const fold = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const rank = (name, q) => {
  const i = fold(name).indexOf(q);
  return i < 0 ? 1000 : i;
};

/**
 * Ctrl+K: jump to a page, open a company by name, or hand the words to the assistant.
 * Arrow keys move, Enter picks, Escape closes.
 */
export function CommandPalette({ onClose, onAsk }) {
  const { leads, config } = useApp();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => inputRef.current?.focus(), []);

  const items = useMemo(() => {
    const q = fold(query.trim());
    const pages = PAGES.filter(([label, , , only]) => (!only || config?.isAdmin) && (!q || fold(label).includes(q))).map(
      ([label, to, icon]) => ({ key: to, label, hint: 'Page', icon, run: () => navigate(to) })
    );
    const companies = q
      ? leads
          .filter((l) => fold(`${l.nom} ${l.categorie}`).includes(q))
          // names that start with the words first, then names containing them, then category matches
          .sort((a, b) => rank(a.nom, q) - rank(b.nom, q) || b.score - a.score)
          .slice(0, 8)
          .map((l) => ({
            key: l.id,
            label: l.nom,
            hint: `${l.categorie || 'Company'} · ${STATUS_LABEL[l.status]}`,
            icon: 'companies',
            run: () => navigate(`/companies?open=${encodeURIComponent(l.id)}`)
          }))
      : [];
    const ask = q
      ? [{ key: 'ask', label: `Ask the assistant: “${query.trim()}”`, hint: 'AI', icon: 'ask', run: () => onAsk(query.trim()) }]
      : [];
    return [...companies, ...pages.slice(0, q ? 4 : PAGES.length), ...ask];
  }, [query, leads, config, navigate, onAsk]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  function pick(item) {
    if (!item) return;
    onClose();
    item.run();
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => Math.min(items.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      pick(items[active]);
    } else if (e.key === 'Escape') {
      onClose();
    }
  }

  return (
    <div className="fixed inset-0 z-60 grid items-start justify-items-center bg-[rgb(8_10_30/0.4)] px-4 pt-[12vh] backdrop-blur-[2px] animate-fade [animation-duration:0.2s]" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-[min(600px,100%)] overflow-hidden rounded-card border border-line bg-surface shadow-[0_24px_80px_-12px_rgb(8_10_30/0.45)] animate-rise [animation-duration:0.3s]"
      >
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Icon name="search" className="shrink-0 text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search a company, a page, or ask a question…"
            aria-label="Search"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={items[active] ? `palette-${active}` : undefined}
            className="h-14 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted/70"
          />
          <kbd className="hidden rounded-md border border-line px-1.5 py-0.5 font-mono text-[10.5px] text-muted sm:block">Esc</kbd>
        </div>

        <ul id="palette-list" ref={listRef} role="listbox" className="max-h-[min(420px,60vh)] overflow-y-auto p-2">
          {items.map((item, i) => (
            <li
              key={item.key}
              id={`palette-${i}`}
              data-index={i}
              role="option"
              aria-selected={i === active}
              onMouseMove={() => setActive(i)}
              onClick={() => pick(item)}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5',
                i === active ? 'bg-accent-soft text-accent' : 'text-fg'
              )}
            >
              <Icon name={item.icon} size={17} className={i === active ? '' : 'text-muted'} />
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{item.label}</span>
              <span className="shrink-0 font-mono text-[10.5px] uppercase tracking-wider text-muted">{item.hint}</span>
            </li>
          ))}
          {!items.length && <li className="px-3 py-6 text-center text-sm text-muted">Nothing found.</li>}
        </ul>
      </div>
    </div>
  );
}
