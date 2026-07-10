"""
db.py — Multi-platform database abstraction for the Moor Water Ledger app.

This module lets the rest of the codebase write ordinary SQLite-style
queries (using '?' placeholders and dict-like rows) while transparently
supporting three deployment targets:

  1. PostgreSQL   — set DATABASE_URL (e.g. Render/Railway/Vercel Postgres,
                     Supabase, Neon, etc.) Recommended for Render & Vercel,
                     since both platforms use ephemeral/serverless
                     filesystems where a local SQLite file will not persist.
  2. MySQL/TiDB    — set DB_HOST (+ DB_USER, DB_PASSWORD, DB_NAME, DB_PORT,
                     optionally DB_SSL_CA). Good for TiDB Serverless.
  3. SQLite (default) — zero setup, file-based. Works great on a VPS or on
                     PythonAnywhere, where the filesystem is persistent.
                     Defaults to `database.db` sitting right next to this
                     file (i.e. the project root), which is exactly
                     `/home/<username>/<project>/database.db` on
                     PythonAnywhere — the same file the app has always used.
                     Override with the DB_PATH env var if you need to point
                     somewhere else.

Resolution order: DATABASE_URL > DB_HOST > SQLite fallback.
"""

import os
import sqlite3

# ─────────────────────────────────────────────
#  Connection resolution
# ─────────────────────────────────────────────

# The project root — the directory this file (db.py) lives in. On
# PythonAnywhere this is /home/<username>/<project>/, so BASE_DIR/database.db
# resolves to the exact same file the app has always read/written, with no
# username hardcoded.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, 'database.db')
_sqlite_path_logged = {}


def _resolve_sqlite_path():
    """
    Pick the SQLite path. Always prefers an explicit DB_PATH override;
    otherwise always resolves to the existing `database.db` sitting next to
    app.py/db.py, so it seamlessly attaches to whatever database is already
    there instead of ever silently creating a new, differently-named file.
    """
    explicit = os.environ.get('DB_PATH')
    if explicit:
        return explicit
    return _DEFAULT_SQLITE_PATH


class DBConnection:
    """
    Thin wrapper so the rest of the app can call conn.execute('... ? ...', params)
    regardless of the underlying engine, and get back dict-like rows.
    """

    def __init__(self, raw_conn, engine):
        self._conn = raw_conn
        self.engine = engine  # 'sqlite' | 'mysql' | 'postgres'

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        q = query
        if self.engine in ('mysql', 'postgres'):
            q = q.replace('?', '%s')
        cur.execute(q, params if params is not None else ())
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db_connection():
    """
    Returns a DBConnection. Resolution order:
      1. DATABASE_URL -> PostgreSQL (recommended for Render / Vercel)
      2. DB_HOST      -> MySQL / TiDB Serverless
      3. otherwise    -> SQLite (recommended for PythonAnywhere / VPS)
    """
    database_url = os.environ.get('DATABASE_URL')
    db_host = os.environ.get('DB_HOST')

    if database_url:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            database_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return DBConnection(conn, 'postgres')

    if db_host:
        import pymysql
        import pymysql.cursors
        db_user = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_name = os.environ.get('DB_NAME')
        db_port = int(os.environ.get('DB_PORT', 4000))
        db_ssl_ca = os.environ.get('DB_SSL_CA')

        ssl_config = {'ssl': {}}
        if db_ssl_ca:
            ssl_config = {'ssl': {'ca': db_ssl_ca}}

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            ssl=ssl_config,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        return DBConnection(conn, 'mysql')

    db_path = _resolve_sqlite_path()
    if not _sqlite_path_logged.get('done'):
        exists = os.path.isfile(db_path)
        print(f"[db] Using SQLite file: {db_path} "
              f"({'found existing data' if exists else 'no existing file — a new one will be created here'})")
        _sqlite_path_logged['done'] = True
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return DBConnection(conn, 'sqlite')


def is_integrity_error(exc):
    """
    Detect a duplicate/unique-constraint violation regardless of which
    driver raised it (sqlite3.IntegrityError, pymysql.err.IntegrityError,
    psycopg2.errors.UniqueViolation / IntegrityError) without requiring
    all three driver packages to be importable at once.
    """
    cls_name = type(exc).__name__
    if 'IntegrityError' in cls_name or 'UniqueViolation' in cls_name:
        return True
    msg = str(exc).lower()
    return any(s in msg for s in (
        'unique constraint', 'duplicate entry', 'duplicate key', 'unique violation'
    ))


def current_engine():
    """Report which engine get_db_connection() would currently use, without opening one."""
    if os.environ.get('DATABASE_URL'):
        return 'postgres'
    if os.environ.get('DB_HOST'):
        return 'mysql'
    return 'sqlite'


# ─────────────────────────────────────────────
#  DDL — per-engine table definitions
# ─────────────────────────────────────────────

def users_ddl(engine):
    if engine == 'postgres':
        return '''
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            email         VARCHAR(254) UNIQUE NOT NULL,
            name          VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'employee'))
        )
        '''
    if engine == 'mysql':
        return '''
        CREATE TABLE IF NOT EXISTS users (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            email         VARCHAR(254) UNIQUE NOT NULL,
            name          VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'employee'))
        )
        '''
    return '''
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('admin', 'employee'))
    )
    '''


