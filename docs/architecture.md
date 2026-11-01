# Pipeline Architecture

## 1. Architecture Overview

The transaction pipeline follows a batch-processing architecture. JSONL files are ingested, validated, stored, processed into current transaction state, and used to publish daily metrics.

## 2. Data Flow

```text
JSONL Input Files
       |
       v
   Ingestion
       |
       v
   Validation
       |
       +--------------------+
       |                    |
       v                    v
 Valid Events          Invalid Events
       |                    |
       v                    v
 Event Processing     Rejected Records
       |
       v
 Transaction Event History
       |
       v
 Current Transaction State
       |
       v
 Daily Metric Calculation
       |
       +----------------------+
       |                      |
       v                      v
 Product Metrics        Customer Metrics
       |                      |
       +----------+-----------+
                  |
                  v
             Reconciliation
                  |
                  v
          Run Status and Results
```

## 3. Main Components

| Component | Responsibility |
|---|---|
| `schema.sql` | Defines database tables and indexes |
| `database.py` | Initializes SQLite and manages database connections |
| `seed_data.py` | Inserts reference customer and product records |
| `generate_data.py` | Generates sample and larger synthetic datasets |
| `ingestion.py` | Reads JSONL files and identifies malformed records |
| `validation.py` | Checks event structure and business rules |
| `processing.py` | Handles event storage, duplicates, transaction state, and metrics |
| `pipeline.py` | Orchestrates processing, run tracking, and file-level idempotency |
| `reconcile.py` | Independently checks published metrics |
| `tests/` | Contains unit and integration tests |

## 4. Database Flow

The main database entities are:

- `dim_customer` and `dim_product`: reference data.
- `transaction_event`: accepted transaction event history.
- `transaction_current`: current state of each transaction.
- `rejected_record`: invalid or conflicting records.
- `processed_file`: processed file tracking.
- `pipeline_run`: execution status and processing counts.
- `daily_product_metric`: daily product-level results.
- `daily_customer_metric`: daily customer-level results.

## 5. Processing Sequence

1. Initialize the database and reference data.
2. Read the incoming JSONL file.
3. Parse records and identify malformed JSON.
4. Validate event fields and business rules.
5. Store valid events and quarantine invalid records.
6. Handle duplicate and conflicting events.
7. Rebuild current transaction state from accepted event history.
8. Recalculate and publish daily product and customer metrics.
9. Run reconciliation to compare published and independently calculated metrics.
10. Record the pipeline execution status and counts.

## 6. Execution Commands

Initialize the database:

```bash
python -m src.database
```

Seed reference data:

```bash
python -m src.seed_data
```

Generate sample input:

```bash
python -m src.generate_data --preset sample
```

Run the pipeline:

```bash
python -m src.pipeline data/incoming/sample.jsonl
```

Run reconciliation:

```bash
python -m src.reconcile
```

Run tests:

```bash
python -m pytest -v
```
