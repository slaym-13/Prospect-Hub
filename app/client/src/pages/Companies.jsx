import { lazy, Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useApp } from '../store/AppContext';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Field';
import { Empty, Message, Spinner } from '../components/ui/Feedback';
import { Icon } from '../components/ui/Icon';
import { cn } from '../lib/cn';
import { Pill, ScorePill } from '../components/ui/Pill';
import { DataTable } from '../components/ui/DataTable';
import { LeadDrawer } from '../features/lead/LeadDrawer';
import { STATUS_LABEL, STATUS_TONE, nf } from '../lib/format';

// Leaflet and the map code download only when the map is first opened.
const CompaniesMap = lazy(() => import('../features/map/CompaniesMap'));
const LEGEND = [
  ['Not contacted', 'bg-muted'],
  ['In progress', 'bg-accent'],
  ['Won', 'bg-good'],
  ['Lost or opted out', 'bg-bad']
];

const EMAIL_FILTERS = [
  ['', 'All'],
  ['has', 'Has email'],
  ['none', 'No email'],
  ['nosite', 'No website']
];

export default function Companies() {
  const { leads, config, loading, error } = useApp();
  const [query, setQuery] = useState('');
  const [emailFilter, setEmailFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sort, setSort] = useState({ key: 'score', dir: -1 });
  const [limit, setLimit] = useState(100);
  // The view and the open company live in the address, so the search (Ctrl+K) and
  // the back button can reach them.
  const [params, setParams] = useSearchParams();
  const view = params.get('view') === 'map' ? 'map' : 'table';
  const openId = params.get('open');
  const update = (changes) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p);
        for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
        return next;
      },
      { replace: true }
    );
  const setOpenId = (id) => update({ open: id });
  const clearFilters = () => {
    setQuery('');
    setEmailFilter('');
    setStatusFilter('');
  };

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = leads.filter((l) => {
      if (q && !`${l.nom} ${l.adresse} ${l.categorie} ${l.email}`.toLowerCase().includes(q)) return false;
      if (statusFilter && l.status !== statusFilter) return false;
      if (emailFilter === 'has' && !l.email) return false;
      if (emailFilter === 'none' && l.email) return false;
      if (emailFilter === 'nosite' && l.site_web) return false;
      return true;
    });

    const { key, dir } = sort;
    return filtered.sort((a, b) => {
      const x = a[key];
      const y = b[key];
      if (typeof x === 'number' || typeof y === 'number') return ((Number(x) || 0) - (Number(y) || 0)) * dir;
      return String(x || '').localeCompare(String(y || '')) * dir;
    });
  }, [leads, query, emailFilter, statusFilter, sort]);

  function toggleSort(key) {
    setSort((s) => ({ key, dir: s.key === key ? -s.dir : key === 'nom' ? 1 : -1 }));
  }

  if (loading) return <Spinner />;
  if (error) return <Message tone="bad">{error}</Message>;

  const columns = [
    {
      key: 'nom',
      header: 'Company',
      sortable: true,
      render: (l) => (
        <>
          <strong className="font-semibold">
            {l.star && <span className="text-warn">★ </span>}
            {l.nom}
          </strong>
          <div className="text-xs text-muted">{l.telephone}</div>
        </>
      )
    },
    { key: 'categorie', header: 'Category', sortable: true, render: (l) => l.categorie || '' },
    { key: 'score', header: 'Score', sortable: true, align: 'right', render: (l) => <ScorePill score={l.score} excluded={l.excluded} /> },
    {
      key: 'note',
      header: 'Rating',
      sortable: true,
      align: 'right',
      render: (l) => (l.note ? `${l.note} (${l.nombre_avis || 0})` : '—')
    },
    {
      key: 'email',
      header: 'Email',
      sortable: true,
      render: (l) => (l.email ? <span className="break-all">{l.email}</span> : <span className="text-muted">—</span>)
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (l) => <Pill tone={STATUS_TONE[l.status]}>{STATUS_LABEL[l.status]}</Pill>
    }
  ];

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="search"
          placeholder="Search name, address, category…"
          aria-label="Search companies"
          className="w-auto! min-w-0 flex-1 basis-55"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setLimit(100);
          }}
        />
        <Select className="w-auto!" aria-label="Email filter" value={emailFilter} onChange={(e) => setEmailFilter(e.target.value)}>
          {EMAIL_FILTERS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <Select className="w-auto!" aria-label="Status filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Any status</option>
          {config.statuses.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </Select>
        <span className="flex-1" />
        <div className="flex overflow-hidden rounded-full border border-line bg-surface" role="group" aria-label="View">
          {[
            ['table', 'Table', 'table'],
            ['map', 'Map', 'map']
          ].map(([value, label, icon]) => (
            <button
              key={value}
              type="button"
              aria-pressed={view === value}
              onClick={() => update({ view: value === 'map' ? 'map' : '' })}
              className={cn(
                'flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium transition-colors',
                view === value ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'
              )}
            >
              <Icon name={icon} size={16} />
              {label}
            </button>
          ))}
        </div>
        <Button href="/api/export.csv">Download CSV</Button>
      </div>

      {view === 'map' ? (
        <Card className="grid gap-3 p-3 sm:p-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[12.5px] text-muted">
            <span>
              <strong className="font-casual font-bold text-fg">{nf(rows.filter((l) => l.latitude != null).length)}</strong> companies
              on the map · bigger pins score higher · click one to open it
            </span>
            <span className="flex flex-wrap gap-3 sm:ml-auto">
              {LEGEND.map(([label, color]) => (
                <span key={label} className="flex items-center gap-1.5">
                  <span className={cn('size-2.5 rounded-full', color)} />
                  {label}
                </span>
              ))}
            </span>
          </div>
          <div className="h-[min(68vh,720px)] min-h-[380px] overflow-hidden rounded-xl border border-line">
            <Suspense fallback={<Spinner label="Loading the map…" />}>
              <CompaniesMap leads={rows} onOpen={setOpenId} />
            </Suspense>
          </div>
        </Card>
      ) : (
      <Card>
        <p className="mb-3 text-[13px] text-muted">
          {nf(rows.length)} companies{rows.length > limit ? ` (showing ${limit})` : ''}
        </p>
        <DataTable
          columns={columns}
          rows={rows.slice(0, limit)}
          rowKey={(l) => l.id}
          onRowClick={(l) => setOpenId(l.id)}
          sort={sort}
          onSort={toggleSort}
          empty={
            <Empty title="No company matches" action={<Button onClick={clearFilters}>Clear the filters</Button>}>
              Try fewer words, or another status or email filter.
            </Empty>
          }
        />
        {rows.length > limit && (
          <div className="pt-3 text-center">
            <Button onClick={() => setLimit((n) => n + 200)}>Show more</Button>
          </div>
        )}
      </Card>
      )}

      {openId && <LeadDrawer leadId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}
