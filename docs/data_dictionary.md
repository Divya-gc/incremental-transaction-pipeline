# Data Dictionary

## 1. Source Event Schema

The pipeline accepts transaction events in JSON Lines (JSONL) format.

| Field | Data type | Description |
|---|---|---|
| event_id | String | Unique identifier for an event |
| transaction_id | String | Identifier of the business transaction |
| event_type | String | sale, update or reversal |
| event_version | Integer | Version number of the transaction event |
| event_time | ISO-8601 timestamp | Business event timestamp |
| customer_id | String | Reference to the customer |
| product_id | String | Reference to the product |
| quantity | Integer | Number of product units |
| unit_price_cents | Integer | Price per unit in cents |
| currency | String | Supported currency: INR |

Reversal events do not require transaction detail fields.

## 2. Database Tables

### dim_customer
Stores customer reference information.

- customer_id: Primary key
- customer_name: Customer name

### dim_product
Stores product reference information.

- product_id: Primary key
- product_name: Product name

### pipeline_run
Stores pipeline execution information.

- run_id: Unique pipeline run identifier
- started_at: Run start timestamp
- completed_at: Run completion timestamp
- status: running, success or failed
- input_count: Number of input records
- accepted_count: Number of accepted events
- rejected_count: Number of rejected records
- duplicate_skip_count: Number of skipped duplicates
- output_count: Number of output metric rows
- failure_reason: Error description when applicable

### transaction_event
Stores accepted transaction event history.

- event_id: Primary key
- transaction_id: Business transaction identifier
- event_type: Event operation
- event_version: Event version
- event_time: Business event timestamp
- customer_id: Customer reference
- product_id: Product reference
- quantity: Transaction quantity
- unit_price_cents: Unit price
- currency: Currency code
- row_hash: Hash used for duplicate detection
- run_id: Associated pipeline run
- received_at: Ingestion timestamp

### transaction_current
Stores the latest current state of each transaction.

- transaction_id: Primary key
- status: Current transaction status
- customer_id: Customer reference
- product_id: Product reference
- quantity: Current quantity
- unit_price_cents: Current unit price
- currency: Currency code
- metric_date: Business reporting date
- last_event_id: Latest applied event identifier
- last_event_version: Latest applied version

### rejected_record
Stores invalid or malformed input records.

- reject_id: Rejection record identifier
- run_id: Associated pipeline run
- source_file: Input file name
- line_number: Original input line
- raw_record: Original record content
- reason: Rejection reason
- rejected_at: Rejection timestamp

### processed_file
Tracks previously processed input files.

- source_file: Input file name
- file_checksum: SHA-256 checksum
- success_run_id: Successful processing run
- processed_at: Processing timestamp

### daily_product_metric
Stores daily product-level metrics.

Grain: One row per metric date and product.

- metric_date
- product_id
- transaction_count
- total_quantity
- gross_revenue_cents
- net_revenue_cents
- reversal_count

### daily_customer_metric
Stores daily customer-level metrics.

Grain: One row per metric date and customer.

- metric_date
- customer_id
- transaction_count
- total_quantity
- net_revenue_cents

## 3. Business Rules

- Event identifiers must be unique.
- Event versions must be positive integers.
- Sales and updates require valid customer and product references.
- Quantity must be positive.
- Unit price cannot be negative.
- Only INR is supported.
- Reversed transactions do not contribute to net revenue.
- Event versions determine transaction state order.
- Business event dates determine metric dates.