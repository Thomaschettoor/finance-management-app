"""
Behavioral Suggestion Engine
-----------------------------
Generates Top-3 category suggestions for UNCLASSIFIED transactions
based on a user's historical spending patterns.

Flow (generate_suggestions):
  1. Fetch last 90 days of categorized transactions for the user
  2. Group by category_id, compute behavioral stats per category
  3. Score each category against the new transaction
  4. Return top-3 ranked suggestions (no auto-assignment)

Scoring formula per category:
  amount_similarity     = 1 - min(|new_amount - avg_amount| / max(avg_amount, 1), 1)
  time_similarity       = 1 - min(|new_hour - avg_hour| / 24, 1)
  recurrence_similarity = 1 if matches monthly recurrence window else 0
  frequency_weight      = freq_last_30d / total_txns_last_30d

  final_score = 0.4*amount_similarity
              + 0.2*time_similarity
              + 0.2*recurrence_similarity
              + 0.2*frequency_weight

User confirmation (confirm_category):
  - Updates transaction_categorizations
  - Upserts user_behavior_profiles with recalculated metrics

IMPORTANT:
  - Do NOT call this engine for CONFIDENT_MERCHANT transactions.
  - requires_user_confirmation is ALWAYS True.
  - No auto-assignment, no model inference.
  - Engine skips scoring and returns empty suggestions when total categorized
    history for the user is < MIN_HISTORY_RECORDS (default 5). Too little
    history produces meaningless scores — better to return nothing than to
    mislead the user.

FUTURE (not implemented):
  - Global behavior patterns: if 80%+ of users categorize ₹150 at 1PM as Food,
    that signal could seed new users before they have personal history. Deferred
    until personal-history path is well-validated.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Constants ─────────────────────────────────────────────────────────────────
HISTORY_DAYS = 90
TOP_N = 3
MIN_HISTORY_RECORDS = 5       # minimum total categorized transactions required
                               # before the engine produces any suggestions.
                               # Below this threshold scores are statistically
                               # meaningless — return empty instead.
MONTHLY_RECURRENCE_MIN = 28   # days — lower bound for "monthly" pattern
MONTHLY_RECURRENCE_MAX = 32   # days — upper bound for "monthly" pattern
RECURRENCE_TOLERANCE = 3      # ±days when checking if a new txn fits the window


# ── Pure computation helpers (no DB, fully testable) ─────────────────────────

def compute_category_stats(records: list[dict]) -> dict:
    """
    Compute behavioral statistics for one category from its historical records.

    Each record must contain:
        amount : float   — transaction amount
        hour   : float   — hour of day (0–24, fractional minutes allowed)
        date   : datetime (tz-aware)

    Returns a stats dict used by score_category().
    """
    amounts = [r["amount"] for r in records if r["amount"] > 0]
    hours   = [r["hour"]   for r in records]
    dates   = sorted(r["date"] for r in records)

    avg_amount    = statistics.mean(amounts)    if amounts              else 0.0
    amount_std    = statistics.stdev(amounts)   if len(amounts) >= 2   else 0.0
    # NOTE (future): arithmetic mean breaks near midnight — e.g. hours [23, 1]
    # gives avg=12 instead of 0. Fix with circular mean when needed.
    avg_hour      = statistics.mean(hours)      if hours               else 12.0
    hour_std      = statistics.stdev(hours)     if len(hours) >= 2     else 0.0

    # Median interval between consecutive transactions
    intervals = [
        (dates[i] - dates[i - 1]).days
        for i in range(1, len(dates))
        if (dates[i] - dates[i - 1]).days > 0
    ]
    recurrence_interval = int(statistics.median(intervals)) if intervals else None
    monthly_flag = (
        recurrence_interval is not None
        and MONTHLY_RECURRENCE_MIN <= recurrence_interval <= MONTHLY_RECURRENCE_MAX
    )

    return {
        "avg_amount":               avg_amount,
        "amount_std_dev":           amount_std,
        "avg_hour":                 avg_hour,
        "hour_std_dev":             hour_std,
        "recurrence_interval_days": recurrence_interval,
        "monthly_recurring_flag":   monthly_flag,
        "last_date":                dates[-1] if dates else None,
        "count":                    len(records),
    }


def score_category(
    stats: dict,
    new_amount: float,
    new_hour: float,
    new_date: datetime,
    freq_last_30d: int,
    total_last_30d: int,
) -> float:
    """
    Compute the final behavioral score for one category given a new transaction.

    Parameters
    ----------
    stats         : output of compute_category_stats()
    new_amount    : amount of the new transaction
    new_hour      : hour of the new transaction (0–24, fractional)
    new_date      : tz-aware datetime of the new transaction
    freq_last_30d : how many times this category appeared in the last 30 days
    total_last_30d: total categorized transactions (all categories) last 30 days

    Returns
    -------
    float in [0, 1]
    """
    avg_amount          = stats["avg_amount"] or 0.0
    avg_hour            = stats["avg_hour"]   or 12.0
    monthly_flag        = stats["monthly_recurring_flag"]
    last_date           = stats["last_date"]
    recurrence_interval = stats["recurrence_interval_days"]

    # ── amount_similarity ────────────────────────────────────────────────────
    amount_similarity = 1.0 - min(
        abs(new_amount - avg_amount) / max(avg_amount, 1.0),
        1.0,
    )

    # ── time_similarity ──────────────────────────────────────────────────────
    time_similarity = 1.0 - min(abs(new_hour - avg_hour) / 24.0, 1.0)

    # ── recurrence_similarity ────────────────────────────────────────────────
    recurrence_similarity = 0.0
    if monthly_flag and last_date is not None and recurrence_interval:
        days_since = (new_date.date() - last_date.date()).days
        if abs(days_since - recurrence_interval) <= RECURRENCE_TOLERANCE:
            recurrence_similarity = 1.0

    # ── frequency_weight ─────────────────────────────────────────────────────
    frequency_weight = freq_last_30d / total_last_30d if total_last_30d > 0 else 0.0

    final_score = (
        0.4 * amount_similarity
        + 0.2 * time_similarity
        + 0.2 * recurrence_similarity
        + 0.2 * frequency_weight
    )
    return round(final_score, 4)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _parse_dt(raw: Any) -> datetime | None:
    """Parse a date string or datetime to a tz-aware datetime."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch_history(user_id: str, cutoff: datetime) -> tuple[list[dict], dict[str, str]]:
    """
    Fetch transactions + their category assignments for a user since `cutoff`.

    Returns
    -------
    txn_rows : list of raw transaction dicts from the DB
    cat_map  : {transaction_id: category_id} (only rows with a non-null category)
    """
    rows = (
        supabase.table("transactions")
        .select("id, amount, transaction_date, created_at")
        .eq("user_id", user_id)
        .gte("transaction_date", cutoff.isoformat())
        .execute()
        .data or []
    )
    if not rows:
        return [], {}

    txn_ids = [r["id"] for r in rows]
    cats = (
        supabase.table("transaction_categorizations")
        .select("transaction_id, primary_category_id")
        .in_("transaction_id", txn_ids)
        .not_.is_("primary_category_id", "null")
        .execute()
        .data or []
    )
    cat_map = {c["transaction_id"]: c["primary_category_id"] for c in cats}
    return rows, cat_map


