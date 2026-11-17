import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useApp } from '../../store/AppContext';
import { Card, CardHeader } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Textarea } from '../../components/ui/Field';
import { Empty, Message } from '../../components/ui/Feedback';
import { Pill } from '../../components/ui/Pill';
import { dateTime } from '../../lib/format';

/** What users wrote through "Contact admin". Answering marks a message resolved. */
export function MessagesCard() {
  const { toast, reloadConfig } = useApp();
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [showResolved, setShowResolved] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  useEffect(() => {
    api.adminMessages().then(setItems).catch((e) => setError(e.message));
  }, []);

  async function update(id, patch, done) {
    setBusy(id);
    setError('');
    try {
      const m = await api.adminUpdateMessage(id, patch);
      setItems((list) => list.map((x) => (x.id === id ? m : x)));
      setDrafts((d) => ({ ...d, [id]: undefined }));
      toast(done);
      reloadConfig();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  async function remove(id) {
    if (!window.confirm('Delete this message?')) return;
    setBusy(id);
    try {
      await api.adminDeleteMessage(id);
      setItems((list) => list.filter((x) => x.id !== id));
      reloadConfig();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  const open = items.filter((m) => m.status !== 'resolved');
  const shown = showResolved ? items : open;

  return (
    <Card>
      <CardHeader
        title="Messages"
        subtitle="Sent by users from “Contact admin”. Your reply appears in their panel."
        action={
          <label className="flex items-center gap-2 text-[13px] text-muted">
            <input type="checkbox" className="size-4 accent-accent" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
            Show answered
          </label>
        }
      />
      {error && <Message tone="bad" className="mb-3">{error}</Message>}
      {!shown.length ? (
        <Empty>{open.length || !items.length ? 'No messages yet.' : 'Nothing waiting for an answer.'}</Empty>
      ) : (
        <div className="grid gap-3">
          {shown.map((m) => (
            <article key={m.id} className="grid gap-2 rounded-card border border-line p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <strong className="min-w-0 flex-1 break-words">{m.subject}</strong>
                <Pill tone={m.status === 'resolved' ? 'good' : 'warn'}>{m.status === 'resolved' ? 'answered' : 'open'}</Pill>
              </div>
              <div className="text-xs text-muted">
                {m.name || m.from} · <a href={`mailto:${m.from}`}>{m.from}</a>
                {m.phone && <> · <a href={`tel:${m.phone.replace(/[^\d+]/g, '')}`}>{m.phone}</a></>} · {dateTime(m.at)}
              </div>
              <p className="m-0 whitespace-pre-wrap">{m.body}</p>
              {m.reply && (
                <div className="rounded-xl bg-surface-2 px-3 py-2">
                  <div className="text-xs text-muted">Your reply · {dateTime(m.repliedAt)}</div>
                  <p className="m-0 whitespace-pre-wrap">{m.reply}</p>
                </div>
              )}
              <Textarea
                rows={2}
                placeholder={m.reply ? 'Change the reply…' : 'Write a reply…'}
                aria-label={`Reply to ${m.subject}`}
                value={drafts[m.id] ?? ''}
                onChange={(e) => setDrafts((d) => ({ ...d, [m.id]: e.target.value }))}
              />
              <div className="flex flex-wrap gap-1.5">
                <Button
                  size="sm"
                  variant="primary"
                  disabled={busy === m.id || !(drafts[m.id] || '').trim()}
                  onClick={() => update(m.id, { reply: drafts[m.id] }, 'Reply sent')}
                >
                  Reply
                </Button>
                <Button
                  size="sm"
                  disabled={busy === m.id}
                  onClick={() =>
                    update(m.id, { status: m.status === 'resolved' ? 'open' : 'resolved' }, m.status === 'resolved' ? 'Reopened' : 'Marked as answered')
                  }
                >
                  {m.status === 'resolved' ? 'Reopen' : 'Mark answered'}
                </Button>
                <Button size="sm" variant="danger" disabled={busy === m.id} onClick={() => remove(m.id)}>
                  Delete
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}
