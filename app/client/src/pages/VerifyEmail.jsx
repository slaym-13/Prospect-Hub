import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { Spinner } from '../components/ui/Feedback';
import { AuthShell } from '../features/auth/AuthShell';

/** Opened from the confirmation email: confirms the address and signs the person in. */
export default function VerifyEmail() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [failed, setFailed] = useState(!token);
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return; // StrictMode runs effects twice in development
    started.current = true;
    api
      .verifyEmail(token)
      .then(() => navigate('/', { replace: true }))
      .catch(() => setFailed(true));
  }, [token, navigate]);

  if (!failed) return <Spinner label="Confirming your email address…" />;

  return (
    <AuthShell
      title="This link no longer works"
      subtitle="Confirmation links expire after 48 hours. Sign in with your email and password to get a new one."
      footer={<Link to="/login">Go to sign in</Link>}
    >
      <div />
    </AuthShell>
  );
}
