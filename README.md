# 📡 Job Radar

Job Radar is a tool for monitoring your job search across public ATS boards (Greenhouse, Lever, Ashby, Workable). It collects, filters, and scores job listings against your profile using Claude AI, then presents the results in a web dashboard.

---

## ⚡ Features

-   **📡 Monitoring**: Polls company ATS boards concurrently.
-   **🧹 Filters**: Regex pre-filtering eliminates ~90% of noise before any scoring.
-   **🧠 AI Scoring**: Analysis of job descriptions for Match, Seniority, and Tech Stack fit.
-   **🖥️ Dashboard**: Next.js interface to manage jobs and track trends.
-   **🛰️ Aggregator**: Access to 900,000+ jobs via a remote aggregator.
-   **🎭 Profiles**: Support for multiple career profiles with separate CVs and keywords.
-   **🔔 Notifications**: Optional Telegram alerts for top matches.

---

## 🚀 Quick Start

### Docker First

If you just want to try the app, you do not need a local Python or Node install:

```bash
docker compose up --build
```

-   **Backend**: [http://localhost:8000](http://localhost:8000)
-   **Frontend**: [http://localhost:3000](http://localhost:3000)

If you want AI scoring, create a `.env` file first so the API can see your Anthropic key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build
```

On Linux, if you want files in `data/` and `reports/` to stay owned by your host user instead of `root`, also add your UID/GID to `.env`:

```bash
echo "HOST_UID=$(id -u)" >> .env
echo "HOST_GID=$(id -g)" >> .env
docker compose up --build
```

On Windows, Docker Desktop is the recommended path. The compose setup enables polling-based file watching for both Next.js and FastAPI so hot reload is more reliable on bind mounts, especially when the repo lives outside WSL.

When running via Docker Compose, the API stores SQLite databases in a Docker named volume mounted at `/app/data` instead of the host `./data` directory. This keeps the code bind-mounted for hot reload, but avoids the severe SQLite write slowdown that can happen on macOS bind mounts. As a result, deleting `data/*.db` on the host does not reset the Docker-backed database; use `make clean-db` or `make clean-db-volume` instead.

### 1. Prerequisites

-   **Python 3.11+**
-   **Node.js 20+**
-   **Anthropic API Key** (Get one at [console.anthropic.com](https://console.anthropic.com))

### 2. One-Minute Installation

```bash
git clone <repo-url>
cd job-radar

# Install dependencies (Python venv + Node modules)
make install

# Configure your environment
cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Launch

```bash
make dev
```
-   **Backend**: [http://localhost:8000](http://localhost:8000) (FastAPI)
-   **Frontend**: [http://localhost:3000](http://localhost:3000) (Next.js)

On first launch the setup wizard will appear — paste your CV and click **Get Started**. Note that sensible defaults are provided for your profile configuration, and you can tune these later at any time in **Settings → Matching Rules**. Then click **Run Pipeline** to start your first scan!

---

## ⚙️ Configuration

Job Radar is highly configurable to match your specific career goals.

### 🗝️ Environment Variables (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | **Yes** | Used by Claude AI to score job descriptions. |
| `TELEGRAM_BOT_TOKEN`| No | Token for Telegram notifications. |
| `TELEGRAM_CHAT_ID` | No | Your numeric Telegram ID for notification delivery. |

### 📂 Profile Configuration (`profiles/{name}/`)

Each profile is a directory containing three core files:

1.  **`profile_doc.md`**: Your CV and scoring guide for the LLM. The more specific the better — include not just your skills but explicit "Critical Skill Gaps" and "What Lowers Fit" sections to prevent score inflation on bad matches. See `profiles/example/profile_doc.md` for the full structure.
2.  **`profile.yaml`**:
    -   `keywords.title_patterns`: Split into `high_confidence` and `broad` tiers for precise filtering.
    -   `keywords.location_patterns` / `remote_patterns`: Primary location targets and a remote tier (governed by the `fallback_tier` field).
    -   `scoring`: Choose your model (e.g., `claude-haiku-4-5-20251001`) and set thresholds.
    -   `output`: Toggle reports and Telegram alerts.
3.  **`companies.yaml`**: Specific companies to monitor directly via their ATS boards, grouped by platform.

---

## 🛤️ The Pipeline

Job Radar uses a multi-stage pipeline to ensure efficiency and accuracy:

```mermaid
graph TD
    A[Collect] -->|Poll APIs| B[Deduplicate]
    B -->|Check SQLite| C[Pre-filter]
    C -->|Regex Check| D[Score]
    D -->|Claude AI| E[Report]
    E -->|UI / Telegram| F[Opportunity]
    
    style D fill:#f96,stroke:#333,stroke-width:2px
```

1.  **Collect**: Fetches jobs from local ATS boards or the aggregator.
2.  **Deduplicate**: Skips jobs you've already seen.
3.  **Pre-filter**: Matches against your `title_patterns` and `location_patterns`.
4.  **Score**: Sends "survivors" to Claude to compute a fit score (0-100).
5.  **Report**: Persists results and triggers notifications.

---

## 🛠️ Make Commands

| Command | Action |
|---------|--------|
| `make install` | Setup Python venv and install all dependencies. |
| `make dev` | Start the full stack (API + Web) with hot reload. |
| `make start` | Start the production build of the application. |
| `make build` | Build the frontend for production. |
| `make types` | Regenerate TypeScript types from the API spec. |
| `make clean-web`| Remove the frontend node_modules and .next cache. |
| `make clean-db`| Wipe local databases and, if Docker is running, remove `/app/data/*.db` inside the API container. |
| `make clean-db-volume`| Remove the Docker named volume used for API SQLite databases. |

---

## 🔒 Security & Privacy

- **Never commit `.env`** — it contains your `ANTHROPIC_API_KEY`. The `.gitignore` already excludes it, but double-check before pushing. If you accidentally expose a key, revoke it immediately at [console.anthropic.com](https://console.anthropic.com).
- **All data stays local** — job listings, scores, and your `profile_doc.md` are stored only on your machine. Native runs use `data/{profile}.db`; Docker Compose runs keep SQLite databases in the Docker API volume mounted at `/app/data`. Nothing is sent to third parties except job descriptions forwarded to the Claude API for scoring.
- **Your profile is not tracked** — `profiles/` is gitignored except for the `example/` template. Your CV (`profile_doc.md`) and company list stay private.

## 🙌 Acknowledgments

Aggregator module data sourced from [job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator).
Remotive source data provided by [Remotive](https://remotive.com).
Remote OK source data provided by [Remote OK](https://remoteok.com).
Hacker News source data provided by [Hacker News](https://news.ycombinator.com) via [Algolia](https://hn.algolia.com).
Arbeitnow source data provided by [Arbeitnow](https://www.arbeitnow.com).
We Work Remotely source data provided by [We Work Remotely](https://weworkremotely.com).

---

## ⚖️ Legal Notice

Job Radar queries the public job board APIs provided by Greenhouse, Lever, Ashby, and Workable. These endpoints are publicly documented and intended for programmatic access. Use responsibly: don't hammer endpoints, respect rate limits, and review each platform's terms of service before use.

---

## ❗ Troubleshooting

### ❌ `ANTHROPIC_API_KEY not found`
Ensure you have created a `.env` file in the root directory and that it contains `ANTHROPIC_API_KEY=your_key_here`.

### ❌ `ModuleNotFoundError`
Run `make install` again to ensure your Python virtual environment is correctly set up.

---

## 📄 License

MIT. Go find your dream job! 🚀
