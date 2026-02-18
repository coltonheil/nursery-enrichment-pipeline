#!/usr/bin/env python3
"""
Overnight Pipeline Orchestrator v2
====================================
7-stage, segment-aware pipeline for nursery/cannabis/hemp lead enrichment.

Stages (idempotent — safe to re-run):
  1  Google Places enrichment    (leads without enriched_at)
  2  Web scraping                (leads with website but no scraped_at)
  3  Gemini AI enrichment        (leads with scraped text but no gemini_enriched_at)
  4  Scoring                     (leads without scored_at)
  5  Email hunting               (leads with domain but no email_hunt_attempted)
  6  Reoon email verification    (leads with email but email_verified IS NULL)
  7  Sync to Supabase            (Tier A/B leads with verified emails)

Usage:
    python overnight_pipeline.py [options]

Options:
    --segment nursery|cannabis_grower|hemp_producer|all  (default: all)
    --tier A|B|C|U         Restrict to one tier across all stages
    --test                 Process only 10 leads per stage (validation run)
    --stage N              Start from stage N (1-7), skip earlier stages
    --dry-run              Stage 7: preview what would sync, no writes
    --skip-sync            Skip stage 7 entirely
"""

import sys
import os
import sqlite3
import time
import json
import argparse
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# ── Path setup (must precede local imports) ──────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(line_buffering=True)

# ── Secret / env loading (before any module imports that read os.environ) ────
SECRETS_FILE = Path.home() / ".openclaw" / ".secrets" / "master.env"
PROJECT_ENV  = Path(__file__).parent / ".env"

def _load_env_file(path: Path) -> None:
    """Parse KEY=VALUE from a shell env file and inject into os.environ."""
    if not path.exists():
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_env_file(SECRETS_FILE)  # master.env (highest priority)
_load_env_file(PROJECT_ENV)   # project .env fills remaining gaps

# ── Enrichment module imports ─────────────────────────────────────────────────
from enrichment.google_places      import enrich_business
from enrichment.web_scraper        import scrape_and_extract
from enrichment.gemini_client      import enrich_lead_with_gemini
from enrichment.scorer             import score_lead
from enrichment.email_hunter       import hunt_email
from enrichment.email_verifier_api import verify_email
from database.models               import (
    get_db_connection,
    update_enriched_data,
    update_scrape_data,
    update_gemini_data,
    update_gemini_error,
    update_lead_score,
)

# ── Constants ─────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "data" / "leads.db"

RATE = {
    "places":  0.5,   # Google Places API
    "scraper": 0.5,   # Web scraper (module has its own internal delay too)
    "gemini":  0.5,   # Gemini API
    "reoon":   1.0,   # Reoon email verification (API rate limit)
}

TIER_ORDER   = ("A", "B", "C", "U")
TEST_LIMIT   = 10    # Leads per stage in --test mode
PROGRESS_INT = 25    # Print progress banner every N leads

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def _banner(stage: int, name: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f"  STAGE {stage}: {name}", flush=True)
    print(f"{'='*60}", flush=True)


def _progress(stage: int, name: str, done: int, ok: int, failed: int) -> None:
    print(
        f"  ── [{done:>4} processed │ {ok:>4} ok │ {failed:>4} failed] ──",
        flush=True,
    )

# ── DB helpers ────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _query(sql: str, params: list) -> List[Dict]:
    conn = _db()
    cur  = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _seg_clause(segment: str) -> Tuple[str, list]:
    """Return (SQL fragment, params) for segment filtering."""
    if segment == "all":
        return "", []
    return "AND segment = ?", [segment]


def _tier_clause(tier: Optional[str]) -> Tuple[str, list]:
    """Return (SQL fragment, params) for tier filtering."""
    if tier:
        return "AND COALESCE(tier_override, tier) = ?", [tier]
    return (
        "AND COALESCE(tier_override, tier) IN ('A','B','C','U')",
        [],
    )


def _tier_order_expr() -> str:
    return "CASE COALESCE(tier_override,tier) WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END, id"


