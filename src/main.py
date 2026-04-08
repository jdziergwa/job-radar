"""CLI orchestrator — entry point for Job Radar.

Supports multiple profiles via --profile flag. Each profile has its own
config, database, and reports directory.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.models import CandidateJob
from src.providers import PROVIDER_REGISTRY, ProviderContext
from src.prefilter import prefilter
from src.reporter import (
    print_candidates,
    print_results,
    print_stats,
    print_scan_summary,
    send_telegram,
    write_report,
)
from src.scorer import score_jobs
from src.store import Store

logger = logging.getLogger("job_radar")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, stream=sys.stderr)
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


def load_config(profile_dir: Path) -> dict[str, Any]:
    """Load search_config.yaml from the profile directory."""
    config_path = profile_dir / "search_config.yaml"
    if not config_path.exists():
        logger.error("Profile config not found: %s", config_path)
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    logger.debug("Loaded config from %s", config_path)
    return config


def load_companies(profile_dir: Path) -> dict[str, list[dict[str, str]]]:
    """Load companies.yaml from the profile directory."""
    companies_path = profile_dir / "companies.yaml"
    if not companies_path.exists():
        logger.error("Companies config not found: %s", companies_path)
        sys.exit(1)

    with open(companies_path, encoding="utf-8") as f:
        companies = yaml.safe_load(f) or {}

    total = sum(len(v) for v in companies.values())
    logger.info("Loaded %d companies from %s", total, companies_path)
    return companies


def load_profile_doc(profile_dir: Path) -> str:
    """Load profile_doc.md from the profile directory."""
    doc_path = profile_dir / "profile_doc.md"
    if not doc_path.exists():
        logger.error("Profile doc not found: %s", doc_path)
        sys.exit(1)

    return doc_path.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Job Radar — personalized job monitor powered by Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python src/main.py                          # Daily scan (default profile)
  python src/main.py --profile android-dev    # Scan with a different profile
  python src/main.py --dry-run -v             # Collect & filter only, verbose
  python src/main.py --history 7              # Show last 7 days of scores
  python src/main.py --stats                  # Database statistics
  python src/main.py --open 42               # Open job #42 in browser
  python src/main.py --mark-applied 42       # Mark job #42 as applied
""",
    )

    parser.add_argument(
        "--profile", "-p", type=str, default="default",
        help="Profile name (loads profiles/<name>/). Default: 'default'",
    )
    parser.add_argument(
        "--source", nargs="+", default=["aggregator", "local"],
        help="Data source provider name(s) (e.g. 'aggregator', 'local'). Must match registered providers.",
    )
    parser.add_argument(
        "--json-progress", action="store_true",
        help="Output structured JSON progress lines (for web UI)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Collect and filter only, skip LLM scoring",
    )
    parser.add_argument(
        "--rescore", action="store_true",
        help="Re-score previously scored jobs",
    )
    parser.add_argument(
        "--history", type=int, metavar="DAYS",
        help="Show scored jobs from last N days",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show database statistics",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "--min-score", type=int, default=50,
        help="Minimum score to display (default: 50)",
    )
    parser.add_argument(
        "--open", type=int, metavar="JOB_ID",
        help="Open a job URL in browser",
    )
    parser.add_argument(
        "--mark-applied", type=int, metavar="JOB_ID",
        help="Mark a job as 'applied'",
    )
    parser.add_argument(
        "--dismiss", type=int, metavar="JOB_ID",
        help="Dismiss a job",
    )
    parser.add_argument(
        "--stale", action="store_true",
        help="Show jobs that disappeared from ATS feeds",
    )
    parser.add_argument(
        "--job-id", type=int,
        help="Target a specific job ID for the operation",
    )

    return parser


import time

# ... (inside run() function usually, but I'll define it locally or use simple variables)
class PipelineTimer:
    def __init__(self):
        self.start_time = time.time()
        self.stage_start_time = time.time()
    
    def reset_stage(self):
        self.stage_start_time = time.time()
    
    def get_stage_duration(self):
        return time.time() - self.stage_start_time
        
    def get_total_duration(self):
        return time.time() - self.start_time

def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rem_seconds = int(seconds % 60)
    return f"{minutes}m {rem_seconds}s"


def emit_progress(step: int, name: str, detail: str = "", stats: dict | None = None, duration: float | None = None) -> None:
    """Emit structured progress for web UI."""
    import json as _json
    msg: dict = {"progress": {"step": step, "name": name}}
    if detail:
        msg["progress"]["detail"] = detail
    if stats:
        msg["progress"]["stats"] = stats
    if duration is not None:
        msg["progress"]["duration"] = duration
    print(_json.dumps(msg), flush=True)

