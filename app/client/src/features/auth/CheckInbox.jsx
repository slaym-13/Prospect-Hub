import { useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/Button';
import { Message } from '../../components/ui/Feedback';

/** "We sent you a link", with a way to ask for it again. */
export function CheckInbox({ email, children }) {
  const [state, setState] = useState({ busy: false, done: false, error: '' });

  async function resend() {
    setState({ busy: true, done: false, error: '' });
    try {
      await api.resendVerification(email);
      setState({ busy: false, done: true, error: '' });
    } catch (err) {
      setState({ busy: false, done: false, error: err.message });
    }
  }

  return (
    <div className="grid gap-3">
      <Message tone="plain">
        {children || (
          <>
            We sent a confirmation link to <strong className="break-all text-fg">{email}</strong>. Open it to finish
            creating your account. It can take a minute, and may land in spam.
          </>
        )}
      </Message>
      {state.done && <Message tone="good">If the account is still waiting for confirmation, a new link is on its way.</Message>}
      {state.error && <Message tone="bad">{state.error}</Message>}
      <Button type="button" disabled={state.busy} onClick={resend} className="justify-center py-2.5">
        {state.busy ? 'Sending…' : 'Send the link again'}
      </Button>
    </div>
  );
}
