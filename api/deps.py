import os
from pathlib import Path
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
