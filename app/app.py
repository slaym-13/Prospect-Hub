"""The Flask application: security headers, the /api routes, and the built React client."""
import os
import traceback

from flask import Flask, Response, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from lib import auth, store
from lib.admin import create_admin_api
from lib.api import PUBLIC, create_api
from lib.util import random_id

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(APP_DIR, 'dist')
INDEX = os.path.join(DIST, 'index.html')

CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


def create_app():
    store.load()
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
    app.json.sort_keys = False
    trust = os.environ.get('TRUST_PROXY')
    if trust:
        hops = 1 if trust == 'true' else int(trust) if trust.isdigit() else 1
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    @app.before_request
    def guard():
        path = request.path
        if not (path == '/api' or path.startswith('/api/')):
            return None
        # Cross-site pages cannot add this header without a CORS preflight, which this server never grants.
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('X-Requested-With') != 'prospect-hub':
            return jsonify({'error': 'Missing request header.'}), 403
        if request.is_json and request.content_length and request.get_json(silent=True) is None:
            return jsonify({'error': 'Bad request.'}), 400
        store.refresh()   # another server instance may have written since this one loaded
        if (request.method, path) in PUBLIC:
            return None
        s = auth.session_from(request)
        if not s:
            return jsonify({'error': 'Please sign in.'}), 401
        g.user = s['u']
        if path == '/api/admin' or path.startswith('/api/admin/'):
            if not auth.is_admin(g.user):
                return jsonify({'error': 'Administrators only.'}), 403
        return None

    @app.after_request
    def headers(res):
        res.headers['X-Content-Type-Options'] = 'nosniff'
        res.headers['X-Frame-Options'] = 'DENY'
        res.headers['Referrer-Policy'] = 'no-referrer'
        res.headers['Content-Security-Policy'] = CSP
        if request.path.startswith('/api'):
            res.headers['Cache-Control'] = 'no-store'
        return res

    app.register_blueprint(create_api())
    app.register_blueprint(create_admin_api())

    # The React client (Vite build). Hashed asset names, so they can be cached hard; index.html never is.
    @app.get('/favicon.ico')
    def favicon():
        return Response(status=204)

    @app.get('/assets/<path:name>')
    def assets(name):
        res = send_from_directory(os.path.join(DIST, 'assets'), name, max_age=365 * 24 * 3600)
        res.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return res

    # Every other GET is a client route: hand back index.html and let React Router decide.
    @app.get('/')
    @app.get('/<path:name>')
    def client(name=''):
        if name.startswith('api/'):
            raise NotFound()
        if name and os.path.isfile(os.path.join(DIST, name)):
            return send_from_directory(DIST, name, max_age=0)
        if not os.path.exists(INDEX):
            return Response('Not found. Run "npm run build" if the client has not been built yet.', status=404)
        res = send_from_directory(DIST, 'index.html', max_age=0)
        res.headers['Cache-Control'] = 'no-store'
        return res

    @app.errorhandler(HTTPException)
    def http_error(e):
        api = request.path.startswith('/api')
        if isinstance(e, MethodNotAllowed):   # an unknown method is an unknown route
            e = NotFound()
        if api:
            msg = {400: 'Bad request.', 404: 'Not found.', 413: 'Request too large.'}.get(e.code, e.name)
            return jsonify({'error': msg}), e.code
        if e.code == 404:
            return Response('Not found. Run "npm run build" if the client has not been built yet.', status=404)
        return e

    @app.errorhandler(Exception)
    def server_error(e):
        # A reference the person can read off the screen and find in the log.
        ref = random_id(6)
        print(f'[{ref}] {request.method} {request.full_path} failed:\n{traceback.format_exc()}')
        if request.path.startswith('/api'):
            return jsonify({'error': f'Something went wrong on the server (ref {ref}). The console has the details.'}), 500
        return Response('Server error', status=500)

    # An administrator must exist before anyone can sign in. This lives here rather
    # than in server.py because a serverless host never runs server.py.
    auth.seed_admin()

    # First run: import the companies that ship with the app. On a host where the only
    # writable place is a scratch directory, DATA_DIR points there and starts empty, so
    # fall back to the copy that travels with the source.
    seed = next((f for f in (os.path.join(store.DATA_DIR, 'companies.csv'), os.path.join(APP_DIR, 'data', 'companies.csv'))
                 if os.path.exists(f)), None)
    if seed and not store.get()['leads']:
        r = store.import_csv_file(seed)
        store.save_now()
        print(f"Imported {r['added']} companies from {seed}")
    return app
