import sqlite3
import os
from werkzeug.security import generate_password_hash
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'database.db'))

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
    db_host = os.environ.get('DB_HOST')
    is_mysql = False
    
    if db_host:
        import pymysql
        db_user = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_name = os.environ.get('DB_NAME')
        db_port = int(os.environ.get('DB_PORT', 4000))
        db_ssl_ca = os.environ.get('DB_SSL_CA')
        
        ssl_config = {'ssl': {}}
        if db_ssl_ca:
            ssl_config = {'ssl': {'ca': db_ssl_ca}}
            
        print(f"Connecting to TiDB/MySQL database at {db_host}:{db_port}...")
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            ssl=ssl_config
        )
        is_mysql = True
    else:
        print(f"Connecting to SQLite database at {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    def run_execute(query, params=None):
        nonlocal is_mysql
        q = query
        if is_mysql:
            q = q.replace('?', '%s')
        if params is not None:
            cursor.execute(q, params)
        else:
            cursor.execute(q)

    def run_executemany(query, params_list):
        nonlocal is_mysql
        q = query
        if is_mysql:
            q = q.replace('?', '%s')
        cursor.executemany(q, params_list)

    # ── Users Table ────────────────────────────────────────
    if is_mysql:
        users_ddl = '''
        CREATE TABLE IF NOT EXISTS users (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            email         VARCHAR(254) UNIQUE NOT NULL,
            name          VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'employee'))
        )
        '''
    else:
        users_ddl = '''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT UNIQUE NOT NULL,
            name          TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL CHECK(role IN ('admin', 'employee'))
        )
        '''
    run_execute(users_ddl)

    # ── Ledger Table ───────────────────────────────────────
    if is_mysql:
        ledger_ddl = '''
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
    else:
        ledger_ddl = '''
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
    run_execute(ledger_ddl)

    # ── Seed default users if table is empty ───────────────
    run_execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Seeding default users...")

        seed_users = [
            # Primary admin
            ('quayen010@gmail.com',    'Quayen Admin',  generate_password_hash('admin123'),    'admin'),
            # Demo employee accounts
            ('employee@moorwater.com', 'Kofi Mensah',   generate_password_hash('employee123'), 'employee'),
            ('ama@moorwater.com',      'Ama Serwaa',    generate_password_hash('employee123'), 'employee'),
        ]

        run_executemany(
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
            run_execute(
                "UPDATE users SET role = 'admin' WHERE email = ?", (email,)
            )
            if cursor.rowcount > 0:
                print(f"  [OK] Upgraded {email} to admin role.")

    conn.commit()
    conn.close()
    print("\nDatabase initialization complete.")



if __name__ == '__main__':
    init_db()
