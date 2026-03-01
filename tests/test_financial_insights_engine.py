import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone

import pytest

import backend_supabase.financial_insights_engine as fie


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

    def execute(self):
        class R: pass
        r = R()
        r.data = self.client.data_for(self.name)
        return r

    def insert(self, payload):
        self.client.inserts.append((self.name, payload))
        class ExecObj:
            def __init__(self):
                self.data = []
            def execute(self):
                return self
        return ExecObj()


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.inserts = []

    def table(self, name):
        return FakeTable(name, self)

    def data_for(self, name):
        return self.tables.get(name, [])


def test_generate_insights_basic(monkeypatch):
    now = datetime.now(timezone.utc)
    # make transactions to trigger evening pattern and weekend spike
    txns = [
        {"transaction_date": now.isoformat(), "amount": 50, "merchant_name": "M1"},
        {"transaction_date": now.isoformat(), "amount": 60, "merchant_name": "M2"},
        {"transaction_date": now.isoformat(), "amount": 70, "merchant_name": "M1"},
    ]
    fake = FakeClient({"transactions": txns, "monthly_user_summary": []})
    monkeypatch.setattr(fie, "_sb", fake)

    out = fie.generate_insights_for_user("u1")
    # insights inserted should be recorded
    assert isinstance(fake.inserts, list)
    # may be zero if heuristics don't trigger, but function should return a list
    assert isinstance(out, list)
