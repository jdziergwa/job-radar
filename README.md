<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/readme-header.png" />
    <source media="(prefers-color-scheme: light)" srcset=".github/assets/readme-header-light.png" />
    <img src=".github/assets/readme-header-light.png" alt="Job Radar" width="350" />
  </picture>
</p>

Job Radar scans curated ATS boards, public remote-job APIs, hiring feeds, and an optional large job aggregator for roles that match your profile. It collects, hydrates, filters, and scores job listings against your profile using Claude, then presents the results in a web dashboard.

Try the live demo: [https://jdziergwa.github.io/job-radar/](https://jdziergwa.github.io/job-radar/)

<p align="center">
  <img src=".github/assets/dashboard.png" alt="Dashboard overview" width="48%" />
  <img src=".github/assets/job-details.png" alt="Job details view" width="48%" />
</p>

---

## ⚡ Features

-   **📡 Monitoring**: Scans curated ATS boards plus built-in providers like Remotive, Remote OK, Hacker News, Arbeitnow, We Work Remotely, Adzuna, and the aggregator.
-   **🧹 Filters**: Regex pre-filtering eliminates ~90% of noise before any scoring.
-   **📝 Hydration**: Fills in missing or sparse job descriptions before filtering and scoring.
-   **🧠 AI Scoring**: Analysis of job descriptions for Match, Seniority, and Tech Stack fit.
-   **🖥️ Dashboard**: Next.js interface to manage jobs and track trends.
-   **🛰️ Aggregator**: Optional broad remote-job scan alongside targeted direct sources.
-   **🎭 Profiles**: Support for multiple career profiles with separate CVs and keywords.
-   **🛠️ Import Tooling**: Generate mergeable `companies.yaml` fragments from external JSON datasets.

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

Create an Anthropic API key in [Console Settings → API Keys](https://platform.claude.com/settings/keys) and add prepaid credits from the [Billing page](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-api-usage). Then paste the key into `.env` as `ANTHROPIC_API_KEY`.

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

### Local Development

### 1. Prerequisites

-   **Python 3.11+**
-   **Node.js 20+**
-   **Anthropic API Key** (Get one at [console.anthropic.com](https://console.anthropic.com))

### 2. One-Minute Installation

```bash
git clone https://github.com/jdziergwa/job-radar.git
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

---

### First Run

On first launch the setup wizard appears automatically. The guided flow uploads your CV, runs AI CV analysis, lets you review extracted facts, set location and preference constraints, and then generates both `profile_doc.md` and `search_config.yaml` before you save the profile and run your first scan.

Later, you can reopen the same guided workflow from **Settings → Guided Edit** to either:
- update saved preferences and regenerate the profile from structured state
- upload a new CV and rebuild the profile from the beginning

If you prefer direct editing, **Settings** still exposes the raw `profile_doc.md`, `search_config.yaml`, and `scoring_philosophy.md` files.

### Cost and Runtime Expectations

Claude costs are reasonable enough to try with a small credit balance. One real first-run example from my setup:

- One-time profile generation with Sonnet: about `$0.15`
- Scoring `855` jobs with Haiku: about `$1.88`
- First broad run with all providers: roughly `30-40 minutes`

Your numbers will vary with provider mix and how many jobs survive filtering, but in that run Haiku scoring came out to about `$0.22` per `100` scored jobs. After the first run, later runs are usually much cheaper and faster because only new surviving jobs need scoring. A `$5` top-up is usually enough to try profile generation plus many incremental runs.

If you want to try the pipeline cost-free first, use the web UI trigger with `Dry Run` to fetch and filter jobs without any Claude scoring, so you can see how many jobs would reach scoring. The CLI supports the same flow with `--dry-run`, for example: `.venv/bin/python -m src.main --source aggregator local --dry-run -v`.

---

## ⚙️ Configuration

Job Radar is highly configurable to match your specific career goals.

### 🗝️ Environment Variables (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | **Yes** | Used by Claude AI to score job descriptions. |
| `ADZUNA_APP_ID` | No | Required only if you enable the Adzuna provider. Create an account at [developer.adzuna.com](https://developer.adzuna.com/) to get it. Adzuna allows personal research use; see [their terms](https://developer.adzuna.com/docs/terms_of_service). |
| `ADZUNA_APP_KEY` | No | Required only if you enable the Adzuna provider. Adzuna issues this alongside your app ID. |

### 📂 Profile Configuration (`profiles/{name}/`)

Each profile is a directory containing four main editable files:

1.  **`profile_doc.md`**: Your CV and scoring guide for the LLM. The more specific the better — include not just your skills but explicit "Critical Skill Gaps" and "What Lowers Fit" sections to prevent score inflation on bad matches. See `profiles/example/profile_doc.md` for the full structure.
2.  **`search_config.yaml`**:
    -   `keywords.title_patterns`: Split into `high_confidence` and `broad` tiers for precise filtering.
    -   `keywords.location_patterns` / `remote_patterns`: Primary location targets and a remote tier (governed by the `fallback_tier` field).
    -   `scoring`: Choose your model (e.g., `claude-haiku-4-5-20251001`) and set thresholds.
3.  **`scoring_philosophy.md`**: The per-profile scoring rubric used by the LLM after pre-filtering. This is editable from **Settings**.
4.  **`companies.yaml`**: Specific companies to monitor directly via their ATS boards, grouped by platform.

The guided wizard also persists structured state alongside those files:
- `cv_analysis.json`: normalized CV extraction and derived signals
- `preferences.json`: saved wizard inputs used by guided edit and start-fresh flows

### 🔌 Providers

Registered providers currently include:

-   `aggregator`
-   `local`
-   `remotive`
-   `remoteok`
-   `hackernews`
-   `arbeitnow`
-   `weworkremotely`
-   `adzuna`

CLI examples:

```bash
# Default broad run
.venv/bin/python -m src.main --source aggregator local

# Direct ATS scan in conservative mode
.venv/bin/python -m src.main --source local --slow --dry-run

# Single-provider validation
.venv/bin/python -m src.main --source arbeitnow --dry-run -v
```

To grow `companies.yaml` from an external JSON dataset:

```bash
.venv/bin/python scripts/import_companies.py --input companies.json
```

---

## 🛤️ The Pipeline

Job Radar uses a multi-stage pipeline to ensure efficiency and accuracy:

```mermaid
graph TD
    A[Collect] -->|Poll APIs| B[Deduplicate]
    B -->|Check SQLite| C[Hydrate]
    C -->|Fetch fuller descriptions| D[Pre-filter]
    D -->|Regex Check| E[Score]
    E -->|Claude AI| F[Report]
    F -->|UI / Reports| G[Opportunity]
    
    style E fill:#f96,stroke:#333,stroke-width:2px
```

1.  **Collect**: Fetches jobs from one or more providers such as `local`, `aggregator`, `remotive`, or `arbeitnow`.
2.  **Deduplicate**: Skips jobs you've already seen.
3.  **Hydrate**: Fetches fuller descriptions for jobs with missing or sparse text.
4.  **Pre-filter**: Matches against your `title_patterns` and `location_patterns`.
5.  **Score**: Sends survivors to Claude to compute a fit score (0-100).
6.  **Report**: Persists results and updates the dashboard and reports.

---

## 🛠️ Make Commands

| Command | Action |
|---------|--------|
| `make install` | Setup Python venv and install all dependencies. |
| `make dev` | Start the full stack (API + Web) with hot reload. |
| `make lint` | Run the frontend linter and TypeScript typecheck. |
| `make build` | Build the frontend for production. |
| `make start` | Build the frontend, then start the FastAPI server. |
| `make types` | Regenerate TypeScript types from the API spec. |
| `make test` | Run the Python test suite. |
| `make test-cov` | Run the Python test suite with coverage for `src/` and `api/`. |
| `make demo-snapshot` | Export static demo files from the current contents of `data/demo.db` into `web/public/demo-data`. Run `.venv/bin/python -m src.main --profile demo --source local` first if you want fresh demo data. |
| `make readme-header` | Regenerate the README header PNG from its HTML source. |
| `make clean-web`| Remove the frontend node_modules and .next cache. |
| `make clean-db`| Wipe local databases and, if Docker is running, remove `/app/data/*.db` inside the API container. |
| `make clean-db-volume`| Remove the Docker named volume used for API SQLite databases. |

---

## 🔒 Security & Privacy

- **Never commit `.env`** — it contains your `ANTHROPIC_API_KEY`. The `.gitignore` already excludes it, but double-check before pushing. If you accidentally expose a key, revoke it immediately at [console.anthropic.com](https://console.anthropic.com).
- **All data stays local** — job listings, scores, and your `profile_doc.md` are stored only on your machine. Native runs use `data/{profile}.db`; Docker Compose runs keep SQLite databases in the Docker API volume mounted at `/app/data`. The only third-party processing is the Claude API calls used for CV analysis, profile generation, and job scoring, which send the relevant job and profile context needed for those prompts.

## 🙌 Acknowledgments

- Aggregator data derived from [job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator), licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
- Remotive source data provided by [Remotive](https://remotive.com).
- Remote OK source data provided by [Remote OK](https://remoteok.com).
- Hacker News source data provided by [Hacker News](https://news.ycombinator.com) via [Algolia](https://hn.algolia.com).
- Arbeitnow source data provided by [Arbeitnow](https://www.arbeitnow.com).
- We Work Remotely source data provided by [We Work Remotely](https://weworkremotely.com).
- Adzuna source data provided by [Adzuna](https://www.adzuna.com).
- Company discovery imports may include normalized ATS company data derived from [Remotebear](https://github.com/remotebear-io/remotebear) and [Awesome Easy Apply](https://github.com/sample-resume/awesome-easy-apply).

---

## ⚖️ Legal Notice

Job Radar uses a mix of direct ATS APIs, public job feeds, and optional third-party datasets. Use providers responsibly: respect rate limits, avoid aggressive scraping, and review each source's terms before enabling it in your workflow. `--slow` is available for more conservative ATS runs, and some providers such as Adzuna require their own API credentials.

---

## ❗ Troubleshooting

### ❌ `ANTHROPIC_API_KEY not found`
Ensure you have created a `.env` file in the root directory and that it contains `ANTHROPIC_API_KEY=your_key_here`.

### ❌ `ModuleNotFoundError`
Run `make install` again to ensure your Python virtual environment is correctly set up.

---

## 📄 License

Licensed under [GNU AGPL v3.0](https://www.gnu.org/licenses/agpl-3.0.en.html). See [LICENSE](LICENSE).
