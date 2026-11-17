import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useApp } from '../../store/AppContext';
import { Card, CardHeader } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Field, Input, Textarea } from '../../components/ui/Field';
import { Message, Spinner } from '../../components/ui/Feedback';
import { Pill } from '../../components/ui/Pill';

/**
 * The signed-in person, as their emails and CV present them. Each account has its own,
 * so two people using the app never send under each other's name.
 */
export function ProfileCard() {
  const { config, reloadConfig } = useApp();
  const [form, setForm] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.profile().then(setForm).catch((e) => setMessage({ tone: 'bad', text: e.message }));
  }, []);

  if (!form) return message ? <Message tone="bad">{message.text}</Message> : <Spinner />;

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      setForm(await api.saveProfile(form));
      setMessage({ tone: 'good', text: 'Profile saved.' });
      reloadConfig();
    } catch (err) {
      setMessage({ tone: 'bad', text: err.message });
    } finally {
      setBusy(false);
    }
  }

  const defaultSignature = [form.fullName, form.headline, form.phone, form.email].filter(Boolean).join('\n');

  return (
    <Card>
      <CardHeader
        title="Your profile"
        subtitle="You are the sender: the AI writes as you, the signature carries your details, and replies come back to you."
        action={<Pill tone={config.profileComplete ? 'good' : 'warn'}>{config.profileComplete ? 'complete' : 'incomplete'}</Pill>}
      />
      <form className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr))]" onSubmit={save}>
        <Field label="Full name *">
          <Input autoComplete="name" value={form.fullName} onChange={set('fullName')} />
        </Field>
        <Field label="Phone number *">
          <Input type="tel" autoComplete="tel" value={form.phone} onChange={set('phone')} />
        </Field>
        <Field label="Email (your sign-in)">
          <Input value={form.email} disabled />
        </Field>
        <Field label="City">
          <Input value={form.city} onChange={set('city')} />
        </Field>
        <Field label='Who you are * (e.g. "3rd-year engineering student, ENSA Marrakech")' className="col-span-full">
          <Input value={form.headline} onChange={set('headline')} />
        </Field>
        <Field label="LinkedIn or portfolio">
          <Input type="url" value={form.linkedin} onChange={set('linkedin')} />
        </Field>
        <Field label='Period / availability (e.g. "July–August 2027")'>
          <Input value={form.period} onChange={set('period')} />
        </Field>
        <Field label="Short background the AI may use (skills, projects)" className="col-span-full">
          <Textarea rows={4} value={form.background} onChange={set('background')} />
        </Field>
        <Field label="Replies go to" hint="Leave empty to receive replies at your sign-in email.">
          <Input type="email" placeholder={form.email} value={form.replyTo} onChange={set('replyTo')} />
        </Field>
        <Field label="Signature" hint="Leave empty to sign with your name, who you are, phone and email." className="col-span-full">
          <Textarea rows={3} placeholder={defaultSignature} value={form.signature} onChange={set('signature')} />
        </Field>
        <div className="col-span-full flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save profile'}
          </Button>
          {message && <Message tone={message.tone}>{message.text}</Message>}
        </div>
      </form>
    </Card>
  );
}
