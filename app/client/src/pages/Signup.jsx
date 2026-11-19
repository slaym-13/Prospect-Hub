import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Field, Input, Textarea } from '../components/ui/Field';
import { Message } from '../components/ui/Feedback';
import { AuthShell } from '../features/auth/AuthShell';
import { CheckInbox } from '../features/auth/CheckInbox';

const MIN_PASSWORD = 10;
const PHONE = /^\+?[0-9 ().-]{8,24}$/;
const digits = (s) => (s.match(/\d/g) || []).length;

const BLANK = {
  fullName: '', email: '', phone: '', headline: '', city: '', linkedin: '', background: '',
  password: '', confirm: ''
};

/** Create your own account. The server checks everything again; this is for the person. */
export default function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState(BLANK);
  const [open, setOpen] = useState(true);
  const [pending, setPending] = useState(null); // { email, sent } once the account waits for its link
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .session()
      .then((s) => {
        if (s.user) navigate('/', { replace: true });
        else setOpen(s.allowSignup !== false);
      })
      .catch(() => {});
  }, [navigate]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const tooShort = form.password.length > 0 && form.password.length < MIN_PASSWORD;
  const mismatch = form.confirm.length > 0 && form.password !== form.confirm;
  const nameBad = form.fullName.length > 0 && !/\S+\s+\S+/.test(form.fullName.trim());
  const phoneBad = form.phone.length > 0 && (!PHONE.test(form.phone.trim()) || digits(form.phone) < 8);
  const ready =
    /\S+\s+\S+/.test(form.fullName.trim()) &&
    form.email &&
    PHONE.test(form.phone.trim()) && digits(form.phone) >= 8 &&
    form.headline.trim().length >= 3 &&
    form.password.length >= MIN_PASSWORD &&
    form.password === form.confirm;

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    if (!ready) return;
    setBusy(true);
    try {
      const res = await api.signup(form);
      if (res.verify) {
        setPending({ email: res.user, sent: res.sent !== false });
        setBusy(false);
        return;
      }
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (pending) {
    return (
      <AuthShell
        title="Check your inbox"
        subtitle="Your account is created. Confirm your email address to start."
        footer={<Link to="/login">Back to sign in</Link>}
      >
        {pending.sent ? (
          <CheckInbox email={pending.email} />
        ) : (
          <CheckInbox email={pending.email}>
            Your account is created, but the confirmation email could not be sent just now. Try again below, or ask an
            administrator to confirm <strong className="break-all text-fg">{pending.email}</strong>.
          </CheckInbox>
        )}
      </AuthShell>
    );
  }

  if (!open) {
    return (
      <AuthShell
        title="Registration is closed"
        subtitle="New accounts are created by an administrator on this instance."
        footer={<Link to="/login">Back to sign in</Link>}
      >
        <div />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Your details sign every email you send and head your CV. You can change them later in Settings."
      wide
      footer={
        <>
          Already have an account? <Link to="/login">Sign in</Link>
        </>
      }
    >
      <form className="grid gap-3" onSubmit={onSubmit} noValidate>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name *" invalid={nameBad} hint={nameBad ? 'First and last name' : undefined}>
            <Input autoComplete="name" required autoFocus value={form.fullName} onChange={set('fullName')} />
          </Field>
          <Field label="Phone number *" invalid={phoneBad} hint={phoneBad ? 'e.g. 06 12 34 56 78' : undefined}>
            <Input type="tel" autoComplete="tel" required placeholder="06 12 34 56 78" value={form.phone} onChange={set('phone')} />
          </Field>
          <Field label="Email *">
            <Input type="email" autoComplete="username" required value={form.email} onChange={set('email')} />
          </Field>
          <Field label="City">
            <Input autoComplete="address-level2" placeholder="Marrakech" value={form.city} onChange={set('city')} />
          </Field>
          <Field label="Who you are *" className="sm:col-span-2">
            <Input
              required
              placeholder="3rd-year computer science student, FST Marrakech"
              value={form.headline}
              onChange={set('headline')}
            />
          </Field>
          <Field label="LinkedIn or portfolio" className="sm:col-span-2">
            <Input type="url" placeholder="https://linkedin.com/in/…" value={form.linkedin} onChange={set('linkedin')} />
          </Field>
          <Field label="Short background (skills, projects) — the AI uses it in your emails" className="sm:col-span-2">
            <Textarea rows={3} value={form.background} onChange={set('background')} />
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Password *" invalid={tooShort} hint={tooShort ? `${MIN_PASSWORD} characters minimum` : undefined}>
          <Input
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={set('password')}
            aria-invalid={tooShort || undefined}
          />
        </Field>

        <Field label="Confirm password *" invalid={mismatch} hint={mismatch ? 'The two passwords do not match.' : undefined}>
          <Input
            type="password"
            autoComplete="new-password"
            required
            value={form.confirm}
            onChange={set('confirm')}
            aria-invalid={mismatch || undefined}
            className={mismatch ? 'border-bad' : undefined}
          />
        </Field>
        </div>
        <p className="m-0 text-[11px] text-muted">* required</p>

        {error && <Message tone="bad">{error}</Message>}

        <Button type="submit" variant="primary" disabled={busy || !ready} className="mt-1 justify-center py-2.5">
          {busy ? 'Creating…' : 'Create account'}
        </Button>
      </form>
    </AuthShell>
  );
}
