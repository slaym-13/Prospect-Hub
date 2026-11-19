import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useApp } from '../store/AppContext';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Field';
import { Message, Spinner } from '../components/ui/Feedback';
import { LeadDrawer } from '../features/lead/LeadDrawer';
import { STATUS_LABEL, nf, shortDate, today } from '../lib/format';
import { cn } from '../lib/cn';

/*
 * The pipeline as a case board: each stage is a pinned label, each company an index
 * card pinned under it, and a red string runs through the stages in order.
 */

const COLUMNS = ['new', 'contacted', 'replied', 'meeting', 'won', 'lost'];
const ALL_STAGES = [...COLUMNS, 'optout'];

/** What each stage is called on the board, under its real name. */
const CASE_NOTE = {
  new: 'Leads to look into',
  contacted: 'First contact made',
  replied: 'They wrote back',
  meeting: 'Face to face',
  won: 'Case closed',
  lost: 'Gone cold'
};

const PIN = {
  new: 'var(--neutral)',
  contacted: 'var(--accent)',
  replied: 'var(--accent)',
  meeting: 'var(--warn)',
  won: 'var(--good)',
  lost: 'var(--bad)'
};

// "New" holds most of the companies; only its best few are pinned up until asked.
const FIRST = { new: 10 };
const PAGE = 25;

// Column geometry, shared by the columns and the string that joins their pins.
const COL_W = 288;
const GAP = 28;
const PAD = 28;

/** A small, steady tilt per card, so the board looks pinned by hand but never jumps. */
function tilt(id) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return ((Math.abs(h) % 9) - 4) * 0.45;
}

function ScoreMark({ lead }) {
  if (lead.excluded) return null;
  const tone = lead.score >= 65 ? 'text-good' : lead.score >= 45 ? 'text-warn' : 'text-muted';
  return (
    <span
      title="Fit score"
      className={cn(
        'grid size-9 shrink-0 rotate-[-6deg] place-items-center rounded-full border-2 border-current font-casual text-[12.5px] font-bold tabular-nums',
        tone
      )}
    >
      {lead.score}
    </span>
  );
}

function CaseCard({ lead, now, onOpen, onMove }) {
  const late = lead.nextStep && lead.nextStep <= now;
  return (
    <article
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', lead.id);
        e.dataTransfer.effectAllowed = 'move';
      }}
      style={{ '--tilt': `${tilt(lead.id)}deg`, '--pin': PIN[lead.status] }}
      className="index-card group relative grid cursor-grab gap-1.5 rounded-[3px] px-3 pb-2.5 pt-3.5 transition-[rotate,translate,box-shadow] duration-200 [rotate:var(--tilt)] hover:z-10 hover:-translate-y-0.5 hover:[rotate:0deg] hover:shadow-[0_18px_30px_-12px_rgb(40_20_0/0.5)] active:cursor-grabbing"
    >
      <span className="pushpin absolute -top-1.5 left-1/2 -translate-x-1/2" aria-hidden="true" />

      <div className="flex min-w-0 items-start gap-2">
        <button
          type="button"
          onClick={onOpen}
          className="line-clamp-2 min-w-0 flex-1 text-left text-[14px] font-semibold leading-snug hover:text-accent"
          title={lead.nom}
        >
          {lead.nom}
        </button>
        <ScoreMark lead={lead} />
      </div>

      <div className="font-mono text-[11px] leading-5 text-muted">
        {lead.categorie && <div className="truncate">{lead.categorie}</div>}
        {lead.telephone && <div>☎ {lead.telephone}</div>}
      </div>

      <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-[11.5px]">
        {lead.nextStep && (
          <span className={cn('rounded px-1.5 font-medium', late ? 'bg-bad-soft text-bad' : 'bg-surface-2 text-muted')}>
            {late ? 'Due ' : 'Next '}
            {shortDate(lead.nextStep)}
          </span>
        )}
        {!lead.email && <span className="rounded bg-warn-soft px-1.5 font-medium text-warn">No email</span>}
        {lead.star && <span className="text-warn">★</span>}

        {/* Dragging does not work on a touch screen, so every card keeps a menu. */}
        <Select
          aria-label={`Stage for ${lead.nom}`}
          className="ml-auto w-auto! border-transparent bg-transparent py-0 pl-1 pr-0 text-[11.5px] text-muted hover:text-accent"
          value={lead.status}
          onChange={(e) => onMove(lead.id, e.target.value)}
        >
          {ALL_STAGES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </Select>
      </div>

      {lead.status === 'won' && <span className="stamp pointer-events-none absolute bottom-2 right-9 text-good">Closed</span>}
      {lead.status === 'lost' && <span className="stamp pointer-events-none absolute bottom-2 right-9 text-bad">Cold</span>}
    </article>
  );
}

