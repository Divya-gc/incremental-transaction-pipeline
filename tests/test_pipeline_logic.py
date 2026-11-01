
import sqlite3
from pathlib import Path

import pytest

from src.processing import store_event, rebuild_current_and_metrics
from src.validation import validate_event


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "src" / "schema.sql"


@pytest.fixture
def connection(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    conn.executemany(
        "INSERT INTO dim_customer VALUES (?, ?)",
        [("C001", "Customer One"), ("C002", "Customer Two")]
    )
    conn.executemany(
        "INSERT INTO dim_product VALUES (?, ?)",
        [("P001", "Laptop"), ("P002", "Phone")]
    )
    conn.execute(
        """
        INSERT INTO pipeline_run (run_id, started_at, status)
        VALUES ('RUN1', '2026-10-30T12:00:00+00:00', 'running')
        """
    )

    yield conn
    conn.close()


def make_event(
    event_id,
    transaction_id,
    event_type,
    version,
    customer="C001",
    product="P001",
    quantity=1,
    price=10000,
    date="2026-10-30"
):
    return {
        "event_id": event_id,
        "transaction_id": transaction_id,
        "event_type": event_type,
        "event_version": version,
        "event_time": f"{date}T12:00:00+00:00",
        "customer_id": customer,
        "product_id": product,
        "quantity": quantity,
        "unit_price_cents": price,
        "currency": "INR",
    }


def add_event(conn, event):
    assert validate_event(event, conn) is None
    result, _ = store_event(conn, event, "RUN1")
    return result


def test_sale_and_update(connection):
    add_event(
        connection,
        make_event("E1", "T1", "sale", 1, quantity=1, price=10000)
    )
    add_event(
        connection,
        make_event("E2", "T1", "update", 2, quantity=2, price=15000)
    )

    rebuild_current_and_metrics(connection)

    row = connection.execute(
        "SELECT * FROM transaction_current WHERE transaction_id='T1'"
    ).fetchone()

    assert row["quantity"] == 2
    assert row["unit_price_cents"] == 15000

    metric = connection.execute(
        "SELECT * FROM daily_product_metric WHERE product_id='P001'"
    ).fetchone()

    assert metric["net_revenue_cents"] == 30000


def test_reversal_removes_net_revenue(connection):
    add_event(
        connection,
        make_event("E1", "T1", "sale", 1, price=20000)
    )

    reversal = make_event("E2", "T1", "reversal", 2)
    for field in [
        "customer_id", "product_id", "quantity",
        "unit_price_cents", "currency"
    ]:
        reversal[field] = None

    add_event(connection, reversal)
    rebuild_current_and_metrics(connection)

    current = connection.execute(
        "SELECT status FROM transaction_current WHERE transaction_id='T1'"
    ).fetchone()

    metric = connection.execute(
        "SELECT * FROM daily_product_metric WHERE product_id='P001'"
    ).fetchone()

    assert current["status"] == "reversed"
    assert metric["gross_revenue_cents"] == 20000
    assert metric["net_revenue_cents"] == 0
    assert metric["reversal_count"] == 1


def test_identical_event_is_duplicate(connection):
    event = make_event("E1", "T1", "sale", 1)

    assert add_event(connection, event) == "accepted"
    assert add_event(connection, event) == "duplicate"


def test_conflicting_event_id_is_rejected(connection):
    event = make_event("E1", "T1", "sale", 1)
    add_event(connection, event)

    changed = make_event("E1", "T1", "sale", 1, quantity=5)
    result, reason = store_event(connection, changed, "RUN1")

    assert result == "rejected"
    assert "event_id" in reason


def test_unknown_customer_is_rejected(connection):
    event = make_event("E1", "T1", "sale", 1, customer="C999")

    assert validate_event(event, connection) == "Unknown customer_id."


def test_invalid_quantity_is_rejected(connection):
    event = make_event("E1", "T1", "sale", 1, quantity=0)

    assert (
        validate_event(event, connection)
        == "quantity must be a positive integer."
    )


def test_late_event_uses_event_date(connection):
    event = make_event("E1", "T1", "sale", 1, date="2026-10-20")
    add_event(connection, event)

    rebuild_current_and_metrics(connection)

    metric = connection.execute(
        "SELECT metric_date FROM daily_product_metric"
    ).fetchone()

    assert metric["metric_date"] == "2026-10-20"


def test_update_after_reversal_does_not_reactivate(connection):
    add_event(
        connection,
        make_event("E1", "T1", "sale", 1)
    )

    reversal = make_event("E2", "T1", "reversal", 2)
    for field in [
        "customer_id", "product_id", "quantity",
        "unit_price_cents", "currency"
    ]:
        reversal[field] = None

    add_event(connection, reversal)

    add_event(
        connection,
        make_event("E3", "T1", "update", 3, quantity=5)
    )

    rebuild_current_and_metrics(connection)

    row = connection.execute(
        "SELECT status, quantity FROM transaction_current "
        "WHERE transaction_id='T1'"
    ).fetchone()

    assert row["status"] == "reversed"
    assert row["quantity"] == 1
