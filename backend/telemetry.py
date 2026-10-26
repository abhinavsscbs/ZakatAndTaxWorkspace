import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import g

log_dir = Path(os.getenv('LOG_DIR', 'logs'))
log_dir.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger('toolkit')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(log_dir / 'app.jsonl', maxBytes=10_000_000, backupCount=5)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)

def event(kind, **fields):
    logger.info(json.dumps({'timestamp': time.time(), 'event': kind, 'request_id': getattr(g, 'request_id', None), **fields}, ensure_ascii=False))

@contextmanager
def step(name, **metadata):
    start = time.perf_counter()
    row = {'name': name, 'status': 'running', **metadata}
    g.steps.append(row)
    event('step_started', **row)
    try:
        yield row
        row['status'] = 'success'
    except Exception as exc:
        row['status'] = 'error'
        row['error_type'] = type(exc).__name__
        raise
    finally:
        row['duration_ms'] = round((time.perf_counter() - start) * 1000, 3)
        event('step_finished', **row)

def begin():
    g.request_id = uuid.uuid4().hex
    g.steps = []
    g.started = time.perf_counter()

def finish():
    return {'request_id': g.request_id, 'provider': getattr(g, 'provider', None), 'total_ms': round((time.perf_counter()-g.started)*1000, 3), 'steps': g.steps}
