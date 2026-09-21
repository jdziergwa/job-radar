from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

from api.deps import get_store
from api.models import AiConfig, AiModelOverrideRequest
from src.llm import AITask, LLMConfigError, describe_active, load_model_overrides, set_model_override

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
from api.routers import applications, jobs, stats, pipeline, profile, companies, wizard
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(applications.router, prefix="/api", tags=["applications"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
app.include_router(wizard.router, prefix="/api", tags=["wizard"])
app.include_router(profile.router, prefix="/api", tags=["profile"])
app.include_router(companies.router, prefix="/api", tags=["companies"])




@app.get("/api/ai-config", tags=["config"], response_model=AiConfig)
def ai_config(profile: str = "default"):
    """Active LLM Provider and per-task Models. Never includes API keys."""
    store = get_store(profile)
    return {**describe_active(store), "overrides": {t.value: m for t, m in load_model_overrides(store).items()}}


@app.put("/api/ai-config/models/{task}", tags=["config"], response_model=AiConfig)
def set_ai_model(task: AITask, body: AiModelOverrideRequest, profile: str = "default"):
    """Set or clear the Settings Model override for an AI Task."""
    store = get_store(profile)
    try:
        set_model_override(store, task, body.model)
    except LLMConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"AI not configured: {e}")
    return ai_config(profile)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "version": "1.0.0"}

# Production: serve Next.js static export from web/out/
static_dir = Path("web/out")
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
