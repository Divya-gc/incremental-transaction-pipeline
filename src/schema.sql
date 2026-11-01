
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id TEXT PRIMARY KEY,
    product_name TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    input_count INTEGER DEFAULT 0,
    accepted_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    duplicate_skip_count INTEGER DEFAULT 0,
    output_count INTEGER DEFAULT 0,
    failure_reason TEXT
);

CREATE TABLE IF NOT EXISTS transaction_event (
    event_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL,
    event_time TEXT NOT NULL,
    customer_id TEXT,
    product_id TEXT,
    quantity INTEGER,
    unit_price_cents INTEGER,
    currency TEXT,
    row_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES pipeline_run(run_id)
);

CREATE INDEX IF NOT EXISTS idx_event_transaction_version
ON transaction_event(transaction_id, event_version);

CREATE TABLE IF NOT EXISTS transaction_current (
    transaction_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    metric_date TEXT NOT NULL,
    last_event_id TEXT NOT NULL,
    last_event_version INTEGER NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

CREATE TABLE IF NOT EXISTS rejected_record (
    reject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    raw_record TEXT NOT NULL,
    reason TEXT NOT NULL,
    rejected_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES pipeline_run(run_id)
);

CREATE TABLE IF NOT EXISTS processed_file (
    source_file TEXT NOT NULL,
    file_checksum TEXT NOT NULL,
    success_run_id TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (source_file, file_checksum),
    FOREIGN KEY (success_run_id) REFERENCES pipeline_run(run_id)
);

CREATE TABLE IF NOT EXISTS daily_product_metric (
    metric_date TEXT NOT NULL,
    product_id TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    total_quantity INTEGER NOT NULL,
    gross_revenue_cents INTEGER NOT NULL,
    net_revenue_cents INTEGER NOT NULL,
    reversal_count INTEGER NOT NULL,
    PRIMARY KEY (metric_date, product_id)
);

CREATE TABLE IF NOT EXISTS daily_customer_metric (
    metric_date TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    total_quantity INTEGER NOT NULL,
    net_revenue_cents INTEGER NOT NULL,
    PRIMARY KEY (metric_date, customer_id)
);
