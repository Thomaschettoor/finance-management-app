import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone

import pytest

import backend_api.routes.transactions as transactions
import backend_api.routes.dashboard as dashboard


# simple fake supabase client/table that applies the most common filters used by our
# endpoints so we can verify logic without hitting a real database.
class DummyTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        # for columns we keep a list of (op, val) tuples; other keys (order, limit, range)
        # remain as scalars for simplicity
        self.query: dict[str, any] = {}

    def select(self, *args, **kwargs):
        return self

    def _add_cond(self, col, cond):
        if col in ('order', 'limit', 'range'):
            # these are special keys, just set
            self.query[col] = cond
        else:
            self.query.setdefault(col, []).append(cond)
        return self

    def eq(self, col, val):
        return self._add_cond(col, ("eq", val))

    def gte(self, col, val):
        return self._add_cond(col, ("gte", val))

    def lte(self, col, val):
        return self._add_cond(col, ("lte", val))

    def lt(self, col, val):
        return self._add_cond(col, ("lt", val))

    def in_(self, col, vals):
        return self._add_cond(col, ("in", vals))

    def order(self, col, desc=False):
        return self._add_cond('order', (col, desc))

    def limit(self, n):
        return self._add_cond('limit', n)

    def range(self, a, b):
        return self._add_cond('range', (a, b))

    def ilike(self, *args, **kwargs):
        # not used in these tests
        return self

    def execute(self):
        # basic filtering of the underlying table data according to gte/lte/lt/eq/in;
        # ordering + limit/range applied afterwards.
        data = self.client.tables.get(self.name, [])

        def matches(row):
            for col, conds in self.query.items():
                # special keys
                if col in ('order', 'limit', 'range'):
                    continue
                # column filters should be a list of (op, val)
                if not isinstance(conds, list):
                    continue
                rv = row.get(col)
                for op, val in conds:
                    if op == 'eq' and rv != val:
                        return False
                    if op == 'gte' and rv < val:
                        return False
                    if op == 'lte' and rv > val:
                        return False
                    if op == 'lt' and rv >= val:
                        return False
                    if op == 'in' and rv not in val:
                        return False
            return True

        results = [r for r in data if matches(r)]

        # ordering
        if 'order' in self.query:
            col, desc = self.query['order']
            results.sort(key=lambda r: r.get(col) or "", reverse=desc)
        # range / limit
        if 'range' in self.query:
            a, b = self.query['range']
            results = results[a:b+1]
        elif 'limit' in self.query:
            results = results[: self.query['limit']]

        class R:
            pass

        r = R()
        r.data = results
        return r


class DummyClient:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return DummyTable(name, self)


# ---------- dashboard summary tests ----------

def test_dashboard_summary_counts_and_month(monkeypatch):
    # freeze now to March 12 2026
    class FixedDate(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 12, tzinfo=timezone.utc)

    monkeypatch.setattr(dashboard, 'datetime', FixedDate)

    fake = DummyClient(
        tables={
            'users': [{'id': 'u1', 'name': 'Tester', 'currency': 'USD'}],
            'transactions': [
                # two transactions in march (one credit, one debit)
                {'amount': 100, 'timestamp': '2026-03-05T12:00:00Z', 'user_id': 'u1', 'transaction_type': 'CREDIT'},
                {'amount': 50, 'timestamp': '2026-03-10T09:00:00Z', 'user_id': 'u1', 'transaction_type': 'DEBIT'},
                # one in february should be ignored
                {'amount': 200, 'timestamp': '2026-02-28T23:59:59Z', 'user_id': 'u1', 'transaction_type': 'DEBIT'},
            ],
        }
    )
    # also verify behaviour when the users table lacks name/currency
    fake2 = DummyClient(
        tables={
            'users': [{'id': 'u1', 'email': 'no_name@x.com'}],
            'transactions': fake.tables['transactions'],
        }
    )
    monkeypatch.setattr(dashboard, '_sb', fake)

    result = dashboard.dashboard_summary(user_id='u1')
    assert result['user_name'] == 'Tester'
    assert result['currency'] == 'USD'
    # only the two march txns should be counted
    assert result['transaction_count'] == 2
    assert result['total_credit'] == round(100.0, 2)
    assert result['total_debit'] == round(50.0, 2)  # positive sum of debit amounts

    # now swap to fake2 where name/currency columns are missing
    monkeypatch.setattr(dashboard, '_sb', fake2)
    result2 = dashboard.dashboard_summary(user_id='u1')
    assert result2['user_name'] == 'no_name@x.com'  # email fallback
    assert result2['currency'] == ''
    assert result2['transaction_count'] == 2

    # also exercise fallback behaviour when transaction_type is absent but
    # debit amounts are stored positive; should still treat them as debits
    fake3 = DummyClient(
        tables={
            'users': [{'id': 'u1', 'name': 'Tester', 'currency': 'USD'}],
            'transactions': [
                {'amount': 20,  'timestamp': '2026-03-03T00:00:00Z', 'user_id': 'u1'},
                {'amount': 30,  'timestamp': '2026-03-04T00:00:00Z', 'user_id': 'u1'},
            ],
        }
    )
    monkeypatch.setattr(dashboard, '_sb', fake3)
    result3 = dashboard.dashboard_summary(user_id='u1')
    # no transaction_type -> sign fallback: both positive treated as credits
    assert result3['total_credit'] == 50
    assert result3['total_debit'] == 0


