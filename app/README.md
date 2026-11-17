# Prospect Hub

A self-hosted web app for finding, contacting and tracking companies in Marrakech.
It scores each company as a prospect, writes the first email with AI, sends it, and
tracks the reply through a pipeline. Email addresses come with the data
(`data/companies.csv`) and can be edited per company.

- **Backend:** Python 3.10+ — Flask 3 + a JSON file database, in [`app.py`](app.py) and [`lib/`](lib/)
- **Frontend:** React 19 + Vite 7 + Tailwind CSS 4, in [`client/`](client/)
- **Data:** 283 companies collected from Google Places (`data/companies.csv`)

The server, the scripts and the tests are Python. The only JavaScript left is the
React client, which runs in the browser; Node.js is needed to build it, not to run the
app.

## Install

Python 3.10 or newer, and Node.js 20.19 or newer for the client build.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # fill in what you have; everything is optional
npm install && npm run build       # builds the React client into dist/
python server.py                   # http://127.0.0.1:3000
```

### The administrator account

On start, if the database holds no account, one is created from `ADMIN_EMAIL` and
`ADMIN_PASSWORD`:

```bash
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='a long password' python server.py
```

Without those variables a development account is created instead, and the server
prints its credentials to the console on first start. They are meant for a local
machine only.

> **`ADMIN_PASSWORD` is required in production.** The development credentials are
> readable in the source, so any publicly reachable instance that keeps them is open
> to anyone. The server warns on every start while they are in use.

Anyone can create their own account from the sign-in page: **Create one** asks for an
email, a password of at least 10 characters, and a confirmation of that password. New
accounts are always ordinary users. An administrator can close registration with the
**Open registration** switch on the Admin page, which also hides the link.

Accounts can also be added from the **Admin** page, or from the terminal:

```bash
python scripts/create_user.py colleague@example.com "a long password"
```

The dataset ships with the app: on first start the 283 companies in
`data/companies.csv` load by themselves, so there is nothing to import. Your working
data then lives in `data/db.json`.

## Develop

Two terminals. Vite serves the client with hot reload and proxies `/api` to Flask:

```bash
python server.py --reload   # Flask API on :3000, restarts when a .py file changes
npm run dev                 # Vite dev server on :5173  <- open this one
```

`python server.py` alone serves the last `npm run build`, so run the build after
changing the client if you are not using the dev server.

## Commands

| Command | What it does |
|---|---|
| `python server.py` | Serve the API and the built client (waitress, 8 threads) |
| `python server.py --reload` | Flask development server, restarts on Python changes |
| `npm run dev` | Vite dev server with hot reload (proxies `/api` to :3000) |
| `npm run build` | Build the client into `dist/` |
| `python -m pytest` | End-to-end tests against a local mock of Gemini (no internet needed) |
| `python scripts/create_user.py` | Create a login from the terminal |
| `python enrich.py companies.json` | Optional website checker (see below) |

## How the backend is organised

```
server.py           entry point: loads .env, serves with waitress (or --reload)
app.py              create_app(): security headers, CSRF header check, sign-in gate,
                    the /api blueprints, the built client and its fallback route
api/index.py        the same app for Vercel's Python runtime
lib/
  store.py          the JSON-file database (db.json), CSV import and export
  api.py            the REST routes and input validation
  admin.py          administrator routes: accounts and company records
  auth.py           accounts, bcrypt, signed session cookies, AES-GCM for AI keys
  ai.py             Gemini calls: the first-contact email
  assistant.py      the help assistant's guide, live numbers and memory
  mailer.py         SMTP sending (smtplib), List-Unsubscribe header, dry run
  places.py         Google Places details
  jobs.py           one background job at a time, with progress
  util.py           value coercion and time helpers shared by the above
scripts/create_user.py
tests/test_e2e.py
```

## How the frontend is organised

```
client/
  index.html            the only HTML file: Vite's entry point
  public/theme-init.js  sets the theme before first paint
  src/
    theme.css           the only stylesheet: design tokens + Tailwind
    main.jsx            routes
    lib/                api client, scoring, formatting (no React)
    store/              AppContext: leads, settings, jobs, toasts
    hooks/              useTheme
    components/
      ui/               Button, Card, Pill, Field, DataTable, Drawer, Kpi…
      charts/           BarChart (Chart.js) and ChartCard
      layout/           AppLayout, RequireAuth, JobBar
    features/lead/      the company drawer, split by panel
    pages/              one file per route