async def run() -> None:
    """Main entry point — runs the full pipeline or handles subcommands."""
    # Load .env early
    load_dotenv()

    timer = PipelineTimer()

    parser = build_parser()
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Resolve profile paths
    profile_dir = Path("profiles") / args.profile
    if not profile_dir.exists():
        logger.error("Profile directory not found: %s", profile_dir)
        print(f"\n  ✗ Profile '{args.profile}' not found at {profile_dir}/")
        print(f"    Available profiles: {', '.join(p.name for p in Path('profiles').iterdir() if p.is_dir()) if Path('profiles').exists() else 'none'}")
        sys.exit(1)

    db_path = f"data/{args.profile}.db"
    store = Store(db_path)

    logger.info("Profile: %s | DB: %s", args.profile, db_path)

    # ── Subcommands (no collection needed) ──────────────────────────

    if args.stats:
        stats = store.get_stats()
        print_stats(stats)
        return

    if args.history is not None:
        scored = store.get_recent_scored(days=args.history, min_score=args.min_score)
        print_results(scored, title=f"Job Radar — Last {args.history} Days")
        return

    if args.open is not None:
        job = store.get_job_by_id(args.open)
        if job:
            print(f"\n  Opening: {job.title} @ {job.company_name}")
            print(f"  URL: {job.url}\n")
            webbrowser.open(job.url)
        else:
            print(f"\n  ✗ Job #{args.open} not found\n")
        return

    if args.mark_applied is not None:
        if store.update_status(args.mark_applied, "applied"):
            job = store.get_job_by_id(args.mark_applied)
            name = f"{job.title} @ {job.company_name}" if job else f"#{args.mark_applied}"
            print(f"\n  ✓ Marked as applied: {name}\n")
        else:
            print(f"\n  ✗ Job #{args.mark_applied} not found\n")
        return

    if args.dismiss is not None:
        if store.update_status(args.dismiss, "dismissed"):
            job = store.get_job_by_id(args.dismiss)
            name = f"{job.title} @ {job.company_name}" if job else f"#{args.dismiss}"
            print(f"\n  ✓ Dismissed: {name}\n")
        else:
            print(f"\n  ✗ Job #{args.dismiss} not found\n")
        return

    if args.stale:
        stale_jobs = store.get_stale(days=30)
        print_results(stale_jobs, title="Job Radar — Stale Jobs (disappeared from feeds)")
        return

    if args.job_id and not (args.rescore or args.open or args.mark_applied or args.dismiss):
        # If ONLY job_id is provided, default to 'show' or 'rescore' depending on case
        # But for pipeline use, we usually want it with --rescore.
        pass

    # ── Full pipeline ───────────────────────────────────────────────

    config = load_config(profile_dir)
    profile_doc = load_profile_doc(profile_dir)
    keywords_config = config.get("keywords", {})

    skip_collection = bool(args.job_id or args.rescore)

    # If targeting a single job ID, we skip collection and pre-filtering
    if args.job_id:
        logger.info("Targeting single job ID: %d", args.job_id)
        job = store.get_job_by_id(args.job_id)
        if not job:
            logger.error("Job #%d not found", args.job_id)
            sys.exit(1)
        
        # Convert ScoredJob back to CandidateJob for the pipeline
        candidates_raw = [CandidateJob(
            db_id=job.db_id,
            ats_platform=job.ats_platform,
            company_slug=job.company_slug,
            company_name=job.company_name,
            job_id=job.job_id,
            title=job.title,
            location=job.location,
            location_metadata=job.location_metadata,
            url=job.url,
            description=job.description,
            posted_at=job.posted_at,
            first_seen_at=job.first_seen_at
        )]
        raw_jobs = candidates_raw # For stats
        new_jobs = []
        companies_scanned = "single-job"
    elif args.rescore:
        raw_jobs = []
        new_jobs = []
        companies_scanned = "rescore-all"
        
    if skip_collection:
        # Skip collection stages in JSON progress
        if args.json_progress and not args.rescore:
            target_str = "single-job target"
            emit_progress(1, "Collecting", f"Skipping collection ({target_str})")
            emit_progress(2, "Deduplicating", f"Skipping deduplication ({target_str})")
        
    def p_callback(current, total, prefix=""):
        if args.json_progress:
            emit_progress(1, "Collecting", f"{prefix}{current}/{total}", duration=timer.get_stage_duration())

    def pre_p_callback(current, total, step=3, name="Pre-filtering", prefix=""):
        if args.json_progress:
            emit_progress(step, name, f"{prefix}{current}/{total}", duration=timer.get_stage_duration())

    if not skip_collection:
        companies = load_companies(profile_dir)
        ctx = ProviderContext(companies=companies, profile_dir=profile_dir, config=config)

        logger.info("Step 1: Collecting jobs (sources=%s)...", args.source)
        raw_jobs = []
        
        for source_name in args.source:
            if source_name not in PROVIDER_REGISTRY:
                logger.error("Unknown source '%s'. Available: %s", source_name, list(PROVIDER_REGISTRY))
                continue

            provider = PROVIDER_REGISTRY[source_name]
            logger.info("Source '%s': Fetching jobs...", provider.name)
            
            provider_jobs = await provider.fetch_jobs(
                ctx,
                progress_callback=lambda c, t, p_name=provider.display_name: p_callback(c, t, f"[{p_name}] "),
            )
            
            # Persist aggregator version metadata when available (side-channel on provider)
            if hasattr(provider, "last_updated") and provider.last_updated != "unknown":
                store.set_metadata("aggregator_version", provider.last_updated)
            
            logger.info("Source '%s': %d jobs fetched", provider.name, len(provider_jobs))
            raw_jobs.extend(provider_jobs)

        # Soft pre-filter (Title/Loc) to avoid bloating DB
        if args.json_progress:
            emit_progress(1, "Collecting", f"Filtering {len(raw_jobs)} raw candidates...")

        survivors, rejected = prefilter(
            raw_jobs, keywords_config,
            progress_callback=lambda c, t: pre_p_callback(c, t, step=1, name="Collecting"),
        )
        for rj, reason in rejected:
            rj.status = "dismissed"
            rj.dismissal_reason = reason

        all_to_save = survivors + [j for j, _ in rejected]
        if args.json_progress:
            emit_progress(2, "Deduplicating", f"Saving {len(all_to_save)} jobs...", duration=timer.get_stage_duration())
        new_jobs = store.upsert_jobs(all_to_save)
        if args.json_progress:
            emit_progress(2, "Deduplicating", f"{len(new_jobs)} new jobs identified", duration=timer.get_stage_duration())
        logger.info("Found %d new jobs (from %d raw)", len(new_jobs), len(raw_jobs))

        companies_scanned = ", ".join(args.source)
        timer.reset_stage()

    if not skip_collection:
        # Mark stale jobs (absent 7+ days)
        stale_count = store.mark_stale(stale_days=7)
        if stale_count:
            logger.info("Marked %d jobs as closed (stale)", stale_count)

    # 3. Pre-filter
    # If we have a single targeted job, we use it directly
    if args.job_id:
        pass # Already populated in candidates_raw
    elif args.rescore:
        candidates_raw = store.get_scored_for_rescore()
        logger.info("Re-scoring %d previously scored jobs", len(candidates_raw))
    else:
        # Convert new RawJobs to CandidateJobs via the store
        candidates_raw = store.get_all_new_jobs()
        logger.info("Found %d unscored jobs for filtering", len(candidates_raw))
        
    if not args.rescore:
        # Providers like aggregator/remotive/remoteok may have missing descriptions
        if candidates_raw:
            # Only fetch for those missing a description (primarily aggregator jobs)
            to_fetch = [j for j in candidates_raw if not j.description]
            if to_fetch:
                from src.fetcher import populate_descriptions
                
                def desc_p_callback(curr, tot):
                    if args.json_progress:
                        emit_progress(3, "Pre-filtering", f"Fetching Descriptions: {curr}/{tot}", duration=timer.get_stage_duration())
                
                # This updates the objects in-place
                await populate_descriptions(to_fetch, progress_callback=desc_p_callback)
                
                # Persist successfully fetched descriptions to DB for future UI/detail views
                for j in to_fetch:
                    if j.description:
                        store.update_job_description(j.db_id, j.description)

            # Filter out jobs that still have no description (fetch failed)
            # We skip these as the LLM fits will be poor without content.
            to_dismiss_no_desc = [j.db_id for j in candidates_raw if not j.description]
            if to_dismiss_no_desc:
                logger.info("Dismissing %d jobs due to missing descriptions", len(to_dismiss_no_desc))
                store.bulk_update_status(to_dismiss_no_desc, "dismissed", reason="Missing Description")
            
            candidates_raw = [j for j in candidates_raw if j.description]

        candidates, rejected = prefilter(candidates_raw, keywords_config, progress_callback=pre_p_callback)
        
        if args.json_progress:
            emit_progress(3, "Pre-filtering", f"Finalizing {len(rejected) + len(candidates)} results...")

        if rejected:
            to_dismiss_with_reasons = [(j.db_id, r) for j, r in rejected if j.db_id]
            store.bulk_update_status_with_reasons(to_dismiss_with_reasons)
        
        if args.json_progress:
            emit_progress(3, "Pre-filtering", f"{len(candidates)} candidates")
        logger.info("%d candidates after full pre-filter", len(candidates))
    else:
        # For rescore, we skip pre-filtering entirely
        candidates = candidates_raw
        logger.info("Skipping pre-filtering for rescore run (%d candidates)", len(candidates))
        if args.json_progress:
            emit_progress(0, "Starting", "Bypassing pre-filtering for rescore")

    # Choose step indexing for JSON progress
    scoring_step = 1 if args.rescore else 4
    done_step = 2 if args.rescore else 5

    scan_stats = {
        "sources": companies_scanned,
        "total_market_jobs": len(raw_jobs),
        "new_jobs": len(new_jobs),
        "candidates": len(candidates),
        "total_duration": format_duration(timer.get_total_duration()),
    }

    # 4. Dry run — stop before scoring
    if args.dry_run:
        print_scan_summary(scan_stats)
        print_candidates(candidates, label="DRY RUN")
        if args.json_progress:
            emit_progress(scoring_step, "Skipped", "Scoring skipped (Dry Run)", duration=timer.get_stage_duration())
            emit_progress(done_step, "Done", stats=scan_stats, duration=timer.get_total_duration())
        return

    # 5. Score with Claude API
    timer.reset_stage()
    if candidates:
        if args.json_progress:
            emit_progress(scoring_step, "Scoring", f"Starting LLM scoring for {len(candidates)} jobs", duration=timer.get_stage_duration())
        
        # Early check for API key
            if not os.getenv("ANTHROPIC_API_KEY"):
                error_msg = "ANTHROPIC_API_KEY not found in environment or .env file. Scoring skipped."
                logger.error(error_msg)
                if args.json_progress:
                    emit_progress(scoring_step, "Error", error_msg)
                else:
                    print(f"\n  ✗ {error_msg}\n")
                sys.exit(1)

        def score_p_callback(curr, tot):
            if args.json_progress:
                emit_progress(scoring_step, "Scoring", f"{curr}/{tot} scored", duration=timer.get_stage_duration())

        scoring_config = config.get("scoring", {})
        scored = await score_jobs(
            candidates,
            profile_doc,
            scoring_config,
            store,
            profile_dir=profile_dir,
            profile_config={
                "keywords": config.get("keywords", {}),
                "scoring_context": config.get("scoring_context", {}),
            },
            progress_callback=score_p_callback,
            concurrency=scoring_config.get("concurrency", 25),
            batch_size=scoring_config.get("batch_size", 5),
        )

        # 6. Report
        scan_stats["scored"] = len(scored)
        scan_stats["total_duration"] = format_duration(timer.get_total_duration())
        print_scan_summary(scan_stats)
        
        good_matches = [j for j in scored if j.fit_score >= args.min_score]
        good_matches.sort(key=lambda j: j.fit_score, reverse=True)

        print_results(good_matches)

        # Write markdown report (all scored, not just good)
        output_config = config.get("output", {})
        if output_config.get("markdown_report", True):
            write_report(scored, profile_name=args.profile, scan_stats=scan_stats)

        # Optional Telegram
        telegram_config = output_config.get("telegram", {})
        if telegram_config.get("enabled", False):
            top_n = telegram_config.get("top_n", 5)
            await send_telegram(good_matches, top_n=top_n)
            
        if args.json_progress:
            emit_progress(done_step, "Done", stats=scan_stats, duration=timer.get_total_duration())
    else:
        print("\n  No new candidates today. Run --history to see past results.\n")
        if args.json_progress:
            scan_stats["scored"] = 0
            scan_stats["total_duration"] = format_duration(timer.get_total_duration())
            emit_progress(done_step, "Done", stats=scan_stats, duration=timer.get_total_duration())


def main() -> None:
    """Sync wrapper for the async entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
