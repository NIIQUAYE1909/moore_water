import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get('DB_PATH', 'database.db')

# ── Admin email whitelist (must match app.py) ──────────────
# These emails are granted admin role automatically.
ADMIN_EMAILS = {
    'quayen010@gmail.com',
    # Add second admin email here when ready:
    # 'second_admin@example.com',
}

def get_role(email: str) -> str:
    return 'admin' if email.strip().lower() in ADMIN_EMAILS else 'employee'


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Users Table ────────────────────────────────────────
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('admin', 'employee'))
    )
    ''')

    # ── Ledger Table ───────────────────────────────────────
    cursor.execute('''
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
    ''')

    # ── Seed default users if table is empty ───────────────
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Seeding default users...")

        seed_users = [
            # Primary admin
            ('quayen010@gmail.com',    'Quayen Admin',  generate_password_hash('admin123'),    'admin'),
            # Demo employee accounts
            ('employee@moorwater.com', 'Kofi Mensah',   generate_password_hash('employee123'), 'employee'),
            ('ama@moorwater.com',      'Ama Serwaa',    generate_password_hash('employee123'), 'employee'),
        ]

        cursor.executemany(
            "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
            seed_users
        )

        print("Default users seeded:")
        print("  ADMIN  -> quayen010@gmail.com   / admin123")
        print("  Worker -> employee@moorwater.com / employee123")
        print("  Worker -> ama@moorwater.com      / employee123")

    else:
        # Update existing admin accounts to match whitelist
        print("Users table already exists. Ensuring admin roles are correct...")
        for email in ADMIN_EMAILS:
            cursor.execute(
                "UPDATE users SET role = 'admin' WHERE email = ?", (email,)
            )
            if cursor.rowcount > 0:
                print(f"  [OK] Upgraded {email} to admin role.")

    conn.commit()
    conn.close()
    print("\nDatabase initialization complete.")


if __name__ == '__main__':
    init_db()
