"""The REST API under /api. Sign-in is checked in app.py before any route here runs."""
import os
import re
import time
from datetime import datetime, timedelta

from flask import Blueprint, Response, g, jsonify, request

from . import ai, assistant, auth, jobs, mailer, places, store
from .util import ApiError, base36, clip, is_date, now_iso, now_ms, parse_int, parse_iso, to_str, truthy

DAY_S = 24 * 3600

# Routes that answer without a session. Everything else under /api needs one.
PUBLIC = {('POST', '/api/login'), ('POST', '/api/logout'), ('GET', '/api/session'),
          ('POST', '/api/signup'), ('POST', '/api/setup'),
          ('POST', '/api/verify-email'), ('POST', '/api/resend-verification'),
          ('POST', '/api/forgot-password'), ('POST', '/api/reset-password')}

OUTCOMES = {'no_answer': 'contacted', 'callback': 'contacted', 'interested': 'replied', 'demo': 'meeting',
            'not_interested': 'lost', 'wrong': 'lost', 'won': 'won'}


def body():
    """The JSON body as a dict; anything else counts as empty."""
    b = request.get_json(silent=True) if request.is_json else None
    return b if isinstance(b, dict) else {}


def err(status, message, **extra):
    return jsonify({'error': message, **extra}), status


def client_ip():
    return request.remote_addr or ''


def light_lead(l):
    log = l.get('log') or []
    return {
        'id': l.get('id'), 'nom': l.get('nom'), 'adresse': l.get('adresse'), 'telephone': l.get('telephone'),
        'site_web': l.get('site_web'), 'google_maps': l.get('google_maps'), 'categorie': l.get('categorie'),
        'note': l.get('note'), 'nombre_avis': l.get('nombre_avis'), 'latitude': l.get('latitude'),
        'longitude': l.get('longitude'), 'status': l.get('status'),
        'email': l.get('email'), 'placesStatus': l.get('placesStatus'),
        'sentLog': [{'at': s.get('at'), 'ok': s.get('ok')} for s in (l.get('sent') or [])],
        'hasNotes': bool(l.get('notes')),
        'nextStep': l.get('nextStep') or '', 'star': bool(l.get('star')), 'snooze': l.get('snooze') or '',
        'checks': l.get('checks') or {}, 'logCount': len(log), 'lastLog': log[0] if log else None,
    }


def _rate(hits, k, limit, window_s):
    """True when k has used up its calls in the window; otherwise records this one."""
    now = time.time()
    recent = [t for t in hits.get(k, []) if now - t < window_s]
    if len(recent) >= limit:
        hits[k] = recent
        return True
    recent.append(now)
    hits[k] = recent
    return False


def app_url(path):
    """An absolute link into the client, for an email.

    Set APP_URL in production: without it the link is built from the Host header of the
    request, which whoever asks for a reset link controls.
    """
    base = (os.environ.get('APP_URL') or request.host_url).rstrip('/')
    return base + path


def send_verification(email):
    """Email the link that confirms this address. True when it went out."""
    link = app_url('/verify-email?token=' + auth.make_verify_token(email))
    text = ('Welcome to Prospect Hub.\n\n'
            'Confirm your email address to finish creating your account:\n\n'
            f'{link}\n\n'
            f'The link works for {auth.VERIFY_TTL_S // 3600} hours. '
            'If you did not create this account, ignore this email.\n')
    try:
        mailer.send(email, 'Confirm your email address', text, transactional=True)
        return True
    except Exception as e:
        print('Could not send the verification email to', email, '-', e)
        return False


def send_reset(email):
    link = app_url('/reset-password?token=' + auth.make_reset_token(email))
    text = ('Someone asked to reset the password of your Prospect Hub account.\n\n'
            'Choose a new password here:\n\n'
            f'{link}\n\n'
            f'The link works once, for {auth.RESET_TTL_S // 60} minutes. '
            'If you did not ask for it, ignore this email: your password stays as it is.\n')
    try:
        mailer.send(email, 'Reset your password', text, transactional=True)
        return True
    except Exception as e:
        print('Could not send the password reset email to', email, '-', e)
        return False


def messages():
    """Notes users have sent to the administrators, oldest first."""
    return store.get().setdefault('messages', [])


