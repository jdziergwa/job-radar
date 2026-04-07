import shutil
from fastapi import APIRouter, HTTPException
import yaml
from api.deps import PROFILES_DIR
from api.models import ProfileContent

router = APIRouter()


@router.post("/profile/{name}")
def create_profile(name: str):
    """Create a new profile by copying the example template."""
    example_dir = PROFILES_DIR / "example"
    if not example_dir.exists():
        raise HTTPException(status_code=500, detail="Example profile template not found")

    target_dir = PROFILES_DIR / name
    if target_dir.exists():
        raise HTTPException(status_code=409, detail=f"Profile '{name}' already exists")

    shutil.copytree(example_dir, target_dir)
    return {"ok": True, "name": name}


@router.get("/profiles")
def list_profiles():
    """List all profile directories."""
    if not PROFILES_DIR.exists():
        return []
    return [
        {"name": d.name}
        for d in sorted(PROFILES_DIR.iterdir())
        if d.is_dir() and not d.name.startswith('.')
    ]


@router.get("/profile/{name}/yaml", response_model=ProfileContent)
def get_profile_yaml(name: str):
    path = PROFILES_DIR / name / "profile.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    return ProfileContent(content=path.read_text(encoding="utf-8"))


@router.put("/profile/{name}/yaml")
def update_profile_yaml(name: str, body: ProfileContent):
    # Validate YAML before writing
    try:
        yaml.safe_load(body.content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")
    
    path = PROFILES_DIR / name / "profile.yaml"
    if not path.parent.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    
    path.write_text(body.content, encoding="utf-8")
    return {"ok": True}


@router.get("/profile/{name}/doc", response_model=ProfileContent)
def get_profile_doc(name: str):
    path = PROFILES_DIR / name / "profile_doc.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile doc '{name}' not found")
    return ProfileContent(content=path.read_text(encoding="utf-8"))


@router.put("/profile/{name}/doc")
def update_profile_doc(name: str, body: ProfileContent):
    path = PROFILES_DIR / name / "profile_doc.md"
    if not path.parent.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    path.write_text(body.content, encoding="utf-8")
    return {"ok": True}


@router.get("/profile/{name}/scoring-philosophy", response_model=ProfileContent)
def get_scoring_philosophy(name: str):
    path = PROFILES_DIR / name / "scoring_philosophy.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Scoring philosophy for profile '{name}' not found")
    return ProfileContent(content=path.read_text(encoding="utf-8"))


@router.put("/profile/{name}/scoring-philosophy")
def update_scoring_philosophy(name: str, body: ProfileContent):
    profile_path = PROFILES_DIR / name
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    if not body.content.strip():
        raise HTTPException(status_code=422, detail="Scoring philosophy cannot be empty")
    path = profile_path / "scoring_philosophy.md"
    path.write_text(body.content, encoding="utf-8")
    return {"ok": True}
