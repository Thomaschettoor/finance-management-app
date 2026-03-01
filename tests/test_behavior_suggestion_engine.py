"""
Unit tests for the Behavioral Suggestion Engine.

Tests cover pure computation functions only — no DB calls.

Tested functions:
  - compute_category_stats()
  - score_category()
  - generate_suggestions() — history guard path (DB mocked)

Design: deterministic, no mocking needed (except history guard tests).
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from backend_supabase.behavior_suggestion_engine import (
    compute_category_stats,
    score_category,
    generate_suggestions,
    MIN_HISTORY_RECORDS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dt(year=2026, month=1, day=1, hour=12, minute=0) -> datetime:
    """Convenience: create a tz-aware datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _records_from(amounts, hours, dates) -> list[dict]:
    return [
        {"amount": a, "hour": h, "date": d}
        for a, h, d in zip(amounts, hours, dates)
    ]


# ── compute_category_stats ────────────────────────────────────────────────────

class TestComputeCategoryStats(unittest.TestCase):

    def test_basic_avg_amount(self):
        records = _records_from(
            amounts=[100, 200, 150],
            hours=[12.0, 13.0, 14.0],
            dates=[_dt(day=1), _dt(day=2), _dt(day=3)],
        )
        s = compute_category_stats(records)
        self.assertAlmostEqual(s["avg_amount"], 150.0, places=2)

    def test_basic_avg_hour(self):
        records = _records_from(
            amounts=[100, 100],
            hours=[10.0, 14.0],
            dates=[_dt(day=1), _dt(day=2)],
        )
        s = compute_category_stats(records)
        self.assertAlmostEqual(s["avg_hour"], 12.0, places=2)

    def test_amount_std_dev_single_record(self):
        """Single record: stdev is undefined → should be 0.0, not raise."""
        records = [{"amount": 500.0, "hour": 9.0, "date": _dt(day=1)}]
        s = compute_category_stats(records)
        self.assertEqual(s["amount_std_dev"], 0.0)

    def test_recurrence_interval_monthly(self):
        """Records 30 days apart → monthly_recurring_flag = True."""
        records = _records_from(
            amounts=[18000, 18000, 18000],
            hours=[10.0, 10.0, 10.0],
            dates=[_dt(month=1, day=1), _dt(month=2, day=1), _dt(month=3, day=1)],
        )
        s = compute_category_stats(records)
        self.assertTrue(s["monthly_recurring_flag"])
        self.assertIsNotNone(s["recurrence_interval_days"])
        self.assertGreaterEqual(s["recurrence_interval_days"], 28)
        self.assertLessEqual(s["recurrence_interval_days"], 32)

    def test_recurrence_interval_weekly_not_monthly(self):
        """Records 7 days apart → monthly_recurring_flag = False."""
        records = _records_from(
            amounts=[500, 500, 500, 500],
            hours=[12.0, 12.0, 12.0, 12.0],
            dates=[
                _dt(month=1, day=1),
                _dt(month=1, day=8),
                _dt(month=1, day=15),
                _dt(month=1, day=22),
            ],
        )
        s = compute_category_stats(records)
        self.assertFalse(s["monthly_recurring_flag"])

    def test_last_date_is_most_recent(self):
        dates = [_dt(day=3), _dt(day=1), _dt(day=5), _dt(day=2)]
        records = _records_from([100] * 4, [12.0] * 4, dates)
        s = compute_category_stats(records)
        self.assertEqual(s["last_date"], _dt(day=5))

    def test_no_recurrence_for_single_record(self):
        """One transaction: interval is undefined, monthly_flag False."""
        records = [{"amount": 200.0, "hour": 8.0, "date": _dt(day=10)}]
        s = compute_category_stats(records)
        self.assertFalse(s["monthly_recurring_flag"])
        self.assertIsNone(s["recurrence_interval_days"])

    def test_count_matches_input(self):
        records = _records_from([100, 200, 300], [12.0] * 3, [_dt(day=i) for i in range(1, 4)])
        s = compute_category_stats(records)
        self.assertEqual(s["count"], 3)


