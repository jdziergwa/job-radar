import asyncio
import json
import logging
import re
from typing import Any, Optional, Callable

import certifi
import httpx

from src.collector import strip_html
from src.models import RawJob

logger = logging.getLogger(__name__)

# Try to match job IDs from URLs
# Greenhouse: /jobs/12345
# Lever: /company/12345-uuid
# Ashby: /company/12345-uuid
ID_REGEX = re.compile(r"/([a-zA-Z0-9\-]+)/?$")

def extract_id(url: str) -> str:
    """Robust job ID extraction from various ATS URL formats."""
    # 1. Check for common query parameters
    # Greenhouse often uses gh_jid on custom domains
    for param in ["gh_jid", "lever-via", "jobId", "id"]:
        match = re.search(f"[?&]{param}=([a-zA-Z0-9\-_]+)", url)
        if match:
            return match.group(1)
            
    # 2. Extract last path segment, ignoring query/fragment
    path = url.split("?")[0].split("#")[0].strip("/")
    parts = f"/{path}".split("/") # Ensure leading slash
    if not parts:
        return ""
        
    # Handle Greenhouse specific IDs which might be numeric but in the middle
    if "greenhouse" in url and "jobs/" in url:
        gh_match = re.search(r"jobs/(\d+)", url)
        if gh_match:
            return gh_match.group(1)
            
    # Handle Lever IDs in path: /slug/uuid
    if "lever.co" in url:
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts[-1]

    return parts[-1] if parts else ""