def ledger_ddl(engine):
    if engine == 'postgres':
        return '''
        CREATE TABLE IF NOT EXISTS ledger (
            id              SERIAL PRIMARY KEY,
            date            VARCHAR(50) UNIQUE NOT NULL,
            factory_status  VARCHAR(20) NOT NULL CHECK(factory_status IN ('Open', 'Closed')),
            total_produced  INTEGER NOT NULL DEFAULT 0,
            bags_in_storage INTEGER NOT NULL DEFAULT 0,
            truck_sent_out  INTEGER NOT NULL DEFAULT 0,
            truck_sold      INTEGER NOT NULL DEFAULT 0,
            leakages        INTEGER NOT NULL DEFAULT 0,
            aboboya_sold    INTEGER NOT NULL DEFAULT 0,
            factory_sold    INTEGER NOT NULL DEFAULT 0,
            price_per_bag   DOUBLE PRECISION NOT NULL DEFAULT 6.0,
            total_amount    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            fuel_expenses   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            other_expenses  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            cash_withdrawn  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            cash_at_hand    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            cash_at_bank    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            comments        TEXT,
            workers_name    VARCHAR(255) NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    if engine == 'mysql':
        return '''
        CREATE TABLE IF NOT EXISTS ledger (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            date            VARCHAR(50) UNIQUE NOT NULL,
            factory_status  VARCHAR(20) NOT NULL CHECK(factory_status IN ('Open', 'Closed')),
            total_produced  INT NOT NULL DEFAULT 0,
            bags_in_storage INT NOT NULL DEFAULT 0,
            truck_sent_out  INT NOT NULL DEFAULT 0,
            truck_sold      INT NOT NULL DEFAULT 0,
            leakages        INT NOT NULL DEFAULT 0,
            aboboya_sold    INT NOT NULL DEFAULT 0,
            factory_sold    INT NOT NULL DEFAULT 0,
            price_per_bag   DOUBLE NOT NULL DEFAULT 6.0,
            total_amount    DOUBLE NOT NULL DEFAULT 0.0,
            fuel_expenses   DOUBLE NOT NULL DEFAULT 0.0,
            other_expenses  DOUBLE NOT NULL DEFAULT 0.0,
            cash_withdrawn  DOUBLE NOT NULL DEFAULT 0.0,
            cash_at_hand    DOUBLE NOT NULL DEFAULT 0.0,
            cash_at_bank    DOUBLE NOT NULL DEFAULT 0.0,
            comments        TEXT,
            workers_name    VARCHAR(255) NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    return '''
    CREATE TABLE IF NOT EXISTS ledger (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date            TEXT UNIQUE NOT NULL,
        factory_status  TEXT NOT NULL CHECK(factory_status IN ('Open', 'Closed')),
        total_produced  INTEGER NOT NULL DEFAULT 0,
        bags_in_storage INTEGER NOT NULL DEFAULT 0,
        truck_sent_out  INTEGER NOT NULL DEFAULT 0,
        truck_sold      INTEGER NOT NULL DEFAULT 0,
        leakages        INTEGER NOT NULL DEFAULT 0,
        aboboya_sold    INTEGER NOT NULL DEFAULT 0,
        factory_sold    INTEGER NOT NULL DEFAULT 0,
        price_per_bag   REAL NOT NULL DEFAULT 6.0,
        total_amount    REAL NOT NULL DEFAULT 0.0,
        fuel_expenses   REAL NOT NULL DEFAULT 0.0,
        other_expenses  REAL NOT NULL DEFAULT 0.0,
        cash_withdrawn  REAL NOT NULL DEFAULT 0.0,
        cash_at_hand    REAL NOT NULL DEFAULT 0.0,
        cash_at_bank    REAL NOT NULL DEFAULT 0.0,
        comments        TEXT,
        workers_name    TEXT NOT NULL,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    '''


# ─────────────────────────────────────────────
#  Admin whitelist (shared by app.py + init_db.py)
# ─────────────────────────────────────────────

def get_admin_emails():
    emails = {'quayen010@gmail.com', os.environ.get('ADMIN_EMAIL_2', '').strip().lower()}
    return {e for e in emails if e}


def get_role_for_email(email: str) -> str:
    return 'admin' if email.strip().lower() in get_admin_emails() else 'employee'


def init_db(verbose=True):
    """Idempotent: creates tables if missing, seeds default users if the
    users table is empty, and re-syncs admin roles against the whitelist.
    Safe to call on every app startup (Render/Railway/Vercel cold start,
    PythonAnywhere reload, or manually via `python init_db.py`)."""
    from werkzeug.security import generate_password_hash

    conn = get_db_connection()
    engine = conn.engine

    def log(msg):
        if verbose:
            print(msg)

    log(f"[db] Initializing '{engine}' database...")

    conn.execute(users_ddl(engine))
    conn.execute(ledger_ddl(engine))
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) AS c FROM users")
    row = cur.fetchone()
    count = row['c'] if isinstance(row, dict) or hasattr(row, 'keys') else row[0]

    if count == 0:
        log("[db] Seeding default users...")
        seed_users = [
            ('quayen010@gmail.com',    'Quayen Admin',  generate_password_hash('admin123'),    'admin'),
            ('employee@moorwater.com', 'Kofi Mensah',   generate_password_hash('employee123'), 'employee'),
            ('ama@moorwater.com',      'Ama Serwaa',    generate_password_hash('employee123'), 'employee'),
        ]
        for email, name, pw_hash, role in seed_users:
            conn.execute(
                "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
                (email, name, pw_hash, role)
            )
        conn.commit()
        log("[db] Default users seeded: admin quayen010@gmail.com / admin123, "
            "employee@moorwater.com / employee123, ama@moorwater.com / employee123")
    else:
        log("[db] Users table already populated. Syncing admin roles against whitelist...")
        for email in get_admin_emails():
            conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
        conn.commit()

    conn.close()
    log("[db] Initialization complete.")


if __name__ == '__main__':
    init_db()
