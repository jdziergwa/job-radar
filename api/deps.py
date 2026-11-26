import os
from pathlib import Path

import yaml

from src.store import Store

PROFILES_DIR = Path(os.getenv("PROFILES_DIR", "profiles"))
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

def get_store(profile: str = "default") -> Store:
    """Returns a Store instance for the given profile."""
    db_path = DATA_DIR / f"{profile}.db"
    return Store(str(db_path))

def get_profile_dir(profile: str = "default") -> Path:
    """Returns the profile directory path."""
    return PROFILES_DIR / profile


def profile_scoring_model(profile: str = "default") -> str | None:
    """The profile YAML `scoring.model`, if the profile sets one."""
    path = get_profile_dir(profile) / "search_config.yaml"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = config["scoring"]["model"]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return None
    return model if isinstance(model, str) else None
