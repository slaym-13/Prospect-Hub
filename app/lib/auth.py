"""Accounts, roles, signed session cookies, and each user's encrypted Gemini key."""
import base64
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
    try:
        with open(USERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def write_users(users):
    with _users_lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        fd = os.open(USERS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)


def _secret():
    env = os.environ.get('SESSION_SECRET') or ''
    if len(env) >= 24:
        return env
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
        write_users(users)


def get_ai_key(email):
    u = next((x for x in read_users() if x['email'] == email), None)
    return decrypt(u['aiKey']) if u and u.get('aiKey') else None


def has_ai_key(email):
    return bool(get_ai_key(email))


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


def create_user(email, password, role='user', allow_short_password=False):
    email = str(email or '').strip().lower()
    if not valid_email(email):
        raise ValueError('Enter a valid email address.')
    if not isinstance(password, str) or (not allow_short_password and len(password) < MIN_PASSWORD):
        raise ValueError(f'The password needs at least {MIN_PASSWORD} characters.')
    hashed = hash_password(password)
    with _users_lock:
        users = [u for u in read_users() if u['email'] != email]
        users.append({'email': email, 'hash': hashed, 'role': 'admin' if role == 'admin' else 'user', 'createdAt': now_iso()})
        write_users(users)


# ---------- accounts and roles ----------

def list_users():
    """Everything the admin screen may see. Never the hash, never the AI key."""
    return [{
        'email': u['email'],
        'role': 'admin' if u.get('role') == 'admin' else 'user',
        'createdAt': u.get('createdAt'),
        'hasAiKey': bool(u.get('aiKey')),
        'defaultPassword': bool(u.get('defaultPassword')),
    } for u in read_users()]


def get_user(email):
    email = str(email or '').strip().lower()
    return next((u for u in read_users() if u['email'] == email), None)


def is_admin(email):
    u = get_user(email)
    return bool(u) and u.get('role') == 'admin'


def count_admins():
    return sum(1 for u in read_users() if u.get('role') == 'admin')


def set_password(email, password):
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
        write_users(users)


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


DEFAULT_ADMIN = {'email': 'admin@prospecthub.com', 'password': 'adminPH'}


def seed_admin():
    """Make sure the administrator account exists at startup.

    This runs on every boot because a host may hand us an empty disk each deploy. The
    account named by ADMIN_EMAIL is created if it is missing and promoted if it is not an
    administrator, so the documented login always works. An existing password is never
    overwritten.
    """
    email = (os.environ.get('ADMIN_EMAIL') or DEFAULT_ADMIN['email']).strip().lower()
    password = os.environ.get('ADMIN_PASSWORD') or DEFAULT_ADMIN['password']
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
            print(f'  {email} still uses the development password. Set ADMIN_PASSWORD, or change it on the Admin page.')
        return {'email': email, 'created': False}

    create_user(email, password, role='admin', allow_short_password=True)
    if password == DEFAULT_ADMIN['password']:
        # Flag it so later boots can keep warning without re-hashing to find out.
        lst = read_users()
        next(u for u in lst if u['email'] == email)['defaultPassword'] = True
        write_users(lst)
        print(f'\n  Development administrator created\n    email:    {email}\n    password: {password}\n'
              '  Set ADMIN_EMAIL and ADMIN_PASSWORD before deploying this.\n')
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

def _mac(body):
    return _b64e(hmac.new(key().encode('utf-8'), body.encode('ascii'), hashlib.sha256).digest())


def sign(payload):
    body = _b64e(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    return body + '.' + _mac(body)


def verify(token):
    if not isinstance(token, str) or '.' not in token:
        return None
    body, mac = token.split('.', 1)
    if not hmac.compare_digest(mac.encode(), _mac(body).encode()):
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
    t = parse_cookies(request.headers.get('Cookie')).get(COOKIE)
    return verify(t) if t else None


def set_session(request, response, email):
    secure = os.environ.get('COOKIE_SECURE') == 'true' or request.is_secure
    tok = sign({'u': email, 'exp': now_ms() + MAX_AGE_S * 1000})
    response.headers.add('Set-Cookie', f"{COOKIE}={tok}; HttpOnly; SameSite=Lax; Path=/; Max-Age={MAX_AGE_S}{'; Secure' if secure else ''}")


def clear_session(response):
    response.headers.add('Set-Cookie', f'{COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')


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
