# GradePulse — Deployment Runbook

Audience: Anyone deploying or operating GradePulse in production.
Last updated: 2026-08-31

---

## Prerequisites

- A Linux VPS (Ubuntu 22.04+ recommended, 2GB+ RAM, 20GB+ disk)
- Docker and Docker Compose installed
- A domain name pointed at your VPS IP (for HTTPS)
- SSH access to the VPS

---

## 1. First-Time Deployment

### 1.1 Prepare the VPS

```bash
# SSH into your VPS
ssh root@your-server-ip

# Install Docker (if not already installed)
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Create a deploy user (optional but recommended)
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
su - deploy
```

### 1.2 Clone and Configure

```bash
git clone https://github.com/divinenwobodo19-creator/Contextual-Band-Algorithm.git gradepulse
cd gradepulse

# Create your .env from the template
cp .env.example .env

# Edit .env — set these at minimum:
#   JWT_SECRET=<generate a strong random secret>
#   BACKUP_ENABLED=true
#   LOG_LEVEL=INFO
nano .env
```

Generate a JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 1.3 Start the Services

```bash
docker compose up -d --build
```

This starts:
- **API** on port 8000 (FastAPI + brain engine)
- **Frontend** on port 3000 (Next.js)

Verify:
```bash
docker compose ps                    # both services should be "running"
curl http://localhost:8000/health     # should return JSON with status
```

### 1.4 Set Up HTTPS (Required for Production)

Install Nginx as a reverse proxy with Let's Encrypt SSL:

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Create the Nginx config:

```bash
nano /etc/nginx/sites-available/gradepulse
```

Paste:

```nginx
# HTTP → redirect to HTTPS
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$host$request_uri;
}

# API (backend)
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Create a second config for the frontend (or use a single server block with paths):

```bash
# Enable the site
ln -s /etc/nginx/sites-available/gradepulse /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Get SSL certificate
certbot --nginx -d api.yourdomain.com
```

Repeat for the frontend domain if deploying separately.

### 1.5 Update Firewall

```bash
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (redirect)
ufw allow 443/tcp   # HTTPS
ufw enable
```

---

## 2. Daily Operations

### Check Service Health

```bash
docker compose ps
curl -s http://localhost:8000/health | python3 -m json.tool
```

### View Logs

```bash
docker compose logs -f api          # follow API logs
docker compose logs --tail=100 web  # last 100 lines of frontend
docker compose logs --since=1h api  # logs from last hour
```

### Restart a Service

```bash
docker compose restart api          # restart API only
docker compose restart              # restart all
```

---

## 3. Backups

### What Gets Backed Up

The automated backup system saves:
- `brain_state.json` (model state — the learned parameters)
- `class_config.json` (school/class registry)

Backups are stored in the Docker volume at `/data/backups/` and also accessible via API.

### Automatic Backups

Enabled by default (`BACKUP_ENABLED=true`). Runs every 6 hours. Keeps last 24 backups.

### Manual Backup (via API)

```bash
# Get an auth token first
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create backup
curl -X POST http://localhost:8000/backup \
  -H "Authorization: Bearer $TOKEN"

# List backups
curl http://localhost:8000/backups \
  -H "Authorization: Bearer $TOKEN"
```

### Manual Backup (from host)

```bash
# Copy backup data out of the Docker volume
docker compose exec api ls /data/backups/
docker cp $(docker compose ps -q api):/data/backups ./local-backups
```

### Restore from Backup

```bash
# Via API
curl -X POST http://localhost:8000/backup/restore \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "/data/backups/20260831_120000_123456"}'

# Then restart to reload state
docker compose restart api
```

---

## 4. Upgrades

### Pull New Code

```bash
cd ~/gradepulse
git pull origin main
```

### Rebuild and Restart

```bash
docker compose up -d --build api    # rebuild only the API
docker compose up -d --build        # rebuild everything
```

The brain state persists in the `gradepulse-data` volume — it survives rebuilds.

### Verify

```bash
docker compose ps
curl -s http://localhost:8000/health | python3 -m json.tool
docker compose logs --tail=20 api
```

---

## 5. Troubleshooting

### API won't start

```bash
docker compose logs api | tail -30
```

Common causes:
- **Port 8000 already in use:** `lsof -i :8000` → kill the process, or change `PORT` in `.env`
- **Corrupt brain state:** Delete `brain_state.json` from the volume and restart (model re-initializes)
- **Missing .env:** Ensure `.env` exists in the project root

### Brain state is empty after restore

The model re-seeds demo data on startup if `brain_state.json` is empty. If you restored a backup but the state is still empty, check:
```bash
docker compose exec api cat /data/brain_state.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Students: {len(d.get(\"students\", {}))}')"
```

### Frontend can't reach the API

1. Check `NEXT_PUBLIC_API_URL` in `.env` — should be `http://localhost:8000` for Docker, or your public API URL
2. Check CORS: `FRONTEND_URL` in `.env` must match the frontend domain
3. If using Nginx, ensure the proxy pass is correct

### Container keeps restarting

```bash
docker compose ps                     # check restart count
docker compose logs --since=5m api    # check recent logs
docker compose exec api sh            # shell into the container
```

### Out of disk space

```bash
docker system prune -a                # remove unused images/containers
docker volume prune                   # remove unused volumes (NOT gradepulse-data)
docker compose exec api ls /data/backups/ | wc -l  # check backup count
```

---

## 6. Monitoring (Manual)

Until a proper monitoring stack is set up, use these manual checks:

```bash
# API responding?
curl -s http://localhost:8000/health

# Brain state size (grows with students/interactions)
docker compose exec api ls -lh /data/brain_state.json

# Backup count
docker compose exec api ls /data/backups/ | wc -l

# Disk usage
df -h
docker system df

# Container resource usage
docker stats --no-stream
```

---

## 7. Emergency Procedures

### Complete data loss (brain state gone)

1. Check backups: `docker compose exec api ls /data/backups/`
2. Restore the most recent: use the restore procedure in Section 3
3. If no backups exist: the model re-seeds demo data on startup. The learned parameters are lost, but the system recovers.

### Server compromised

1. `docker compose down` — stop everything immediately
2. Take a forensic snapshot of the volume
3. Rotate `JWT_SECRET` in `.env`
4. Re-deploy from a clean clone on a new VPS
5. Restore from the latest backup

### High memory usage

```bash
docker stats --no-stream              # check per-container memory
free -h                               # system memory
```

If the API is using too much memory, reduce `WEB_CONCURRENCY` in `.env` (default 2).
