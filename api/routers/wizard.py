import json
import logging
import asyncio
import yaml
import shutil
import base64
import re
import fitz  # pymupdf
import anthropic
from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException, UploadFile, File
from api.deps import PROFILES_DIR
from api.models import (
    CVAnalysisResponse,
    ProfileGenerateRequest,
    ProfileGenerateResponse,
    ProfileRefineRequest,
    ProfileRefineResponse,
    ProfileSaveRequest,
    ProfileTemplateResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Resolve paths relative to src/
from pathlib import Path
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"

def _load_cv_analysis_prompt() -> str:
    """Load the system prompt for CV analysis from src/prompts/cv_analysis.md.

    Follows the code-block-extraction pattern from scorer.py.
    """
    path = _SRC_DIR / "prompts" / "cv_analysis.md"
    if not path.exists():
        logger.error("CV analysis prompt not found at %s", path)
        raise HTTPException(status_code=500, detail="CV analysis prompt template not found")

    content = path.read_text(encoding="utf-8").strip()

    # Code-block-extraction pattern: if wrapped in ```, extract content
    if content.startswith("```"):
        try:
            first_newline = content.index("\n")
            content = content[first_newline + 1:]
        except ValueError:
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

    return content.strip()


def _load_refinement_prompt() -> str:
    """Load the refinement system prompt."""
    path = _SRC_DIR / "prompts" / "profile_refinement.md"
    if not path.exists():
        raise HTTPException(status_code=500, detail="Refinement prompt not found")
    return path.read_text(encoding="utf-8").strip()

def _extract_json(text: str) -> str:
    """Extract JSON block from text using regex, same as scorer.py."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text.strip()

def _is_extraction_poor(text: str) -> bool:
    """
    Heuristic to detect if text extraction is poor (scanned PDF or garbled symbols).
    - Text length < 200
    - Non-alphanumeric ratio > 30% (indicative of garbled symbols in designed PDFs)
    """
    if not text or len(text.strip()) < 200:
        return True
    
    # Count alphanumeric characters and spaces
    alnum_chars = sum(1 for c in text if c.isalnum() or c.isspace())
    total_chars = len(text)
    
    if total_chars == 0:
        return True
        
    alnum_ratio = alnum_chars / total_chars
    # If less than 70% is alphanumeric or space, it's likely garbled symbols
    return alnum_ratio < 0.7

def _render_pdf_to_images(file_bytes: bytes, dpi: int = 300, max_pages: int = 10) -> list[bytes]:
    """Convert PDF pages to PNG images for Claude Vision."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    
    # 300 DPI: scale factor = 300/72 ≈ 4.17
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    
    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
        
    doc.close()
    return images


@router.post("/wizard/analyze-cv", response_model=CVAnalysisResponse)
async def analyze_cv(file: UploadFile = File(...)):
    """
    Extract text from PDF and return a structured CV analysis using Claude.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are supported")

    # 1. Server-side file size limit (10MB)
    try:
        chunk = await file.read(10_000_001)
        if len(chunk) > 10_000_000:
            raise HTTPException(
                status_code=422, 
                detail="File too large. Maximum size is 10MB."
            )
        await file.seek(0)
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Error checking file size: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

    # 2. Extract text using PyMuPDF (fitz)
    text = ""
    page_count = 0
    file_bytes = await file.read()
    
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        logger.error(f"Error reading PDF with PyMuPDF: {e}")
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

    # 3. Hybrid Detection: Decide between text mode and vision mode
    extraction_method = "text"
    user_content = []
    
    if _is_extraction_poor(text):
        logger.info(f"Poor text extraction detected (length: {len(text)}). Falling back to Vision mode.")
        extraction_method = "vision"
        try:
            images = _render_pdf_to_images(file_bytes, dpi=300)
            for img_bytes in images:
                b64_data = base64.b64encode(img_bytes).decode("utf-8")
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64_data,
                    }
                })
            user_content.append({
                "type": "text",
                "text": "Analyze this CV. The pages are provided as images above. Extract all professional information visible across all pages."
            })
        except Exception as e:
            logger.error(f"Error rendering PDF to images: {e}")
            # If vision fallback fails, we try to proceed with whatever text we have if it's not totally empty
            if len(text.strip()) < 50:
                raise HTTPException(status_code=422, detail=f"Failed to read CV even with vision fallback: {e}")
            extraction_method = "text"
            user_content = [{"type": "text", "text": f"Analyze this CV text:\n\n{text}"}]
    else:
        user_content = [{"type": "text", "text": f"Here is the candidate's CV text:\n\n{text}"}]

    system_prompt = _load_cv_analysis_prompt()

    async with AsyncAnthropic() as client:
        # We want up to 2 retries (3 total attempts) for API errors
        # JSON fix-up is handled separately and only on the first attempt
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_content}],
                    timeout=120.0,
                )

                raw_text = response.content[0].text
                json_str = _extract_json(raw_text)

                try:
                    data = json.loads(json_str)
                    return CVAnalysisResponse(
                        page_count=page_count, 
                        extraction_method=extraction_method,
                        **data
                    )
                except (json.JSONDecodeError, Exception) as e:
                    # If this is the first attempt, try one JSON fix-up call
                    if attempt == 0:
                        logger.warning(f"Initial JSON parse error: {e}. Attempting fix-up...")
                        retry_message = f"Your previous response was not valid JSON or didn't match the schema. Error: {e}. Please fix the JSON and return the full object again."
                        fix_response = await client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=4096,
                            system=system_prompt,
                            messages=[
                                {"role": "user", "content": user_content},
                                {"role": "assistant", "content": raw_text},
                                {"role": "user", "content": retry_message}
                            ],
                            timeout=120.0,
                        )
                        raw_text = fix_response.content[0].text
                        json_str = _extract_json(raw_text)
                        data = json.loads(json_str)
                        return CVAnalysisResponse(
                            page_count=page_count, 
                            extraction_method=extraction_method,
                            **data
                        )
                    else:
                        raise HTTPException(status_code=502, detail=f"LLM returned invalid JSON after fix-up: {e}")

            except anthropic.RateLimitError:
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                raise HTTPException(status_code=502, detail="Anthropic Rate Limit exceeded")
            except anthropic.APIError as e:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                raise HTTPException(status_code=502, detail=f"Anthropic API Error: {e}")
            except Exception as e:
                if isinstance(e, HTTPException): raise e
                logger.error(f"Unexpected error in CV analysis: {e}")
                raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

    raise HTTPException(status_code=502, detail="Failed to analyze CV after multiple attempts")


from api.wizard_helpers import generate_profile_yaml, generate_profile_doc

@router.post("/wizard/generate-profile", response_model=ProfileGenerateResponse)
async def generate_profile(req: ProfileGenerateRequest):
    """
    Build profile.yaml and profile_doc.md from structured data and user preferences.
    """
    try:
        preferences_dict = req.user_preferences.model_dump()
        profile_yaml = generate_profile_yaml(req.cv_analysis, preferences_dict)
        profile_doc = generate_profile_doc(req.cv_analysis, preferences_dict)

        return ProfileGenerateResponse(
            profile_yaml=profile_yaml,
            profile_doc=profile_doc
        )
    except Exception as e:
        logger.error(f"Error generating profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate profile: {e}")


@router.post("/wizard/refine-profile", response_model=ProfileRefineResponse)
async def refine_profile(req: ProfileRefineRequest):
    """
    Refine template-generated profile files using LLM second pass.
    Falls back to original drafts on any failure.
    """
    system_prompt = _load_refinement_prompt()

    # Build user message with all context
    user_message = f"""## CV Analysis (source of truth)
```json
{req.cv_analysis.model_dump_json(indent=2)}
```

## User Preferences
```json
{req.user_preferences.model_dump_json(indent=2)}
```

## Draft profile_doc.md
{req.draft_doc}

## Draft profile.yaml
```yaml
{req.draft_yaml}
```

Refine both files following the instructions. Stay grounded in the CV analysis."""

    try:
        async with AsyncAnthropic() as client:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                timeout=120.0,
            )

            raw_text = response.content[0].text
            json_str = _extract_json(raw_text)
            data = json.loads(json_str)

            refined_doc = data.get("profile_doc", req.draft_doc)
            refined_yaml = data.get("profile_yaml", req.draft_yaml)
            changes = data.get("changes_made", [])

            # Validate YAML before returning
            try:
                yaml.safe_load(refined_yaml)
            except yaml.YAMLError:
                logger.warning("Refined YAML is invalid, falling back to draft")
                refined_yaml = req.draft_yaml
                changes.append("Warning: YAML refinement produced invalid syntax, kept original")

            return ProfileRefineResponse(
                profile_doc=refined_doc,
                profile_yaml=refined_yaml,
                changes_made=changes,
            )

    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        # Graceful fallback — return originals unchanged
        return ProfileRefineResponse(
            profile_doc=req.draft_doc,
            profile_yaml=req.draft_yaml,
            changes_made=[f"Refinement skipped: {str(e)[:100]}"],
        )


@router.post("/wizard/save-profile")
async def save_profile(req: ProfileSaveRequest):
    """
    Write profile files to disk and ensure dependencies like scoring_philosophy.md exist.
    """
    # 1. Validate YAML
    try:
        yaml.safe_load(req.profile_yaml)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid profile.yaml: {e}")

    profile_dir = PROFILES_DIR / req.profile_name
    example_dir = PROFILES_DIR / "example"

    # 2. Create directory if it doesn't exist
    if not profile_dir.exists():
        if not example_dir.exists():
            raise HTTPException(status_code=500, detail="Example profile template not found")
        # Start by copying the example template (gets scoring_philosophy.md and companies.yaml)
        shutil.copytree(example_dir, profile_dir)
    else:
        # 3. If directory exists, ensure scoring_philosophy.md and companies.yaml are present
        for filename in ["scoring_philosophy.md", "companies.yaml"]:
            target_path = profile_dir / filename
            if not target_path.exists():
                source_path = example_dir / filename
                if source_path.exists():
                    shutil.copy2(source_path, target_path)

    # 4. Overwrite generated files
    (profile_dir / "profile.yaml").write_text(req.profile_yaml, encoding="utf-8")
    (profile_dir / "profile_doc.md").write_text(req.profile_doc, encoding="utf-8")

    return {"ok": True, "name": req.profile_name}


@router.get("/wizard/template", response_model=ProfileTemplateResponse)
async def get_template():
    """
    Return the contents of the example profile template files.
    """
    example_dir = PROFILES_DIR / "example"
    if not example_dir.exists():
        raise HTTPException(status_code=500, detail="Example profile template not found")

    profile_yaml_path = example_dir / "profile.yaml"
    profile_doc_path = example_dir / "profile_doc.md"

    if not profile_yaml_path.exists() or not profile_doc_path.exists():
        raise HTTPException(status_code=500, detail="Template files missing in example profile")

    return ProfileTemplateResponse(
        profile_yaml=profile_yaml_path.read_text(encoding="utf-8"),
        profile_doc=profile_doc_path.read_text(encoding="utf-8")
    )
