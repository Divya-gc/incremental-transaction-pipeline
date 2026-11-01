
import sqlite3
from pathlib import Path


# Find the main project folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Database and schema file locations
DATABASE_PATH = PROJECT_ROOT / "data" / "pipeline.db"
SCHEMA_PATH = PROJECT_ROOT / "src" / "schema.sql"


def get_connection():
    """Create and return a SQLite database connection."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    # Enable foreign key validation
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database():
    """Create all database tables using schema.sql."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_PATH}"
        )

    with get_connection() as connection:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)

    print(f"Database initialized: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()

