import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone, timedelta

import pytest

from backend_api.routes import analytics
from backend_supabase import analytics_service


class DummyTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.query = {}

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        # store for filtering later if needed
        self.query[args[0]] = args[1]
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

    def is_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        # return data depending on table name
        class R:
            pass
        r = R()
        r.data = self.client.data_for(self.name)
        return r


class DummyClient:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return DummyTable(name, self)

    def data_for(self, name):
        return self.tables.get(name, [])


# --- analytics route tests --------------------------------------------------

def test_monthly_forecast_no_rows(monkeypatch):
    # service returns no trend data
    monkeypatch.setattr(analytics_service, 'get_monthly_trend', lambda u, m: [])
    res = analytics.monthly_forecast(user_id='u1')
    assert res['months'] == []
    assert 'prediction_text' in res


def test_monthly_forecast_with_data(monkeypatch):
    data = [
        {'month': '2026-01', 'total_debit': 100},
        {'month': '2026-02', 'total_debit': 150},
        {'month': '2026-03', 'total_debit': 120},
    ]
    monkeypatch.setattr(analytics_service, 'get_monthly_trend', lambda u, m: data)
    res = analytics.monthly_forecast(user_id='u1')
    months = res['months']
    # should have original 3 plus prediction for April
    assert len(months) == 4
    assert months[0]['month'] == '2026-01'
    assert months[-1]['month'] == '2026-04'  # predicted next month
    assert months[-1]['predicted'] == 120


def test_risk_score_route(monkeypatch):
    fake = {'risk_score': 42, 'risk_level': 'medium'}
    monkeypatch.setattr(analytics_service, 'compute_risk_profile_for_user', lambda u: fake)
    out = analytics.risk_score(user_id='u1')
    assert out['risk_score'] == 42
    assert out['risk_level'] == 'medium'
    assert 'message' in out


def test_spending_summary_overview(monkeypatch):
    # fake 2 debit transactions, one credit should be ignored
    now = datetime.now(timezone.utc)
    tx1 = {'id': 't1', 'amount': 100, 'transaction_date': now.isoformat(), 'transaction_type': 'DEBIT'}
    tx2 = {'id': 't2', 'amount': 50, 'transaction_date': now.isoformat(), 'transaction_type': 'DEBIT'}
    tx3 = {'id': 't3', 'amount': 30, 'transaction_date': now.isoformat(), 'transaction_type': 'CREDIT'}
    monkeypatch.setattr(analytics, '_sb', DummyClient({'transactions': [tx1, tx2, tx3]}))
    res = analytics.spending_summary_overview(period='this_month', user_id='u1')
    assert res['total_spent'] == 150
    assert res['transaction_count'] == 2


def test_spending_alerts(monkeypatch):
    # create transactions to mimic last month 100, this month 200 -> spike warning
    now = datetime.now(timezone.utc)
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_start = (this_start - timedelta(days=1)).replace(day=1)
    tx_this = [{'id': 'a', 'amount': 200, 'transaction_date': this_start.isoformat(), 'transaction_type': 'DEBIT'}]
    tx_last = [{'id': 'b', 'amount': 100, 'transaction_date': last_start.isoformat(), 'transaction_type': 'DEBIT'}]
    # monkeypatch the helper to return the appropriate list depending on bounds
    def fake_fetch(uid, s, e):
        # simple check date range
        if s == this_start:
            return tx_this
        else:
            return tx_last
    monkeypatch.setattr(analytics, '_fetch_categorized_txns', fake_fetch)
    out = analytics.spending_alerts(user_id='u1')
    assert any(a['type'] == 'warning' for a in out['alerts'])


def test_recommendations():
    out = analytics.recommendations(user_id='u1')
    assert 'recommendations' in out
    assert len(out['recommendations']) >= 1
