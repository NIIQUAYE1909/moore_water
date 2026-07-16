# Hosting Guide: Moor Water Flask App

Your application is **ready for hosting** on PythonAnywhere, Render, Railway, a plain VPS, or Vercel. It has a WSGI entry point (`wsgi.py`), a production WSGI server package (`gunicorn` in `requirements.txt`), automatic database initialization on startup (`db.py`), and supports SQLite, MySQL/TiDB, and PostgreSQL out of the box via environment variables.

---

## 0. What changed in this audit

- **SQLite path bug fixed** — an earlier revision of `db.py` guessed a PythonAnywhere path using the wrong filename (`moore_water.db`) and silently created a brand-new, empty database instead of attaching to your real `database.db`. `db.py` now always resolves the SQLite file to `database.db` sitting right next to `app.py`/`db.py` (i.e. your project root — `/home/<username>/<project>/database.db` on PythonAnywhere), unless you explicitly override it with `DB_PATH`. Both ledger submission (`/api/ledger`) and querying (`/api/admin/ledger`) go through the same `get_db_connection()`, so they always hit the same file. On startup, the server log prints exactly which file it opened and whether it found existing data, so you can confirm it's attached correctly.

- **Mobile scroll-lock fixed** — the login and register cards can no longer get trapped above the fold on short/mobile viewports; the page now always scrolls.
- **Mobile admin header overlap fixed** — the session badge ("Admin: Name" / online status) no longer floats on top of the "Admin Portal" title and "Restricted Access" pill on small screens. Below 768px they stack as clean, full-width strips above the header instead of overlapping it.
- **New Power BI–style admin dashboard** — a dedicated Dashboard tab with enhanced stat cards and two Chart.js visualizations (production/revenue trend, sales-channel distribution). The heavy raw ledger table now lives under a **Historical Records** tab, tucked inside a collapsible accordion, with a live search box and status filter.
- **Multi-database support** — `db.py` is a new shared module that transparently targets **PostgreSQL** (`DATABASE_URL`), **MySQL/TiDB** (`DB_HOST`), or **SQLite** (fallback), with automatic table creation + seeding on every app startup. This replaces the app's previous SQLite-only connection logic.
- **`app` object confirmed exposed** at module level in `app.py` (`app = Flask(__name__)`), so `gunicorn wsgi:app` / `app:app` both work unchanged.
- **Small SQL bug fixed**: a query used double-quoted `"employee"` as a string literal, which SQLite and MySQL tolerate but PostgreSQL treats as an identifier and rejects. Now uses standard single quotes everywhere.
- **`vercel.json`** sample added for serverless deployment.

All existing Flask routes, business logic, and ledger/employee behavior are unchanged.

---

## 1. Important Production Preparations

Before hosting your application online, configure these environment variables:

| Variable | Description | Recommended Value |
| :--- | :--- | :--- |
| `SECRET_KEY` | Signs session cookies. | A long, random alphanumeric string. |
| `FLASK_ENV` | Sets the Flask environment. | `production` (enables security headers and HTTPS session cookies) |
| `ADMIN_EMAIL_2` | A secondary admin email (in addition to `quayen010@gmail.com`). | An email address you own. |

### Whitelisting Admins
- The email `quayen010@gmail.com` is the hardcoded primary admin, defined once in `db.py` (`get_admin_emails()`), and shared by both `app.py` and `init_db.py`.
- Add a second admin via the `ADMIN_EMAIL_2` environment variable.
- To change the primary admin, edit `db.py`.

---

## 2. Choosing a Database for Hosting

`db.py` resolves your database backend automatically, in this order:

1. **`DATABASE_URL` set → PostgreSQL** (recommended for Render and required for Vercel)
2. **`DB_HOST` set → MySQL / TiDB Serverless**
3. **Neither set → SQLite** (recommended for PythonAnywhere or a VPS)

### Option A: SQLite (Default — PythonAnywhere / VPS)
- Zero setup. Tables are created and default users seeded automatically on first request.
- **File-based** — if your host wipes the filesystem on redeploy (Render/Railway free web services, and *always* on Vercel), your data resets. Only use SQLite where the filesystem is persistent:
  - PythonAnywhere (persistent by default)
  - A VPS
  - Render/Railway **with a persistent Disk/Volume attached**
- On PythonAnywhere, `db.py` automatically looks for `~/moore_water/moore_water.db` if that folder exists; otherwise set `DB_PATH` explicitly to override.

