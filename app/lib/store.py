"""Tiny JSON-file database. Fine for a few thousand leads; nothing to install or run."""
import copy
import csv
import io
import json
import os
import re
import threading
import time

from .util import clip, js_round, now_iso, now_ms, base36, random_id, parse_float, to_str

DATA_DIR = os.environ.get('DATA_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DB_FILE = os.path.join(DATA_DIR, 'db.json')

DEFAULT_SETTINGS = {
    'sender': {'name': '', 'role': '', 'background': ''},
    'goal': 'internship',          # 'internship' | 'pitch'
    'language': 'fr',              # 'fr' | 'en'
    'period': '',                  # e.g. "summer 2027, 2 months"
    'signature': '',
    'optOut': {
        'fr': 'Si vous ne souhaitez plus recevoir de message de ma part, répondez simplement « stop » et je ne vous écrirai plus.',
        'en': 'If you would rather not hear from me, just reply "stop" and I will not write again.',
    },
    'replyTo': '',
    'dailyCap': 20,
    'allowSignup': True,           # whether anyone may create their own account
    # Lead scoring (ported from the Prospect Ledger). Weights are relative, not percentages.
    'scoring': {'weights': {'fit': 30, 'pain': 30, 'reach': 15, 'volume': 25}, 'tiers': {}, 'perDay': 5, 'icpOnly': True},
}

STATUSES = ['new', 'contacted', 'replied', 'meeting', 'won', 'lost', 'optout']

# Request threads share one in-memory database; writes to disk go through this lock.
LOCK = threading.RLock()
_db = None
_timer = None


def blank_db():
    return {'version': 1, 'leads': {}, 'settings': copy.deepcopy(DEFAULT_SETTINGS), 'assistant': {}}


def merge_settings(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_settings(out[k], v)
        else:
            out[k] = v
    return out


def load():
    global _db
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, encoding='utf-8') as f:
                _db = json.load(f)
        except (OSError, ValueError):
            bad = f'{DB_FILE}.corrupt-{now_ms()}'
            os.replace(DB_FILE, bad)
            print('db.json was unreadable and was moved to', bad)
            _db = blank_db()
    else:
        _db = blank_db()
    _db['leads'] = _db.get('leads') or {}
    if not isinstance(_db.get('assistant'), dict):
        _db['assistant'] = {}
    # keep leads saved by older versions usable
    gone = ['emails', 'emailManual', 'emailStatus', 'emailCheckedAt', 'emailError', 'siteTitle', 'siteText', 'siteDiscovered']
    for lead in _db['leads'].values():
        for k in gone:   # left over from the removed email crawler
            lead.pop(k, None)
        lead.setdefault('nextStep', '')
        if not isinstance(lead.get('log'), list):
            lead['log'] = []
        lead.setdefault('star', False)
        lead.setdefault('snooze', '')
        if not isinstance(lead.get('checks'), dict):
            lead['checks'] = {}
    _db['settings'] = merge_settings(DEFAULT_SETTINGS, _db.get('settings') or {})
    return _db


def save_now():
    global _timer
    if _db is None:
        return
    with LOCK:
        if _timer:
            _timer.cancel()
            _timer = None
        os.makedirs(DATA_DIR, exist_ok=True)
        # Another request thread may be changing a lead while we serialise; try again.
        for _ in range(5):
            try:
                text = json.dumps(_db, ensure_ascii=False, separators=(',', ':'))
                break
            except RuntimeError:
                time.sleep(0.01)
        tmp = DB_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, DB_FILE)


def save():
    """Write soon. Several changes in a row become one write."""
    global _timer
    if os.environ.get('VERCEL'):
        # A serverless function is frozen after the response: write before returning.
        return save_now()
    with LOCK:
        if _timer:
            _timer.cancel()
        _timer = threading.Timer(0.2, save_now)
        _timer.daemon = True
        _timer.start()


def get():
    return _db if _db is not None else load()


# ---------- CSV ----------

def num(v):
    if v is None or v == '':
        return None
    return parse_float(v)


def _s(r, *keys):
    for k in keys:
        v = r.get(k)
        if v not in (None, '', 0, False):
            return to_str(v).strip()
    return ''


