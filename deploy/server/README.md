# Free server: Oracle Cloud "Always Free" + DuckDNS + Caddy

GradePulse keeps its data in SQLite files, so it needs a server with a disk that
survives restarts. Oracle Cloud's Always Free tier gives a real virtual machine
with persistent storage at no cost, which free "app hosting" tiers (Render,
Koyeb and similar) do not. A free DuckDNS name gives it an address, and Caddy
gets the HTTPS certificate automatically.

Oracle has changed the free allowance before (in 2026 it went from 4 to 2 Arm
CPUs and from 24 to 12 GB of memory). The setup below needs far less than that.

## 1. Create the Oracle Cloud account (you)

1. Sign up at https://signup.cloud.oracle.com. A card is required to verify you;
   Always Free resources are not charged.
2. **Home region:** pick one close to Nigeria if offered, for example
   *South Africa Central (Johannesburg)*. It cannot be changed later.

## 2. Create the server (you)

In the Oracle console: **Compute → Instances → Create instance**.

| Setting | Choose |
|---|---|
| Image | Canonical **Ubuntu 24.04** |
| Shape | **Ampere → VM.Standard.A1.Flex**, 2 OCPUs, 12 GB memory (shows "Always Free-eligible") |
| Networking | Create a new VCN with a public subnet; **assign a public IPv4 address** |
| SSH keys | **Paste public key**, and paste the key shown below |
| Boot volume | Default (about 47 GB) is plenty |

Public key to paste (its private half stays on the GradePulse laptop at
`~/.ssh/gradepulse_server`):

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP/T2Uzs0XyJkD70hsk2f3QWxIY030q3vBK4pHrzGdHE gradepulse-deploy@jazzman-HP-Laptop-15-bs0xx
```

If Oracle says **"Out of capacity"** for the Ampere shape, try another
availability domain in the same form, or try again later. This is common.

After it starts, note the **public IP address**.

**Open the web ports:** Instance → Subnet → Security list → *Add ingress
rules*: source `0.0.0.0/0`, TCP, destination ports `80` and `443`.

## 3. Get a free address (you)

1. Sign in at https://www.duckdns.org (Google or GitHub login).
2. Add a sub-domain, for example `gradepulse` → `gradepulse.duckdns.org`.
3. Put the server's public IP in its box and press **update ip**.

## 4. Prepare and deploy (from the GradePulse laptop)

```bash
# once, to install Docker and open the server's own firewall
scp -i ~/.ssh/gradepulse_server deploy/server/setup-server.sh ubuntu@SERVER_IP:
ssh -i ~/.ssh/gradepulse_server ubuntu@SERVER_IP 'sudo bash setup-server.sh'

# every deploy
SERVER=ubuntu@SERVER_IP DOMAIN=gradepulse.duckdns.org ./deploy/server/deploy.sh
```

`deploy.sh` sends the committed code, writes the server's `.env` from the local
`.env` (JWT secret, operator key, Paystack key and price) with production
settings added, builds, starts, and waits until `https://DOMAIN/api/health`
answers. The first build takes several minutes.

## 5. After the first deploy

- Open `https://DOMAIN`, sign up: that account is the school's admin.
- **Paystack:** set the webhook URL to `https://DOMAIN/api/billing/webhook`
  (dashboard → Settings → API Keys & Webhooks).
- **Backups** run every 6 hours into the `gradepulse-data` volume. To take one
  now: `curl -X POST https://DOMAIN/api/backup -H "X-Operator-Key: $OPERATOR_KEY"`.
  Copy them off the server now and then:
  `ssh ... 'docker run --rm -v gradepulse_gradepulse-data:/d alpine tar -cz -C /d backups' > backups.tgz`.

## What runs on the server

| Container | Role |
|---|---|
| `caddy` | Only thing reachable from outside (80/443); HTTPS; forwards to `web` |
| `web` | The Next.js app; forwards `/api/*` to `api` on the private network |
| `api` | The FastAPI backend; data in the `gradepulse-data` volume |