### Option B: MySQL / TiDB Serverless
Set: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` (e.g. `4000` for TiDB), optionally `DB_SSL_CA`.

### Option C: PostgreSQL (Recommended for Render & required for Vercel)
Set `DATABASE_URL` to a full connection string, e.g.:
```
postgres://user:password@host:5432/dbname
```
Render, Railway, Neon, and Supabase all provide this out of the box when you provision a Postgres database — just copy their connection string into `DATABASE_URL`.

---

## 3. Deployment Options

### Option 1: PythonAnywhere
1. Upload your project (or `git clone` it) to `/home/<your-username>/moore_water`.
2. Open a Bash console and create a virtualenv:
   ```bash
   cd ~/moore_water
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Go to the **Web** tab → **Add a new web app** → **Manual configuration** (Flask, matching Python version).
4. Set the **Working directory** and **virtualenv path** to your project folder.
5. Edit the generated WSGI file (`/var/www/<username>_pythonanywhere_com_wsgi.py`) so it imports your app:
   ```python
   import sys
   path = '/home/<your-username>/moore_water'
   if path not in sys.path:
       sys.path.insert(0, path)
   from wsgi import app as application
   ```
6. In the **Web** tab, add environment variables under **Environment variables** (or set them in the WSGI file before the import): `SECRET_KEY`, `FLASK_ENV=production`, `ADMIN_EMAIL_2`.
7. Click **Reload**. `db.py` will auto-create `~/moore_water/moore_water.db` and seed default users on first request.

### Option 2: Render (Easiest, container-based)
1. **Push your code to GitHub** and create a Web Service on [Render](https://render.com/) connected to your repo.
2. **Configure the Service**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
3. **Set Environment Variables**: `FLASK_ENV=production`, `SECRET_KEY=<random>`, `ADMIN_EMAIL_2=<email>`.
4. **Database** — pick one:
   - **Postgres (recommended)**: Render → **New +** → **PostgreSQL**, then copy the **Internal Database URL** into `DATABASE_URL` on your web service.
   - **SQLite + Disk**: Add a Disk mounted at `/data`, set `DB_PATH=/data/database.db`.
5. Click **Create Web Service**.

### Option 3: Railway
1. Push to GitHub, then **New Project → Deploy from GitHub repo** on [Railway.app](https://railway.app/).
2. Add variables: `FLASK_ENV=production`, `SECRET_KEY=<random>`.
3. **Database** — pick one:
   - **Postgres (recommended)**: **New → Database → Add PostgreSQL**, then **Reference Variable** its connection string into `DATABASE_URL` on your service.
   - **MySQL**: **New → Database → Add MySQL**, then reference `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`/`DB_PORT`.
   - **SQLite + Volume**: **Settings → Volumes → Add Volume** mounted at `/data`, set `DB_PATH=/data/database.db`.

### Option 4: Vercel (Serverless)
Vercel's filesystem is ephemeral and functions are stateless between invocations, so **`DATABASE_URL` (PostgreSQL) is required** — SQLite will not persist data here.

1. Provision a Postgres database (Vercel Postgres, Neon, or Supabase all work) and copy its connection string.
2. In your Vercel project settings, set `DATABASE_URL`, `SECRET_KEY`, `FLASK_ENV=production`.
3. A starter `vercel.json` is included in this project. Vercel's Python runtime configuration changes fairly often — check [Vercel's current Python docs](https://vercel.com/docs) before deploying, since the exact `builds`/`functions` syntax may need adjusting for the Vercel CLI version you're using.
4. Deploy with `vercel --prod` or via the Vercel dashboard's Git integration.

### Option 5: VPS Self-Hosting (DigitalOcean / Linode / AWS EC2)
Use Nginx + Gunicorn + Systemd, same as before:
```bash
sudo apt update && sudo apt install python3-pip python3-venv git nginx -y
cd /var/www && git clone <your-repo-url> moore_water && cd moore_water
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 wsgi:app   # test run
```
Then create a systemd service (`/etc/systemd/system/moore_water.service`) running
`gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app`, enable it, and put Nginx in front with a reverse proxy + Let's Encrypt SSL, exactly as in a standard Flask+Gunicorn+Nginx setup.

---

## 4. Post-Hosting Verification

1. **Initial Seed User Login**: `employee@moorwater.com` / `employee123`, or register a new account.
2. **Access Control**: Visit `/admin` while logged out — should redirect to login. Visit while logged in as a non-admin — should show a friendly 403 page.
3. **PWA Support**: In DevTools, confirm the Service Worker (`/sw.js`) registers and the app is installable.
4. **Admin Dashboard**: Log in as `quayen010@gmail.com` / `admin123`, confirm the Dashboard tab renders the two charts once you have ledger entries, and that Historical Records search/filter work.
5. **Mobile check**: Open `/login` and `/admin` on a narrow/short viewport (or DevTools device mode) — the login card should scroll into view, and the admin header should not overlap the session badge.
