import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import asyncio

from backend_api.routes.chat import chat_query, ChatQueryRequest, create_ai_context

# reuse dummy client/table from previous tests (copied for clarity)
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


def test_chat_query_returns_user_specific_summary(monkeypatch):
    # prepare data for two users
    fake = DummyClient(
        tables={
            "transactions": [
                {"id": "t1", "amount": 10, "merchant_name": "A", "timestamp": "2026-03-01T00:00:00Z", "user_id": "u1"},
                {"id": "t2", "amount": 20, "merchant_name": "B", "timestamp": "2026-03-02T00:00:00Z", "user_id": "u2"},
            ],
            "transaction_categorizations": [
                {"transaction_id": "t1", "primary_category_id": "c1"},
                {"transaction_id": "t2", "primary_category_id": "c1"},
            ],
            "master_categories": [{"id": "c1", "name": "Food"}],
        }
    )
    import backend_api.routes.transactions as transactions
    # patch both loci
    monkeypatch.setattr(__import__("backend_api.routes.chat", fromlist=["_sb"]), "_sb", fake)
    monkeypatch.setattr(transactions, "_sb", fake)

    # also patch query_openrouter_ai so we don't hit network
    async def fake_ai(ctx):
        return "ok"
    monkeypatch.setattr(
        __import__("backend_api.routes.chat", fromlist=["query_openrouter_ai"]),
        "query_openrouter_ai",
        fake_ai,
    )

    # call chat_query for u1
    request = ChatQueryRequest(query="hello")
    result = asyncio.run(chat_query(request, user_id="u1"))
    assert result.context_used["transactions_analyzed"] == 1
    assert result.context_used["total_amount"] == 10
    assert "Food" in result.response or result.response == "ok"

    # call chat_query for u2
    result2 = asyncio.run(chat_query(request, user_id="u2"))
    assert result2.context_used["transactions_analyzed"] == 1
    assert result2.context_used["total_amount"] == 20


def test_ai_context_includes_correct_numbers():
    user_data = {
        "total_transactions": 3,
        "total_amount": 150,
        "avg_transaction": 50,
        "period": "Last 90 days",
        "spending_by_category": {"X": {"amount": 150, "count": 3}},
        "top_merchants": [("A", 3)],
        "recent_transactions": [],
    }
    ctx = create_ai_context(user_data, "hi")
    assert "Total transactions: 3" in ctx
    assert "Total amount spent: ₹150.00" in ctx