def _exec_sql(sql: str, params: list) -> None:
    conn = _db()
    conn.execute(sql, params)
    conn.commit()
    conn.close()

# ── DB migrations (idempotent — adds columns the new pipeline needs) ──────────

def _ensure_columns() -> None:
    """Add any columns the v2 pipeline needs that may not exist yet."""
    needed = [
        # Stage 1 idempotency marker (more explicit than enriched_at)
        ("google_enriched_at", "TIMESTAMP DEFAULT NULL"),
        # Stage 6
        ("email_verified",            "BOOLEAN DEFAULT NULL"),
        ("email_verification_result", "TEXT DEFAULT NULL"),
    ]
    conn = _db()
    cur  = conn.cursor()
    cur.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in cur.fetchall()}
    for col, coltype in needed:
        if col not in existing:
            try:
                cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {coltype}")
                log(f"Migration: added column {col}")
            except Exception as e:
                log(f"Migration warning ({col}): {e}", "WARN")
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: Google Places Enrichment
# ─────────────────────────────────────────────────────────────────────────────

def run_stage1_places(segment: str, tier: Optional[str], limit: int) -> Tuple[int, int]:
    """Enrich leads that haven't been through Google Places yet."""
    seg_sql, seg_params = _seg_clause(segment)
    tier_sql, tier_params = _tier_clause(tier)

    sql = f"""
        SELECT id, business_name, city, state, website
        FROM leads
        WHERE google_enriched_at IS NULL
          {seg_sql}
          {tier_sql}
        ORDER BY {_tier_order_expr()}
        LIMIT ?
    """
    leads = _query(sql, seg_params + tier_params + [limit])

    if not leads:
        log("Stage 1: no leads to enrich — all done or already enriched")
        return 0, 0

    log(f"Stage 1: {len(leads)} leads to Places-enrich")
    ok = failed = 0

    for i, lead in enumerate(leads, 1):
        lead_id = lead["id"]
        try:
            result = enrich_business(
                business_name=lead["business_name"],
                city=lead.get("city") or "",
                state=lead.get("state") or "",
            )
            if result and "error" not in result:
                update_enriched_data(lead_id, result)
                ok += 1
                log(f"  [{i}] ✓ {lead['business_name']} — rating={result.get('rating')}, "
                    f"website={'yes' if result.get('website') else 'no'}")
            else:
                err = result.get("error", "unknown") if result else "no result"
                log(f"  [{i}] ✗ {lead['business_name']} — {err}", "WARN")
                failed += 1
        except Exception as e:
            log(f"  [{i}] ✗ {lead['business_name']} — {e}", "WARN")
            failed += 1
        finally:
            # Always mark attempted so idempotency skips on next run
            _exec_sql(
                "UPDATE leads SET google_enriched_at = ? WHERE id = ?",
                [datetime.now().isoformat(), lead_id],
            )

        time.sleep(RATE["places"])

        if i % PROGRESS_INT == 0:
            _progress(1, "Google Places", i, ok, failed)

    return ok, failed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: Web Scraping
# ─────────────────────────────────────────────────────────────────────────────

def run_stage2_scrape(segment: str, tier: Optional[str], limit: int) -> Tuple[int, int]:
    """Scrape websites for leads that have a URL but no scraped_at."""
    seg_sql, seg_params = _seg_clause(segment)
    tier_sql, tier_params = _tier_clause(tier)

    sql = f"""
        SELECT id, business_name, website
        FROM leads
        WHERE website IS NOT NULL
          AND website != ''
          AND scraped_at IS NULL
          {seg_sql}
          {tier_sql}
        ORDER BY {_tier_order_expr()}
        LIMIT ?
    """
    leads = _query(sql, seg_params + tier_params + [limit])

    if not leads:
        log("Stage 2: no leads to scrape — all done or no websites")
        return 0, 0

    log(f"Stage 2: {len(leads)} leads to scrape")
    ok = failed = 0

    for i, lead in enumerate(leads, 1):
        lead_id = lead["id"]
        try:
            text, info = scrape_and_extract(lead["website"])
            if text and len(text) > 100:
                update_scrape_data(lead_id, text, "scraped")
                ok += 1
                log(f"  [{i}] ✓ {lead['business_name']} — {len(text):,} chars "
                    f"({info.get('pages_scraped', 0)} pages)")
            else:
                update_scrape_data(lead_id, None, "failed", "No usable text extracted")
                failed += 1
                log(f"  [{i}] ✗ {lead['business_name']} — no text", "WARN")
        except Exception as e:
            update_scrape_data(lead_id, None, "failed", str(e)[:200])
            log(f"  [{i}] ✗ {lead['business_name']} — {e}", "WARN")
            failed += 1

        time.sleep(RATE["scraper"])

        if i % PROGRESS_INT == 0:
            _progress(2, "Web Scraping", i, ok, failed)

    return ok, failed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3: Gemini AI Enrichment
