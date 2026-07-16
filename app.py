from flask import Flask, request, jsonify, render_template, redirect, url_for, session, make_response, send_from_directory
import os
import time
from collections import defaultdict
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

import db as dbmod

# ─────────────────────────────────────────────
#  App Initialization
# ─────────────────────────────────────────────
app = Flask(__name__, template_folder='templates', static_folder='static')

SECRET_KEY = os.environ.get('SECRET_KEY', None)
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "\n[SECURITY WARNING] No SECRET_KEY env var found. "
        "Using insecure default. Set SECRET_KEY before hosting!\n",
        stacklevel=2
    )
    SECRET_KEY = 'moor_water_DEV_key_CHANGE_BEFORE_HOSTING_3a9f2b'

app.secret_key = SECRET_KEY
IS_PRODUCTION = os.environ.get('FLASK_ENV', 'development') == 'production'

# ── Session Cookie Security ─────────────────────
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if IS_PRODUCTION else 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 43200  # 12 hours

# ─────────────────────────────────────────────
#  ADMIN EMAIL WHITELIST
#  Only these emails can have admin role.
#  Add ADMIN_EMAIL_2 via environment variable when ready.
#  (Shared with db.py so init_db.py stays in sync automatically.)
# ─────────────────────────────────────────────
get_role_for_email = dbmod.get_role_for_email


# ─────────────────────────────────────────────
#  Rate Limiter (no extra dependencies)
# ─────────────────────────────────────────────
_login_attempts = defaultdict(list)
MAX_ATTEMPTS   = 5
LOCKOUT_WINDOW = 300  # 5 minutes


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOCKOUT_WINDOW]
    return len(_login_attempts[ip]) >= MAX_ATTEMPTS


def record_failed_attempt(ip: str):
    _login_attempts[ip].append(time.time())


def clear_attempts(ip: str):
    _login_attempts.pop(ip, None)


# ─────────────────────────────────────────────
#  Security Headers
# ─────────────────────────────────────────────
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'DENY'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']     = 'geolocation=(), microphone=(), camera=()'
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


# ─────────────────────────────────────────────
#  Database Helper
#  Transparently targets PostgreSQL (DATABASE_URL), MySQL/TiDB (DB_HOST),
#  or SQLite (fallback — PythonAnywhere / VPS). See db.py for details.
# ─────────────────────────────────────────────
def get_db_connection():
    return dbmod.get_db_connection()


# Auto-create tables (and seed default users) on cold start. This is what
# makes Render/Railway/Vercel deployments work without a manual SSH step,
# and it's a harmless no-op on repeat calls (CREATE TABLE IF NOT EXISTS).
try:
    dbmod.init_db(verbose=True)
except Exception as _db_init_err:
    import warnings
    warnings.warn(f"[db] Auto-initialization failed: {_db_init_err}", stacklevel=2)


