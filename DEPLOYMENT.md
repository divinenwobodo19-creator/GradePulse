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

- `brain_state.json` — the recommendation engine's state (model parameters, content, engine sessions)
- `class_config.json` — legacy school/class registry. No longer written; if present it is copied into `gradepulse_users.db` on first start
- `gradepulse_users.db` — accounts, invites, schools, classes, students and scores (SQLite, WAL mode). This is the file that matters most
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
GRADEPULSE_ENV=production
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
        proxy_set_header X-Forwarded-For $remote_addr;
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
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/gradepulse /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d api.yourdomain.com -d web.yourdomain.com
```

**Sign-in rate limits behind nginx.** The limits count attempts per visitor address. Behind a proxy every request looks like it comes from the proxy, so by default all visitors share one allowance. The web app's `/api` proxy does not add the visitor's address itself; it passes on whatever `X-Forwarded-For` it receives, which a visitor can set. The nginx config above *overwrites* that header with the real address (`$remote_addr`). Once that is in place **and** ports 3000 and 8000 are not reachable from outside except through nginx (firewall them, or publish them on `127.0.0.1` only), set `TRUST_FORWARDED_FOR=true` in `.env`. Leave it `false` otherwise.

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

The backup endpoints act on every school's data, so they take the deployment's **operator key** (`OPERATOR_KEY` in `.env`), not a school login. With `OPERATOR_KEY` unset they return 403 for everyone; scheduled backups still run.

```bash
OPERATOR_KEY=...   # the value from .env

curl -X POST http://localhost:8000/backup -H "X-Operator-Key: $OPERATOR_KEY"     # create
curl http://localhost:8000/backups -H "X-Operator-Key: $OPERATOR_KEY"           # list
```

### Taking payments (Paystack)

Schools pay per student, per term, from the Billing page (admins only). To switch it on:

1. In the Paystack dashboard, copy your **secret key** (Settings → API Keys & Webhooks). Start with the `sk_test_...` key.
2. In `.env`, set `PAYSTACK_SECRET_KEY`, `PRICE_PER_STUDENT_NAIRA` (whole naira) and, if a term is not 120 days, `TERM_DAYS`. `FREE_STUDENTS` (default 40) and `GRACE_DAYS` (default 14) set the free plan and the renewal grace period. Make sure `FRONTEND_URL` is the public web address; Paystack sends the admin back to `FRONTEND_URL/billing` after paying.
3. In the same Paystack page, set the **webhook URL** to `https://api.yourdomain.com/billing/webhook`. Paystack signs each call with the secret key, and GradePulse rejects unsigned or forged ones. The webhook records a payment even if the admin closes the tab before returning.
4. `docker compose up -d` to apply. Pay a test term with one of Paystack's test cards, then check the Billing page shows it.
5. When ready, swap in the `sk_live_...` key.

Plans: a school that has not paid is on the **free plan**, up to `FREE_STUDENTS` (default 40) students with everything except printable reports. A paid term covers the students paid for (never fewer than the free plan), reports and parent progress sheets included; paying for extra students during a term tops it up until the term ends. When a term ends the school keeps its paid plan for `GRACE_DAYS` (default 14), then falls back to the free plan. Nothing is deleted and the data always stays visible; the free plan only holds back adding students past the limit, entering scores while over it, and the reports. The admin sees a reminder bar when a term has ended, when the school has more students than it paid for, or when a free school reaches its limit. Without the Paystack settings nothing is limited.

### A locked-out school admin

Teachers get reset links from their school admin in Settings. If the admin themselves is locked out, issue a code with the operator key and send them the link:

```bash
curl -X POST http://localhost:8000/auth/operator-reset \
  -H "X-Operator-Key: $OPERATOR_KEY" -H "Content-Type: application/json" \
  -d '{"email":"admin@school.ng"}'
# -> {"code":"...","expires_at":"..."}   link: https://<your-site>/reset-password?code=<code>
```

### Backup from the host

```bash
docker cp $(docker compose ps -q api):/data/backups ./local-backups
```

### Restore

> **Maintenance window required.** Restore overwrites the live model + registry + user DB. Stop writes first, restore, then restart.

```bash
curl -X POST "http://localhost:8000/backup/restore?backup_path=/data/backups/20260927_100000_123456" \
  -H "X-Operator-Key: $OPERATOR_KEY"
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
| Container exits immediately | Check `docker compose logs api` — in `GRADEPULSE_ENV=production` a weak/missing `JWT_SECRET` aborts deliberately at boot. |
| Port 8000 busy | `lsof -i :8000` and kill, or change `PORT` in `.env`. |
| API recovers with empty model | A deployment starts with an empty engine when `brain_state.json` is absent (students and scores are in `gradepulse_users.db`, not in that file). Restore from `/data/backups/` if needed. |
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
3. If nothing survived, the engine starts empty; learned parameters are lost. Students and scores are unaffected as long as `gradepulse_users.db` survived.

### Compromise
1. `docker compose down`
2. Snapshot the volume: `docker run --rm -v gradepulse-data:/data -v $PWD:/out alpine sh -c "cp -r /data /out/forensic-$(date +%s)"`
3. Rotate `JWT_SECRET` in `.env`.
4. Re-deploy from a clean clone on a fresh VPS; restore the latest backup; then rotate the secret again.

### Memory pressure
`docker stats --no-stream`, `free -h`. Drop `WEB_CONCURRENCY` to 1 (default) or shrink the model. Upgrade RAM if `brain_state.json` growth (more schools/students/sessions) is sustained.