# ─────────────────────────────────────────────────────────────────────────────

def run_stage3_gemini(segment: str, tier: Optional[str], limit: int) -> Tuple[int, int]:
    """Run Gemini enrichment on leads that have scraped text but no gemini result."""
    seg_sql, seg_params = _seg_clause(segment)
    tier_sql, tier_params = _tier_clause(tier)

    sql = f"""
        SELECT id, business_name, city, state, website_text, segment
        FROM leads
        WHERE website_text IS NOT NULL
          AND LENGTH(website_text) >= 100
          AND gemini_enriched_at IS NULL
          {seg_sql}
          {tier_sql}
        ORDER BY {_tier_order_expr()}
        LIMIT ?
    """
    leads = _query(sql, seg_params + tier_params + [limit])

    if not leads:
        log("Stage 3: no leads to Gemini-enrich — all done or no scraped text")
        return 0, 0

    log(f"Stage 3: {len(leads)} leads to Gemini-enrich")
    ok = failed = 0

    for i, lead in enumerate(leads, 1):
        lead_id  = lead["id"]
        seg_val  = lead.get("segment") or "nursery"
        try:
            enrichment = enrich_lead_with_gemini(
                website_text=lead["website_text"],
                business_name=lead["business_name"],
                city=lead.get("city") or "",
                state=lead.get("state") or "",
                segment=seg_val,
            )
            update_gemini_data(lead_id, enrichment, raw_response=enrichment)
            ok += 1
            biz_type = enrichment.get("business_type", "?")
            confidence = enrichment.get("confidence", "?")
            log(f"  [{i}] ✓ {lead['business_name']} — {biz_type} (conf={confidence})")
        except Exception as e:
            update_gemini_error(lead_id, str(e)[:200])
            log(f"  [{i}] ✗ {lead['business_name']} — {e}", "WARN")
            failed += 1

        time.sleep(RATE["gemini"])

        if i % PROGRESS_INT == 0:
            _progress(3, "Gemini Enrichment", i, ok, failed)

    return ok, failed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4: Scoring
# ─────────────────────────────────────────────────────────────────────────────

def run_stage4_score(segment: str, tier: Optional[str], limit: int) -> Tuple[int, int]:
    """Score leads that have Gemini data but no scored_at."""
    seg_sql, seg_params = _seg_clause(segment)
    tier_sql, tier_params = _tier_clause(tier)

    # Score leads that:
    #   a) have gemini enrichment, OR
    #   b) have basic business data (even without Gemini) — so no lead is left unscored
    # Idempotency: skip if scored_at is already set
    sql = f"""
        SELECT id, business_name, city, state, segment,
               business_type, is_wholesale, is_retail,
               greenhouse_sqft, acreage, multiple_locations,
               container_production, soil_relevance, organic_focus,
               is_organic_certified, uses_growing_media, production_method,
               scale_indicators, purchases_soil, soil_brands_mentioned,
               disqualification_signals, negative_indicators,
               appointment_only,
               crops_grown, size_signals, tier
        FROM leads
        WHERE scored_at IS NULL
          AND (gemini_enriched_at IS NOT NULL OR website_text IS NOT NULL OR website IS NOT NULL)
          {seg_sql}
          {tier_sql}
        ORDER BY {_tier_order_expr()}
        LIMIT ?
    """
    leads = _query(sql, seg_params + tier_params + [limit])

    if not leads:
        log("Stage 4: no leads to score — all done")
        return 0, 0

    log(f"Stage 4: {len(leads)} leads to score")
    ok = failed = 0

    for i, lead in enumerate(leads, 1):
        lead_id = lead["id"]
        try:
            result = score_lead(lead)
            update_lead_score(lead_id, result)
            ok += 1
            log(f"  [{i}] ✓ {lead['business_name']} — "
                f"Tier {result['tier']} (score={result['total']}, "
                f"icp={result.get('icp_type','?')})")
        except Exception as e:
            log(f"  [{i}] ✗ {lead['business_name']} — {e}", "WARN")
            failed += 1

        # No rate limit needed — scoring is pure computation (no API calls)
        if i % PROGRESS_INT == 0:
            _progress(4, "Scoring", i, ok, failed)

    return ok, failed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5: Email Hunting
