"""
init_db.py — Standalone database initializer.

Usage:
    python init_db.py

This creates the `users` and `ledger` tables if they don't exist yet, seeds
three default accounts on first run, and re-syncs admin roles against the
whitelist in db.py on every run. It works against whichever backend db.py
resolves to (PostgreSQL via DATABASE_URL, MySQL/TiDB via DB_HOST, or SQLite
as the fallback) — see db.py for the full resolution order.

Note: app.py also calls this logic automatically on startup, so running
this script by hand is optional in most deployments. It's still useful for:
  - a one-off manual setup/verification step, or
  - CI/deploy hooks that want DB setup to happen before the app boots.
"""

from db import init_db

if __name__ == '__main__':
    init_db()
