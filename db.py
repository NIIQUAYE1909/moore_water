"""
diagnose_db.py — Read-only diagnostic. Finds every SQLite file under your
home directory, and for each one that has `users`/`ledger` tables, prints
row counts and the most recent ledger dates. Use this to figure out which
physical file actually holds your real historical data.

Run it from a PythonAnywhere Bash console:
    cd ~/moore_water
    python3 diagnose_db.py

It does not modify anything.
"""

import os
import sqlite3
import glob

SEARCH_ROOTS = [os.path.expanduser('~')]


def inspect(db_path):
    try:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        print(f"\n📄 {db_path}")
        print(f"   size: {os.path.getsize(db_path):,} bytes")
        print(f"   tables: {tables}")

        if 'users' in tables:
            n = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            emails = [r[0] for r in cur.execute("SELECT email FROM users").fetchall()]
            print(f"   users: {n} row(s) -> {emails}")

        if 'ledger' in tables:
            n = cur.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
            print(f"   ledger: {n} row(s)")
            if n > 0:
                recent = cur.execute(
                    "SELECT date, workers_name, total_amount FROM ledger ORDER BY date DESC LIMIT 5"
                ).fetchall()
                print("   most recent ledger rows:")
                for row in recent:
                    print(f"      {row}")

        conn.close()
    except Exception as e:
        print(f"\n📄 {db_path}  -- could not open: {e}")


def main():
    seen = set()
    print("Scanning for .db files under:", SEARCH_ROOTS)
    for root in SEARCH_ROOTS:
        for path in glob.glob(os.path.join(root, '**', '*.db'), recursive=True):
            real = os.path.realpath(path)
            if real in seen:
                continue
            seen.add(real)
            inspect(path)

    if not seen:
        print("No .db files found at all under", SEARCH_ROOTS)

    print("\nDone. Whichever file above shows your real ledger rows is the one")
    print("DB_PATH should point to (or move/rename it to database.db in your")
    print("project root, which is what db.py uses by default).")


if __name__ == '__main__':
    main()