# ─────────────────────────────────────────────────────────────────────────────

def run_stage5_email_hunt(segment: str, tier: Optional[str], limit: int) -> Tuple[int, int]:
    """Hunt emails for leads that have a domain but haven't been attempted yet."""
    seg_sql, seg_params = _seg_clause(segment)
    tier_sql, tier_params = _tier_clause(tier)

    sql = f"""
        SELECT id, business_name, owner_name,
               website, website_text, places_email, segment
        FROM leads
        WHERE (website IS NOT NULL AND website != '')
          AND (email_hunt_attempted = 0 OR email_hunt_attempted IS NULL)
          {seg_sql}
          {tier_sql}
        ORDER BY {_tier_order_expr()}
        LIMIT ?
    """
    leads = _query(sql, seg_params + tier_params + [limit])

    if not leads:
        log("Stage 5: no leads to email-hunt — all done or no websites")
        return 0, 0

    log(f"Stage 5: {len(leads)} leads to email-hunt")
    ok = failed = 0

    for i, lead in enumerate(leads, 1):
        lead_id   = lead["id"]
        owner_name = lead.get("owner_name") or ""
        now = datetime.now().isoformat()

        try:
            result = hunt_email(
                owner_name=owner_name,
                business_name=lead["business_name"],
                website=lead.get("website"),
                website_text=lead.get("website_text"),
                places_email=lead.get("places_email"),
                enable_web_search=True,
                verify_mx=True,
                verify_email_result=False,  # Verification handled in Stage 6 (Reoon)
            )

            conn = _db()
            cur  = conn.cursor()

            if result.email:
                ok += 1
                log(f"  [{i}] ✓ {lead['business_name']} — {result.email} "
                    f"(method={result.method}, conf={result.confidence})")
                cur.execute("""
                    UPDATE leads SET
                        owner_email          = COALESCE(owner_email, ?),
                        contact_email        = COALESCE(contact_email, ?),
                        email_source         = ?,
                        email_method         = ?,
                        email_confidence     = ?,
                        generic_email        = COALESCE(generic_email, ?),
                        contact_page_text    = COALESCE(contact_page_text, ?),
                        email_hunt_attempted = 1,
                        email_found_at       = ?
                    WHERE id = ?
                """, [
                    result.email,
                    result.email,
                    result.method,
                    result.method,
                    result.confidence,
                    result.generic_email,
                    result.contact_page_text,
                    now,
                    lead_id,
                ])
            else:
                failed += 1
                log(f"  [{i}] – {lead['business_name']} — no email found "
                    f"(domain_valid={result.domain_valid}, "
                    f"err={result.error})", "WARN")
                cur.execute("""
                    UPDATE leads SET
                        email_hunt_attempted = 1,
                        generic_email        = COALESCE(generic_email, ?),
                        contact_form_url     = COALESCE(contact_form_url, ?)
                    WHERE id = ?
                """, [result.generic_email, result.contact_form_url, lead_id])

            conn.commit()
            conn.close()

        except Exception as e:
            # Mark attempted so we don't loop forever on broken leads
            _exec_sql(
                "UPDATE leads SET email_hunt_attempted = 1 WHERE id = ?",
                [lead_id],
            )
            log(f"  [{i}] ✗ {lead['business_name']} — {e}", "WARN")
            failed += 1

        # Tavily has internal rate limiting; add a small buffer
        time.sleep(0.2)

        if i % PROGRESS_INT == 0:
            _progress(5, "Email Hunting", i, ok, failed)

    return ok, failed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 6: Reoon Email Verification