# ── score_category ────────────────────────────────────────────────────────────

class TestScoreCategory(unittest.TestCase):

    def _food_stats(self) -> dict:
        """Simulate a 'Food & Dining' profile: avg ₹150, avg 1 PM, not monthly."""
        records = _records_from(
            amounts=[120, 130, 140, 150, 160, 170, 180] * 3,   # 21 records
            hours=  [12.0, 12.5, 13.0, 13.25, 13.5, 14.0, 12.0] * 3,
            dates=  [_dt(day=i) for i in range(1, 22)],
        )
        return compute_category_stats(records)

    def _rent_stats(self) -> dict:
        """Simulate a 'Rent' profile: avg ₹18000, once per month, 1st of month."""
        records = _records_from(
            amounts=[18000, 18000, 18000],
            hours=[10.0, 10.0, 10.0],
            dates=[_dt(month=1, day=1), _dt(month=2, day=1), _dt(month=3, day=1)],
        )
        return compute_category_stats(records)

    def test_perfect_amount_match_scores_high(self):
        """Transaction amount = avg_amount → amount_similarity = 1.0."""
        stats = self._food_stats()
        avg = stats["avg_amount"]
        s = score_category(
            stats,
            new_amount=avg,         # perfect match
            new_hour=stats["avg_hour"],
            new_date=_dt(month=4, day=15, hour=13),
            freq_last_30d=20,
            total_last_30d=25,
        )
        self.assertGreater(s, 0.7)

    def test_rent_low_score_for_small_amount(self):
        """₹150 transaction against ₹18000 rent profile → low score."""
        stats = self._rent_stats()
        s = score_category(
            stats,
            new_amount=150.0,
            new_hour=13.0,
            new_date=_dt(month=4, day=15, hour=13),
            freq_last_30d=1,
            total_last_30d=25,
        )
        self.assertLess(s, 0.30)

    def test_food_beats_rent_for_small_lunchtime_txn(self):
        """
        Spec example: ₹150 at 1:15 PM → Food should score much higher than Rent.
        """
        food_stats = self._food_stats()
        rent_stats = self._rent_stats()
        new_date = _dt(month=4, day=15, hour=13, minute=15)

        food_score = score_category(
            food_stats,
            new_amount=150.0,
            new_hour=13.25,
            new_date=new_date,
            freq_last_30d=20,
            total_last_30d=25,
        )
        rent_score = score_category(
            rent_stats,
            new_amount=150.0,
            new_hour=13.25,
            new_date=new_date,
            freq_last_30d=1,
            total_last_30d=25,
        )
        self.assertGreater(food_score, rent_score)
        # Food should be noticeably higher, not just marginally
        self.assertGreater(food_score - rent_score, 0.3)

    def test_score_bounded_0_to_1(self):
        """Score must always be in [0, 1]."""
        stats = self._food_stats()
        for amount in [0, 1, 50, 150, 10_000, 100_000]:
            s = score_category(
                stats,
                new_amount=float(amount),
                new_hour=13.0,
                new_date=_dt(month=4, day=15),
                freq_last_30d=5,
                total_last_30d=20,
            )
            self.assertGreaterEqual(s, 0.0, f"score negative for amount={amount}")
            self.assertLessEqual(s, 1.0,    f"score > 1 for amount={amount}")

    def test_zero_total_history_no_division_error(self):
        """If there's no history, frequency_weight = 0, no ZeroDivisionError."""
        stats = self._food_stats()
        try:
            s = score_category(
                stats,
                new_amount=150.0,
                new_hour=13.0,
                new_date=_dt(month=4, day=15),
                freq_last_30d=0,
                total_last_30d=0,   # ← would divide-by-zero if unguarded
            )
        except ZeroDivisionError:
            self.fail("score_category raised ZeroDivisionError with total_last_30d=0")
        self.assertGreaterEqual(s, 0.0)

    def test_frequency_weight_proportional(self):
        """Higher frequency → higher final score (all else equal)."""
        stats = self._food_stats()
        new_date = _dt(month=4, day=15, hour=13)

        score_low_freq  = score_category(stats, 150.0, 13.0, new_date, freq_last_30d=1,  total_last_30d=20)
        score_high_freq = score_category(stats, 150.0, 13.0, new_date, freq_last_30d=18, total_last_30d=20)
        self.assertGreater(score_high_freq, score_low_freq)

    def test_recurrence_similarity_triggers_correctly(self):
        """Monthly profile + transaction ~30 days after last → recurrence_similarity = 1."""
        # Build a monthly recurring profile
        base = _dt(month=1, day=1)
        records = _records_from(
            amounts=[18000, 18000, 18000, 18000],
            hours=[10.0] * 4,
            dates=[base, base + timedelta(days=30), base + timedelta(days=60), base + timedelta(days=90)],
        )
        stats = compute_category_stats(records)
        self.assertTrue(stats["monthly_recurring_flag"])

        # New transaction ~30 days after last (day=90+30=120)
        new_date = base + timedelta(days=120)
        s_with_recurrence = score_category(
            stats,
            new_amount=18000.0,
            new_hour=10.0,
            new_date=new_date,
            freq_last_30d=1,
            total_last_30d=2,
        )
        # New transaction 15 days after last (doesn't match ±3 window around 30d)
        new_date_off = base + timedelta(days=105)
        s_without_recurrence = score_category(
            stats,
            new_amount=18000.0,
            new_hour=10.0,
            new_date=new_date_off,
            freq_last_30d=1,
            total_last_30d=2,
        )
        self.assertGreater(s_with_recurrence, s_without_recurrence)

    def test_amount_similarity_exact_zero_amount(self):
        """avg_amount=0: denominator clamped to 1 to avoid divide-by-zero."""
        records = [{"amount": 0.0, "hour": 12.0, "date": _dt(day=1)},
                   {"amount": 0.0, "hour": 12.0, "date": _dt(day=2)}]
        stats = compute_category_stats(records)
        try:
            s = score_category(stats, 0.0, 12.0, _dt(day=3), 1, 5)
        except ZeroDivisionError:
            self.fail("ZeroDivisionError when avg_amount=0")
        self.assertGreaterEqual(s, 0.0)

    def test_score_formula_weights_sum_to_1(self):
        """
        Verify the formula weights: 0.4 + 0.2 + 0.2 + 0.2 = 1.0 (maximum score).
        A txn that is a perfect match on all 4 dimensions should yield 1.0.
        """
        # Build a monthly recurring profile
        base = _dt(month=1, day=1)
        records = _records_from(
            amounts=[500, 500, 500, 500],
            hours=[12.0] * 4,
            dates=[base, base + timedelta(days=30), base + timedelta(days=60), base + timedelta(days=90)],
        )
        stats = compute_category_stats(records)
        self.assertTrue(stats["monthly_recurring_flag"])

        # New txn: perfect amount, perfect hour, perfect recurrence window
        new_date = base + timedelta(days=120)   # exactly 30d after last
        s = score_category(
            stats,
            new_amount=500.0,       # = avg_amount → amount_similarity = 1
            new_hour=12.0,          # = avg_hour   → time_similarity   = 1
            new_date=new_date,      # = 30d after last → recurrence     = 1
            freq_last_30d=10,
            total_last_30d=10,      # freq = 10/10 = 1 → freq_weight    = 1
        )
        self.assertAlmostEqual(s, 1.0, places=4)


