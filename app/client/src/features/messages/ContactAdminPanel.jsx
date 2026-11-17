import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useApp } from '../../store/AppContext';
import { Drawer } from '../../components/ui/Drawer';
import { Button } from '../../components/ui/Button';
import { Field, Input, Textarea } from '../../components/ui/Field';
import { Message } from '../../components/ui/Feedback';
import { Pill } from '../../components/ui/Pill';
import { dateTime } from '../../lib/format';

/** Write to the administrators, and read their answers. */
export function ContactAdminPanel({ onClose }) {
  const { toast } = useApp();
  const [mine, setMine] = useState([]);
  const [form, setForm] = useState({ subject: '', body: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.myMessages().then(setMine).catch((e) => setError(e.message));
  }, []);

  async function send(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const m = await api.sendMessage(form);
      setMine((list) => [m, ...list]);
      setForm({ subject: '', body: '' });
      toast('Message sent to the administrators');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title="Contact an administrator"
      badge={<span className="text-[13px] text-muted">A question, a company to add, an account problem…</span>}
    >
      <form className="grid gap-2.5" onSubmit={send}>
        <Field label="Subject">
          <Input maxLength={120} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
        </Field>
        <Field label="Message">
          <Textarea rows={5} maxLength={2000} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
        </Field>
        {error && <Message tone="bad">{error}</Message>}
        <div>
          <Button type="submit" variant="primary" disabled={busy || form.subject.trim().length < 3 || form.body.trim().length < 10}>
            {busy ? 'Sending…' : 'Send'}
          </Button>
        </div>
      </form>

      {!!mine.length && (
        <div className="grid gap-2.5">
          <h3 className="text-[15px] font-semibold tracking-tight">Your messages</h3>
          {mine.map((m) => (
            <article key={m.id} className="grid gap-1.5 rounded-card border border-line p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <strong className="min-w-0 flex-1 break-words">{m.subject}</strong>
                <Pill tone={m.status === 'resolved' ? 'good' : 'warn'}>{m.status === 'resolved' ? 'answered' : 'waiting'}</Pill>
              </div>
              <p className="m-0 whitespace-pre-wrap text-muted">{m.body}</p>
              <span className="text-xs text-muted">{dateTime(m.at)}</span>
              {m.reply && (
                <div className="rounded-xl bg-surface-2 px-3 py-2">
                  <div className="text-xs text-muted">Reply · {dateTime(m.repliedAt)}</div>
                  <p className="m-0 whitespace-pre-wrap">{m.reply}</p>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </Drawer>
  );
}