# ─────────────────────────────────────────────────────────────────────────────

def run_stage6_verify(segment: str, tier: Optional[str], limit: int) -> Tuple[int, int]:
    """Verify emails via Reoon for leads that have an email but no verification result."""
    seg_sql, seg_params = _seg_clause(segment)
    tier_sql, tier_params = _tier_clause(tier)

    sql = f"""
        SELECT id, business_name,
               COALESCE(owner_email, contact_email) AS email
        FROM leads
        WHERE (owner_email IS NOT NULL OR contact_email IS NOT NULL)
          AND email_verified IS NULL
          {seg_sql}
          {tier_sql}
        ORDER BY {_tier_order_expr()}
        LIMIT ?
    """
    leads = _query(sql, seg_params + tier_params + [limit])

    if not leads:
        log("Stage 6: no leads to verify — all emails verified or no emails")
        return 0, 0

    log(f"Stage 6: {len(leads)} emails to verify via Reoon")
    ok = failed = 0

    for i, lead in enumerate(leads, 1):
        lead_id = lead["id"]
        email   = lead.get("email") or ""

        if not email or "@" not in email:
            _exec_sql(
                "UPDATE leads SET email_verified = 0 WHERE id = ?",
                [lead_id],
            )
            failed += 1
            continue

        try:
            vr = verify_email(email)
            is_good = 1 if vr.is_deliverable else 0
            vr_json = json.dumps(vr.to_dict())

            _exec_sql("""
                UPDATE leads SET
                    email_verified            = ?,
                    email_verification_result = ?,
                    email_verification        = ?
                WHERE id = ?
            """, [is_good, vr_json, vr.status, lead_id])

            if vr.is_deliverable:
                ok += 1
                log(f"  [{i}] ✓ {lead['business_name']} — {email} "
                    f"({vr.status} via {vr.provider})")
            else:
                failed += 1
                log(f"  [{i}] – {lead['business_name']} — {email} "
                    f"UNDELIVERABLE ({vr.status})", "WARN")

        except Exception as e:
            _exec_sql(
                "UPDATE leads SET email_verified = 0 WHERE id = ?",
                [lead_id],
            )
            log(f"  [{i}] ✗ {lead['business_name']} — verify error: {e}", "WARN")
            failed += 1

        time.sleep(RATE["reoon"])  # Reoon rate limit: 1 req/s

        if i % PROGRESS_INT == 0:
            _progress(6, "Reoon Verification", i, ok, failed)

    return ok, failed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 7: Sync to Supabase
# ─────────────────────────────────────────────────────────────────────────────

def run_stage7_sync(segment: str, dry_run: bool) -> Tuple[int, int]:
    """
    Sync Tier A/B leads with verified emails to Supabase.
    Calls scripts/sync_to_supabase.py as a subprocess (it handles its own
    env loading, deduplication, and batch inserts).
    """
    script = Path(__file__).parent / "scripts" / "sync_to_supabase.py"
    if not script.exists():
        log(f"Stage 7: sync script not found at {script}", "ERROR")
        return 0, 1

    cmd = [sys.executable, str(script)]
    if dry_run:
        cmd.append("--dry-run")

    log(f"Stage 7: calling {script.name}" + (" (dry-run)" if dry_run else ""))
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,   # let stdout/stderr stream live
            text=True,
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            return 1, 0
        else:
            log(f"Stage 7: sync_to_supabase.py exited with code {result.returncode}", "ERROR")
            return 0, 1
    except Exception as e:
        log(f"Stage 7: failed to run sync script — {e}", "ERROR")
        return 0, 1


