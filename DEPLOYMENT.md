# GradePulse — Deployment Runbook

Audience: Anyone deploying or operating GradePulse in production.
Last updated: 2026-09-27 (Phase 3 — production deploy)

---

## Overview

Two services run together:

| Service | Tech | Container port | Host port |
|---|---|---|---|
| API (backend engine) | FastAPI + uvicorn | 8000 | `${PORT:-8000}` |
| Web (Next.js SPA) | Node 20 | 3000 | `${WEB_PORT:-3000}` |

The browser talks to the web app, which **server-side proxies** `/api/*` to the API container; the API host is never exposed to browsers. Both persist data in the `gradepulse-data` Docker volume at `/data`:

- `brain_state.json` — the model (LinUCB parameters, students, sessions)
- `class_config.json` — school/class registry
- `gradepulse_users.db` — accounts (SQLite, WAL mode)
- `backups/` — automated backups (all three of the above)

---

## Prerequisites

- Linux VPS (Ubuntu 22.04+ recommended, 2 GB+ RAM, 20 GB+ disk)
- Docker + Docker Compose (plugin) installed
- A domain (or two) pointed at the VPS for HTTPS
- SSH access to the VPS

---

## 1. First-Time Deployment

### 1.1 Prepare the VPS

```bash
ssh root@your-server-ip

# Install Docker + Compose plugin
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin
systemctl enable --now docker

# Create a deploy user (recommended)
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
su - deploy
```

### 1.2 Clone and configure

```bash
git clone https://github.com/divinenwobodo19-creator/GradePulse.git gradepulse
cd gradepulse

cp .env.example .env
nano .env   # must-haves below
```

Set in `.env`:

```dotenv
GRADEPULPE_ENV=production
JWT_SECRET=<generate below>
FRONTEND_URL=https://your-web-domain.com
WEB_CONCURRENCY=1
LOG_LEVEL=info
```

Generate a strong JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

> **Fail-fast guarantee:** the API refuses to boot in production unless `JWT_SECRET` is a non-placeholder value ≥ 32 chars. Never use the example secret.

### 1.3 Start the services

```bash
docker compose up -d --build
docker compose ps            # both should be Up (healthy)
curl http://localhost:8000/health
```

`/health` should return `{"status":"alive","engine":"GradePulse", ...}`. The web app is at `http://<vps-ip>:3000`.

### 1.4 HTTPS

Use Nginx as a reverse proxy; certbot issues Let's Encrypt certs.

```bash
apt install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/gradepulse`:

```nginx
# HTTP → HTTPS
server {
    listen 80;
    server_name api.yourdomain.com web.yourdomain.com;
    return 301 https://$host$request_uri;
}

# API
server {
    listen 443 ssl;
    server_name api.yourdomain.com;
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Web (Next.js)
server {
    listen 443 ssl;
    server_name web.yourdomain.com;
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/gradepulse /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d api.yourdomain.com -d web.yourdomain.com
```

### 1.5 Firewall

```bash
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP redirect
ufw allow 443/tcp   # HTTPS
ufw enable
```

---

## 2. Daily Operations

```bash
docker compose ps
curl -s http://localhost:8000/health | python3 -m json.tool
docker compose logs -f api
docker compose logs --tail=100 web
docker compose restart api
```

The API container restarts automatically on crash/reboot (`restart: unless-stopped`).

---

## 3. Backups

### What gets backed up

Automatically (every 6 hours, keeps the last 24): `brain_state.json`, `class_config.json`, **and `gradepulse_users.db`** (+ its SQLite WAL sidecars). Stored in the volume at `/data/backups/`.

### Manual backup via API

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -X POST http://localhost:8000/backup -H "Authorization: Bearer $TOKEN"     # create
curl http://localhost:8000/backups -H "Authorization: Bearer $TOKEN"           # list
```

### Backup from the host

```bash
docker cp $(docker compose ps -q api):/data/backups ./local-backups
```

### Restore

> **Maintenance window required.** Restore overwrites the live model + registry + user DB. Stop writes first, restore, then restart.

```bash
curl -X POST "http://localhost:8000/backup/restore?backup_path=/data/backups/20260927_100000_123456" \
  -H "Authorization: Bearer $TOKEN"
docker compose restart api
```

For a full-volume restore from a host copy:

```bash
docker compose down
# replace the three files under the volume, e.g. via a temp container:
docker run --rm -v gradepulse-data:/data -v $PWD/local-backups:/in alpine \
  sh -c "cp /in/*/ /data/ 2>/dev/null; ls /data"
docker compose up -d
```

---

## 4. Upgrades

```bash
cd ~/gradepulse
git pull origin main
docker compose up -d --build api
docker compose up -d --build web      # when the frontend changed
curl -s http://localhost:8000/health
```

Data persists in `gradepulse-data` across rebuilds. **Rollback** to a previous release:

```bash
git log --oneline -5                  # find the last good commit/tag
git checkout <release-tag>            # e.g. v0.2.0
docker compose up -d --build
```

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Container exits immediately | Check `docker compose logs api` — in `GRADEPULPE_ENV=production` a weak/missing `JWT_SECRET` aborts deliberately at boot. |
| Port 8000 busy | `lsof -i :8000` and kill, or change `PORT` in `.env`. |
| API recovers with empty model | Fresh deployment seeds demo data when `brain_state.json` is absent. Restore from `/data/backups/` if needed. |
| Web can't reach the API | `API_URL=http://api:8000` is set in `docker-compose.yml`; only override via the `API_URL` build ARG/env. Browsers must call `/api/*` same-origin. |
| Out of disk | `docker system prune -a`, `docker volume prune` (never the `gradepulse-data` volume), trim `/data/backups/`. |
| 429 Too Many Requests | Signup/login rate limit (30/min per address, 120/min per host) — legitimate users just wait. |
| 403 on cross-school ops | School-ownership scoping (Phase 2): the caller's token isn't attached to that student/school. Re-login if the token predates the Phase 2 deploy. |

---

## 6. Monitoring (manual until a stack is wired up)

```bash
curl -s http://localhost:8000/health
docker compose exec api ls -lh /data/brain_state.json
docker compose exec api ls /data/backups/ | wc -l
df -h && docker system df
docker stats --no-stream
```

---

## 7. Emergency Procedures

### Data loss
1. List backups: `docker compose exec api ls /data/backups/`
2. Restore via Section 3 (API or volume copy).
3. If nothing survived, the engine re-seeds demo data; learned parameters are lost.

### Compromise
1. `docker compose down`
2. Snapshot the volume: `docker run --rm -v gradepulse-data:/data -v $PWD:/out alpine sh -c "cp -r /data /out/forensic-$(date +%s)"`
3. Rotate `JWT_SECRET` in `.env`.
4. Re-deploy from a clean clone on a fresh VPS; restore the latest backup; then rotate the secret again.

### Memory pressure
`docker stats --no-stream`, `free -h`. Drop `WEB_CONCURRENCY` to 1 (default) or shrink the model. Upgrade RAM if `brain_state.json` growth (more schools/students/sessions) is sustained.