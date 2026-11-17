import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useApp } from '../store/AppContext';
import { Card, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Field, Input, Select, Textarea } from '../components/ui/Field';
import { Empty, Message, Spinner } from '../components/ui/Feedback';
import { CV_CSS, CvDocument, cvToHtml } from '../features/cv/CvDocument';
import { dateTime } from '../lib/format';

const BLANK = { target: '', summary: '', experience: '', education: '', projects: '', skills: '', languages: '' };

const HINT = 'One block per entry, separated by an empty line. First line: title - organisation (period). Then one line per point.';

/** Build a one-page CV from your profile and a few notes, with Gemini or as typed. */
export default function Cv() {
  const { config, loading, reloadConfig } = useApp();
  const [input, setInput] = useState(BLANK);
  const [language, setLanguage] = useState('fr');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState(null);

  useEffect(() => {
    api
      .cv()
      .then((r) => {
        setInput({ ...BLANK, ...r.input });
        if (r.language) setLanguage(r.language);
        setResult(r);
      })
      .catch((e) => setMessage({ tone: 'bad', text: e.message }));
  }, []);

  // The account settings arrive separately; wait for both before reading config.ai.
  if (loading || !config || (!result && !message)) return <Spinner />;

  const set = (key) => (e) => setInput((f) => ({ ...f, [key]: e.target.value }));

  // Same rule as the Ask button: grey, and the hover says why.
  const aiReason = !config.ai
    ? config.aiError || 'No API key yet. Add your Gemini key in Settings.'
    : config.aiError
      ? `The last AI request failed: ${config.aiError}`
      : '';

  async function build(ai) {
    setBusy(ai ? 'ai' : 'plain');
    setMessage(null);
    try {
      const r = await api.buildCv({ input, language, ai });
      setResult(r);
      setMessage(
        ai
          ? { tone: 'good', text: 'Written by Gemini from your notes. Check every line: it must only say what is true.' }
          : { tone: 'plain', text: 'Built from your notes as you typed them.' }
      );
    } catch (e) {
      setMessage({ tone: 'bad', text: e.message });
    } finally {
      setBusy('');
      if (ai) reloadConfig();
    }
  }

  function download() {
    const blob = new Blob([cvToHtml(result.cv, result.header, language)], { type: 'text/html' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `CV_${(result.header.name || 'cv').replace(/\s+/g, '_')}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  const cv = result?.cv;
  const header = result?.header || {};

  return (
    <>
      <style>{CV_CSS}</style>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">CV</h1>
        <p className="mt-1 max-w-[70ch] text-muted">
          Your name, contact details and headline come from <Link to="/settings">your profile</Link>. Add your experience
          and education below, then let the AI turn them into a clean one-page CV — or build it exactly as typed.
        </p>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <Card>
          <CardHeader title="Your notes" subtitle="Only what you write here ends up on the CV. Nothing is invented." />
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <Field label="What the CV is for">
                <Input placeholder="Internship in web development" value={input.target} onChange={set('target')} />
              </Field>
              <Field label="Language">
                <Select value={language} onChange={(e) => setLanguage(e.target.value)}>
                  <option value="fr">Français</option>
                  <option value="en">English</option>
                </Select>
              </Field>
            </div>
            <Field label="Experience" hint={HINT}>
              <Textarea
                rows={6}
                placeholder={'Web developer intern - Atlas Digital (Jul–Aug 2025)\nBuilt the booking page in React\nCut page load time by half'}
                value={input.experience}
                onChange={set('experience')}
              />
            </Field>
            <Field label="Education">
              <Textarea rows={4} placeholder="Bachelor in computer science - FST Marrakech (2022–2025)" value={input.education} onChange={set('education')} />
            </Field>
            <Field label="Projects">
              <Textarea rows={4} placeholder={'Prospect Hub - personal project (2026)\nFlask API and React dashboard'} value={input.projects} onChange={set('projects')} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Skills (comma separated)">
                <Textarea rows={2} placeholder="Python, React, SQL" value={input.skills} onChange={set('skills')} />
              </Field>
              <Field label="Languages">
                <Textarea rows={2} placeholder="Arabe, Français, Anglais" value={input.languages} onChange={set('languages')} />
              </Field>
            </div>
            <Field label="Profile summary (only used without AI — the AI writes its own)">
              <Textarea rows={2} value={input.summary} onChange={set('summary')} />
            </Field>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant={aiReason ? 'default' : 'primary'}
                className={aiReason ? 'border-line bg-surface-2 text-muted hover:border-line hover:text-muted' : undefined}
                title={aiReason || 'Gemini rewrites your notes into a short CV'}
                aria-disabled={!config.ai || undefined}
                disabled={!!busy}
                onClick={() => (config.ai ? build(true) : setMessage({ tone: 'bad', text: aiReason }))}
              >
                {busy === 'ai' ? 'Writing…' : 'Write with AI'}
              </Button>
              <Button disabled={!!busy} onClick={() => build(false)}>
                {busy === 'plain' ? 'Building…' : 'Build without AI'}
              </Button>
            </div>
            {message && <Message tone={message.tone}>{message.text}</Message>}
          </div>
        </Card>

        <Card className="grid gap-3">
          <CardHeader
            title="Preview"
            subtitle={result?.at ? `Last built ${dateTime(result.at)}${cv?.ai ? ' with AI' : ''}` : 'Nothing built yet'}
            action={
              cv && (
                <div className="flex gap-1.5">
                  <Button size="sm" onClick={() => window.print()} title="Print, or choose “Save as PDF”">
                    Print / PDF
                  </Button>
                  <Button size="sm" onClick={download}>
                    Download
                  </Button>
                </div>
              )
            }
          />
          {cv ? (
            <div className="rounded-xl border border-line bg-white p-8 text-black shadow-card">
              <CvDocument cv={cv} header={header} language={language} />
            </div>
          ) : (
            <Empty>Write your notes, then press “Write with AI” or “Build without AI”.</Empty>
          )}
        </Card>
      </div>

      {/* Printing shows only this copy of the CV (see theme.css). */}
      {cv && createPortal(
        <div id="cv-print">
          <CvDocument cv={cv} header={header} language={language} />
        </div>,
        document.body
      )}
    </>
  );
}