# ─────────────────────────────────────────────────────────────────────────────
# Stats / Summary
# ─────────────────────────────────────────────────────────────────────────────

def _get_db_summary(segment: str) -> Dict:
    """Pull current pipeline status counts from the DB."""
    seg_sql, seg_params = _seg_clause(segment)

    sql = f"""
        SELECT
            COUNT(*)                                             AS total,
            SUM(CASE WHEN google_enriched_at IS NOT NULL THEN 1 ELSE 0 END) AS places_done,
            SUM(CASE WHEN scraped_at IS NOT NULL          THEN 1 ELSE 0 END) AS scraped,
            SUM(CASE WHEN gemini_enriched_at IS NOT NULL  THEN 1 ELSE 0 END) AS gemini_done,
            SUM(CASE WHEN scored_at IS NOT NULL           THEN 1 ELSE 0 END) AS scored,
            SUM(CASE WHEN email_hunt_attempted = 1        THEN 1 ELSE 0 END) AS email_hunted,
            SUM(CASE WHEN email_verified IS NOT NULL      THEN 1 ELSE 0 END) AS email_verified,
            SUM(CASE WHEN email_verified = 1              THEN 1 ELSE 0 END) AS email_verified_good,
            SUM(CASE WHEN COALESCE(tier_override,tier) = 'A' THEN 1 ELSE 0 END) AS tier_a,
            SUM(CASE WHEN COALESCE(tier_override,tier) = 'B' THEN 1 ELSE 0 END) AS tier_b,
            SUM(CASE WHEN COALESCE(tier_override,tier) = 'C' THEN 1 ELSE 0 END) AS tier_c,
            SUM(CASE WHEN COALESCE(tier_override,tier) = 'U' OR tier IS NULL THEN 1 ELSE 0 END) AS tier_u_or_unscored
        FROM leads
        WHERE 1=1 {seg_sql}
    """
    rows = _query(sql, seg_params)
    return rows[0] if rows else {}


