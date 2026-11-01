
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.database import get_connection
from src.ingestion import read_event_file
from src.processing import store_event, rebuild_current_and_metrics
from src.validation import validate_event


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def run_pipeline(input_path):
    """Run ingestion, validation, processing and metric publishing."""

    input_path = Path(input_path)
    run_id = str(uuid.uuid4())
    started_at = current_timestamp()
    source_file = input_path.name

    connection = get_connection()

    # Record the run separately so failures can be logged.
    connection.execute(
        """
        INSERT INTO pipeline_run (run_id, started_at, status)
        VALUES (?, ?, 'running')
        """,
        (run_id, started_at),
    )
    connection.commit()

    try:
        events, malformed, checksum = read_event_file(input_path)
        input_count = len(events) + len(malformed)

        connection.execute("BEGIN")

        # File-level idempotency check
        already_processed = connection.execute(
            """
            SELECT 1 FROM processed_file
            WHERE source_file = ? AND file_checksum = ?
            """,
            (source_file, checksum),
        ).fetchone()

        if already_processed:
            connection.execute(
                """
                UPDATE pipeline_run
                SET status = 'success',
                    completed_at = ?,
                    input_count = ?,
                    duplicate_skip_count = ?
                WHERE run_id = ?
                """,
                (current_timestamp(), input_count, input_count, run_id),
            )
            connection.commit()
            print("This file was already processed. Skipping it.")
            print(f"Run ID: {run_id}")
            connection.close()
            return

        accepted_count = 0
        rejected_count = 0
        duplicate_skip_count = 0

        # Save malformed JSON records
        for record in malformed:
            connection.execute(
                """
                INSERT INTO rejected_record (
                    run_id, source_file, line_number,
                    raw_record, reason, rejected_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_file,
                    record["line_number"],
                    record["raw_record"],
                    record["reason"],
                    current_timestamp(),
                ),
            )
            rejected_count += 1

        # Validate and process parsed events
        for record in events:
            event = record["event"]

            reason = validate_event(event, connection)

            if reason:
                connection.execute(
                    """
                    INSERT INTO rejected_record (
                        run_id, source_file, line_number,
                        raw_record, reason, rejected_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        source_file,
                        record["line_number"],
                        record["raw_record"],
                        reason,
                        current_timestamp(),
                    ),
                )
                rejected_count += 1
                continue

            result, message = store_event(
                connection, event, run_id
            )

            if result == "accepted":
                accepted_count += 1

            elif result == "duplicate":
                duplicate_skip_count += 1

            else:
                connection.execute(
                    """
                    INSERT INTO rejected_record (
                        run_id, source_file, line_number,
                        raw_record, reason, rejected_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        source_file,
                        record["line_number"],
                        record["raw_record"],
                        message,
                        current_timestamp(),
                    ),
                )
                rejected_count += 1

        # Rebuild current transactions and publish metrics
        rebuild_current_and_metrics(connection)

        product_metric_count = connection.execute(
            "SELECT COUNT(*) FROM daily_product_metric"
        ).fetchone()[0]

        customer_metric_count = connection.execute(
            "SELECT COUNT(*) FROM daily_customer_metric"
        ).fetchone()[0]

        output_count = product_metric_count + customer_metric_count

        # Check the record-count reconciliation
        if input_count != (
            accepted_count + rejected_count + duplicate_skip_count
        ):
            raise ValueError("Input and output record counts do not reconcile.")

        # Mark the file as successfully processed
        connection.execute(
            """
            INSERT INTO processed_file (
                source_file, file_checksum,
                success_run_id, processed_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                source_file,
                checksum,
                run_id,
                current_timestamp(),
            ),
        )

        connection.execute(
            """
            UPDATE pipeline_run
            SET status = 'success',
                completed_at = ?,
                input_count = ?,
                accepted_count = ?,
                rejected_count = ?,
                duplicate_skip_count = ?,
                output_count = ?
            WHERE run_id = ?
            """,
            (
                current_timestamp(),
                input_count,
                accepted_count,
                rejected_count,
                duplicate_skip_count,
                output_count,
                run_id,
            ),
        )

        connection.commit()

        print("\nPIPELINE COMPLETED")
        print("------------------")
        print(f"Run ID: {run_id}")
        print(f"Input records: {input_count}")
        print(f"Accepted records: {accepted_count}")
        print(f"Rejected records: {rejected_count}")
        print(f"Duplicate skips: {duplicate_skip_count}")
        print(f"Output metric rows: {output_count}")
        print("Status: SUCCESS")

    except Exception as error:
        connection.rollback()

        connection.execute(
            """
            UPDATE pipeline_run
            SET status = 'failed',
                completed_at = ?,
                failure_reason = ?
            WHERE run_id = ?
            """,
            (current_timestamp(), str(error), run_id),
        )
        connection.commit()

        print(f"PIPELINE FAILED: {error}")
        print(f"Run ID: {run_id}")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python -m src.pipeline "
            "data/incoming/sample.jsonl"
        )
        sys.exit(1)

    run_pipeline(sys.argv[1])
