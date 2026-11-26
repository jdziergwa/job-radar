import yaml
from fastapi import APIRouter, HTTPException

from api.deps import get_profile_dir, get_store
from api.llm_errors import llm_http_errors
from api.models import AiConfig, AiModelOverrideRequest
from src.llm import AITask, LLMConfigError, describe_active, load_model_overrides, set_model_override

router = APIRouter()


def _profile_scoring_model(profile: str) -> str | None:
    """The profile YAML `scoring.model`, if the profile sets one."""
    path = get_profile_dir(profile) / "search_config.yaml"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = config["scoring"]["model"]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return None
    return model if isinstance(model, str) else None


@router.get("/ai-config", response_model=AiConfig)
def ai_config(profile: str = "default"):
    """Active LLM Provider and per-task Models (a profile's `scoring.model` wins for scoring). Never includes API keys."""
    store = get_store(profile)
    return {**describe_active(store, profile_model=_profile_scoring_model(profile)), "overrides": {t.value: m for t, m in load_model_overrides(store).items()}}


@router.put("/ai-config/models/{task}", response_model=AiConfig)
def set_ai_model(task: AITask, body: AiModelOverrideRequest, profile: str = "default"):
    """Set or clear the Settings Model override for an AI Task."""
    store = get_store(profile)
    with llm_http_errors():
        try:
            set_model_override(store, task, body.model)
        except LLMConfigError as e:
            raise HTTPException(status_code=422, detail=str(e))
    return ai_config(profile)