def _print_summary(segment: str, stage_results: Dict[int, Tuple[int, int]]) -> None:
    db = _get_db_summary(segment)

    print(f"\n{'='*60}", flush=True)
    print(f"  PIPELINE COMPLETE  ({segment.upper()})", flush=True)
    print(f"{'='*60}", flush=True)

    STAGE_NAMES = {
        1: "Google Places",
        2: "Web Scraping",
        3: "Gemini Enrichment",
        4: "Scoring",
        5: "Email Hunting",
        6: "Reoon Verification",
        7: "Supabase Sync",
    }
    print("\nStage results (this run):", flush=True)
    for st, (ok, fail) in sorted(stage_results.items()):
        name = STAGE_NAMES.get(st, f"Stage {st}")
        total_done = ok + fail
        print(f"  Stage {st} {name:<22} {ok:>5} ok │ {fail:>4} failed │ {total_done:>5} total")

    print(f"\nDB snapshot (segment={segment}):", flush=True)
    print(f"  Total leads          : {db.get('total', 0):>7,}")
    print(f"  Places-enriched      : {db.get('places_done', 0):>7,}")
    print(f"  Scraped              : {db.get('scraped', 0):>7,}")
    print(f"  Gemini-enriched      : {db.get('gemini_done', 0):>7,}")
    print(f"  Scored               : {db.get('scored', 0):>7,}")
    print(f"  Email-hunted         : {db.get('email_hunted', 0):>7,}")
    print(f"  Email verified (all) : {db.get('email_verified', 0):>7,}")
    print(f"  Email verified (good): {db.get('email_verified_good', 0):>7,}")
    print(f"  Tier A               : {db.get('tier_a', 0):>7,}")
    print(f"  Tier B               : {db.get('tier_b', 0):>7,}")
    print(f"  Tier C               : {db.get('tier_c', 0):>7,}")
    print(f"  Unscored / U         : {db.get('tier_u_or_unscored', 0):>7,}")
    print(f"{'='*60}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Overnight Pipeline Orchestrator v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--segment",
        choices=["nursery", "cannabis_grower", "hemp_producer", "all"],
        default="all",
        help="Filter by segment (default: all)",
    )
    parser.add_argument(
        "--tier",
        choices=["A", "B", "C", "U"],
        default=None,
        help="Process only this tier across all stages",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help=f"Test mode: process {TEST_LIMIT} leads per stage only",
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=range(1, 8),
        default=1,
        metavar="N",
        help="Start from stage N (1-7), skipping earlier stages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Stage 7 only: preview sync without writing to Supabase",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip stage 7 (Supabase sync) entirely",
    )
    args = parser.parse_args()

    started_at = datetime.now()
    log("=" * 60)
    log("OVERNIGHT PIPELINE ORCHESTRATOR v2")
    log(f"  Segment   : {args.segment}")
    log(f"  Tier      : {args.tier or 'all (A→B→C→U)'}")
    log(f"  Start     : stage {args.stage}")
    log(f"  Test mode : {args.test}")
    log(f"  Dry-run   : {args.dry_run}")
    log(f"  Skip sync : {args.skip_sync}")
    log("=" * 60)

    # Apply migrations for new columns
    _ensure_columns()

    # Per-stage lead limit
    limit = TEST_LIMIT if args.test else 999_999

    stage_results: Dict[int, Tuple[int, int]] = {}

    # ── Stage 1: Google Places ────────────────────────────────────────────────
    if args.stage <= 1:
        _banner(1, "Google Places Enrichment")
        ok, fail = run_stage1_places(args.segment, args.tier, limit)
        stage_results[1] = (ok, fail)
        log(f"Stage 1 complete: {ok} enriched, {fail} failed/skipped")

    # ── Stage 2: Web Scraping ─────────────────────────────────────────────────
    if args.stage <= 2:
        _banner(2, "Web Scraping")
        ok, fail = run_stage2_scrape(args.segment, args.tier, limit)
        stage_results[2] = (ok, fail)
        log(f"Stage 2 complete: {ok} scraped, {fail} failed")

    # ── Stage 3: Gemini Enrichment ────────────────────────────────────────────
    if args.stage <= 3:
        _banner(3, "Gemini AI Enrichment")
        ok, fail = run_stage3_gemini(args.segment, args.tier, limit)
        stage_results[3] = (ok, fail)
        log(f"Stage 3 complete: {ok} enriched, {fail} failed")

    # ── Stage 4: Scoring ──────────────────────────────────────────────────────
    if args.stage <= 4:
        _banner(4, "Scoring")
        ok, fail = run_stage4_score(args.segment, args.tier, limit)
        stage_results[4] = (ok, fail)
        log(f"Stage 4 complete: {ok} scored, {fail} failed")

    # ── Stage 5: Email Hunting ────────────────────────────────────────────────
    if args.stage <= 5:
        _banner(5, "Email Hunting")
        ok, fail = run_stage5_email_hunt(args.segment, args.tier, limit)
        stage_results[5] = (ok, fail)
        log(f"Stage 5 complete: {ok} found email, {fail} no email found")

    # ── Stage 6: Reoon Verification ───────────────────────────────────────────
    if args.stage <= 6:
        _banner(6, "Reoon Email Verification")
        ok, fail = run_stage6_verify(args.segment, args.tier, limit)
        stage_results[6] = (ok, fail)
        log(f"Stage 6 complete: {ok} verified deliverable, {fail} failed/undeliverable")

    # ── Stage 7: Supabase Sync ────────────────────────────────────────────────
    if args.stage <= 7 and not args.skip_sync:
        _banner(7, "Sync to Supabase" + (" (DRY RUN)" if args.dry_run else ""))
        ok, fail = run_stage7_sync(args.segment, args.dry_run)
        stage_results[7] = (ok, fail)
        log(f"Stage 7 complete: {'dry-run' if args.dry_run else 'sync done'}")
    elif args.skip_sync:
        log("Stage 7: skipped (--skip-sync)")

    # ── Final summary ─────────────────────────────────────────────────────────
    elapsed = (datetime.now() - started_at).total_seconds()
    log(f"\nTotal elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    _print_summary(args.segment, stage_results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
