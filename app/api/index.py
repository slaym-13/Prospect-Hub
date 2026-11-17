"""Serverless entry point for Vercel.

Vercel never runs server.py: its Python runtime imports this file and serves the WSGI
application named `app`, once per request. Routing is in ../vercel.json, which sends
/api/* here and serves the built client from dist/ as static files.

Everything stateful lives under DATA_DIR, which must point at a writable directory
(/tmp/data on Vercel). See the deployment section of the README for the full list of
environment variables.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))

from app import create_app  # noqa: E402

app = create_app()
