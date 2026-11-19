"""Serverless entry point for Vercel.

Vercel never runs server.py: its Python runtime imports this file and serves the WSGI
application named `app`, once per request. Routing is in ../vercel.json, which sends
/api/* here and serves the built client from dist/ as static files.

Everything stateful lives in the database named by DATABASE_URL, or else under
DATA_DIR (/tmp/data on Vercel). See the deployment section of the README for the full
list of environment variables.
"""
import json
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))

try:
    from app import create_app  # noqa: E402
    app = create_app()
except Exception as _e:  # noqa: BLE001
    # Without this, Vercel answers every request with a bare crash page and the browser
    # only says "request failed". Say what broke; the full trace goes to the logs.
    print('The app could not start:\n' + traceback.format_exc())
    _reason = type(_e).__name__
    if 'psycopg' in type(_e).__module__ or 'connection' in str(_e).lower():
        _hint = 'The database could not be reached. Check DATABASE_URL in the Vercel settings.'
    else:
        _hint = 'Open the Vercel logs for the details.'
    _body = json.dumps({'error': f'The server could not start ({_reason}). {_hint}'}).encode()

    def app(environ, start_response):  # noqa: F811
        start_response('503 Service Unavailable', [('Content-Type', 'application/json'),
                                                    ('Content-Length', str(len(_body)))])
        return [_body]
