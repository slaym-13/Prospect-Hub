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

def _failed(e):
    """A stand-in that says what broke, instead of Vercel's bare crash page (which the
    browser can only report as "request failed"). The full trace goes to the logs."""
    print('The app could not start:\n' + traceback.format_exc())
    if 'psycopg' in type(e).__module__ or 'connection' in str(e).lower():
        hint = 'The database could not be reached. Check DATABASE_URL in the Vercel settings.'
    else:
        hint = 'Open the Vercel logs for the details.'
    body = json.dumps({'error': f'The server could not start ({type(e).__name__}). {hint}'}).encode()

    def wsgi(environ, start_response):
        start_response('503 Service Unavailable', [('Content-Type', 'application/json'),
                                                   ('Content-Length', str(len(body)))])
        return [body]
    return wsgi


def _build():
    try:
        from app import create_app
        return create_app()
    except Exception as e:  # noqa: BLE001
        return _failed(e)


# Vercel finds the application by this top-level name; keep it a plain assignment here.
app = _build()
