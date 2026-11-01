
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone


def calculate_row_hash(event):
    """Create a stable hash for an event's content."""
    canonical = json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def store_event(connection, event, run_id):
    """
    Store one validated event.

    Returns:
        accepted
        duplicate
        rejected
    """

    row_hash = calculate_row_hash(event)

    existing_id = connection.execute(
        """
        SELECT row_hash
        FROM transaction_event
        WHERE event_id = ?
        """,
        (event["event_id"],),
    ).fetchone()

    if existing_id:
        if existing_id["row_hash"] == row_hash:
            return "duplicate", "Identical event already exists."
        return "rejected", "Conflicting payload for existing event_id."

    existing_version = connection.execute(
        """
        SELECT row_hash
        FROM transaction_event
        WHERE transaction_id = ? AND event_version = ?
        """,
        (event["transaction_id"], event["event_version"]),
    ).fetchone()

    if existing_version:
        if existing_version["row_hash"] == row_hash:
            return "duplicate", "Identical transaction version already exists."
        return "rejected", "Conflicting transaction version."

    if event["event_type"] == "sale":
        existing_sale = connection.execute(
            """
            SELECT 1
            FROM transaction_event
            WHERE transaction_id = ? AND event_type = 'sale'
            """,
            (event["transaction_id"],),
        ).fetchone()

        if existing_sale:
            return "rejected", "A sale already exists for this transaction."

    received_at = datetime.now(timezone.utc).isoformat()

    connection.execute(
        """
        INSERT INTO transaction_event (
            event_id,
            transaction_id,
            event_type,
            event_version,
            event_time,
            customer_id,
            product_id,
            quantity,
            unit_price_cents,
            currency,
            row_hash,
            run_id,
            received_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            event["transaction_id"],
            event["event_type"],
            event["event_version"],
            event["event_time"],
            event.get("customer_id"),
            event.get("product_id"),
            event.get("quantity"),
            event.get("unit_price_cents"),
            event.get("currency"),
            row_hash,
            run_id,
            received_at,
        ),
    )

    return "accepted", "Event stored successfully."


def rebuild_current_and_metrics(connection):
    """
    Rebuild current transactions and daily metrics
    from the complete event history.
    """

    connection.execute("DELETE FROM transaction_current")
    connection.execute("DELETE FROM daily_product_metric")
    connection.execute("DELETE FROM daily_customer_metric")

    transactions = connection.execute(
        """
        SELECT *
        FROM transaction_event
        ORDER BY transaction_id, event_version
        """
    ).fetchall()

    grouped = defaultdict(list)

    for event in transactions:
        grouped[event["transaction_id"]].append(event)

    current_rows = []

    for transaction_id, events in grouped.items():

        sales = [
            event for event in events
            if event["event_type"] == "sale"
        ]

        # Transactions without a sale remain in event history.
        if not sales:
            continue

        sale = sales[0]
        snapshot = None
        reversal = None

        for event in events:
            if event["event_version"] < sale["event_version"]:
                continue

            if event["event_type"] == "sale":
                if snapshot is None:
                    snapshot = event

            elif event["event_type"] == "update":
                if reversal is None:
                    snapshot = event

            elif event["event_type"] == "reversal":
                if reversal is None:
                    reversal = event

        if snapshot is None:
            continue

        status = "reversed" if reversal else "active"

        last_event_id = (
            reversal["event_id"] if reversal else snapshot["event_id"]
        )

        last_event_version = (
            reversal["event_version"]
            if reversal else snapshot["event_version"]
        )

        metric_date = datetime.fromisoformat(
            snapshot["event_time"].replace("Z", "+00:00")
        ).date().isoformat()

        current_rows.append((
            transaction_id,
            status,
            snapshot["customer_id"],
            snapshot["product_id"],
            snapshot["quantity"],
            snapshot["unit_price_cents"],
            snapshot["currency"],
            metric_date,
            last_event_id,
            last_event_version,
        ))

    connection.executemany(
        """
        INSERT INTO transaction_current (
            transaction_id,
            status,
            customer_id,
            product_id,
            quantity,
            unit_price_cents,
            currency,
            metric_date,
            last_event_id,
            last_event_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        current_rows,
    )

    product_metrics = defaultdict(
        lambda: {
            "transaction_count": 0,
            "total_quantity": 0,
            "gross_revenue_cents": 0,
            "net_revenue_cents": 0,
            "reversal_count": 0,
        }
    )

    customer_metrics = defaultdict(
        lambda: {
            "transaction_count": 0,
            "total_quantity": 0,
            "net_revenue_cents": 0,
        }
    )

    current_transactions = connection.execute(
        "SELECT * FROM transaction_current"
    ).fetchall()

    for transaction in current_transactions:
        amount = (
            transaction["quantity"]
            * transaction["unit_price_cents"]
        )

        product_key = (
            transaction["metric_date"],
            transaction["product_id"],
        )

        customer_key = (
            transaction["metric_date"],
            transaction["customer_id"],
        )

        product = product_metrics[product_key]

        # Gross revenue includes the last known value
        # of reversed transactions.
        product["gross_revenue_cents"] += amount

        if transaction["status"] == "reversed":
            product["reversal_count"] += 1
            continue

        product["transaction_count"] += 1
        product["total_quantity"] += transaction["quantity"]
        product["net_revenue_cents"] += amount

        customer = customer_metrics[customer_key]
        customer["transaction_count"] += 1
        customer["total_quantity"] += transaction["quantity"]
        customer["net_revenue_cents"] += amount

    connection.executemany(
        """
        INSERT INTO daily_product_metric (
            metric_date,
            product_id,
            transaction_count,
            total_quantity,
            gross_revenue_cents,
            net_revenue_cents,
            reversal_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                date,
                product_id,
                values["transaction_count"],
                values["total_quantity"],
                values["gross_revenue_cents"],
                values["net_revenue_cents"],
                values["reversal_count"],
            )
            for (date, product_id), values in product_metrics.items()
        ],
    )

    connection.executemany(
        """
        INSERT INTO daily_customer_metric (
            metric_date,
            customer_id,
            transaction_count,
            total_quantity,
            net_revenue_cents
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                date,
                customer_id,
                values["transaction_count"],
                values["total_quantity"],
                values["net_revenue_cents"],
            )
            for (date, customer_id), values in customer_metrics.items()
        ],
    )