```

Styling is Tailwind utilities only. Colours come from tokens defined once in
`theme.css` (`--color-surface`, `--color-accent`…), redefined under `.dark`, so no
component ever branches on the theme. The theme follows the system setting unless the
header toggle overrides it.

## Pages

| Page | What it does |
|---|---|
| **Dashboard** | Coverage funnel, email coverage by category, rating bands, pipeline. Every chart has a Table view. |
| **Today** | Follow-ups that are due, companies in conversation with no next step, then the best new leads by fit score. |
| **Companies** | The full list: search, filter, sort, export CSV. Click a row for the company drawer. |
| **Pipeline** | A kanban board. Each column scrolls on its own so the board stays one screen tall; the board scrolls sideways for the last columns. Drag a card or use its menu, filter every column at once, overdue follow-ups first. |
| **Outbox** | Every message the app tried to send. |
| **Settings** | Your Gemini API key, who you are, sending limits, the scoring weights (with a live count of how many companies each change promotes) and the category tiers. |
| **Admin** | Administrators only. Accounts (add, change password, grant or remove rights, delete, open or close registration) and the company records themselves (correct, add, delete, reload the dataset). |

### The company drawer

Details and contact buttons (Call, WhatsApp, Email, Maps, Site — each shown only when
it can work), the fit score broken down by factor, the follow-up date, the email panel
(find, pick, edit), the AI draft and send, the contact log, the website checks and
private notes.

## AI: bring your own key

AI is per person, not per server. Each signed-in user pastes their own
**Google Gemini** API key on the Settings page; a free one takes a minute to create at
<https://aistudio.google.com/apikey>. The key is checked against Google before it is
accepted, encrypted with AES-256-GCM before it is written to `data/users.json`, and
never sent back to the browser.

That key powers two things:

- **Write draft with AI** in the company panel. Without a key the button still works
  and fills in a plain template instead.
- **Ask**, the help assistant (the button in the top right). It answers questions about
  how to use the app.

### How the assistant knows things

It has no training on this app, so it is given what it needs on every question:

1. A written guide to the app, `KNOWLEDGE` in [`lib/assistant.py`](lib/assistant.py):
   the pages, the company panel, the scoring factors, how email finding works and the
   sending rules. **Edit that string whenever the app changes** — it is the single
   place the assistant learns from, and it is told never to invent a button that is
   not in it.
2. A snapshot of your own numbers (how many companies, how many have an email, the
   status breakdown, follow-ups due), so it can answer questions about your data.
3. The conversation so far, kept per user in `data/db.json` and capped at 20 exchanges,
   so follow-up questions make sense. "Clear" in the panel forgets it.

`GEMINI_MODEL` in `.env` changes the model for everyone (default `gemini-2.5-flash`).

## The fit score

Each company gets 0–100 from four weighted factors. The weights and the category tiers
are on the Settings page, and every list re-ranks as you change them. The score is
computed in the browser ([`client/src/lib/scoring.js`](client/src/lib/scoring.js)) so
a slider change re-ranks instantly; the analysis pipeline computes the same formula in
Python.

| Factor | Default weight | Scores high when |
|---|---|---|
| Category fit | 30 | The line of work is valuable (hotels, travel, real estate, health) |
| Pain | 30 | No website, a social page only, a free builder site, or a site missing WhatsApp, chat or booking |
| Reach | 15 | A mobile number exists (a landline counts half) |
| Volume | 25 | Many Google reviews, which suggests many customer messages |

Categories are graded A (best fit) to D (weak), or Excluded. Excluded categories score 0
and never appear on Today.

## Environment (.env)

| Variable | Purpose |
|---|---|
| `SESSION_SECRET` | 24+ random characters; keeps logins valid across restarts |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | the administrator created on first start |
| `GEMINI_MODEL` | which Gemini model the users' keys call (default `gemini-2.5-flash`) |
| `SMTP_HOST/PORT/USER/PASS`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` | sending (Gmail needs an app password) |
| `SMTP_MODE=json` | dry run: logs messages, delivers nothing |
| `GOOGLE_PLACES_API_KEY` | fills missing websites and phone numbers |
| `HOST`, `PORT`, `TRUST_PROXY` | server binding (default 127.0.0.1:3000) |
| `DATA_DIR` | where `db.json` lives (default `data/`) |

## Deploying

Build the client, install the Python requirements, and run the server:

```
Build command:  pip install -r requirements.txt && npm install && npm run build
Start command:  python server.py
```

Set `HOST=0.0.0.0`, a long `SESSION_SECRET`, and `TRUST_PROXY=true` behind a proxy.
`data/db.json` is a plain file, so give it a persistent disk, or it is wiped on each deploy.

On **Vercel**, [`vercel.json`](vercel.json) builds the client and serves the API from
[`api/index.py`](api/index.py) on the Python runtime, which installs
`requirements.txt` by itself. Set `DATA_DIR=/tmp/data`: it is the only writable
place, and it is emptied between cold starts, so the dataset reloads from
`data/companies.csv` and accounts come back from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Sending responsibly

Unsolicited email to businesses is regulated (Morocco law 09-08; GDPR for EU
recipients). Every email gets your opt-out line, a `List-Unsubscribe` header, a daily
cap (20 by default), a 14-day duplicate guard, and a "do not contact" status. Review
every draft: AI text can be wrong. Respect replies that say stop. Start in dry-run mode
(`SMTP_MODE=json`).

## Security notes

Passwords are bcrypt-hashed, sessions are signed HttpOnly cookies, login is
rate-limited, state-changing requests need a custom header, and a strict CSP is set.
Keep it on localhost, or put it behind HTTPS and set `TRUST_PROXY`.

## Tests

`python -m pytest` runs the end-to-end suite against a local mock of Gemini: auth,
seeding the dataset, the per-user AI key (including that it is never returned and
never stored in the clear), AI drafts, the assistant's memory, sending rules, the
contact log, settings, CSV export, administration, and that the built client is served
on every route (that one is skipped until `npm run build` has run). No internet needed.

## Website checker (optional)

`enrich.py` visits each company's website once and records whether it is live, works
on a phone, and has a WhatsApp button, a chat widget or online booking:

```bash
python enrich.py companies.json                 # writes enrichment.json
python enrich.py companies.json out.json --concurrency 8 --timeout 15000 --force
```
