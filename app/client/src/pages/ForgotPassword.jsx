import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Button } from '../components/ui/Button';
import { Field, Input } from '../components/ui/Field';
import { Message } from '../components/ui/Feedback';
import { AuthShell } from '../features/auth/AuthShell';

/** Ask for a reset link. The answer is the same whether or not the address has an account. */
export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    if (!email) return setError('Enter your email address.');
    setBusy(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Forgot your password?"
      subtitle="Enter your email and we will send you a link to choose a new one."
      footer={<Link to="/login">Back to sign in</Link>}
    >
      {sent ? (
        <Message tone="good">
          If an account uses <strong className="break-all">{email}</strong>, a reset link is on its way. It works for one
          hour. Check your spam folder if it does not arrive.
        </Message>
      ) : (
        <form className="grid gap-3" onSubmit={onSubmit} noValidate>
          <Field label="Email">
            <Input type="email" autoComplete="username" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          {error && <Message tone="bad">{error}</Message>}
          <Button type="submit" variant="primary" disabled={busy} className="mt-1 justify-center py-2.5">
            {busy ? 'Sending…' : 'Send the reset link'}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