# ── History guard (generate_suggestions) ─────────────────────────────────────

CAT_A = "31dd2d93-0000-0000-0000-000000000001"
CAT_B = "31dd2d93-0000-0000-0000-000000000002"
USER  = "user-0000-0000-0000-000000000001"


def _fake_txn_rows(n: int, amount=150.0, days_ago_start=1) -> list[dict]:
    """Generate n fake transaction rows."""
    base = datetime(2026, 1, 31, 13, 0, tzinfo=timezone.utc)
    return [
        {
            "id": f"txn-{i:04d}",
            "amount": amount,
            "transaction_date": (base - timedelta(days=days_ago_start + i)).isoformat(),
            "created_at":       (base - timedelta(days=days_ago_start + i)).isoformat(),
        }
        for i in range(n)
    ]


def _cat_map_for(rows: list[dict], cat_id: str) -> dict:
    return {r["id"]: cat_id for r in rows}


class TestHistoryGuard(unittest.TestCase):
    """Tests for the MIN_HISTORY_RECORDS gate inside generate_suggestions()."""

    def _call(self, txn_rows, cat_map):
        """Helper: call generate_suggestions with mocked _fetch_history."""
        txn = {
            "transaction_id": "new-txn-0001",
            "amount": 150.0,
            "timestamp": datetime(2026, 2, 1, 13, 0, tzinfo=timezone.utc),
        }
        with patch(
            "backend_supabase.behavior_suggestion_engine._fetch_history",
            return_value=(txn_rows, cat_map),
        ):
            return generate_suggestions(USER, txn)

    def test_constant_value(self):
        """MIN_HISTORY_RECORDS must be exactly 5."""
        self.assertEqual(MIN_HISTORY_RECORDS, 5)

    def test_empty_history_returns_empty_suggestions(self):
        """Zero history → empty suggestions, no crash."""
        result = self._call([], {})
        self.assertEqual(result["suggestions"], [])
        self.assertTrue(result["requires_user_confirmation"])

    def test_below_threshold_returns_empty(self):
        """4 categorized transactions (< 5) → engine skips, returns empty."""
        rows = _fake_txn_rows(4)
        cat_map = _cat_map_for(rows, CAT_A)
        result = self._call(rows, cat_map)
        self.assertEqual(result["suggestions"], [],
                         "Expected empty suggestions for < MIN_HISTORY_RECORDS")

    def test_exactly_at_threshold_produces_suggestions(self):
        """Exactly 5 categorized transactions → engine runs, non-empty suggestions."""
        rows = _fake_txn_rows(5)
        cat_map = _cat_map_for(rows, CAT_A)
        result = self._call(rows, cat_map)
        # With 5 records in one category there should be 1 suggestion
        self.assertGreater(len(result["suggestions"]), 0)
        self.assertTrue(result["requires_user_confirmation"])

    def test_above_threshold_produces_suggestions(self):
        """10 transactions across 2 categories → up to 2 suggestions returned."""
        rows_a = _fake_txn_rows(6, amount=150.0, days_ago_start=1)
        rows_b = _fake_txn_rows(4, amount=800.0, days_ago_start=30)
        all_rows = rows_a + rows_b
        cat_map = {**_cat_map_for(rows_a, CAT_A), **_cat_map_for(rows_b, CAT_B)}
        result = self._call(all_rows, cat_map)
        self.assertGreater(len(result["suggestions"]), 0)
        # Suggestions are sorted descending by confidence
        confs = [s["confidence"] for s in result["suggestions"]]
        self.assertEqual(confs, sorted(confs, reverse=True))

    def test_requires_user_confirmation_always_true(self):
        """requires_user_confirmation must be True regardless of history size."""
        # Below threshold
        result_low = self._call([], {})
        self.assertTrue(result_low["requires_user_confirmation"])
        # Above threshold
        rows = _fake_txn_rows(10)
        cat_map = _cat_map_for(rows, CAT_A)
        result_high = self._call(rows, cat_map)
        self.assertTrue(result_high["requires_user_confirmation"])


if __name__ == "__main__":
    unittest.main()