# ---------- transactions list tests ----------

def make_txn(id, ts, amount=0, user=None):
    txn = {'id': id, 'timestamp': ts, 'amount': amount}
    if user:
        txn['user_id'] = user
    return txn


def test_list_transactions_sorting_and_month_filter(monkeypatch):
    fake_txns = [
        make_txn('t1', '2026-03-01T10:00:00Z', 10, user='foo'),
        make_txn('t2', '2026-03-02T09:00:00Z', 20, user='foo'),
        make_txn('t3', '2026-02-15T12:00:00Z', 5, user='foo'),
    ]
    fake = DummyClient({'transactions': fake_txns})
    monkeypatch.setattr(transactions, '_sb', fake)

    # default call (no filters) should return all rows sorted by timestamp desc
    out = transactions.list_transactions(
        page=1,
        limit=10,
        category=None,
        search=None,
        sort=None,
        min_amount=None,
        max_amount=None,
        start_date=None,
        end_date=None,
        month=None,
        year=None,
        tx_type=None,
        user_id='foo',
    )
    ids = [t['id'] for t in out['transactions']]
    assert ids == ['t2', 't1', 't3']

    # request March 2026 should only include t1 and t2
    out = transactions.list_transactions(
        page=1,
        limit=10,
        category=None,
        search=None,
        sort=None,
        min_amount=None,
        max_amount=None,
        start_date=None,
        end_date=None,
        month=3,
        year=2026,
        tx_type=None,
        user_id='foo',
    )
    ids = [t['id'] for t in out['transactions']]
    assert ids == ['t2', 't1']

    # if you supply only month or only year, we should get a 400
    with pytest.raises(Exception):
        transactions.list_transactions(
            page=1,
            limit=10,
            category=None,
            search=None,
            sort=None,
            min_amount=None,
            max_amount=None,
            start_date=None,
            end_date=None,
            month=3,
            year=None,
            tx_type=None,
            user_id='foo',
        )


def test_recent_transactions_order_and_limit(monkeypatch):
    # ensure the dashboard endpoint respects sorting and limit parameter
    fake_txns = [
        make_txn('a', '2026-03-01T01:00:00Z', user='u1'),
        make_txn('b', '2026-03-02T01:00:00Z', user='u1'),
        make_txn('c', '2026-03-03T01:00:00Z', user='u1'),
    ]
    fake = DummyClient({'transactions': fake_txns})
    monkeypatch.setattr(dashboard, '_sb', fake)

    res = dashboard.recent_transactions(limit=2, user_id='u1')
    ids = [t['transaction_id'] for t in res['transactions']]
    assert ids == ['c', 'b']


def test_recent_transactions_handles_failure(monkeypatch):
    # if the supabase client throws an exception, we should not 500
    class BrokenClient:
        def table(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(dashboard, '_sb', BrokenClient())
    res = dashboard.recent_transactions(limit=5, user_id='u1')
    assert res['transactions'] == []
    assert 'error' in res


def test_recent_transactions_tolerates_bad_amount(monkeypatch):
    fake_txns = [
        {
            'id': 'x',
            'merchant_name': 'm',
            'amount': 'notanumber',
            'category_id': None,
            'timestamp': '2026-03-01T00:00:00Z',
            'created_at': '2026-03-01T00:00:00Z',
            'user_id': 'u1',
        }
    ]
    fake = DummyClient({'transactions': fake_txns})
    monkeypatch.setattr(dashboard, '_sb', fake)
    res = dashboard.recent_transactions(limit=1, user_id='u1')
    assert res['transactions'][0]['amount'] == 0.0
