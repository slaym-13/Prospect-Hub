"""Administration: accounts, and the company records themselves.

Every route here is behind the administrator check in app.py. The ordinary API lets a
user change the working state of a company (status, notes, follow-up); this one lets an
administrator correct the underlying record, add or delete companies, and reload the
shipped dataset.
"""
import os

from flask import Blueprint, g, jsonify

from . import auth, store
from .api import body, err
from .util import clip

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def seed_file():
    """The seed file, wherever it happens to live on this host."""
    for f in (os.path.join(store.DATA_DIR, 'companies.csv'), os.path.join(APP_DIR, 'data', 'companies.csv')):
        if os.path.exists(f):
            return f
    return None


def create_admin_api():
    r = Blueprint('admin', __name__, url_prefix='/api/admin')

    # ----- overview -----
    @r.get('/stats')
    def stats():
        leads = list(store.get()['leads'].values())
        by_status = {}
        for l in leads:
            by_status[l.get('status')] = by_status.get(l.get('status'), 0) + 1
        return jsonify({
            'companies': len(leads),
            'withEmail': sum(1 for l in leads if l.get('email')),
            'withWebsite': sum(1 for l in leads if l.get('site_web')),
            'contacted': sum(1 for l in leads if l.get('status') != 'new'),
            'sent': sum(1 for l in leads for s in (l.get('sent') or []) if s.get('ok')),
            'logged': sum(len(l.get('log') or []) for l in leads),
            'byStatus': by_status,
            'allowSignup': store.get()['settings'].get('allowSignup') is not False,
            'users': len(auth.list_users()),
            'admins': auth.count_admins(),
        })

    # ----- accounts -----
    @r.get('/users')
    def users():
        return jsonify(auth.list_users())

    @r.post('/users')
    def add_user():
        b = body()
        try:
            auth.create_user(b.get('email'), b.get('password'), role='admin' if b.get('role') == 'admin' else 'user')
            return jsonify(auth.list_users()), 201
        except ValueError as e:
            return err(400, str(e))

    @r.patch('/users/<email>')
    def patch_user(email):
        email = email.lower()
        b = body()
        if not auth.get_user(email):
            return err(404, 'No such account.')
        try:
            if 'password' in b:
                auth.set_password(email, b['password'])
            if 'role' in b:
                # Removing your own admin rights locks you out of this screen immediately.
                if email == g.user and b['role'] != 'admin':
                    return err(400, 'You cannot remove your own administrator rights.')
                auth.set_role(email, b['role'])
            return jsonify(auth.list_users())
        except ValueError as e:
            return err(400, str(e))

    @r.delete('/users/<email>')
    def delete_user(email):
        email = email.lower()
        if email == g.user:
            return err(400, 'You cannot delete the account you are signed in with.')
        try:
            auth.delete_user(email)
            return jsonify(auth.list_users())
        except ValueError as e:
            return err(404 if str(e) == 'No such account.' else 400, str(e))

    @r.patch('/signup')
    def signup_switch():
        """Open or close public registration."""
        enabled = body().get('enabled')
        if not isinstance(enabled, bool):
            return err(400, 'Send {"enabled": true} or {"enabled": false}.')
        store.get()['settings']['allowSignup'] = enabled
        store.save()
        return jsonify({'allowSignup': enabled})

    # ----- company records -----
    @r.post('/leads')
    def add_lead():
        b = body()
        try:
            lead = store.add_lead({
                'place_id': clip(b.get('place_id'), 120), 'nom': clip(b.get('nom'), 200),
                'adresse': clip(b.get('adresse'), 300), 'telephone': clip(b.get('telephone'), 40),
                'site_web': clip(b.get('site_web'), 300), 'email': clip(b.get('email'), 160),
                'categorie': clip(b.get('categorie'), 80), 'google_maps': clip(b.get('google_maps'), 400),
                'note': b.get('note'), 'nombre_avis': b.get('nombre_avis'), 'latitude': b.get('latitude'),
                'longitude': b.get('longitude'), 'query': 'manuel',
            })
            return jsonify(lead), 201
        except ValueError as e:
            return err(400, str(e))

    @r.patch('/leads/<lead_id>')
    def patch_lead(lead_id):
        b = body()
        fields = {}
        for k, mx in (('nom', 200), ('adresse', 300), ('telephone', 40), ('site_web', 300),
                      ('email', 160), ('categorie', 80), ('google_maps', 400)):
            if k in b:
                fields[k] = clip(b[k], mx)
        for k in ('note', 'nombre_avis', 'latitude', 'longitude'):
            if k in b:
                fields[k] = b[k]
        if fields.get('email') and not auth.valid_email(fields['email']):
            return err(400, 'That email address does not look valid.')
        try:
            return jsonify(store.update_lead(lead_id, fields))
        except KeyError as e:
            return err(404, e.args[0])

    @r.delete('/leads/<lead_id>')
    def delete_lead(lead_id):
        try:
            store.remove_lead(lead_id)
            return jsonify({'ok': True})
        except KeyError as e:
            return err(404, e.args[0])

    @r.post('/reset')
    def reset():
        """Destructive: drops every company, note and status, then reloads the dataset."""
        f = seed_file()
        if not f:
            return err(500, 'The dataset that ships with the app could not be found.')
        if body().get('confirm') != 'reset':
            return err(400, 'Send {"confirm":"reset"} to confirm.')
        try:
            return jsonify(store.reset_leads(f))
        except Exception as e:
            return err(500, str(e))

    return r
