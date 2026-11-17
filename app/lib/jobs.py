"""One background job at a time (the Places refresh), with progress for the UI."""
import threading
import time

from .util import ApiError, now_iso

_lock = threading.Lock()
_job = {'id': 0, 'type': '', 'running': False, 'total': 0, 'done': 0, 'found': 0, 'failed': 0,
        'message': '', 'startedAt': None, 'finishedAt': None, 'cancel': False}


def current():
    return {k: v for k, v in _job.items() if k != 'cancel'}


def cancel():
    if _job['running']:
        _job['cancel'] = True
    return current()


def start(job_type, items, worker, concurrency=3, pause_s=0.15):
    global _job
    with _lock:
        if _job['running']:
            raise ApiError('A job is already running.', code='BUSY')
        _job = {'id': _job['id'] + 1, 'type': job_type, 'running': True, 'total': len(items), 'done': 0, 'found': 0,
                'failed': 0, 'message': '', 'startedAt': now_iso(), 'finishedAt': None, 'cancel': False}
    mine = _job
    queue = list(items)
    qlock = threading.Lock()

    def lane():
        while not mine['cancel']:
            with qlock:
                if not queue:
                    return
                item = queue.pop(0)
            try:
                r = worker(item) or {}
                with qlock:
                    if r.get('found'):
                        mine['found'] += 1
                    if r.get('failed'):
                        mine['failed'] += 1
            except Exception as e:
                with qlock:
                    mine['failed'] += 1
                    mine['message'] = str(e)[:160]
            with qlock:
                mine['done'] += 1
            if pause_s:
                time.sleep(pause_s)

    def run():
        lanes = [threading.Thread(target=lane, daemon=True) for _ in range(min(concurrency, max(len(items), 1)))]
        for t in lanes:
            t.start()
        for t in lanes:
            t.join()
        mine['running'] = False
        mine['finishedAt'] = now_iso()
        if mine['cancel']:
            mine['message'] = 'Stopped.'

    # fire and forget; the UI polls current()
    threading.Thread(target=run, daemon=True).start()
    return current()
