import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Field, Input } from '../components/ui/Field';
import { Message } from '../components/ui/Feedback';
import { AuthShell } from '../features/auth/AuthShell';

const MIN_PASSWORD = 10;

/** Opened from the emailed link: choose a new password, then go straight in. */
export default function ResetPassword() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [form, setForm] = useState({ password: '', confirm: '' });
  const [error, setError] = useState('');
  const [badLink, setBadLink] = useState(!token);
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const tooShort = form.password.length > 0 && form.password.length < MIN_PASSWORD;
  const mismatch = form.confirm.length > 0 && form.password !== form.confirm;
  const ready = form.password.length >= MIN_PASSWORD && form.password === form.confirm;

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    if (!ready) return;
    setBusy(true);
    try {
      await api.resetPassword(token, form.password, form.confirm);
      navigate('/', { replace: true });
    } catch (err) {
      if (err.body.code === 'BAD_TOKEN') setBadLink(true);
      else setError(err.message);
      setBusy(false);
    }
  }

  if (badLink) {
    return (
      <AuthShell
        title="This link no longer works"
        subtitle="Reset links work once, for one hour."
        footer={<Link to="/login">Back to sign in</Link>}
      >
        <Link to="/forgot-password" className="text-center text-sm font-medium text-accent">
          Ask for a new link
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="You will be signed in as soon as it is saved."
      footer={<Link to="/login">Back to sign in</Link>}
    >
      <form className="grid gap-3" onSubmit={onSubmit} noValidate>
        <Field label="New password" invalid={tooShort} hint={tooShort ? `${MIN_PASSWORD} characters minimum` : undefined}>
          <Input type="password" autoComplete="new-password" required autoFocus value={form.password} onChange={set('password')} />
        </Field>
        <Field label="Confirm new password" invalid={mismatch} hint={mismatch ? 'The two passwords do not match.' : undefined}>
          <Input
            type="password"
            autoComplete="new-password"
            required
            value={form.confirm}
            onChange={set('confirm')}
            className={mismatch ? 'border-bad' : undefined}
          />
        </Field>
        {error && <Message tone="bad">{error}</Message>}
        <Button type="submit" variant="primary" disabled={busy || !ready} className="mt-1 justify-center py-2.5">
          {busy ? 'Saving…' : 'Save and sign in'}
        </Button>
      </form>
    </AuthShell>
  );
}