def extract_json_ld(html: str) -> Optional[str]:
    """Try to find and parse schema.org JobPosting in JSON-LD."""
    def find_description(obj: Any) -> Optional[str]:
        """Recursively search for JobPosting or any description-like field."""
        if isinstance(obj, dict):
            # 1. Direct JobPosting hit
            type_val = str(obj.get("@type") or obj.get("type", "")).lower()
            if "jobposting" in type_val:
                desc = obj.get("description") or obj.get("jobDescription") or obj.get("descriptionHtml")
                if desc and isinstance(desc, str):
                    return desc
            
            # 2. Heuristic: if we see a field named "description", and it's a long string, use it
            # This helps with non-standard JSON-LD
            for k, v in obj.items():
                k_lower = k.lower()
                if ("description" in k_lower or "content" in k_lower) and isinstance(v, str) and len(v) > 100:
                    return v

            # 3. Search children recursively
            for v in obj.values():
                res = find_description(v)
                if res: return res
                
        elif isinstance(obj, list):
            for item in obj:
                res = find_description(item)
                if res: return res
        return None

    # Find all <script> tags with ld+json
    matches = re.finditer(r'<script[^>]*type=["\']application\/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    for m in matches:
        try:
            raw_text = m.group(1).strip()
            data = json.loads(raw_text)
            desc = find_description(data)
            if desc:
                return desc
        except (json.JSONDecodeError, Exception):
            continue
    return None

async def fetch_description(client: httpx.AsyncClient, sem: asyncio.Semaphore, job: Any) -> Optional[str]:
    """
    Given a job, fetch its full description using ATS-specific APIs or HTML scraping.
    """
    async with sem:
        url = str(job.url or "")
        ats = str(job.ats_platform or "").lower()
        slug = str(job.company_slug or "").lower() # Force lowercase
        job_id = extract_id(url)
        
        # Realistic headers to avoid bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Cache-Control": "no-cache",
        }

        try:
            # 1. Try Platform-Specific API Hydration First
            
            # Greenhouse (boards or job-boards)
            if "greenhouse" in ats or "greenhouse.io" in url or "gh_jid=" in url:
                if not slug:
                    # Try to extract slug from common patterns
                    for pattern in [r"greenhouse\.io/([^/?#]+)", r"careers/([^/?#]+)"]:
                        match = re.search(pattern, url)
                        if match: 
                            slug = match.group(1).lower()
                            break
                
                if slug and job_id:
                    # Try some common slug variations if the first one fails
                    slugs_to_try = [slug]
                    if "pro" not in slug: slugs_to_try.append(f"{slug}pro")
                    if "-" in slug: slugs_to_try.append(slug.replace("-", ""))
                    else: slugs_to_try.append("-".join(re.findall(r'[a-z]+', slug))) # e.g. housecall -> housecall
                    
                    # Clean up duplicates
                    slugs_to_try = list(dict.fromkeys(slugs_to_try))

                    for s in slugs_to_try:
                        api_url = f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs/{job_id}"
                        resp = await client.get(api_url, timeout=8)
                        if resp.status_code == 200:
                            data = resp.json()
                            content = data.get("content", "")
                            if content: return content
                        elif resp.status_code == 404:
                            continue # Try next slug
                        else:
                            break # Other error, stop
                        
            # Lever
            elif "lever" in ats or "lever.co" in url:
                if not slug:
                    match = re.search(r"lever\.co/([^/?#]+)", url)
                    if match: slug = match.group(1).lower()
                
                if slug and job_id:
                    slugs_to_try = [slug]
                    # Lever slugs are almost always lowercase but sometimes have -inc or similar
                    for s in slugs_to_try:
                        api_url = f"https://api.lever.co/v0/postings/{s}/{job_id}"
                        resp = await client.get(api_url, timeout=8)
                        if resp.status_code == 200:
                            data = resp.json()
                            html_content = data.get("description", "")
                            for lst in data.get("lists", []):
                                html_content += f"\n<h3>{lst.get('text', '')}</h3>\n<ul>"
                                for item in lst.get("content", []):
                                    html_content += f"<li>{item}</li>"
                                html_content += "</ul>"
                            if html_content: return html_content
                        elif resp.status_code == 404:
                            continue
                        else:
                            break

            # Workable
            elif "workable" in ats or "workable.com" in url:
                if not slug:
                    match = re.search(r"workable\.com/([^/?#]+)", url)
                    if match: slug = match.group(1).lower()
                
                if slug and job_id:
                    api_url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs/{job_id}"
                    resp = await client.get(api_url, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        html_content = (data.get("description", "") + "\n" + 
                                       data.get("requirements", "") + "\n" + 
                                       data.get("benefits", ""))
                        if html_content: return html_content

        except Exception as e:
            logger.debug("API hydration failed for %s: %s", job.company_name, e)

        # 2. General Scraper Fallback (JSON-LD and common selectors)
        # This handles BambooHR, Workday, and failed API attempts
        try:
            resp = await client.get(url, timeout=12, follow_redirects=True, headers=headers)
            if resp.status_code == 200:
                html = resp.text
                
                # Check for JobPosting metadata first - the most reliable way
                json_ld_desc = extract_json_ld(html)
                if json_ld_desc:
                    return json_ld_desc

                # Ashby/Other JSON extraction workarounds
                if "ashby" in ats or "ashbyhq.com" in url:
                    match = re.search(r'"descriptionHtml":"(.*?)","', html)
                    if match:
                        return match.group(1).replace("\\n", "\n").replace("\\\"", "\"")
                
                # Heuristic: look for common job description containers
                for selector in [
                    r'class=["\'][^"\']*(?:job-description|description|posting-content|job-detail-description)[^"\']*["\'][^>]*>(.*?)</div>',
                    r'id=["\'][^"\']*(?:job-description|description|content)[^"\']*["\'][^>]*>(.*?)</div>',
                    r'<article[^>]*>(.*?)</article>',
                    r'<main[^>]*>(.*?)</main>',
                ]:
                    match = re.search(selector, html, re.DOTALL | re.IGNORECASE)
                    if match:
                        content_piece = match.group(1)
                        if len(strip_html(content_piece)) > 200:
                            return content_piece

                # Absolute last resort
                content = strip_html(html)
                if len(content) > 300:
                    return content
                
        except Exception as e:
            logger.debug("Scraper fallback failed for %s (%s): %s", job.company_name, url, e)
            
    return None

async def populate_descriptions(
    jobs: list[Any], 
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> list[Any]:
    """Iterates through jobs and fetches missing descriptions asynchronously."""
    if not jobs:
        return []
        
    logger.info("Lazily fetching descriptions for %d candidate jobs...", len(jobs))
    sem = asyncio.Semaphore(10) # 10 concurrent requests to not spam
    ssl_context = certifi.where()
    
    completed = 0
    total = len(jobs)
    
    async with httpx.AsyncClient(verify=ssl_context) as client:
        tasks = [fetch_description(client, sem, job) for job in jobs]
        
        # We need to map results back to jobs, but as_completed doesn't preserve order.
        # However, fetch_description modifies the job object in place if we wanted, 
        # but here it returns the description string.
        
        # To maintain mapping and support progress, we can wrap the task
        async def fetch_and_assign(job_obj):
            desc = await fetch_description(client, sem, job_obj)
            if desc:
                job_obj.description = desc
            return job_obj

        wrapped_tasks = [fetch_and_assign(j) for j in jobs]
        
        for task in asyncio.as_completed(wrapped_tasks):
            await task
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
            
    # Filter out ones that failed
    successful = [j for j in jobs if j.description]
    if len(successful) < len(jobs):
        logger.warning("Failed to fetch descriptions for %d jobs (they will be skipped)", len(jobs) - len(successful))
        
    return successful
