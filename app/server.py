"""Start Prospect Hub.

    python server.py            serve the API and the built client (waitress)
    python server.py --reload   development: Flask's server, restarts when a .py file changes
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from app import create_app  # noqa: E402  (reads the environment loaded above)
from lib import auth  # noqa: E402

PORT = int(os.environ.get('PORT') or 3000)
HOST = os.environ.get('HOST') or '127.0.0.1'


def main():
    app = create_app()
    shown = 'localhost' if HOST == '0.0.0.0' else HOST
    print(f'Prospect Hub is running at http://{shown}:{PORT}')
    if not auth.has_users():
        print('No account yet: open the page and create one, or run: python scripts/create_user.py you@example.com "a long password"')
    if '--reload' in sys.argv:
        app.run(host=HOST, port=PORT, debug=True, use_reloader=True)
    else:
        from waitress import serve
        serve(app, host=HOST, port=PORT, threads=8)


if __name__ == '__main__':
    main()
