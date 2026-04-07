from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="Job Radar API",
    version="1.0.0",
    description="REST API for Job Radar web interface",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers will be registered here in later prompts (03-06)
from api.routers import jobs, stats, pipeline, profile, companies, wizard
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
app.include_router(wizard.router, prefix="/api", tags=["wizard"])
app.include_router(profile.router, prefix="/api", tags=["profile"])
app.include_router(companies.router, prefix="/api", tags=["companies"])




@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "version": "1.0.0"}

# Production: serve Next.js static export from web/out/
static_dir = Path("web/out")
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
