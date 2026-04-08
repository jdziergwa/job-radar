"""Output layer — terminal, markdown reports, and optional Telegram.

Produces colored terminal output, daily markdown reports, and (if configured)
Telegram notifications for top matches.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import ScoredJob

logger = logging.getLogger(__name__)

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _score_color(score: int) -> str:
    """Return ANSI color code based on score."""
    if score >= 80:
        return GREEN
    elif score >= 60:
        return YELLOW
    return RED


def _score_emoji(score: int) -> str:
    """Return emoji based on score."""
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    return "🔴"


def _format_normalization_audit(audit: dict[str, object] | None) -> str:
    """Format a concise normalization audit summary for user-facing output."""
    if not audit:
        return ""

    raw_fit = audit.get("raw_fit_score")
    weighted_fit = audit.get("weighted_fit_score")
    normalized_fit = audit.get("normalized_fit_score")
    raw_priority = audit.get("raw_apply_priority")
    normalized_priority = audit.get("normalized_apply_priority")
    raw_skip = audit.get("raw_skip_reason")
    normalized_skip = audit.get("normalized_skip_reason")

    parts = []
    if raw_fit != normalized_fit:
        parts.append(f"fit {raw_fit} -> {normalized_fit} (weighted {weighted_fit})")
    if raw_priority != normalized_priority:
        parts.append(f"priority {raw_priority} -> {normalized_priority}")
    if raw_skip != normalized_skip:
        parts.append(f"skip {raw_skip} -> {normalized_skip}")

    return "; ".join(parts)


def _format_fit_category(fit_category: str) -> str:
    labels = {
        "core_fit": "Core fit",
        "adjacent_stretch": "Adjacent stretch",
        "conditional_fit": "Conditional fit",
        "strategic_exception": "Strategic exception",
    }
    return labels.get(fit_category or "", "")


# ── Terminal Output ─────────────────────────────────────────────────


def print_results(jobs: list[ScoredJob], title: str = "Job Radar") -> None:
    """Print scored jobs to terminal with color coding."""
    if not jobs:
        print(f"\n{DIM}  No matches found.{RESET}\n")
        return

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  {title} — {len(jobs)} matches found{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    for i, job in enumerate(jobs, 1):
        color = _score_color(job.fit_score)

        print(f"  {color}{BOLD}[{job.fit_score}%]{RESET} {job.title}")
        print(f"        {DIM}{job.company_name} · {job.location}{RESET}")
        if job.reasoning:
            # Truncate reasoning for terminal
            reason = job.reasoning[:120]
            if len(job.reasoning) > 120:
                reason += "..."
            print(f"        {reason}")
        fit_category = _format_fit_category(job.fit_category)
        if fit_category:
            print(f"        {DIM}Fit category: {fit_category}{RESET}")
        audit_note = _format_normalization_audit(job.normalization_audit)
        if audit_note:
            print(f"        {DIM}Normalization audit: {audit_note}{RESET}")
        print(f"        {DIM}{job.url}{RESET}")
        if job.red_flags:
            print(f"        {YELLOW}⚠ {', '.join(job.red_flags)}{RESET}")
        if job.key_matches:
            print(f"        {GREEN}✓ {', '.join(job.key_matches[:5])}{RESET}")
        print()


def print_stats(stats: dict[str, Any]) -> None:
    """Print database statistics to terminal."""
    print(f"\n{BOLD}{'=' * 40}{RESET}")
    print(f"{BOLD}  Job Radar — Database Stats{RESET}")
    print(f"{BOLD}{'=' * 40}{RESET}\n")

    print(f"  Total jobs:    {stats['total_jobs']}")
    print(f"  New today:     {stats['new_today']}")
    print(f"  Scored:        {stats['scored']}")
    print(f"  Applied:       {stats['applied']}")
    print(f"  Dismissed:     {stats['dismissed']}")
    print(f"  Closed/stale:  {stats['closed']}")

    dist = stats.get("score_distribution", {})
    if any(dist.values()):
        print(f"\n  {BOLD}Score Distribution:{RESET}")
        for bucket, count in dist.items():
            if count > 0:
                bar = "█" * min(count, 30)
                print(f"    {bucket:>6}: {bar} {count}")
    print()


def print_scan_summary(scan_stats: dict[str, Any]) -> None:
    """Print the high-level summary of the current scan to the terminal."""
    print(f"\n{BOLD}  📊 Scan Summary{RESET}")
    print(f"  • Sources:             {scan_stats.get('sources', 'Unknown')}")
    if "total_market_jobs" in scan_stats:
        print(f"  • Total market jobs:   {scan_stats['total_market_jobs']:,}")
    print(f"  • New jobs found:      {scan_stats.get('new_jobs', 0)}")
    print(f"  • Sent to AI:          {scan_stats.get('candidates', 0)}\n")


def print_candidates(candidates: list[Any], label: str = "DRY RUN") -> None:
    """Print candidate jobs that would be scored."""
    print(f"\n{BOLD}[{label}]{RESET} {len(candidates)} candidates would be scored:\n")
    for job in candidates:
        print(f"  • {job.title}")
        print(f"    {DIM}{job.company_name} · {job.location}{RESET}")
        print(f"    {DIM}{job.url}{RESET}")
        print()


# ── Markdown Report ─────────────────────────────────────────────────


def write_report(
    scored_jobs: list[ScoredJob],
    profile_name: str = "default",
    scan_stats: dict[str, Any] | None = None,
) -> Path:
    """Write a daily markdown report to reports/{profile_name}/YYYY-MM-DD.md."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    report_dir = Path("reports") / profile_name
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{today}.md"

    sorted_jobs = sorted(scored_jobs, key=lambda j: j.fit_score, reverse=True)

    lines: list[str] = []
    lines.append(f"# Job Radar Report — {today}\n")

    # Summary
    lines.append("## Summary\n")
    if scan_stats:
        lines.append(f"- Sources: {scan_stats.get('sources', '?')}")
        lines.append(f"- New jobs found: {scan_stats.get('new_jobs', '?')}")
        lines.append(f"- Passed pre-filter: {scan_stats.get('candidates', '?')}")

    high = sum(1 for j in sorted_jobs if j.fit_score >= 80)
    medium = sum(1 for j in sorted_jobs if 60 <= j.fit_score < 80)
    low = sum(1 for j in sorted_jobs if j.fit_score < 60)
    lines.append(f"- Scored 80%+: {high}")
    lines.append(f"- Scored 60-79%: {medium}")
    lines.append(f"- Scored <60%: {low}")
    lines.append("")

    # Top matches
    if sorted_jobs:
        lines.append("## Matches\n")
        for job in sorted_jobs:
            emoji = _score_emoji(job.fit_score)
            lines.append(f"### {emoji} {job.fit_score}% — {job.title} ({job.company_name})\n")
            lines.append(f"- **Location:** {job.location or 'Not specified'}")
            if job.breakdown:
                for dim, score in job.breakdown.items():
                    dim_label = dim.replace("_", " ").title()
                    lines.append(f"- **{dim_label}:** {score}%")
            if job.reasoning:
                lines.append(f"- **Assessment:** {job.reasoning}")
            fit_category = _format_fit_category(job.fit_category)
            if fit_category:
                lines.append(f"- **Fit category:** {fit_category}")
            audit_note = _format_normalization_audit(job.normalization_audit)
            if audit_note:
                lines.append(f"- **Normalization audit:** {audit_note}")
            if job.key_matches:
                lines.append(f"- **Key matches:** {', '.join(job.key_matches)}")
            if job.red_flags:
                lines.append(f"- **Red flags:** {', '.join(job.red_flags)}")
            lines.append(f"- **Priority:** {job.apply_priority.upper()}")
            lines.append(f"- [Apply →]({job.url})")
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report written to %s", report_path)
    return report_path


# ── Telegram (Optional) ────────────────────────────────────────────


async def send_telegram(
    jobs: list[ScoredJob],
    top_n: int = 5,
) -> None:
    """Send top matches to Telegram. Silently skips if not configured."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.debug("Telegram not configured — skipping")
        return

    top_jobs = sorted(jobs, key=lambda j: j.fit_score, reverse=True)[:top_n]
    if not top_jobs:
        return

    # Build message
    lines = [f"🔍 *Job Radar — {len(top_jobs)} top matches*\n"]
    for job in top_jobs:
        emoji = _score_emoji(job.fit_score)
        lines.append(f"{emoji} *{job.fit_score}%* — [{job.title}]({job.url})")
        lines.append(f"   {job.company_name} · {job.location}")
        if job.reasoning:
            lines.append(f"   _{job.reasoning[:80]}_")
        lines.append("")

    message = "\n".join(lines)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram message sent (%d jobs)", len(top_jobs))
            else:
                logger.warning("Telegram API error: %d %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
