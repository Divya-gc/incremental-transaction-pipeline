
import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "incoming"

CUSTOMER_IDS = [f"C{i:03d}" for i in range(1, 6)]
PRODUCT_IDS = [f"P{i:03d}" for i in range(1, 6)]


def timestamp(days_ago=0):
    """Return a deterministic ISO-8601 timestamp."""
    base = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    return (base - timedelta(days=days_ago)).isoformat()


def make_event(
    event_id,
    transaction_id,
    event_type,
    event_version,
    event_time,
    customer_id=None,
    product_id=None,
    quantity=None,
    unit_price_cents=None,
):
    return {
        "event_id": event_id,
        "transaction_id": transaction_id,
        "event_type": event_type,
        "event_version": event_version,
        "event_time": event_time,
        "customer_id": customer_id,
        "product_id": product_id,
        "quantity": quantity,
        "unit_price_cents": unit_price_cents,
        "currency": "INR",
    }


def generate_sample():
    """Create a small dataset covering important business scenarios."""

    events = [
        # Normal sale
        make_event(
            "E001", "T001", "sale", 1, timestamp(2),
            "C001", "P001", 1, 50000
        ),

        # Update: quantity and price change
        make_event(
            "E002", "T001", "update", 2, timestamp(1),
            "C001", "P001", 2, 45000
        ),

        # Sale followed by reversal
        make_event(
            "E003", "T002", "sale", 1, timestamp(1),
            "C002", "P002", 1, 25000
        ),
        make_event(
            "E004", "T002", "reversal", 2, timestamp(1)
        ),

        # Late-arriving sale: old event date, generated now
        make_event(
            "E005", "T003", "sale", 1, timestamp(5),
            "C003", "P003", 3, 2000
        ),

        # Invalid customer reference for rejection testing
        make_event(
            "E006", "T004", "sale", 1, timestamp(0),
            "C999", "P004", 1, 10000
        ),
    ]

    return events


def generate_large(row_count, seed):
    """Generate reproducible synthetic transaction events."""

    rng = random.Random(seed)
    events = []

    for i in range(row_count):
        transaction_number = i // 2 + 1
        is_update = i % 2 == 1

        event = make_event(
            event_id=f"EV{i + 1:08d}",
            transaction_id=f"TX{transaction_number:08d}",
            event_type="update" if is_update else "sale",
            event_version=2 if is_update else 1,
            event_time=timestamp(rng.randint(0, 30)),
            customer_id=rng.choice(CUSTOMER_IDS),
            product_id=rng.choice(PRODUCT_IDS),
            quantity=rng.randint(1, 5),
            unit_price_cents=rng.randint(500, 100000),
        )

        events.append(event)

    return events


def write_events(events, filename):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename

    with output_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event) + "\n")

    print(f"Generated {len(events)} events.")
    print(f"Output file: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate transaction event datasets."
    )

    parser.add_argument(
        "--preset",
        choices=["sample"],
        help="Generate the small sample dataset."
    )

    parser.add_argument(
        "--rows",
        type=int,
        help="Generate a larger dataset with this many events."
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible data."
    )

    args = parser.parse_args()

    if args.preset == "sample":
        write_events(generate_sample(), "sample.jsonl")

    elif args.rows is not None:
        if args.rows <= 0:
            parser.error("--rows must be greater than zero.")

        events = generate_large(args.rows, args.seed)
        write_events(events, f"large_{args.rows}.jsonl")

    else:
        parser.error("Specify either --preset sample or --rows.")


if __name__ == "__main__":
    main()
