import src.reconcile as reconcile_module
import json
import sqlite3
from pathlib import Path

import pytest

import src.pipeline as pipeline_module


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "src" / "schema.sql"


@pytest.fixture
def test_environment(tmp_path, monkeypatch):
    """Create an isolated database and redirect the pipeline to it."""

    db_path = tmp_path / "test_pipeline.db"
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    # Initialize the temporary database.
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        SCHEMA_PATH.read_text(encoding="utf-8")
    )

    connection.executemany(
        "INSERT INTO dim_customer VALUES (?, ?)",
        [("C001", "Customer One")]
    )
    connection.executemany(
        "INSERT INTO dim_product VALUES (?, ?)",
        [("P001", "Laptop")]
    )

    connection.commit()
    connection.close()

    # Make every pipeline connection use the temporary database.
    def get_test_connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(
        pipeline_module,
        "get_connection",
        get_test_connection
    )

    return db_path, input_dir


def read_database(db_path, query):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    result = connection.execute(query).fetchall()
    connection.close()
    return result


def make_valid_event():
    return {
        "event_id": "E100",
        "transaction_id": "T100",
        "event_type": "sale",
        "event_version": 1,
        "event_time": "2026-10-30T12:00:00+00:00",
        "customer_id": "C001",
        "product_id": "P001",
        "quantity": 2,
        "unit_price_cents": 15000,
        "currency": "INR"
    }


def test_malformed_json_is_quarantined(test_environment):
    db_path, input_dir = test_environment

    input_file = input_dir / "malformed.jsonl"
    input_file.write_text(
        '{"event_id": invalid json}\n',
        encoding="utf-8"
    )

    pipeline_module.run_pipeline(input_file)

    rejected = read_database(
        db_path,
        "SELECT * FROM rejected_record"
    )
    runs = read_database(
        db_path,
        "SELECT * FROM pipeline_run"
    )

    assert len(rejected) == 1
    assert runs[0]["status"] == "success"
    assert runs[0]["input_count"] == 1
    assert runs[0]["rejected_count"] == 1
    assert runs[0]["accepted_count"] == 0


def test_empty_file_completes_successfully(test_environment):
    db_path, input_dir = test_environment

    input_file = input_dir / "empty.jsonl"
    input_file.write_text("", encoding="utf-8")

    pipeline_module.run_pipeline(input_file)

    runs = read_database(
        db_path,
        "SELECT * FROM pipeline_run"
    )
    processed_files = read_database(
        db_path,
        "SELECT * FROM processed_file"
    )

    assert len(runs) == 1
    assert runs[0]["status"] == "success"
    assert runs[0]["input_count"] == 0
    assert runs[0]["accepted_count"] == 0
    assert len(processed_files) == 1


def test_rerunning_same_file_does_not_duplicate_events(
    test_environment
):
    db_path, input_dir = test_environment

    input_file = input_dir / "valid.jsonl"
    event = make_valid_event()

    input_file.write_text(
        json.dumps(event) + "\n",
        encoding="utf-8"
    )

    # First execution.
    pipeline_module.run_pipeline(input_file)

    # Second execution with the exact same file.
    pipeline_module.run_pipeline(input_file)

    events = read_database(
        db_path,
        "SELECT * FROM transaction_event"
    )
    runs = read_database(
        db_path,
        "SELECT * FROM pipeline_run ORDER BY started_at"
    )

    assert len(events) == 1
    assert len(runs) == 2
    assert all(run["status"] == "success" for run in runs)

    assert runs[0]["accepted_count"] == 1
    assert runs[1]["accepted_count"] == 0
    assert runs[1]["duplicate_skip_count"] == 1



def test_failed_run_can_be_retried(test_environment, monkeypatch):
    db_path, input_dir = test_environment

    input_file = input_dir / "retry.jsonl"
    event = make_valid_event()

    input_file.write_text(
        json.dumps(event) + "\n",
        encoding="utf-8"
    )

    # Keep the original function so we can restore only this patch.
    original_rebuild = pipeline_module.rebuild_current_and_metrics

    # Simulate a failure during metric publishing.
    def simulated_failure(connection):
        raise RuntimeError("Simulated publishing failure")

    monkeypatch.setattr(
        pipeline_module,
        "rebuild_current_and_metrics",
        simulated_failure
    )

    with pytest.raises(RuntimeError, match="Simulated publishing failure"):
        pipeline_module.run_pipeline(input_file)

    failed_runs = read_database(
        db_path,
        "SELECT * FROM pipeline_run"
    )

    events_after_failure = read_database(
        db_path,
        "SELECT * FROM transaction_event"
    )

    assert len(failed_runs) == 1
    assert failed_runs[0]["status"] == "failed"
    assert len(events_after_failure) == 0

    # Restore only the metric function.
    # Keep the temporary database connection active.
    monkeypatch.setattr(
        pipeline_module,
        "rebuild_current_and_metrics",
        original_rebuild
    )

    # Retry the same file.
    pipeline_module.run_pipeline(input_file)

    successful_runs = read_database(
        db_path,
        "SELECT * FROM pipeline_run"
    )

    final_events = read_database(
        db_path,
        "SELECT * FROM transaction_event"
    )

    assert len(successful_runs) == 2
    assert sorted(run["status"] for run in successful_runs) == [
        "failed", "success"
    ]
    assert len(final_events) == 1

def test_reconciliation_passes_for_correct_metrics(
    test_environment, monkeypatch
):
    db_path, input_dir = test_environment
    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    monkeypatch.setattr(
        reconcile_module,
        "get_connection",
        get_test_connection
    )

    input_file = input_dir / "reconcile.jsonl"
    input_file.write_text(
        json.dumps(make_valid_event()) + "\n",
        encoding="utf-8"
    )

    pipeline_module.run_pipeline(input_file)

    assert reconcile_module.run_reconciliation() is True


def test_reconciliation_detects_incorrect_metrics(
    test_environment, monkeypatch
):
    db_path, input_dir = test_environment
    def get_test_connection():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    monkeypatch.setattr(
        reconcile_module,
        "get_connection",
        get_test_connection
    )


    input_file = input_dir / "reconcile.jsonl"
    input_file.write_text(
        json.dumps(make_valid_event()) + "\n",
        encoding="utf-8"
    )

    pipeline_module.run_pipeline(input_file)

    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        UPDATE daily_product_metric
        SET net_revenue_cents = net_revenue_cents + 100
        """
    )
    connection.commit()
    connection.close()

    assert reconcile_module.run_reconciliation() is False

