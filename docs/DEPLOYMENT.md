# Deployment Guide — Job Radar

---

## Local Development (Primary Use Case)

### Prerequisites
- Python 3.11+ (`brew install python` on macOS)
- Node.js 20+ (`brew install node`)
- Anthropic API key

### Setup (one-time)

```bash
git clone <repo>
cd job-radar

# 1. Set API key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

# 2. Install dependencies
make install
```

### Daily usage

```bash
# Start web interface (both servers, hot reload)
make dev
# Browser: http://localhost:3000

# OR use the CLI as before (unchanged)
python src/main.py
```

### Stopping

`Ctrl+C` in the terminal running `make dev`. Both processes stop together.

---

## Demo Snapshot Behavior

The hosted demo is a static export, but it now includes application-tracker data in addition to board data.

Current behavior:
- `make demo-snapshot` exports tracker fields and tracker-aware stats from `data/demo.db` into `web/public/demo-data`
- the demo frontend serves `/api/applications`, `/api/applications/stats`, and `/api/jobs/{id}/timeline` from that snapshot
- “today” counters and relative dates are rebased from the latest demo dataset timestamp so the snapshot stays presentation-current

If you want mocked applications to persist across future snapshot rebuilds, seed them in `data/demo.db` before running `make demo-snapshot`. Manual edits to generated JSON files are overwritten the next time the snapshot is rebuilt.

---

## Local Production Mode

Single uvicorn process serves both the API and the Next.js static build. Useful for running as a background service.

```bash
# Build frontend (one-time, or after UI changes)
make build

# Start single server
make start
# Browser: http://localhost:8000
```

### Run as background service (macOS launchd)

Create `~/Library/LaunchAgents/com.jobradar.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jobradar</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/job-radar/.venv/bin/uvicorn</string>
        <string>api.main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/job-radar</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ANTHROPIC_API_KEY</key>
        <string>sk-ant-...</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/jobradar.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/jobradar.err</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.jobradar.plist
# Starts on boot, restarts on crash
# Logs: tail -f /tmp/jobradar.log
```

---

## Railway (Recommended for Online Deployment)

Railway detects Python automatically and supports persistent volumes for SQLite.

### Setup

1. Push code to GitHub (user data is gitignored — safe to push)
2. Create new Railway project → "Deploy from GitHub repo"
3. Add a persistent volume: Storage → Add Volume → mount at `/data`
4. Set environment variables:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   DATA_DIR=/data
   PROFILES_DIR=/profiles
   APP_PASSWORD=your-password   # enables basic auth on write endpoints
   ```

5. Create `railway.toml` in project root:

```toml
[build]
buildCommand = "pip install -r requirements.txt && cd web && npm install && npm run build"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
```

6. Deploy — Railway builds and starts automatically

### First-run setup

Since `profiles/` is gitignored, no profile exists on a fresh deploy. Open the app in a browser and the setup wizard will appear automatically. The guided flow uploads your CV, generates `profile_doc.md` and `search_config.yaml`, and saves the profile directly onto the persistent volume. No SSH or manual file upload is required.

After onboarding, the same deployment also supports Settings-driven guided edit:
- `Edit Saved Preferences` reuses persisted wizard state to regenerate the profile from saved structured inputs
- `Start Fresh` uploads a new CV and rebuilds the profile from the beginning

For those guided edit flows to work across deploys, keep the profile directory persistent because the app stores `cv_analysis.json` and `preferences.json` alongside the profile files.

### Cost
Railway free tier: $5/month credit (enough for this app). Paid: ~$5-10/month for a small instance + persistent volume.

---

## Fly.io (Alternative)

More control, generous free tier, first-class persistent volumes.

### Setup

```bash
# Install Fly CLI
brew install flyctl
flyctl auth login

# Initialize
cd job-radar
flyctl launch --no-deploy
# Choose: app name, region (closest to you), no Postgres
```

Create `fly.toml`:

```toml
app = "job-radar-yourname"
primary_region = "fra"  # Frankfurt for EU

[build]
  ignorefile = ".flyignore"

[env]
  PORT = "8080"
  DATA_DIR = "/data"
  PROFILES_DIR = "/profiles"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true

[[mounts]]
  source = "job_radar_data"
  destination = "/data"

[[mounts]]
  source = "job_radar_profiles"
  destination = "/profiles"
```

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install Node.js for building frontend
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build frontend
RUN cd web && npm install && npm run build

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
# Create volumes
flyctl volumes create job_radar_data --size 1 --region fra
flyctl volumes create job_radar_profiles --size 1 --region fra

# Set secrets
flyctl secrets set ANTHROPIC_API_KEY=sk-ant-...
flyctl secrets set APP_PASSWORD=your-password

# Deploy
flyctl deploy
```

---

## Self-Hosted VPS (Full Control)

Recommended for: cheap hosting, complete control, no vendor lock-in.

### Setup (Ubuntu 22.04)

```bash
# On server
sudo apt update
sudo apt install python3.12 python3.12-venv nodejs npm nginx -y

# Clone repo
git clone https://github.com/yourname/job-radar.git
cd job-radar

# Install deps and build
make install
make build

# Create systemd service
sudo nano /etc/systemd/system/jobradar.service
```

```ini
[Unit]
Description=Job Radar API
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/job-radar
Environment=ANTHROPIC_API_KEY=sk-ant-...
Environment=APP_PASSWORD=your-password
ExecStart=/home/youruser/job-radar/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable jobradar
sudo systemctl start jobradar
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name jobradar.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/jobradar.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jobradar.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name jobradar.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo certbot --nginx -d jobradar.yourdomain.com
sudo systemctl reload nginx
```

### Updates

```bash
cd job-radar
git pull
make build
sudo systemctl restart jobradar
```

---

## Authentication (for Online Deployment)

The Settings page exposes your CV summary and keyword configuration. When deployed online, protect it with HTTP Basic Auth.

Add to `api/main.py`:

```python
import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()
APP_PASSWORD = os.getenv("APP_PASSWORD")

def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if not APP_PASSWORD:
        return  # Auth disabled if APP_PASSWORD not set (local-only mode)
    correct_password = secrets.compare_digest(
        credentials.password.encode(),
        APP_PASSWORD.encode(),
    )
    if not correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )

# Apply to write endpoints only
@router.put("/profile/{name}/yaml", dependencies=[Depends(require_auth)])
def update_yaml(...):
    ...
```

Browser will show a native Basic Auth prompt. For a single-user tool, this is sufficient.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key for scoring |
| `DATA_DIR` | No | `data` | Path to SQLite database directory |
| `PROFILES_DIR` | No | `profiles` | Path to profile configs directory |
| `APP_PASSWORD` | No | — | Enables HTTP Basic Auth if set |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram notifications (optional) |
| `TELEGRAM_CHAT_ID` | No | — | Telegram chat ID (optional) |
| `NEXT_PUBLIC_API_URL` | No | `""` | API base URL for frontend (empty = same origin) |

---

## Makefile Reference

```makefile
make install   # pip install + npm install (one-time setup)
make dev       # Start FastAPI :8000 + Next.js :3000 (development)
make types     # Regenerate web/src/lib/api/types.ts from OpenAPI spec
make build     # Build Next.js static export → web/out/
make start     # Single production process at :8000
make lint      # ESLint + TypeScript type check
```