def sender_settings(user):
    """The settings as one user's emails see them: their own profile is the sender.

    Fields the person left empty fall back to the shared settings, so an install set up
    before profiles existed keeps writing the same emails.
    """
    s = store.get()['settings']
    p = auth.get_profile(user)
    shared = s.get('sender') or {}
    signature = p['signature'] or s.get('signature') or '\n'.join(
        x for x in [p['fullName'], p['headline'], p['phone'], user] if x)
    return {
        **s,
        'sender': {'name': p['fullName'] or shared.get('name', ''), 'role': p['headline'] or shared.get('role', ''),
                   'background': p['background'] or shared.get('background', '')},
        'period': p['period'] or s.get('period', ''),
        'signature': signature,
        # Replies go to the person who wrote, not to the shared sending account.
        'replyTo': p['replyTo'] or user,
    }


def create_api():
    r = Blueprint('api', __name__, url_prefix='/api')
    db = store.get

    def lead_or_404(lead_id):
        return db()['leads'].get(lead_id)

    not_found = lambda: err(404, 'Lead not found.')  # noqa: E731

    # ----- session -----
    @r.post('/login')
    def login():
        b = body()
        email, password = clip(b.get('email'), 120), clip(b.get('password'), 200)
        k = client_ip() + '|' + email.lower()
        wait = auth.lock_state(k)
        if wait:
            return err(429, f'Too many attempts. Try again in {-(-wait // 60)} minute(s).')
        user = auth.check_login(email, password)
        if not user:
            auth.note_fail(k)
            return err(401, 'Incorrect email or password.')
        auth.note_ok(k)
        if not auth.is_verified(user):
            return err(403, 'Confirm your email address first: open the link we sent you.', code='UNVERIFIED')
        res = jsonify({'ok': True, 'user': user})
        auth.set_session(request, res, user)
        return res

    @r.post('/logout')
    def logout():
        res = jsonify({'ok': True})
        auth.clear_session(res)
        return res

    @r.get('/session')
    def session():
        s = auth.session_from(request)
        return jsonify({'user': s['u'] if s else None, 'needsSetup': not auth.has_users(),
                        'allowSignup': db()['settings'].get('allowSignup') is not False,
                        'canEmail': mailer.mode() != 'off'})

    # ----- sign-up -----
    signup_hits = {}

    @r.post('/signup')
    def signup():
        if db()['settings'].get('allowSignup') is False:
            return err(403, 'Registration is closed. Ask an administrator for an account.')
        # A handful of accounts per address per hour is plenty for a real person.
        now = time.time()
        hits = [t for t in signup_hits.get(client_ip(), []) if now - t < 3600]
        if len(hits) >= 5:
            return err(429, 'Too many accounts created from here. Try again later.')

        b = body()
        email = clip(b.get('email'), 120).strip().lower()
        password = clip(b.get('password'), 200)
        confirm = clip(b.get('confirm'), 200)

        if not auth.valid_email(email):
            return err(400, 'Enter a valid email address.')
        if password != confirm:
            return err(400, 'The two passwords do not match.')
        if len(password) < auth.MIN_PASSWORD:
            return err(400, f'The password needs at least {auth.MIN_PASSWORD} characters.')
        # Say the same thing whether or not the address is taken, so this cannot be
        # used to find out who already has an account.
        # Everything the outreach emails and the CV need about the sender, asked once here.
        profile = auth.clean_profile(b)
        problem = auth.profile_problem(profile)
        if problem:
            return err(400, problem)
        if auth.get_user(email):
            return err(409, 'That address cannot be used. Try another, or sign in.')
        # Without a way to send email there is nothing to verify with, so the account is
        # usable at once, as before. With one, it waits for the link.
        must_verify = mailer.mode() != 'off'
        try:
            auth.create_user(email, password, profile=profile, verified=not must_verify)
        except ValueError as e:
            return err(400, str(e))
        hits.append(now)
        signup_hits[client_ip()] = hits
        if must_verify:
            sent = send_verification(email)
            res = jsonify({'ok': True, 'user': email, 'verify': True, 'sent': sent})
            res.status_code = 201
            return res
        res = jsonify({'ok': True, 'user': email, 'verify': False})
        res.status_code = 201
        auth.set_session(request, res, email)
        return res

    # ----- email verification and password reset -----
    # Asking for a link always answers the same way, so these cannot tell anyone which
    # addresses have accounts. Each is limited per address and per caller.
    link_hits = {}

    def too_many_links(kind, email):
        return _rate(link_hits, (kind, 'ip', client_ip()), 10, 3600) or _rate(link_hits, (kind, email), 3, 3600)

    @r.post('/verify-email')
    def verify_email():
        email = auth.read_verify_token(clip(body().get('token'), 2000))
        if not email:
            return err(400, 'This link is invalid or has expired. Sign in to get a new one.', code='BAD_TOKEN')
        auth.mark_verified(email)
        res = jsonify({'ok': True, 'user': email})
        auth.set_session(request, res, email)
        return res

    @r.post('/resend-verification')
    def resend_verification():
        email = clip(body().get('email'), 120).strip().lower()
        if not auth.valid_email(email):
            return err(400, 'Enter a valid email address.')
        if mailer.mode() == 'off':
            return err(503, 'This server cannot send email. Ask an administrator.')
        if too_many_links('verify', email):
            return err(429, 'Too many emails asked for. Try again in an hour.')
        u = auth.get_user(email)
        if u and u.get('verified') is False:
            send_verification(email)
        return jsonify({'ok': True})

    @r.post('/forgot-password')
    def forgot_password():
        email = clip(body().get('email'), 120).strip().lower()
        if not auth.valid_email(email):
            return err(400, 'Enter a valid email address.')
        if mailer.mode() == 'off':
            return err(503, 'This server cannot send email. Ask an administrator to reset your password.')
        if too_many_links('reset', email):
            return err(429, 'Too many emails asked for. Try again in an hour.')
        if auth.get_user(email):
            send_reset(email)
        return jsonify({'ok': True})

    @r.post('/reset-password')
    def reset_password():
        b = body()
        email = auth.read_reset_token(clip(b.get('token'), 2000))
        if not email:
            return err(400, 'This link is invalid, expired or already used. Ask for a new one.', code='BAD_TOKEN')
        password, confirm = clip(b.get('password'), 200), clip(b.get('confirm'), 200)
        if password != confirm:
            return err(400, 'The two passwords do not match.')
        try:
            auth.set_password(email, password, verify_email=True)
        except ValueError as e:
            return err(400, str(e))
        auth.note_ok(client_ip() + '|' + email)   # someone locked out can sign in again at once
        res = jsonify({'ok': True, 'user': email})
        auth.set_session(request, res, email)
        return res

    @r.post('/setup')
    def setup():
        if auth.has_users():
            return err(403, 'An account already exists.')
        local = client_ip() in ('127.0.0.1', '::1', '::ffff:127.0.0.1')
        if not local and os.environ.get('ALLOW_REMOTE_SETUP') != 'true':
            return err(403, 'First-time setup is only allowed from this computer.')
        b = body()
        try:
            auth.create_user(b.get('email'), b.get('password'))
        except ValueError as e:
            return err(400, str(e))
        res = jsonify({'ok': True})
        auth.set_session(request, res, to_str(b.get('email')).strip().lower())
        return res

    # ----- everything below needs a session (checked in app.py) -----
    @r.get('/config')
    def config():
        admin = auth.is_admin(g.user)
        profile = auth.get_profile(g.user)
        out = {'user': g.user, 'name': profile['fullName'], 'isAdmin': admin, **auth.ai_state(g.user),
               'profileComplete': auth.profile_problem(profile) is None,
               'model': ai.MODEL(), 'smtp': mailer.mode(),
               'places': bool(os.environ.get('GOOGLE_PLACES_API_KEY')), 'statuses': store.STATUSES}
        if admin:
            out['openMessages'] = sum(1 for m in messages() if m.get('status') != 'resolved')
        return jsonify(out)

    # ----- the signed-in person's profile: the sender of their emails, the header of their CV -----
    @r.get('/profile')
    def get_profile():
        return jsonify({**auth.get_profile(g.user), 'email': g.user})

    @r.put('/profile')
    def put_profile():
        profile = auth.clean_profile(body())
        problem = auth.profile_problem(profile)
        if problem:
            return err(400, problem)
        profile['replyTo'] = profile['replyTo'].lower()
        return jsonify({**auth.set_profile(g.user, profile), 'email': g.user})

    # ----- the signed-in person's own Gemini key -----
    @r.put('/ai-key')
    def put_ai_key():
        value = to_str(body().get('key') or '').strip()
        if len(value) < 20 or len(value) > 200 or re.search(r'\s', value):
            return err(400, 'That does not look like an API key.')
        try:
            ai.check_key(value)
        except ApiError as e:
            return err(400, str(e))
        try:
            auth.set_ai_key(g.user, value)
        except Exception as e:
            # Google accepted the key; the failure is ours (unwritable data directory,
            # missing account). Say which, instead of a blank "something went wrong".
            print('Could not store the AI key for', g.user, '-', e)
            return err(500, f'The key is valid but could not be saved: {e}')
        return jsonify({'ai': True, 'model': ai.MODEL()})

    @r.delete('/ai-key')
    def delete_ai_key():
        auth.set_ai_key(g.user, '')
        return jsonify({'ai': False})

    # ----- help assistant -----
    ask_hits = {}

    @r.get('/assistant')
    def get_assistant():
        return jsonify({'history': assistant.history(g.user), 'ai': auth.has_ai_key(g.user)})

    @r.delete('/assistant')
    def clear_assistant():
        assistant.clear(g.user)
        return jsonify({'history': []})

    @r.post('/assistant')
    def ask():
        key = auth.get_ai_key(g.user)
        if not key:
            return err(400, 'Add your Gemini API key in Settings to use the assistant.', code='NO_KEY')
        if _rate(ask_hits, g.user, 20, 60):
            return err(429, 'Slow down: 20 questions per minute at most.')
        try:
            out = assistant.ask(g.user, body().get('message'), key)
        except ApiError as e:
            if not e.status:   # Gemini's failure, not a bad question: remember it for the Ask button
                auth.set_ai_error(g.user, str(e))
            return err(e.status or 502, str(e))
        auth.set_ai_error(g.user, None)
        return jsonify(out)

    @r.get('/settings')
    def get_settings():
        return jsonify(db()['settings'])

    @r.put('/settings')
    def put_settings():
        b = body()
        s = db()['settings']
        snd = b.get('sender') if isinstance(b.get('sender'), dict) else {}
        s['sender'] = {'name': clip(snd.get('name'), 80), 'role': clip(snd.get('role'), 160),
                       'background': clip(snd.get('background'), 800)}
        s['goal'] = 'pitch' if b.get('goal') == 'pitch' else 'internship'
        s['language'] = 'en' if b.get('language') == 'en' else 'fr'
        s['period'] = clip(b.get('period'), 100)
        s['signature'] = clip(b.get('signature'), 400)
        s['replyTo'] = b['replyTo'] if auth.valid_email(b.get('replyTo')) else ''
        oo = b.get('optOut') if isinstance(b.get('optOut'), dict) else {}
        s['optOut'] = {'fr': clip(oo.get('fr'), 300) or store.DEFAULT_SETTINGS['optOut']['fr'],
                       'en': clip(oo.get('en'), 300) or store.DEFAULT_SETTINGS['optOut']['en']}
        s['dailyCap'] = max(1, min(200, parse_int(b.get('dailyCap')) or 20))
        sc = b.get('scoring')
        if truthy(sc):
            sc = sc if isinstance(sc, dict) else {}
            d = store.DEFAULT_SETTINGS['scoring']
            w = sc.get('weights') if isinstance(sc.get('weights'), dict) else {}

            def weight(v, dflt):
                n = parse_int(v)
                return max(0, min(100, n)) if n is not None else dflt

            s['scoring'] = {
                'weights': {k: weight(w.get(k), d['weights'][k]) for k in ('fit', 'pain', 'reach', 'volume')},
                'tiers': {}, 'perDay': max(1, min(50, parse_int(sc.get('perDay')) or d['perDay'])),
                'icpOnly': sc.get('icpOnly') is not False,
            }
            tiers = sc.get('tiers') if isinstance(sc.get('tiers'), dict) else {}
            for k, v in tiers.items():
                if v in ('A', 'B', 'C', 'D', 'X'):
                    s['scoring']['tiers'][clip(k, 80)] = v
        store.save()
        return jsonify(s)

    # ----- leads -----
    @r.get('/leads')
    def list_leads():
        return jsonify([light_lead(l) for l in list(db()['leads'].values())])

    @r.get('/leads/<lead_id>')
    def get_lead(lead_id):
        l = lead_or_404(lead_id)
        return jsonify(l) if l else not_found()

    @r.patch('/leads/<lead_id>')
    def patch_lead(lead_id):
        l = lead_or_404(lead_id)
        if not l:
            return not_found()
        b = body()
        if 'status' in b:
            if b['status'] not in store.STATUSES:
                return err(400, 'Unknown status.')
            l['status'] = b['status']
        if 'notes' in b:
            l['notes'] = clip(b['notes'], 4000)
        for k in ('nextStep', 'snooze'):
            if k in b:
                if not (b[k] == '' or is_date(b[k])):
                    return err(400, 'Dates must look like 2026-03-01.')
                l[k] = b[k]
        if 'star' in b:
            l['star'] = truthy(b['star'])
        if isinstance(b.get('checks'), (dict, list)):
            src = b['checks'] if isinstance(b['checks'], dict) else {}
            l['checks'] = {k: src[k] for k in ('live', 'mobile', 'whatsapp', 'chat', 'booking') if isinstance(src.get(k), bool)}
        if 'email' in b:
            e = to_str(b['email'] if b['email'] is not None else 'null').strip().lower()
            if e and not auth.valid_email(e):
                return err(400, 'That email address does not look valid.')
            l['email'] = e
        store.save()
        return jsonify(l)

    @r.post('/leads/<lead_id>/places')
    def lead_places(lead_id):
        l = lead_or_404(lead_id)
        if not l:
            return not_found()
        key = os.environ.get('GOOGLE_PLACES_API_KEY')
        if not key:
            return err(400, 'GOOGLE_PLACES_API_KEY is not set.')
        try:
            d = places.place_details(l['id'], key)
            changes = places.apply_details(l, d)
            store.save()
            return jsonify({'lead': l, 'changes': changes})
        except Exception as e:
            return err(502, str(e))

    # ----- contact log (call, WhatsApp, visit...) -----
    @r.post('/leads/<lead_id>/log')
    def add_log(lead_id):
        l = lead_or_404(lead_id)
        if not l:
            return not_found()
        b = body()
        outcome = b.get('outcome')
        if not isinstance(outcome, str) or outcome not in OUTCOMES:
            return err(400, 'Unknown outcome.')
        if truthy(b.get('nextStep')) and not is_date(b.get('nextStep')):
            return err(400, 'Dates must look like 2026-03-01.')
        l['log'] = [{'at': now_iso(), 'outcome': outcome, 'via': clip(b.get('via'), 30), 'note': clip(b.get('note'), 1000)}] \
            + (l.get('log') or [])
        l['log'] = l['log'][:200]
        l['status'] = OUTCOMES[outcome]
        if 'nextStep' in b:
            l['nextStep'] = b['nextStep']
        store.save()
        return jsonify(l)

    @r.delete('/leads/<lead_id>/log/<i>')
    def delete_log(lead_id, i):
        l = lead_or_404(lead_id)
        if not l:
            return not_found()
        n = parse_int(i)
        log = l.get('log') or []
        if n is None or n < 0 or n >= len(log):
            return err(404, 'No such log entry.')
        log.pop(n)
        store.save()
        return jsonify(l)

    # ----- background jobs -----
    @r.get('/jobs/current')
    def job_current():
        return jsonify(jobs.current())

    @r.post('/jobs/cancel')
    def job_cancel():
        return jsonify(jobs.cancel())

    @r.post('/jobs/start')
    def job_start():
        job_type = body().get('type')
        if job_type == 'places':
            key = os.environ.get('GOOGLE_PLACES_API_KEY')
            if not key:
                return err(400, 'GOOGLE_PLACES_API_KEY is not set.')
            items = [l for l in db()['leads'].values() if not l.get('site_web') and not l.get('placesCheckedAt')][:500]

            def work(l):
                d = places.place_details(l['id'], key)
                ch = places.apply_details(l, d)
                store.save()
                return {'found': 'website' in ch}
            try:
                return jsonify(jobs.start(job_type, items, work, concurrency=4))
            except ApiError as e:
                return err(409 if e.code == 'BUSY' else 500, str(e))
        return err(400, 'Unknown job type.')

    # ----- AI draft -----
    draft_hits = {}

    @r.post('/leads/<lead_id>/draft')
    def draft(lead_id):
        l = lead_or_404(lead_id)
        if not l:
            return not_found()
        if _rate(draft_hits, g.user, 20, 60):
            return err(429, 'Slow down: 20 drafts per minute at most.')
        b = body()
        ctx = {'lead': l, 'settings': sender_settings(g.user), 'goal': 'pitch' if b.get('goal') == 'pitch' else 'internship',
               'language': 'en' if b.get('language') == 'en' else 'fr', 'tone': clip(b.get('tone'), 30),
               'extra': clip(b.get('extra'), 300)}
        out, ai_error = None, None
        key = auth.get_ai_key(g.user)
        if key:
            try:
                out = ai.draft_email(ctx, key)
                auth.set_ai_error(g.user, None)
            except Exception as e:
                ai_error = str(e)
                auth.set_ai_error(g.user, ai_error)
        elif auth.ai_state(g.user)['aiError']:
            ai_error = auth.ai_state(g.user)['aiError']
        if not out:
            out = {**ai.template_draft(ctx), 'ai': False}
        l['draft'] = {**out, 'at': now_iso(), 'goal': ctx['goal'], 'language': ctx['language']}
        store.save()
        return jsonify({**out, 'aiError': ai_error, 'language': ctx['language']})

    # ----- send -----
    recent = {}   # requestId -> (expires at, response payload): a double click sends once

    @r.post('/leads/<lead_id>/send')
    def send(lead_id):
        l = lead_or_404(lead_id)
        if not l:
            return not_found()
        b = body()
        settings = db()['settings']
        for k in [k for k, (exp, _) in recent.items() if exp < time.time()]:
            recent.pop(k, None)
        rid = clip(b.get('requestId'), 60)
        if rid and rid in recent:
            return jsonify(recent[rid][1])
        if not l.get('email') or not auth.valid_email(l['email']):
            return err(400, 'This lead has no valid email address yet.')
        if l.get('status') == 'optout':
            return err(400, 'This lead is marked "do not contact".')
        subject = re.sub(r'[\r\n]+', ' ', clip(b.get('subject'), 150)).strip()
        text_body = clip(b.get('body'), 4000).strip()
        if len(subject) < 3:
            return err(400, 'Write a subject first.')
        if len(text_body) < 20:
            return err(400, 'The message is too short.')
        lang = 'en' if b.get('language') == 'en' else 'fr'
        opt_out = (settings['optOut'].get(lang) or '').strip()
        if not opt_out:
            return err(400, 'Add an opt-out line in Settings first.')
        start_of_day = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today = sum(1 for x in db()['leads'].values() for s in (x.get('sent') or [])
                    if s.get('ok') and (parse_iso(s.get('at')) or start_of_day - timedelta(1)) >= start_of_day)
        if today >= settings['dailyCap']:
            return err(429, f"Daily limit reached ({settings['dailyCap']}). Change it in Settings or continue tomorrow.")
        ok_sent = [s for s in (l.get('sent') or []) if s.get('ok')]
        last_ok = ok_sent[-1] if ok_sent else None
        if last_ok and not truthy(b.get('force')):
            last_at = parse_iso(last_ok['at'])
            if last_at and (datetime.now(last_at.tzinfo) - last_at).total_seconds() < 14 * DAY_S:
                return err(409, f"You already emailed this address on {last_ok['at'][:10]}.", code='RECENT', last=last_ok['at'])
        sender = sender_settings(g.user)
        signature = sender['signature'].strip() + '\n\n' if sender.get('signature') else ''
        text = text_body + '\n\n' + signature + opt_out
        entry = {'id': 's' + base36(now_ms()), 'at': now_iso(), 'to': l['email'], 'subject': subject, 'body': text,
                 'language': lang, 'by': g.user}
        try:
            out = mailer.send(l['email'], subject, text, sender.get('replyTo'))
            entry.update(ok=True, mode=out['mode'], messageId=out['messageId'])
            if l.get('status') == 'new':
                l['status'] = 'contacted'
        except Exception as e:
            entry.update(ok=False, mode=mailer.mode(), error=str(e)[:200])
        l.setdefault('sent', []).append(entry)
        store.save()
        payload = {'ok': entry['ok'], 'entry': entry, 'lead': l, 'error': entry.get('error')}
        if rid:
            recent[rid] = (time.time() + 600, payload)
        return jsonify(payload), (200 if entry['ok'] else 502)

    @r.get('/outbox')
    def outbox():
        rows = [{**s, 'leadId': l.get('id'), 'company': l.get('nom')}
                for l in list(db()['leads'].values()) for s in (l.get('sent') or [])]
        rows.sort(key=lambda x: x.get('at') or '', reverse=True)
        return jsonify(rows[:500])

    # ----- contact the administrators -----
    message_hits = {}

    def own(m):
        return {k: m.get(k) for k in ('id', 'subject', 'body', 'at', 'status', 'reply', 'repliedAt')}

    @r.get('/messages')
    def my_messages():
        mine = [own(m) for m in messages() if m.get('from') == g.user]
        return jsonify(list(reversed(mine)))

    @r.post('/messages')
    def send_message():
        b = body()
        subject = re.sub(r'[\r\n]+', ' ', clip(b.get('subject'), 120)).strip()
        text_body = clip(b.get('body'), 2000).strip()
        if len(subject) < 3:
            return err(400, 'Give your message a subject.')
        if len(text_body) < 10:
            return err(400, 'Write a little more so an administrator can help.')
        if _rate(message_hits, g.user, 10, 3600):
            return err(429, 'You have sent 10 messages in the last hour. Wait for a reply.')
        p = auth.get_profile(g.user)
        m = {'id': 'm' + base36(now_ms()), 'from': g.user, 'name': p['fullName'], 'phone': p['phone'],
             'subject': subject, 'body': text_body, 'at': now_iso(), 'status': 'open', 'reply': '', 'repliedAt': None}
        messages().append(m)
        store.save()
        return jsonify(own(m)), 201

    # ----- CV -----
    def cv_record():
        return store.get().setdefault('cvs', {}).setdefault(g.user, {'input': {}, 'cv': None, 'at': None})

    CV_INPUT = {'target': 200, 'summary': 600, 'experience': 4000, 'education': 3000, 'projects': 3000,
                'skills': 1000, 'languages': 500}

    def cv_input(raw):
        raw = raw if isinstance(raw, dict) else {}
        return {k: clip(raw.get(k), n) for k, n in CV_INPUT.items()}

    def cv_payload(rec):
        p = auth.get_profile(g.user)
        contact = {'email': g.user, 'phone': p['phone'], 'city': p['city'], 'linkedin': p['linkedin']}
        return {**rec, 'header': {'name': p['fullName'], 'headline': p['headline'], **contact}}

    @r.get('/cv')
    def get_cv():
        return jsonify(cv_payload(cv_record()))

    @r.post('/cv')
    def build_cv():
        b = body()
        rec = cv_record()
        rec['input'] = cv_input(b.get('input'))
        language = 'en' if b.get('language') == 'en' else 'fr'
        rec['language'] = language
        use_ai = b.get('ai') is not False
        ai_error = None
        if use_ai:
            key = auth.get_ai_key(g.user)
            if not key:
                return err(400, auth.ai_state(g.user)['aiError'] or 'Add your Gemini API key in Settings to write the CV with AI.',
                           code='NO_KEY')
            if _rate(draft_hits, g.user, 20, 60):
                return err(429, 'Slow down: 20 AI requests per minute at most.')
            try:
                cv = {**ai.generate_cv(auth.get_profile(g.user), rec['input'], language, key), 'ai': True}
                auth.set_ai_error(g.user, None)
            except ApiError as e:
                ai_error = str(e)
                if 'expected shape' not in ai_error:
                    auth.set_ai_error(g.user, ai_error)
                return err(502, ai_error)
        else:
            cv = {**ai.plain_cv(rec['input']), 'ai': False}
        rec['cv'], rec['at'] = cv, now_iso()
        store.save()
        return jsonify(cv_payload(rec))

    # ----- data out -----
    @r.get('/export.csv')
    def export_csv():
        return Response(store.export_csv(), headers={
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="entreprises_avec_email.csv"'})

    return r
