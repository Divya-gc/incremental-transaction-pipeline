# AI Prompt History

## AI Tools Used

- ChatGPT: Used for project planning, understanding data engineering concepts, implementation guidance, debugging, testing, and documentation.
- Cursor: [Include only if used for this project.]

## Project Prompt History

The following entries document the AI assistance used during the challenge. Entries marked as summaries are not verbatim transcripts.

### 1. Project Understanding and Planning
[Add the actual prompt or a clearly labelled summary of the prompt used to understand the challenge requirements and plan the solution.]

### 2. Database and Schema Design
[Add the actual prompt or summary used for designing the SQLite schema and tables.]

### 3. Data Generation and Ingestion
[Add the actual prompt or summary used for implementing JSONL generation and ingestion.]

### 4. Validation and Transaction Processing
[Add the actual prompt or summary used for validation, duplicate handling, updates, reversals, and late events.]

### 5. Pipeline and Reconciliation
[Add the actual prompt or summary used for orchestration, idempotency, run tracking, and reconciliation.]

### 6. Testing and Debugging
[Add the actual prompts or summaries used to create and debug unit and integration tests.]

### 7. Performance Testing
[Add the actual prompt or summary used to benchmark the 10,000-record and 100,000-record datasets.]

### 8. Documentation and Final Review
[Add the actual prompt or summary used to prepare the README, data dictionary, design notes, and architecture documentation.]

## AI Assistance Disclosure

AI assistance was used as a support tool during development. The implementation was run and tested locally, and the project owner reviewed the code and execution results. AI-generated suggestions were checked against the actual project behavior before being included.
# Python virtual environment
.venv/

# Python cache files
__pycache__/
*.py[cod]
.pytest_cache/

# Local SQLite database
data/pipeline.db
data/pipeline.db-shm
data/pipeline.db-wal

# Large generated benchmark datasets
data/incoming/large_*.jsonl
