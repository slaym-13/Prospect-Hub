import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Field, Input } from '../components/ui/Field';
import { Message } from '../components/ui/Feedback';
import { AuthShell } from '../features/auth/AuthShell';
import { CheckInbox } from '../features/auth/CheckInbox';

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [canSignup, setCanSignup] = useState(false);
  const [canEmail, setCanEmail] = useState(false);
  const [unverified, setUnverified] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .session()
      .then((s) => {
        if (s.user) navigate('/', { replace: true });
        else {
          setCanSignup(s.allowSignup !== false);
          setCanEmail(s.canEmail === true);
        }
      })
      .catch(() => {});
  }, [navigate]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    if (!form.email || !form.password) return setError('Enter your email and password.');
    setBusy(true);
    try {
      await api.login(form.email, form.password);
      navigate('/', { replace: true });
    } catch (err) {
      if (err.body.code === 'UNVERIFIED') setUnverified(form.email.trim().toLowerCase());
      else setError(err.message);
      setBusy(false);
    }
  }

  if (unverified) {
    return (
      <AuthShell
        title="Confirm your email"
        subtitle="One more step before you can sign in."
        footer={<button type="button" className="text-accent" onClick={() => setUnverified('')}>Back to sign in</button>}
      >
        <CheckInbox email={unverified}>
          Your account is waiting for you to confirm <strong className="break-all text-fg">{unverified}</strong>. Open the
          link in the email we sent, or ask for a new one.
        </CheckInbox>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Your companies, emails and outreach in one place."
      footer={canSignup ? <>No account yet? <Link to="/signup">Create one</Link></> : null}
    >
      <form className="grid gap-3" onSubmit={onSubmit} noValidate>
        <Field label="Email">
          <Input type="email" autoComplete="username" required autoFocus value={form.email} onChange={set('email')} />
        </Field>
        <Field label="Password">
          <Input type="password" autoComplete="current-password" required value={form.password} onChange={set('password')} />
        </Field>
        {canEmail && (
          <Link to="/forgot-password" className="-mt-1 justify-self-end text-xs text-accent">
            Forgot your password?
          </Link>
        )}
        {error && <Message tone="bad">{error}</Message>}
        <Button type="submit" variant="primary" disabled={busy} className="mt-1 justify-center py-2.5">
          {busy ? 'Please wait…' : 'Sign in'}
        </Button>
      </form>
    </AuthShell>
  );
}
