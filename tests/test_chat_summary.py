import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import backend_api.routes.chat as chat


# --- simple fake supabase client/table for chat summary tests ---
class DummyTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.filters = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, vals))
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        data = self.client.tables.get(self.name, [])
        out = []
        for r in data:
            ok = True
            for op, col, val in self.filters:
                rv = r.get(col)
                if op == "eq" and rv != val:
                    ok = False
                    break
                if op == "in" and rv not in val:
                    ok = False
                    break
                if op == "gte" and rv < val:
                    ok = False
                    break
            if ok:
                out.append(r)
        class R:
            pass
        res = R()
        res.data = out
        return res


class DummyClient:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return DummyTable(name, self)


# --- tests ---

def test_summary_fallback_to_master_categories(monkeypatch):
    """If the `categories` table is missing, the function should still work using
    `master_categories`."""
    fake = DummyClient(
        tables={
            "transactions": [
                {"id": "t1", "amount": 100, "merchant_name": "Store", "timestamp": "2026-03-10T00:00:00Z", "user_id": "u1"}
            ],
            "transaction_categorizations": [
                {"transaction_id": "t1", "primary_category_id": "c1"}
            ],
            # only master_categories exists here
            "master_categories": [{"id": "c1", "name": "Food"}],
        }
    )
    import backend_api.routes.transactions as transactions
    monkeypatch.setattr(chat, "_sb", fake)
    monkeypatch.setattr(transactions, "_sb", fake)

    summary = chat.get_user_transaction_summary("u1")
    assert summary["total_transactions"] == 1
    assert summary["total_amount"] == 100
    # check that category name from master_categories was used
    assert "Food" in summary["spending_by_category"]


def test_summary_uses_master_categories_when_available(monkeypatch):
    """Master_categories takes precedence over `categories` when both are present."""
    fake = DummyClient(
        tables={
            "transactions": [
                {"id": "t1", "amount": 50, "merchant_name": "Shop", "timestamp": "2026-03-11T00:00:00Z", "user_id": "u1"}
            ],
            "transaction_categorizations": [
                {"transaction_id": "t1", "primary_category_id": "c2"}
            ],
            "categories": [{"id": "c2", "name": "Utilities"}],
            # master_categories also present but should not override
            "master_categories": [{"id": "c2", "name": "Wrong"}],
        }
    )
    import backend_api.routes.transactions as transactions
    monkeypatch.setattr(chat, "_sb", fake)
    monkeypatch.setattr(transactions, "_sb", fake)

    summary = chat.get_user_transaction_summary("u1")
    # the helper always prefers master_categories regardless of whether
    # a regular categories table also exists
    assert "Wrong" in summary["spending_by_category"]
    assert summary["spending_by_category"]["Wrong"]["amount"] == 50
