import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row


@contextmanager
def connection():
    dsn = os.environ.get('BMW_DATABASE_URL')
    if not dsn:
        raise psycopg.OperationalError('Database is not configured')
    with psycopg.connect(dsn,connect_timeout=3,row_factory=dict_row) as conn:
        role=conn.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()
        if role['rolsuper']:
            raise psycopg.OperationalError('Application requires a non-superuser role')
        conn.execute("SET LOCAL statement_timeout='8s'")
        yield conn


def one(conn,query,params=()):
    return conn.execute(query,params).fetchone()


def all_rows(conn,query,params=()):
    return conn.execute(query,params).fetchall()
