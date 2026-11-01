# Design Notes

## 1. Design Overview

The project implements a local transaction-processing pipeline using Python and SQLite. It ingests JSONL transaction events, validates records, handles duplicates and invalid data, maintains the current transaction state, and publishes daily product and customer metrics.

The pipeline is designed to be repeatable and to make processing outcomes visible.

## 2. Key Design Decisions

### SQLite for Storage

SQLite was selected because it is lightweight, requires no separate database server, and supports reproducible local execution.

**Trade-off:** SQLite is suitable for this prototype but is not intended to provide the distributed processing capacity of a production data platform.

### JSONL for Input

JSON Lines allows each transaction event to be stored as an individual JSON record. This makes sample generation and batch ingestion straightforward.

### Event History and Current State

The pipeline stores accepted transaction events in `transaction_event` and maintains the latest transaction state in `transaction_current`.

This separates the event history from the current business view.

### Version-Based Transaction Updates

Transaction versions determine which event represents the latest state. This allows updates and reversals to be processed without treating every event as a separate transaction.

### Validation and Rejected Records

Records are validated before being accepted. Invalid records are stored in `rejected_record` with a reason, allowing data-quality issues to be reviewed without silently discarding them.

## 3. Duplicate Handling and Idempotency

The pipeline uses event identifiers and event content checks to identify duplicate or conflicting events.

- Reprocessing the same file with the same checksum is skipped.
- Previously accepted events are not inserted again.
- Conflicting records using an existing event ID are rejected.
- A different file containing previously processed events is still protected by event-level duplicate checks.

These mechanisms make repeated processing safer.

## 4. Updates, Reversals, and Late Events

- **Sale:** Creates a transaction.
- **Update:** Changes the transaction's current details when the event version is newer.
- **Reversal:** Marks the transaction as reversed and excludes it from net revenue.
- **Late-arriving event:** Is processed using its event timestamp for reporting dates.

An update received after a reversal does not reactivate the transaction.

## 5. Metric Calculation

The pipeline publishes two daily metric tables:

- `daily_product_metric`: metrics grouped by event date and product.
- `daily_customer_metric`: metrics grouped by event date and customer.

Gross revenue includes the value of reversed transactions. Net revenue excludes reversed transactions.

Amounts are stored in integer paise to avoid floating-point currency calculations.

## 6. Reconciliation

The reconciliation module independently calculates expected metrics from the current transaction state and compares them with the published metric tables.

A successful reconciliation indicates that the published metrics match the independently calculated values for the checked data.

## 7. Retry and Failure Handling

Pipeline runs are tracked in `pipeline_run`.

Successful runs record processing counts and status. Failed runs record a failure reason and are marked as failed. The integration tests verify that a failed run can be retried.

## 8. Performance Observations

The local benchmark results were:

| Input records | Accepted | Rejected | Duplicate skips | Execution time |
|---:|---:|---:|---:|---:|
| 10,000 | 10,000 | 0 | 0 | 1.16 seconds |
| 100,000 | 90,000 | 0 | 10,000 | 10.89 seconds |

The 100,000-record dataset was generated with the same seed as the earlier 10,000-record dataset. Therefore, its first 10,000 events overlapped with previously processed events and were skipped by event-level duplicate detection.

These are local prototype measurements, not production performance guarantees.

## 9. Current Limitations

- The pipeline rebuilds current state and daily metrics from stored event history rather than recomputing only affected dates or entities.
- Input events are parsed into memory during ingestion.
- The implementation uses a local SQLite database and does not include distributed processing or cloud orchestration.
- Only INR transactions are supported.
- Abrupt process termination recovery for runs left in a running state is not implemented.

## 10. Future Improvements

- Implement incremental recomputation for affected customers, products, and dates.
- Introduce a staging layer for raw input events.
- Add stronger recovery handling for interrupted runs.
- Optimize bulk database operations and indexing for larger workloads.
- Add automated scheduling, monitoring, and alerting.
- Evaluate a scalable database and distributed processing framework for production workloads.