import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone

import pytest

import backend_supabase.analytics_service as svc


class FakeTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def lte(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    @property
    def not_(self):
        return self

    def is_(self, *a, **k):
        return self

    def execute(self):
        # return data depending on table
        data = self.client.data_for(self.name)
        class R: pass
        r = R()
        r.data = data
        return r

    def upsert(self, payload, on_conflict=None):
        self.client.upserts.append((self.name, payload))
        class ExecObj:
            def __init__(self):
                self.data = []
            def execute(self):
                return self
        return ExecObj()


class FakeClient:
    def __init__(self, tables):
        # tables: dict name->data
        self.tables = tables
        self.upserts = []

    def table(self, name):
        return FakeTable(name, self)

    def data_for(self, name):
        return self.tables.get(name, [])


def make_txn(id, amount, date_str, ttype="DEBIT", merchant="M"):
    return {"id": id, "amount": amount, "transaction_date": date_str, "transaction_type": ttype, "merchant_name": merchant}


def test_detect_recurring_for_user_simple(monkeypatch):
    # prepare three monthly transactions for same merchant/category
    tx1 = make_txn("t1", 100, "2025-11-01T00:00:00Z")
    tx2 = make_txn("t2", 100, "2025-12-02T00:00:00Z")
    tx3 = make_txn("t3", 100, "2026-01-03T00:00:00Z")

    transactions = [tx1, tx2, tx3]
    categorizations = [
        {"transaction_id": "t1", "primary_category_id": "c1"},
        {"transaction_id": "t2", "primary_category_id": "c1"},
        {"transaction_id": "t3", "primary_category_id": "c1"},
    ]

    fake = FakeClient({"transactions": transactions, "transaction_categorizations": categorizations})
    monkeypatch.setattr(svc, "_sb", fake)

    res = svc.detect_recurring_for_user("u1", lookback_days=400)
    # expect at least one recurring detected and an upsert recorded
    assert len(res) >= 1
    assert any(p[0] == "recurring_transactions" for p in fake.upserts)
    # payload has merchant_name and avg_amount
    names = [p[1].get("merchant_name") for p in fake.upserts if p[0] == "recurring_transactions"]
    assert "M" in names
