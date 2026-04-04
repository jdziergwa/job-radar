from fastapi import APIRouter, HTTPException
import yaml
from api.deps import PROFILES_DIR
from api.models import CompanyEntry, CompaniesResponse

router = APIRouter()

PLATFORMS = ["greenhouse", "lever", "ashby", "workable"]


def _load_companies(profile: str) -> dict:
    path = PROFILES_DIR / profile / "companies.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for p in PLATFORMS:
        data.setdefault(p, [])
    return data


def _save_companies(profile: str, data: dict):
    path = PROFILES_DIR / profile / "companies.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


@router.get("/companies/{profile}", response_model=CompaniesResponse)
def get_companies(profile: str):
    data = _load_companies(profile)
    return CompaniesResponse(
        greenhouse=data.get("greenhouse", []),
        lever=data.get("lever", []),
        ashby=data.get("ashby", []),
        workable=data.get("workable", []),
    )


@router.post("/companies/{profile}")
def add_company(profile: str, body: CompanyEntry):
    data = _load_companies(profile)
    platform_list = data.get(body.platform, [])
    
    # Check for duplicate slug
    if any(c.get("slug") == body.slug for c in platform_list):
        raise HTTPException(
            status_code=409,
            detail=f"Company '{body.slug}' already exists in {body.platform}"
        )
    
    platform_list.append({"slug": body.slug, "name": body.name})
    data[body.platform] = platform_list
    _save_companies(profile, data)
    return {"ok": True}


@router.delete("/companies/{profile}/{platform}/{slug}")
def remove_company(profile: str, platform: str, slug: str):
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform '{platform}'")
    
    data = _load_companies(profile)
    platform_list = data.get(platform, [])
    original_len = len(platform_list)
    data[platform] = [c for c in platform_list if c.get("slug") != slug]
    
    if len(data[platform]) == original_len:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found in {platform}")
    
    _save_companies(profile, data)
    return {"ok": True}
