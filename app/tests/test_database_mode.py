"""Runs the whole end-to-end suite again with the database backend (in memory).

The suite shares module state, so it runs in a separate process with DATABASE_URL set.
"""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.skipif(bool(os.environ.get('DATABASE_URL')), reason='already running on the database backend')
def test_the_suite_passes_on_the_database_backend():
    env = {**os.environ, 'DATABASE_URL': 'memory://'}
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', os.path.join(HERE, 'test_e2e.py')],
                       cwd=os.path.dirname(HERE), env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