def _rebuild_and_upsert_profile(user_id: str, category_id: str) -> None:
    """
    Re-fetch the last 90 days of history for one user-category pair,
    recompute all stats, and upsert into user_behavior_profiles.
    Called after a user confirmation.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    cutoff_30 = datetime.now(timezone.utc) - timedelta(days=30)

    txn_rows, cat_map = _fetch_history(user_id, cutoff)

    records = []
    freq_30 = 0
    for row in txn_rows:
        if cat_map.get(row["id"]) != category_id:
            continue
        raw_date = row.get("transaction_date") or row.get("created_at")
        dt = _parse_dt(raw_date)
        if dt is None:
            continue
        amt = float(row.get("amount") or 0)
        records.append({"amount": amt, "hour": dt.hour + dt.minute / 60.0, "date": dt})
        if dt >= cutoff_30:
            freq_30 += 1

    if not records:
        return

    s = compute_category_stats(records)

    supabase.table("user_behavior_profiles").upsert(
        {
            "user_id":                  user_id,
            "category_id":              category_id,
            "avg_amount":               s["avg_amount"],
            "amount_std_dev":           s["amount_std_dev"],
            "avg_hour":                 s["avg_hour"],
            "hour_std_dev":             s["hour_std_dev"],
            "monthly_recurring_flag":   s["monthly_recurring_flag"],
            "recurrence_interval_days": s["recurrence_interval_days"],
            "frequency_last_30_days":   freq_30,
        },
        on_conflict="user_id,category_id",
    ).execute()


# ── Public API ────────────────────────────────────────────────────────────────

def generate_suggestions(user_id: str, transaction: dict) -> dict:
    """
    Generate Top-3 category suggestions for an UNCLASSIFIED transaction.

    Only call this when prediction_source == "UNCLASSIFIED".
    Never call for CONFIDENT_MERCHANT transactions.

    Parameters
    ----------
    user_id     : UUID string of the user
    transaction : dict with keys:
                    "transaction_id" : str
                    "amount"         : float
                    "timestamp"      : datetime | ISO string

    Returns
    -------
    {
        "transaction_id": str,
        "suggestions": [
            {"category_id": str, "confidence": float},
            ...  # up to 3, sorted descending by confidence
        ],
        "requires_user_confirmation": True
    }
    """
    transaction_id = transaction["transaction_id"]
    new_amount     = float(transaction.get("amount") or 0.0)

    ts = transaction.get("timestamp")
    new_date = _parse_dt(ts) or datetime.now(timezone.utc)
    new_hour = new_date.hour + new_date.minute / 60.0

    cutoff_90 = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    cutoff_30 = datetime.now(timezone.utc) - timedelta(days=30)

    empty = {"transaction_id": transaction_id, "suggestions": [], "requires_user_confirmation": True}

    txn_rows, cat_map = _fetch_history(user_id, cutoff_90)
    if not txn_rows or not cat_map:
        return empty

    # Index rows by txn id for fast lookup
    txn_meta = {r["id"]: r for r in txn_rows}

    # Group historical records by category
    category_records: dict[str, list[dict]] = {}
    for hist_id, cat_id in cat_map.items():
        row = txn_meta.get(hist_id)
        if not row:
            continue
        raw_date = row.get("transaction_date") or row.get("created_at")
        dt = _parse_dt(raw_date)
        if dt is None:
            continue
        amt = float(row.get("amount") or 0)
        category_records.setdefault(cat_id, []).append(
            {"amount": amt, "hour": dt.hour + dt.minute / 60.0, "date": dt}
        )

    if not category_records:
        return empty

    # Guard: require minimum history before scoring.
    # Too few transactions → stats are unreliable (mean of 2 numbers,
    # zero std dev, etc.) → return empty so the app prompts a plain
    # manual pick rather than showing low-quality suggestions.
    total_history = sum(len(recs) for recs in category_records.values())
    if total_history < MIN_HISTORY_RECORDS:
        print(f"[BehaviorEngine] user={user_id} has only {total_history} categorized txn(s) — skipping (min={MIN_HISTORY_RECORDS})")
        return empty

    # Total categorized transactions in last 30 days (all categories combined)
    total_last_30d = sum(
        1
        for hist_id, cat_id in cat_map.items()
        if (row := txn_meta.get(hist_id))
        and (dt := _parse_dt(row.get("transaction_date") or row.get("created_at")))
        and dt >= cutoff_30
    )

    # Score each category
    scored: list[dict] = []
    for cat_id, records in category_records.items():
        stats = compute_category_stats(records)

        freq_last_30d = sum(
            1
            for hist_id, cid in cat_map.items()
            if cid == cat_id
            and (row := txn_meta.get(hist_id))
            and (dt := _parse_dt(row.get("transaction_date") or row.get("created_at")))
            and dt >= cutoff_30
        )

        s = score_category(
            stats,
            new_amount=new_amount,
            new_hour=new_hour,
            new_date=new_date,
            freq_last_30d=freq_last_30d,
            total_last_30d=total_last_30d,
        )
        scored.append({"category_id": cat_id, "confidence": s})

    scored.sort(key=lambda x: x["confidence"], reverse=True)
    suggestions = scored[:TOP_N]

    return {
        "transaction_id":          transaction_id,
        "suggestions":             suggestions,
        "requires_user_confirmation": True,
    }


def confirm_category(user_id: str, transaction_id: str, confirmed_category_id: str) -> None:
    """
    Called when a user manually confirms a category suggestion.

    Actions:
      1. Updates transaction_categorizations — sets confirmed category,
         prediction_source = 'USER_CONFIRMED', prediction_status = 'OK'
      2. Upserts user_behavior_profiles — recalculates stats for this
         user-category pair from the last 90 days of history

    Parameters
    ----------
    user_id                : UUID of the user
    transaction_id         : UUID of the transaction being confirmed
    confirmed_category_id  : UUID of the category chosen by the user
    """
    # Step 1 — update transaction_categorizations
    supabase.table("transaction_categorizations").upsert(
        {
            "transaction_id":      transaction_id,
            "user_id":             user_id,
            "primary_category_id": confirmed_category_id,
            "primary_confidence":  1.0,
            "prediction_source":   "USER_CONFIRMED",
            "prediction_status":   "OK",
        },
        on_conflict="transaction_id",
    ).execute()

    # Step 2 — rebuild and upsert the behavior profile for this category
    _rebuild_and_upsert_profile(user_id, confirmed_category_id)

    print(f"[Confirm] txn={transaction_id} -> category={confirmed_category_id} confirmed by user={user_id}")
