"""Accounts, roles, signed session cookies, and each user's encrypted Gemini key."""
import base64
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from urllib.parse import unquote

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import g, has_request_context

from . import kv
from .store import DATA_DIR
from .util import now_iso, now_ms

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
SECRET_FILE = os.path.join(DATA_DIR, '.secret')
COOKIE = 'ph_session'
MAX_AGE_S = 7 * 24 * 3600
MIN_PASSWORD = 10
_EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]{2,}')
_users_lock = threading.RLock()


def _b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode('ascii')


def _b64d(s):
    s = str(s)
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def read_users():
    if kv.enabled():
        # One query per request, not one per call: a request asks several times.
        if has_request_context() and '_ph_users' in g:
            return copy.deepcopy(g._ph_users)
        text = kv.read('users')[0]
        try:
            users = json.loads(text) if text else []
        except ValueError:
            users = []
        if has_request_context():
            g._ph_users = users
        return copy.deepcopy(users)
    try:
        with open(USERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def write_users(users):
    with _users_lock:
        if kv.enabled():
            kv.write('users', json.dumps(users, ensure_ascii=False))
            if has_request_context():
                g._ph_users = copy.deepcopy(users)
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        fd = os.open(USERS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)


def _secret():
    env = os.environ.get('SESSION_SECRET') or ''
    if len(env) >= 24:
        return env
    if kv.enabled():
        # Every instance must sign with the same key, so it lives with the data.
        return kv.insert_if_missing('secret', secrets.token_hex(32))
    try:
        with open(SECRET_FILE, encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        pass
    s = secrets.token_hex(32)
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(s)
    return s


_SECRET = None


def key():
    global _SECRET
    if _SECRET is None:
        _SECRET = _secret()
    return _SECRET


def valid_email(e):
    return isinstance(e, str) and len(e) <= 120 and _EMAIL.fullmatch(e) is not None


# ---------- per-user AI key ----------
# Each person brings their own Gemini key. It is encrypted at rest with a key derived
# from the session secret, and never sent back to the browser.

def _aes_key():
    return hashlib.sha256(('ai-key|' + key()).encode('utf-8')).digest()


def encrypt(text):
    iv = secrets.token_bytes(12)
    sealed = AESGCM(_aes_key()).encrypt(iv, str(text).encode('utf-8'), None)
    data, tag = sealed[:-16], sealed[-16:]
    return '.'.join([_b64e(iv), _b64e(tag), _b64e(data)])


def decrypt(blob):
    try:
        iv, tag, data = str(blob).split('.')
        return AESGCM(_aes_key()).decrypt(_b64d(iv), _b64d(data) + _b64d(tag), None).decode('utf-8')
    except Exception:  # wrong secret, or the file was edited by hand
        return None


def set_ai_key(email, plain):
    """Store (or clear, with an empty value) this user's AI key."""
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            raise ValueError('No such account.')
        if plain:
            u['aiKey'] = encrypt(plain)
        else:
            u.pop('aiKey', None)
        u.pop('aiError', None)   # a new key (or none) starts with a clean slate
        write_users(users)


def get_ai_key(email):
    u = next((x for x in read_users() if x['email'] == email), None)
    return decrypt(u['aiKey']) if u and u.get('aiKey') else None


def has_ai_key(email):
    return bool(get_ai_key(email))


UNREADABLE_KEY = ('Your saved Gemini key can no longer be read (the server secret changed). '
                  'Remove it in Settings and add it again.')


def set_ai_error(email, message):
    """Remember why this user's last AI call failed (None clears it). Writes only on change."""
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            return
        current = (u.get('aiError') or {}).get('message')
        if current == message:
            return
        if message:
            u['aiError'] = {'message': str(message)[:300], 'at': now_iso()}
        else:
            u.pop('aiError', None)
        write_users(users)


def ai_state(email):
    """What the interface shows for AI: whether it can be used, and if not, why."""
    u = get_user(email)
    if not u or not u.get('aiKey'):
        return {'ai': False, 'aiError': None}
    if decrypt(u['aiKey']) is None:
        return {'ai': False, 'aiError': UNREADABLE_KEY}
    return {'ai': True, 'aiError': (u.get('aiError') or {}).get('message')}


# ---------- profile: who the person is, used as the sender and on their CV ----------

PROFILE_FIELDS = {'fullName': 120, 'phone': 40, 'headline': 160, 'city': 80, 'linkedin': 200,
                  'background': 1500, 'period': 100, 'signature': 400, 'replyTo': 120}
_PHONE = re.compile(r'\+?[0-9 ().\-]{8,24}')


def clean_profile(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for k, n in PROFILE_FIELDS.items():
        v = raw.get(k)
        out[k] = ('' if v is None else str(v)).strip()[:n]
    return out


def profile_problem(p):
    """The first thing wrong with a profile, or None. Name, phone and headline are required."""
    if len(p.get('fullName', '')) < 3 or ' ' not in p['fullName']:
        return 'Enter your full name (first and last name).'
    phone = p.get('phone', '')
    if not _PHONE.fullmatch(phone) or sum(c.isdigit() for c in phone) < 8:
        return 'Enter a valid phone number, for example 06 12 34 56 78 or +212 6 12 34 56 78.'
    if len(p.get('headline', '')) < 3:
        return 'Say in a few words who you are (for example "3rd-year computer science student").'
    if p.get('replyTo') and not valid_email(p['replyTo'].lower()):
        return 'The reply-to address does not look valid.'
    return None


def get_profile(email):
    u = get_user(email)
    return clean_profile((u or {}).get('profile'))


def set_profile(email, profile):
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            raise ValueError('No such account.')
        u['profile'] = clean_profile(profile)
        write_users(users)
        return u['profile']


def profile_complete(email):
    return profile_problem(get_profile(email)) is None


# ---------- passwords ----------

def _pw(password):
    # bcrypt only reads the first 72 bytes.
    return str(password).encode('utf-8')[:72]


def hash_password(password):
    return bcrypt.hashpw(_pw(password), bcrypt.gensalt(12)).decode('ascii')


def _check(password, hashed):
    try:
        return bcrypt.checkpw(_pw(password), hashed.encode('ascii'))
    except ValueError:
        return False


def create_user(email, password, role='user', allow_short_password=False, profile=None, verified=True):
    email = str(email or '').strip().lower()
    if not valid_email(email):
        raise ValueError('Enter a valid email address.')
    if not isinstance(password, str) or (not allow_short_password and len(password) < MIN_PASSWORD):
        raise ValueError(f'The password needs at least {MIN_PASSWORD} characters.')
    hashed = hash_password(password)
    with _users_lock:
        users = [u for u in read_users() if u['email'] != email]
        user = {'email': email, 'hash': hashed, 'role': 'admin' if role == 'admin' else 'user', 'createdAt': now_iso()}
        if profile:
            user['profile'] = clean_profile(profile)
        if not verified:
            user['verified'] = False   # absent means verified: accounts made before this existed, or by an admin
        users.append(user)
        write_users(users)


# ---------- accounts and roles ----------

def list_users():
    """Everything the admin screen may see. Never the hash, never the AI key."""
    return [{
        'email': u['email'],
        'fullName': (u.get('profile') or {}).get('fullName', ''),
        'phone': (u.get('profile') or {}).get('phone', ''),
        'role': 'admin' if u.get('role') == 'admin' else 'user',
        'createdAt': u.get('createdAt'),
        'hasAiKey': bool(u.get('aiKey')),
        'defaultPassword': bool(u.get('defaultPassword')),
        'verified': u.get('verified') is not False,
    } for u in read_users()]


def get_user(email):
    email = str(email or '').strip().lower()
    return next((u for u in read_users() if u['email'] == email), None)


def is_admin(email):
    u = get_user(email)
    return bool(u) and u.get('role') == 'admin'


def count_admins():
    return sum(1 for u in read_users() if u.get('role') == 'admin')


def set_password(email, password, verify_email=False):
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise ValueError(f'The password needs at least {MIN_PASSWORD} characters.')
    hashed = hash_password(password)
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            raise ValueError('No such account.')
        u['hash'] = hashed
        u.pop('defaultPassword', None)   # whatever it is now, it is no longer the shipped one
        if verify_email:
            u.pop('verified', None)      # the reset link reached the inbox: that proves the address
        write_users(users)


def is_verified(email):
    u = get_user(email)
    return bool(u) and u.get('verified') is not False


def mark_verified(email):
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            return False
        if u.get('verified') is False:
            u.pop('verified', None)
            write_users(users)
        return True


def set_role(email, role):
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            raise ValueError('No such account.')
        nxt = 'admin' if role == 'admin' else 'user'
        # Locking everyone out of the admin screen is not a recoverable mistake.
        if u.get('role') == 'admin' and nxt != 'admin' and count_admins() <= 1:
            raise ValueError('This is the last administrator.')
        u['role'] = nxt
        write_users(users)


def delete_user(email):
    with _users_lock:
        users = read_users()
        u = next((x for x in users if x['email'] == email), None)
        if not u:
            raise ValueError('No such account.')
        if u.get('role') == 'admin' and count_admins() <= 1:
            raise ValueError('This is the last administrator.')
        write_users([x for x in users if x['email'] != email])


# Only the address has a default. There is no default password: one written in the
# source would let anyone into a public instance that forgot to set ADMIN_PASSWORD.
DEFAULT_ADMIN_EMAIL = 'admin@prospecthub.com'


def seed_admin():
    """Make sure the administrator account exists at startup.

    This runs on every boot because a host may hand us an empty disk each deploy. The
    account named by ADMIN_EMAIL is created if it is missing and promoted if it is not an
    administrator, so the documented login always works. An existing password is never
    overwritten.
    """
    email = (os.environ.get('ADMIN_EMAIL') or DEFAULT_ADMIN_EMAIL).strip().lower()
    password = os.environ.get('ADMIN_PASSWORD') or ''
    users = read_users()
    had_accounts = len(users) > 0
    had_admin = any(u.get('role') == 'admin' for u in users)
    existing = next((u for u in users if u['email'] == email), None)

    if existing:
        if existing.get('role') != 'admin':
            existing['role'] = 'admin'
            write_users(users)
            print(f'Promoted {email} to administrator.')
        if existing.get('defaultPassword'):
            print(f'  {email} still uses a development password. Change it on the Admin page.')
        return {'email': email, 'created': False}

    generated = not password
    if generated:
        if os.environ.get('VERCEL'):
            # The disk is wiped between cold starts, so a password printed once in the
            # logs would keep changing. Better no administrator than that.
            print('ADMIN_PASSWORD is not set: no administrator account was created. '
                  'Set ADMIN_EMAIL and ADMIN_PASSWORD in the Vercel project settings, then redeploy.')
            return {'email': email, 'created': False}
        password = secrets.token_urlsafe(12)

    create_user(email, password, role='admin', allow_short_password=True)
    if generated:
        # Flag it so later boots can keep warning without re-hashing to find out.
        lst = read_users()
        next(u for u in lst if u['email'] == email)['defaultPassword'] = True
        write_users(lst)
        print(f'\n  Development administrator created\n    email:    {email}\n    password: {password}\n'
              '  It is shown only now. Set ADMIN_EMAIL and ADMIN_PASSWORD before deploying.\n')
    else:
        print(f'Created the administrator account {email}.')

    # An install that predates roles keeps its original owner as an administrator,
    # rather than being quietly demoted by the upgrade.
    if had_accounts and not had_admin:
        lst = read_users()
        others = sorted((u for u in lst if u['email'] != email), key=lambda u: str(u.get('createdAt')))
        if others:
            others[0]['role'] = 'admin'
            write_users(lst)
            print(f"Kept {others[0]['email']} as an administrator.")
    return {'email': email, 'created': True}


_DUMMY_HASH = hash_password('not-a-real-password')


def check_login(email, password):
    email = str(email or '').strip().lower()
    u = next((x for x in read_users() if x['email'] == email), None)
    ok = _check(str(password or ''), u['hash'] if u else _DUMMY_HASH)  # same work whether or not the user exists
    return u['email'] if u and ok else None


def has_users():
    return len(read_users()) > 0


# ---------- signed, stateless session token ----------

def _mac(body, purpose=''):
    # Each purpose signs with its own key, so an emailed link can never pass for a session cookie.
    k = key() if not purpose else key() + '|' + purpose
    return _b64e(hmac.new(k.encode('utf-8'), body.encode('ascii'), hashlib.sha256).digest())


def sign(payload, purpose=''):
    body = _b64e(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    return body + '.' + _mac(body, purpose)


def verify(token, purpose=''):
    if not isinstance(token, str) or '.' not in token:
        return None
    body, mac = token.split('.', 1)
    if not hmac.compare_digest(mac.encode(), _mac(body, purpose).encode()):
        return None
    try:
        p = json.loads(_b64d(body))
        return p if p.get('exp', 0) > now_ms() else None
    except Exception:
        return None


def parse_cookies(header):
    out = {}
    for part in str(header or '').split(';'):
        i = part.find('=')
        if i > 0:
            out[part[:i].strip()] = unquote(part[i + 1:].strip())
    return out


def session_from(request):
    """The signed-in session, or None. A valid cookie for an account that no longer
    exists (deleted, or lost with a wiped disk) counts as signed out."""
    t = parse_cookies(request.headers.get('Cookie')).get(COOKIE)
    s = verify(t) if t else None
    return s if s and get_user(s.get('u')) else None


def set_session(request, response, email):
    secure = os.environ.get('COOKIE_SECURE') == 'true' or request.is_secure
    tok = sign({'u': email, 'exp': now_ms() + MAX_AGE_S * 1000})
    response.headers.add('Set-Cookie', f"{COOKIE}={tok}; HttpOnly; SameSite=Lax; Path=/; Max-Age={MAX_AGE_S}{'; Secure' if secure else ''}")


def clear_session(response):
    response.headers.add('Set-Cookie', f'{COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')


# ---------- emailed links: address verification and password reset ----------
VERIFY_TTL_S = 48 * 3600
RESET_TTL_S = 3600


def _hash_print(u):
    # Changes whenever the password does, so a reset link works once and dies with the old password.
    return hashlib.sha256(('pw|' + u['hash']).encode('utf-8')).hexdigest()[:20]


def make_verify_token(email):
    return sign({'u': email, 'exp': now_ms() + VERIFY_TTL_S * 1000}, 'verify-email')


def read_verify_token(token):
    p = verify(str(token or ''), 'verify-email')
    return p['u'] if p and get_user(p.get('u')) else None


def make_reset_token(email):
    u = get_user(email)
    return sign({'u': u['email'], 'h': _hash_print(u), 'exp': now_ms() + RESET_TTL_S * 1000}, 'reset-password')


def read_reset_token(token):
    p = verify(str(token or ''), 'reset-password')
    if not p:
        return None
    u = get_user(p.get('u'))
    return u['email'] if u and hmac.compare_digest(str(p.get('h', '')), _hash_print(u)) else None


# ---------- brute-force guard: 5 failures per ip+email, then 15 minutes ----------
_fails = {}


def lock_state(k):
    f = _fails.get(k)
    if f and f['until'] and f['until'] > now_ms():
        return -(-(f['until'] - now_ms()) // 1000)
    return 0


def note_fail(k):
    f = _fails.get(k) or {'n': 0, 'until': 0}
    if f['until'] and f['until'] <= now_ms():
        f['n'] = 0
        f['until'] = 0
    f['n'] += 1
    if f['n'] >= 5:
        f['until'] = now_ms() + 15 * 60 * 1000
        f['n'] = 0
    _fails[k] = f


def note_ok(k):
    _fails.pop(k, None)