/** The red string through the stage pins, sagging a little between each. */
function RedString({ count }) {
  const xs = Array.from({ length: count }, (_, i) => PAD + COL_W / 2 + i * (COL_W + GAP));
  const y = 34; // board padding + label margin + pin centre
  const d = xs.reduce((path, x, i) => {
    if (i === 0) return `M ${x} ${y}`;
    const mid = (xs[i - 1] + x) / 2;
    return `${path} Q ${mid} ${y + 30 + (i % 2) * 8} ${x} ${y}`;
  }, '');
  const width = xs[xs.length - 1] + COL_W / 2 + PAD;
  return (
    <svg
      className="pointer-events-none absolute left-0 top-0 z-[1] overflow-visible"
      width={width}
      height="80"
      aria-hidden="true"
    >
      <path d={d} fill="none" stroke="rgb(0 0 0 / 0.22)" strokeWidth="2.5" transform="translate(1.5 3)" />
      <path d={d} fill="none" stroke="var(--bad)" strokeWidth="2" strokeLinecap="round" className="animate-fade" />
    </svg>
  );
}

export default function Pipeline() {
  const { leads, loading, error, mergeLead, toast } = useApp();
  const [openId, setOpenId] = useState(null);
  const [dragOver, setDragOver] = useState(null);
  const [query, setQuery] = useState('');
  const [shown, setShown] = useState(() => Object.fromEntries(COLUMNS.map((s) => [s, FIRST[s] || PAGE])));

  const byStatus = useMemo(() => {
    const q = query.trim().toLowerCase();
    const groups = Object.fromEntries(COLUMNS.map((s) => [s, []]));
    for (const lead of leads) {
      if (!groups[lead.status]) continue;
      if (q && !`${lead.nom} ${lead.categorie}`.toLowerCase().includes(q)) continue;
      groups[lead.status].push(lead);
    }
    // Follow-ups that are already due float to the top, then the best score.
    const now = today();
    for (const list of Object.values(groups)) {
      list.sort((a, b) => {
        const aDue = a.nextStep && a.nextStep <= now ? 0 : 1;
        const bDue = b.nextStep && b.nextStep <= now ? 0 : 1;
        return aDue - bDue || b.score - a.score;
      });
    }
    return groups;
  }, [leads, query]);

  async function move(id, status) {
    const lead = leads.find((l) => l.id === id);
    if (!lead || lead.status === status) return;
    try {
      mergeLead(await api.patchLead(id, { status }));
      toast(`${lead.nom} → ${STATUS_LABEL[status]}`);
    } catch (e) {
      toast(e.message, 'bad');
    }
  }

  if (loading) return <Spinner />;
  if (error) return <Message tone="bad">{error}</Message>;

  const now = today();
  const inPlay = ['contacted', 'replied', 'meeting'].reduce((n, s) => n + byStatus[s].length, 0);
  const dueTotal = COLUMNS.reduce((n, s) => n + byStatus[s].filter((l) => l.nextStep && l.nextStep <= now).length, 0);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">Case board</p>
          <h1 className="text-[30px] leading-tight">Pipeline</h1>
          <p className="mt-1 text-sm text-muted">
            <span className="font-casual font-bold text-fg">{nf(inPlay)}</span> in progress ·{' '}
            <span className="font-casual font-bold text-fg">{nf(byStatus.won.length)}</span> won
            {dueTotal > 0 && (
              <>
                {' '}· <span className="font-semibold text-bad">{dueTotal} due today</span>
              </>
            )}
            <span className="hidden sm:inline"> · drag a card to move it</span>
          </p>
        </div>
        <Input
          type="search"
          placeholder="Filter the board…"
          aria-label="Filter the board"
          className="w-64"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="corkboard overflow-x-auto rounded-[14px]">
        <div
          className="relative flex h-[calc(100dvh-14rem)] min-h-[560px] w-max items-stretch pb-6 pt-4"
          style={{ gap: GAP, paddingLeft: PAD, paddingRight: PAD }}
        >
          <RedString count={COLUMNS.length} />

          {COLUMNS.map((status) => {
            const list = byStatus[status];
            const limit = shown[status];
            const step = FIRST[status] || PAGE;
            return (
              <section
                key={status}
                aria-label={STATUS_LABEL[status]}
                style={{ width: COL_W, '--pin': PIN[status] }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(status);
                }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget)) setDragOver((s) => (s === status ? null : s));
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(null);
                  const id = e.dataTransfer.getData('text/plain');
                  if (id) move(id, status);
                }}
                className={cn(
                  'flex shrink-0 flex-col rounded-xl transition-colors duration-200',
                  dragOver === status && 'bg-white/15 outline-2 outline-offset-4 outline-dashed outline-accent'
                )}
              >
                {/* the stage's label, pinned where the string passes */}
                <header className="relative z-[2] mx-auto mb-5 mt-2 w-[85%] rotate-[-1deg] rounded-[3px] bg-surface px-3 pb-2 pt-4 text-center shadow-[0_6px_12px_-6px_rgb(40_20_0/0.45)]">
                  <span className="pushpin absolute left-1/2 top-[3px] -translate-x-1/2" aria-hidden="true" />
                  <h2 className="font-mono text-[12px] font-bold uppercase tracking-[0.2em]">
                    {STATUS_LABEL[status]}
                    <span className="ml-2 font-casual text-[13px] tracking-normal text-bad">{list.length}</span>
                  </h2>
                  <p className="m-0 text-[11.5px] italic text-muted">
                    {status === 'new' && list.length > limit ? `the best ${limit} of ${nf(list.length)}` : CASE_NOTE[status]}
                  </p>
                </header>

                {/* each column scrolls on its own; the board stays one screen tall */}
                <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-2 pb-2 pt-2 [scrollbar-width:thin]">
                  {list.slice(0, limit).map((lead) => (
                    <CaseCard key={lead.id} lead={lead} now={now} onOpen={() => setOpenId(lead.id)} onMove={move} />
                  ))}

                  {!list.length && <EmptyColumn status={status} filtered={!!query} />}

                  {list.length > limit && (
                    <button
                      type="button"
                      onClick={() => setShown((s) => ({ ...s, [status]: s[status] + step }))}
                      className="tape mx-auto mt-2 rounded-[3px] bg-surface/90 px-4 py-2 text-[12.5px] font-medium text-muted shadow-[0_4px_10px_-4px_rgb(40_20_0/0.4)] hover:text-accent"
                    >
                      Pin {Math.min(step, list.length - limit)} more · {nf(list.length - limit)} left
                    </button>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </div>

      {openId && <LeadDrawer leadId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}

/** What an empty stage is waiting for, and how to get something into it. */
function EmptyColumn({ status, filtered }) {
  const text = filtered
    ? 'Nothing here matches the filter.'
    : {
        new: 'Every lead has been looked into.',
        contacted: 'Drag a lead here once you have called or written.',
        replied: 'Move a card here when they answer.',
        meeting: 'Booked a visit or a call? Pin it here.',
        won: 'Your first win goes here.',
        lost: 'Nothing has gone cold. Good.'
      }[status];
  return (
    <div className="mx-1 grid justify-items-center gap-2 rounded-[3px] border-2 border-dashed border-[color-mix(in_oklab,var(--fg)_22%,transparent)] px-3 py-5 text-center">
      <p className="m-0 text-[12.5px] font-medium text-[color-mix(in_oklab,var(--fg)_70%,transparent)]">{text}</p>
      {status === 'contacted' && !filtered && (
        <Button as={Link} to="/today" size="sm">
          Find someone to contact →
        </Button>
      )}
    </div>
  );
}