# ─────────────────────────────────────────────
#  Auth Decorator
# ─────────────────────────────────────────────
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                if request.is_json:
                    return jsonify({'error': 'Unauthorized. Please login.'}), 401
                return redirect(url_for('login_page'))
            if role and session.get('user_role') != role:
                if request.is_json:
                    return jsonify({'error': 'Forbidden. Admin access only.'}), 403
                return render_template('403.html'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ─────────────────────────────────────────────
#  HTML Page Routes
# ─────────────────────────────────────────────
@app.route('/')
def index_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    if session.get('user_role') == 'admin':
        return redirect(url_for('admin_page'))
    return render_template('index.html',
                           user_name=session.get('user_name'),
                           user_role=session.get('user_role'),
                           is_guest=False)


@app.route('/preview')
def preview_page():
    """Guest preview — full employee form, no auth needed. Data not saved."""
    return render_template('index.html',
                           user_name='Guest (Preview Mode)',
                           user_role='guest',
                           is_guest=True)


@app.route('/login')
def login_page():
    if 'user_id' in session:
        if session.get('user_role') == 'admin':
            return redirect(url_for('admin_page'))
        return redirect(url_for('index_page'))
    return render_template('login.html')


@app.route('/register')
def register_page():
    """Self-registration page for new employees."""
    if 'user_id' in session:
        return redirect(url_for('index_page'))
    return render_template('register.html')


@app.route('/admin')
@login_required(role='admin')
def admin_page():
    return render_template('admin.html', user_name=session.get('user_name'))


# ── PWA Support Routes ──────────────────────────
@app.route('/sw.js')
def service_worker():
    response = make_response(
        send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js')
    )
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control']          = 'no-cache, no-store, must-revalidate'
    response.headers['Content-Type']           = 'application/javascript'
    return response


@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')


# ─────────────────────────────────────────────
#  API: Self-Registration (Employees)
# ─────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided.'}), 400

    name     = str(data.get('name', '')).strip()
    email    = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    confirm  = str(data.get('confirm_password', ''))

    # Validation
    if not name or not email or not password:
        return jsonify({'error': 'Name, email and password are required.'}), 400
    if len(name) < 2:
        return jsonify({'error': 'Name must be at least 2 characters.'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400
    if password != confirm:
        return jsonify({'error': 'Passwords do not match.'}), 400
    if len(email) > 254:
        return jsonify({'error': 'Email address is too long.'}), 400

    # Determine role based on email whitelist
    role = get_role_for_email(email)

    conn = get_db_connection()
    try:
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        conn.execute(
            'INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)',
            (email, name, password_hash, role)
        )
        conn.commit()

        # Auto-login after registration
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        session.clear()
        session.permanent = True
        session['user_id']   = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']

        return jsonify({
            'success': f'Account created successfully. Welcome, {name}!',
            'role': role,
            'name': name
        })

    except Exception as e:
        conn.rollback()
        if dbmod.is_integrity_error(e):
            return jsonify({'error': 'That email address is already registered. Please log in instead.'}), 400
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  API: Authentication (Login)
# ─────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def api_login():
    client_ip = request.remote_addr or '0.0.0.0'

    if is_rate_limited(client_ip):
        return jsonify({
            'error': 'Too many failed login attempts. Please wait 5 minutes and try again.'
        }), 429

    data     = request.get_json(silent=True) or request.form
    email    = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400
    if len(email) > 254 or len(password) > 128:
        return jsonify({'error': 'Invalid input.'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    if user and check_password_hash(user['password_hash'], password):
        # Re-check admin whitelist on every login (in case whitelist was updated)
        correct_role = get_role_for_email(email)
        if user['role'] != correct_role:
            conn.execute('UPDATE users SET role = ? WHERE id = ?', (correct_role, user['id']))
            conn.commit()

        conn.close()
        clear_attempts(client_ip)
        session.clear()
        session.permanent = True
        session['user_id']   = user['id']
        session['user_name'] = user['name']
        session['user_role'] = correct_role

        return jsonify({
            'success': 'Login successful.',
            'role':    correct_role,
            'name':    user['name']
        })

    conn.close()
    record_failed_attempt(client_ip)
    remaining = max(0, MAX_ATTEMPTS - len(_login_attempts[client_ip]))
    return jsonify({
        'error': f'Invalid email or password. {remaining} attempt(s) remaining before lockout.'
    }), 401


@app.route('/api/logout', methods=['GET', 'POST'])
def api_logout():
    session.clear()
    if request.method == 'POST' or request.is_json:
        return jsonify({'success': 'Logged out successfully.'})
    return redirect(url_for('login_page'))


# ─────────────────────────────────────────────
#  API: Session Info
# ─────────────────────────────────────────────
@app.route('/api/session', methods=['GET'])
def api_session():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'name': session.get('user_name'),
            'role': session.get('user_role')
        })
    return jsonify({'logged_in': False}), 401


# ─────────────────────────────────────────────
#  API: Ledger (authenticated employees + admins)
# ─────────────────────────────────────────────
@app.route('/api/ledger', methods=['POST'])
@login_required()
def api_save_ledger():
    # Block guest role from saving
    if session.get('user_role') == 'guest':
        return jsonify({'error': 'guest_mode'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON data provided.'}), 400

    date           = str(data.get('date', '')).strip()
    factory_status = str(data.get('factory_status', 'Open')).strip()

    if not date:
        return jsonify({'error': 'Date is required.'}), 400
    if factory_status not in ('Open', 'Closed'):
        return jsonify({'error': 'Factory status must be Open or Closed.'}), 400

    def safe_int(v):
        try: return max(0, int(float(v)))
        except: return 0

    def safe_float(v):
        try: return max(0.0, float(v))
        except: return 0.0

    total_produced  = safe_int(data.get('total_produced'))
    bags_in_storage = safe_int(data.get('bags_in_storage'))
    truck_sent_out  = safe_int(data.get('truck_sent_out'))
    truck_sold      = safe_int(data.get('truck_sold'))
    leakages        = safe_int(data.get('leakages'))
    aboboya_sold    = safe_int(data.get('aboboya_sold'))
    factory_sold    = safe_int(data.get('factory_sold'))
    price_per_bag   = safe_float(data.get('price_per_bag', 6.0))
    total_amount    = (truck_sold + aboboya_sold + factory_sold) * price_per_bag
    fuel_expenses   = safe_float(data.get('fuel_expenses'))
    other_expenses  = safe_float(data.get('other_expenses'))
    cash_withdrawn  = safe_float(data.get('cash_withdrawn'))
    cash_at_hand    = safe_float(data.get('cash_at_hand'))
    cash_at_bank    = safe_float(data.get('cash_at_bank'))
    comments        = str(data.get('comments', ''))[:500]
    workers_name    = session.get('user_name', 'Unknown')

    conn = get_db_connection()
    try:
        existing = conn.execute('SELECT id FROM ledger WHERE date = ?', (date,)).fetchone()
        if existing:
            conn.execute('''
                UPDATE ledger SET
                    factory_status=?, total_produced=?, bags_in_storage=?,
                    truck_sent_out=?, truck_sold=?, leakages=?,
                    aboboya_sold=?, factory_sold=?, price_per_bag=?,
                    total_amount=?, fuel_expenses=?, other_expenses=?,
                    cash_withdrawn=?, cash_at_hand=?, cash_at_bank=?,
                    comments=?, workers_name=?
                WHERE date=?
            ''', (factory_status, total_produced, bags_in_storage,
                  truck_sent_out, truck_sold, leakages,
                  aboboya_sold, factory_sold, price_per_bag,
                  total_amount, fuel_expenses, other_expenses,
                  cash_withdrawn, cash_at_hand, cash_at_bank,
                  comments, workers_name, date))
            conn.commit()
            return jsonify({'success': f'Record for {date} updated successfully.'})
        else:
            conn.execute('''
                INSERT INTO ledger (
                    date, factory_status, total_produced, bags_in_storage,
                    truck_sent_out, truck_sold, leakages, aboboya_sold,
                    factory_sold, price_per_bag, total_amount, fuel_expenses,
                    other_expenses, cash_withdrawn, cash_at_hand, cash_at_bank,
                    comments, workers_name
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (date, factory_status, total_produced, bags_in_storage,
                  truck_sent_out, truck_sold, leakages, aboboya_sold,
                  factory_sold, price_per_bag, total_amount, fuel_expenses,
                  other_expenses, cash_withdrawn, cash_at_hand, cash_at_bank,
                  comments, workers_name))
            conn.commit()
            return jsonify({'success': f'Record for {date} saved successfully.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  API: Admin — Employee Management
# ─────────────────────────────────────────────
@app.route('/api/admin/employees', methods=['GET', 'POST'])
@login_required(role='admin')
def api_admin_employees():
    conn = get_db_connection()

    if request.method == 'GET':
        users = conn.execute(
            'SELECT id, email, name, role FROM users ORDER BY role, name'
        ).fetchall()
        conn.close()
        return jsonify([dict(u) for u in users])

    data     = request.get_json(silent=True)
    if not data:
        conn.close()
        return jsonify({'error': 'No data provided.'}), 400

    email    = str(data.get('email', '')).strip().lower()
    name     = str(data.get('name',  '')).strip()
    password = str(data.get('password', ''))

    if not email or not name or not password:
        conn.close()
        return jsonify({'error': 'Name, email and password are all required.'}), 400
    if len(password) < 6:
        conn.close()
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400

    role = get_role_for_email(email)

    try:
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        conn.execute(
            'INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)',
            (email, name, password_hash, role)
        )
        conn.commit()
        return jsonify({'success': f'Account for "{name}" created successfully.'})
    except Exception as e:
        conn.rollback()
        if dbmod.is_integrity_error(e):
            return jsonify({'error': 'That email is already registered.'}), 400
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/api/admin/employees/<int:emp_id>', methods=['DELETE'])
@login_required(role='admin')
def api_delete_employee(emp_id):
    if emp_id == session.get('user_id'):
        return jsonify({'error': 'You cannot delete your own account.'}), 400
    conn = get_db_connection()
    try:
        result = conn.execute("DELETE FROM users WHERE id = ? AND role = 'employee'", (emp_id,))
        conn.commit()
        if result.rowcount == 0:
            return jsonify({'error': 'Employee not found.'}), 404
        return jsonify({'success': 'Employee removed successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  API: Admin — Ledger
# ─────────────────────────────────────────────
@app.route('/api/admin/ledger', methods=['GET'])
@login_required(role='admin')
def api_admin_ledger():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM ledger ORDER BY date DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/admin/db-diagnostics', methods=['GET'])
@login_required(role='admin')
def api_db_diagnostics():
    """Read-only sanity check: which DB engine/file is actually being used
    right now, and how many rows each core table has. Handy for confirming
    the app is attached to the database you expect, without SSH access."""
    conn = get_db_connection()
    info = {'engine': conn.engine}
    if conn.engine == 'sqlite':
        info['sqlite_path'] = dbmod._resolve_sqlite_path()
        info['file_exists'] = os.path.isfile(info['sqlite_path'])
    try:
        info['users_count'] = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    except Exception as e:
        info['users_count_error'] = str(e)
    try:
        info['ledger_count'] = conn.execute('SELECT COUNT(*) AS c FROM ledger').fetchone()['c']
    except Exception as e:
        info['ledger_count_error'] = str(e)
    conn.close()
    return jsonify(info)


@app.route('/api/admin/ledger/<int:entry_id>', methods=['DELETE'])
@login_required(role='admin')
def api_delete_ledger(entry_id):
    conn = get_db_connection()
    try:
        result = conn.execute('DELETE FROM ledger WHERE id = ?', (entry_id,))
        conn.commit()
        if result.rowcount == 0:
            return jsonify({'error': 'Entry not found.'}), 404
        return jsonify({'success': 'Ledger entry deleted.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Error Handlers
# ─────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    if request.is_json:
        return jsonify({'error': 'Not found.'}), 404
    return redirect(url_for('login_page'))


@app.errorhandler(403)
def forbidden(e):
    if request.is_json:
        return jsonify({'error': 'Forbidden.'}), 403
    return render_template('403.html'), 403


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error.'}), 500


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=not IS_PRODUCTION)
