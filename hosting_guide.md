# Hosting Guide: Moore Water Flask App

Your application is **ready for hosting**! It has a WSGI entry point (`wsgi.py`), a production WSGI server package (`gunicorn` in `requirements.txt`), automatic database initialization (`init_db.py`), and supports both SQLite and MySQL/TiDB out of the box via environment variables.

---

## 1. Important Production Preparations

Before hosting your application online, you need to configure these production settings to secure the application.

### Key Environment Variables to Set
| Variable | Description | Recommended Value |
| :--- | :--- | :--- |
| `SECRET_KEY` | Used to sign session cookies and prevent tampering. | A long, random alphanumeric string. |
| `FLASK_ENV` | Sets the Flask environment. | `production` (enables security headers and HTTPS session cookies) |
| `ADMIN_EMAIL_2` | A secondary admin email address (in addition to `quayen010@gmail.com`). | An email address you own. |
| `DB_PATH` | *(Optional)* Custom file path for the SQLite database. | Defaults to `database.db`. |

### Whitelisting Admins
- The email `quayen010@gmail.com` is currently hardcoded as the primary admin in [app.py](file:///c:/Users/HP/Desktop/MOORE_WATER/app.py#L48-L51) and [init_db.py](file:///c:/Users/HP/Desktop/MOORE_WATER/init_db.py#L9-L13).
- To add a second admin, set the `ADMIN_EMAIL_2` environment variable.
- To change the primary admin, modify the email directly in those files.

---

## 2. Choosing a Database for Hosting

Your app is database-agnostic and supports two setups:

### Option A: SQLite (Default)
- **Pros**: Zero setup. The app automatically creates `database.db` and seeds default users.
- **Cons**: File-based. If your host deletes/rebuilds files on deployment (like Render or Heroku standard tiers), your database resets daily unless you configure a **Persistent Volume / Disk**.
- **Best For**: Direct VPS hosting, or hosting services with persistent disks (e.g., Render Web Service with a Disk, Railway with a volume).

### Option B: Cloud MySQL / TiDB Serverless (Recommended for Production)
- **Pros**: Persistent, scalable, does not lose data on server restarts. TiDB Serverless has an excellent free tier.
- **Cons**: Requires setting up a database server or account.
- **Setup**: Provide the following environment variables, and the app will automatically switch from SQLite to MySQL:
  - `DB_HOST` (e.g., `gateway01.us-east-1.prod.aws.tidbcloud.com`)
  - `DB_USER` (e.g., `xxxxxx.root`)
  - `DB_PASSWORD` (Your database password)
  - `DB_NAME` (e.g., `moore_water`)
  - `DB_PORT` (e.g., `4000` for TiDB)
  - `DB_SSL_CA` (Optional path to SSL Certificate, if required by the cloud DB)

---

## 3. Deployment Options

Here are step-by-step guides for the three best ways to host this app yourself.

### Option 1: Render (Easiest and Highly Recommended)
Render connects directly to your GitHub repository and automatically deploys whenever you push changes.

#### Steps:
1. **Push your code to GitHub**:
   - Create a private GitHub repository.
   - Run the following in your local terminal:
     ```bash
     git remote add origin <your-github-repo-url>
     git branch -M main
     git push -u origin main
     ```
2. **Create a Web Service on Render**:
   - Sign up at [Render](https://render.com/).
   - Click **New +** > **Web Service**.
   - Connect your GitHub account and select your `MOORE_WATER` repository.
3. **Configure the Service**:
   - **Name**: `moore-water-ledger`
   - **Region**: Select closest to your users.
   - **Language**: `Python 3` (Render will auto-detect Python).
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
   - **Instance Type**: `Free` (or any tier).
4. **Set Up Environment Variables**:
   - In the **Environment** tab, click **Add Environment Variable** and add:
     - `FLASK_ENV` = `production`
     - `SECRET_KEY` = `generate-a-secure-random-key-here`
     - `ADMIN_EMAIL_2` = `your-email@example.com`
5. **(Crucial if using SQLite)** **Add a Persistent Disk**:
   - Standard free instances on Render reset daily. To keep SQLite data:
   - Go to the **Advanced** or **Disks** section in Render.
   - Click **Add Disk**.
   - **Name**: `moore-water-db`
   - **Mount Path**: `/data`
   - **Size**: `1 GB` (Plenty for SQLite ledger).
   - Go back to **Environment Variables** and set `DB_PATH` = `/data/database.db`.
6. **Deploy**:
   - Click **Create Web Service**. Render will build and launch your application!

---

### Option 2: Railway (Extremely Fast setup)
Railway is another excellent PaaS that easily handles persistent volumes and lets you provision a MySQL database with one click.

#### Steps:
1. Push your code to GitHub.
2. Sign up at [Railway.app](https://railway.app/).
3. Click **New Project** > **Deploy from GitHub repo** and select your repository.
4. Click **Variables** on the service and add:
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = `generate-a-secure-random-key-here`
5. **If using SQLite (Persistent Volume)**:
   - Go to **Settings** > **Volumes** > **Add Volume**.
   - Mount it at `/data`.
   - Set environment variable `DB_PATH` = `/data/database.db`.
6. **If using MySQL/TiDB (Highly Recommended)**:
   - In the same project, click **New** > **Database** > **Add MySQL**.
   - Railway will provision a MySQL database.
   - Go to your Flask service's **Variables** tab, click **Reference Variable**, and link the MySQL connection credentials directly to the environment variables your app expects (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT`).

---

### Option 3: VPS Self-Hosting (DigitalOcean / Linode / AWS EC2)
If you want complete control, you can host on a Linux VPS (Ubuntu server) using **Nginx**, **Gunicorn**, and **Systemd**.

#### Steps:
1. **SSH into your VPS**:
   ```bash
   ssh root@your_server_ip
   ```
2. **Update system & install dependencies**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install python3-pip python3-venv git nginx -y
   ```
3. **Clone the repository**:
   ```bash
   cd /var/www
   git clone <your-github-repo-url> moore_water
   cd moore_water
   ```
4. **Set up virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Test running with Gunicorn**:
   ```bash
   gunicorn --bind 0.0.0.0:8000 wsgi:app
   ```
   *Press Ctrl+C to stop.*

6. **Create a Systemd Service File**:
   This runs Gunicorn in the background and restarts it if the server reboots.
   ```bash
   sudo nano /etc/systemd/system/moore_water.service
   ```
   Paste the following:
   ```ini
   [Unit]
   Description=Gunicorn instance to serve Moore Water Flask app
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/moore_water
   Environment="PATH=/var/www/moore_water/venv/bin"
   Environment="FLASK_ENV=production"
   Environment="SECRET_KEY=your_secure_random_key_here"
   Environment="ADMIN_EMAIL_2=your-email@example.com"
   ExecStart=/var/www/moore_water/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app

   [Install]
   WantedBy=multi-user.target
   ```
   *Save and exit (Ctrl+O, Enter, Ctrl+X).*

7. **Start and enable the systemd service**:
   ```bash
   sudo systemctl start moore_water
   sudo systemctl enable moore_water
   ```

8. **Configure Nginx as a Reverse Proxy**:
   Nginx will handle SSL, serve static files, and forward web traffic to Gunicorn.
   ```bash
   sudo nano /etc/nginx/sites-available/moore_water
   ```
   Paste the following (replace `yourdomain.com` with your actual domain or IP address):
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com www.yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static {
           alias /var/www/moore_water/static;
       }
   }
   ```
   Enable the site and restart Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/moore_water /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

9. **Secure with HTTPS (SSL)** using free Let's Encrypt certificates:
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```
   Follow the prompts to enable auto-redirection to HTTPS.

---

## 4. Post-Hosting Verification

Once hosted, navigate to your URL and verify the following:
1. **Initial Seed User Login**: Use `employee@moorwater.com` with password `employee123` to log in, or register a new account.
2. **Access Control**: Go to `/admin` and confirm it redirects you or shows a `403 Forbidden` if you are not logged in as the admin (`quayen010@gmail.com` or `ADMIN_EMAIL_2`).
3. **PWA Support**: Inspect page in browser, open developer tools, and verify the Service Worker loads successfully (`sw.js`) and the app is installable.
