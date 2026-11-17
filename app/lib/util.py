"""Small helpers shared by the server modules.

The API accepts loosely typed JSON from the browser, so a few helpers pin down how
values are coerced (to text, to numbers, to booleans) in one place.
"""
import math
import random
import re
import time
from datetime import datetime, timezone

_INT_PREFIX = re.compile(r'\s*[+-]?\d+')
_FLOAT_PREFIX = re.compile(r'\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
DATE_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


def to_str(v):
    """Text form of a JSON value: None becomes '', booleans 'true'/'false'."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dict, list)):
        return '[object Object]'
    return str(v)


def clip(v, n):
    """Text form of v, at most n characters."""
    return to_str(v)[:n]


def truthy(v):
    """Truthiness as the browser means it: empty lists and objects still count."""
    if isinstance(v, (dict, list)):
        return True
    return bool(v)


def parse_int(v):
    """Leading integer of v's text, or None ('12abc' -> 12, 'abc' -> None)."""
    if isinstance(v, bool) or v is None:
        return None
    m = _INT_PREFIX.match(to_str(v))
    return int(m.group(0)) if m else None


def parse_float(v):
    """Leading number of v's text with a comma accepted as decimal point, or None."""
    if isinstance(v, bool) or v is None:
        return None
    m = _FLOAT_PREFIX.match(to_str(v).replace(',', '.', 1))
    if not m:
        return None
    n = float(m.group(0))
    if not math.isfinite(n):
        return None
    return int(n) if n.is_integer() and abs(n) < 2 ** 53 else n


def js_round(n):
    """Round half up, the way the dataset was rounded originally (2.5 -> 3)."""
    return int(math.floor(n + 0.5))


def is_date(v):
    return isinstance(v, str) and DATE_RE.fullmatch(v) is not None


def now_iso():
    """UTC timestamp like 2026-11-17T10:00:00.000Z."""
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def parse_iso(s):
    try:
        d = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def now_ms():
    return int(time.time() * 1000)


def base36(n):
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    out = ''
    while True:
        n, r = divmod(n, 36)
        out = chars[r] + out
        if not n:
            return out


def random_id(k=4):
    return ''.join(random.choice('0123456789abcdefghijklmnopqrstuvwxyz') for _ in range(k))


class ApiError(Exception):
    """An error with an HTTP status and an optional machine-readable code."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code
