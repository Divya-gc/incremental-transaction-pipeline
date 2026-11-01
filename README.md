# Incremental Transaction Processing and Daily Metrics Pipeline

## 1. Project Overview

This project implements a local data engineering pipeline using Python, SQLite and SQL to process incremental transaction events and publish daily product and customer metrics.

The pipeline supports transaction sales, updates, reversals, late-arriving events, duplicate detection, data validation, rejected-record quarantine, safe reruns and reconciliation.

The solution is designed as a reproducible local prototype.

## 2. Architecture

```text
Synthetic JSONL Input
        |
        v
     Ingestion
        |
        v
   Data Validation
        |
        +------ Invalid Records
        |             |
        |             v
        |       Rejected Record
        |         Quarantine
        |
        v
 Duplicate Detection
        |
        v
 Event History Storage
        |
        v
 Current Transaction State
        |
        v
 Daily Metric Aggregation
        |
        +------------------+
        |                  |
        v                  v
 Daily Product       Daily Customer
    Metrics              Metrics
        |                  |
        +--------+---------+
                 |
                 v
          Reconciliation
```

## 3. Technology Stack

- Python 3.10+
- SQLite
- SQL
- Pytest
- JSON Lines (JSONL)

## 4. Project Structure

```text
incre_transc_pipeline/
|
|-- data/
|   |-- incoming/
|   |-- pipeline.db
|
|-- docs/
|-- prompt_history/
|-- reports/
|-- src/
|   |-- schema.sql
|   |-- database.py
|   |-- seed_data.py
|   |-- generate_data.py
|   |-- ingestion.py
|   |-- validation.py
|   |-- processing.py
|   |-- pipeline.py
|   |-- reconcile.py
|
|-- tests/
|-- requirements.txt
|-- README.md
```

## 5. Setup Instructions

### Prerequisites

- Python 3.10 or later
- pip

### Install dependencies

```bash
python -m venv .venv
```

Activate the environment on Windows:

```cmd
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Initialize the database

```bash
python -m src.database
python -m src.seed_data
```

### Generate sample data

```bash
python -m src.generate_data --preset sample
```

### Run the pipeline

```bash
python -m src.pipeline data/incoming/sample.jsonl
```

### Run reconciliation

```bash
python -m src.reconcile
```

### Run automated tests

```bash
python -m pytest -v
```

## 6. Data Processing and Business Rules

- Sale events create transactions.
- Update events replace the current transaction values.
- Reversal events mark transactions as reversed.
- Reversed transactions remain in event history but do not contribute to net revenue.
- Late-arriving events use their event date for reporting.
- Duplicate events are skipped.
- Conflicting event identifiers and invalid records are rejected.
- Unknown customer or product references are rejected.
- Event versions determine transaction update order.

Revenue is calculated using integer cents to avoid floating-point currency calculation errors.

## 7. Idempotency and Recovery

The pipeline uses file checksums and event-level duplicate checks to prevent duplicate processing.

Previously processed files are skipped. Repeated event identifiers with identical payloads are treated as duplicates, while conflicting payloads are rejected.

Failed runs are recorded and can be retried.

## 8. Data Quality and Monitoring

Each pipeline execution records:

- Run ID
- Start and completion timestamps
- Run status
- Input record count
- Accepted record count
- Rejected record count
- Duplicate skip count
- Output metric row count
- Failure reason, when applicable

Malformed and invalid records are stored in a rejected-record quarantine table with their source information and rejection reason.

## 9. Testing

The automated test suite contains 14 tests covering:

- Sale and update processing
- Reversal handling
- Duplicate event handling
- Conflicting event identifiers
- Invalid customer references
- Invalid quantities
- Late-arriving events
- Updates after reversals
- Malformed JSON input
- Empty input files
- File rerun idempotency
- Failed-run retry
- Successful metric reconciliation
- Detection of incorrect published metrics

Run:

```bash
python -m pytest -v
```

## 10. Performance Testing

Performance was measured locally using generated synthetic datasets.

| Input records | Accepted | Duplicate skips | Execution time |
|---:|---:|---:|---:|
| 10,000 | 10,000 | 0 | 1.16 seconds |
| 100,000 | 90,000 | 10,000 | 10.89 seconds |

Both datasets used the same random seed. Therefore, the larger dataset contained events already processed in the earlier benchmark. These were skipped through duplicate detection.

The measurements are specific to the local development environment and are not production performance guarantees.

## 11. Final Sample Execution Results

The final clean sample execution produced:

- Input records: 6
- Accepted records: 5
- Rejected records: 1
- Duplicate skips: 0
- Current transactions: 3
- Daily product metric rows: 3
- Daily customer metric rows: 2

Reconciliation completed successfully.

## 12. Design Decisions and Limitations

- SQLite was selected for a lightweight, reproducible local implementation.
- Transaction history is retained separately from the current transaction state.
- Daily metrics are rebuilt from current transaction records after processing each batch.
- The implementation is intended for a local prototype rather than a distributed production environment.
- Full metric recomputation may become expensive at larger scales.
- The pipeline currently supports INR transactions.
- External orchestration, cloud deployment and distributed processing are outside the current scope.

## 13. Future Improvements

- Incremental recomputation of only affected metric dates and dimensions.
- Batch-oriented database operations and optimized duplicate lookups.
- Improved recovery for interrupted runs.
- Cloud object storage and managed database integration.
- Workflow orchestration and scheduling.
- Expanded schema evolution and monitoring support.

## 14. AI Assistance

AI tools were used for learning, design discussion, debugging assistance, documentation and implementation guidance.

The implementation was developed, executed and tested locally. Relevant AI prompts are documented in the `prompt_history/` directory.