def new_lead(r):
    reviews = num(r.get('nombre_avis'))
    return {
        'id': _s(r, 'place_id', 'id'),
        'nom': _s(r, 'nom'),
        'adresse': _s(r, 'adresse'),
        'telephone': _s(r, 'telephone'),
        'site_web': _s(r, 'site_web'),
        'google_maps': _s(r, 'google_maps'),
        'categorie': _s(r, 'categorie'),
        'note': num(r.get('note')),
        'nombre_avis': None if reviews is None else js_round(reviews),
        'latitude': num(r.get('latitude')),
        'longitude': num(r.get('longitude')),
        'query': _s(r, 'query'),
        'status': 'new', 'notes': '',
        'email': _s(r, 'email').lower(), 'placesStatus': '', 'placesCheckedAt': None,
        'sent': [], 'draft': None, 'createdAt': now_iso(),
        # pipeline extras: next follow-up date, contact log, star, snooze-until, manual website checks
        'nextStep': '', 'log': [], 'star': False, 'snooze': '', 'checks': {},
    }


def import_csv_text(text, merge=True):
    if text.startswith('﻿'):
        text = text[1:]
    rows = list(csv.DictReader(io.StringIO(text)))
    d = get()
    added = updated = skipped = 0
    for r in rows:
        lead = new_lead(r)
        if not lead['id'] or not lead['nom']:
            skipped += 1
            continue
        ex = d['leads'].get(lead['id'])
        if not ex:
            d['leads'][lead['id']] = lead
            added += 1
            continue
        if not merge:
            skipped += 1
            continue
        for k in ['nom', 'adresse', 'telephone', 'google_maps', 'categorie', 'query', 'site_web']:
            if lead[k]:
                ex[k] = lead[k]
        for k in ['note', 'nombre_avis', 'latitude', 'longitude']:
            if lead[k] is not None:
                ex[k] = lead[k]
        if lead['email'] and not ex.get('email'):
            ex['email'] = lead['email']
        updated += 1
    save()
    return {'rows': len(rows), 'added': added, 'updated': updated, 'skipped': skipped}


def import_csv_file(path, merge=True):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return import_csv_text(f.read(), merge)


# ---------- administration ----------

# The company fields an administrator may correct. Everything else is derived.
EDITABLE = ['nom', 'adresse', 'telephone', 'site_web', 'email', 'categorie', 'google_maps', 'query']
NUMERIC = ['note', 'nombre_avis', 'latitude', 'longitude']


def add_lead(fields):
    d = get()
    lead = new_lead(fields)
    if not lead['nom']:
        raise ValueError('A company needs a name.')
    if not lead['id']:
        lead['id'] = 'man-' + base36(now_ms()) + random_id(4)
    if lead['id'] in d['leads']:
        raise ValueError('A company with that identifier already exists.')
    d['leads'][lead['id']] = lead
    save()
    return lead


def update_lead(lead_id, fields):
    lead = get()['leads'].get(lead_id)
    if not lead:
        raise KeyError('No such company.')
    for k in EDITABLE:
        if k in fields:
            lead[k] = to_str(fields[k]).strip()
    if lead.get('email'):
        lead['email'] = lead['email'].lower()
    for k in NUMERIC:
        if k in fields:
            lead[k] = None if fields[k] in ('', None) else num(fields[k])
    save()
    return lead


def remove_lead(lead_id):
    d = get()
    if lead_id not in d['leads']:
        raise KeyError('No such company.')
    del d['leads'][lead_id]
    save()


def reset_leads(seed_file):
    """Throw the working data away and load the shipped dataset again."""
    d = get()
    d['leads'] = {}
    result = import_csv_file(seed_file)
    save_now()
    return result


_FORMULA = re.compile(r'^[=+\-@\t\r]')


def _guard(v):
    """Stop a spreadsheet from running a cell as a formula."""
    v = to_str(v)
    return "'" + v if _FORMULA.match(v) else v


def export_csv():
    cols = ['place_id', 'nom', 'adresse', 'telephone', 'site_web', 'email', 'google_maps', 'categorie', 'note',
            'nombre_avis', 'latitude', 'longitude', 'query', 'status', 'next_step', 'last_contacted']
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    w.writerow(cols)
    for l in list(get()['leads'].values()):
        ok = [s for s in (l.get('sent') or []) if s.get('ok')]
        last = ok[-1] if ok else None
        row = [l.get('id'), l.get('nom'), l.get('adresse'), l.get('telephone'), l.get('site_web'), l.get('email'),
               l.get('google_maps'), l.get('categorie'), l.get('note'), l.get('nombre_avis'), l.get('latitude'),
               l.get('longitude'), l.get('query'), l.get('status'), l.get('nextStep') or '', last['at'] if last else '']
        w.writerow([_guard(v) for v in row])
    return '﻿' + out.getvalue()


__all__ = ['load', 'get', 'save', 'save_now', 'import_csv_text', 'import_csv_file', 'export_csv', 'add_lead',
           'update_lead', 'remove_lead', 'reset_leads', 'DEFAULT_SETTINGS', 'STATUSES', 'DATA_DIR', 'merge_settings',
           'clip']
