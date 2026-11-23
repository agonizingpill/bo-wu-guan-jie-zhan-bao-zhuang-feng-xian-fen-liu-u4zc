import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from redis import Redis

QUEUE = 'museum:triage'


def connection():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row)


def queue():
    return Redis.from_url(os.environ['REDIS_URL'], socket_timeout=4, socket_connect_timeout=2)


def initialize():
    with connection() as db:
        db.execute('SELECT pg_advisory_xact_lock(66001)')
        for migration in sorted(Path(__file__).resolve().parents[1].joinpath('migrations').glob('*.sql')):
            db.execute(migration.read_text())


def audit(db, loan_id, actor, action, **details):
    db.execute('INSERT INTO audit_entry (loan_id, actor, action, details) VALUES (%s,%s,%s,%s)',
               (loan_id, actor, action, Jsonb(details)))
