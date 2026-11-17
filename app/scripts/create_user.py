"""Create (or reset) a login from the terminal.

    python scripts/create_user.py you@example.com "a password of 10+ characters"
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))

from lib import auth  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print('Usage: python scripts/create_user.py you@example.com "a password of 10+ characters"', file=sys.stderr)
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]
    try:
        auth.create_user(email, password)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print('Account saved for', email.lower())


if __name__ == '__main__':
    main()
