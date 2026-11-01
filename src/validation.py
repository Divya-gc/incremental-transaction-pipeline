
from datetime import datetime


REQUIRED_FIELDS = [
    "event_id",
    "transaction_id",
    "event_type",
    "event_version",
    "event_time",
]

VALID_EVENT_TYPES = {"sale", "update", "reversal"}
VALID_CURRENCY = {"INR"}


def validate_event(event, connection):
    """
    Validate one transaction event.

    Returns None when valid, otherwise returns a rejection reason.
    """

    if not isinstance(event, dict):
        return "Record must be a JSON object."

    # Check mandatory fields
    for field in REQUIRED_FIELDS:
        if field not in event or event[field] is None:
            return f"Missing required field: {field}"

        if isinstance(event[field], str) and not event[field].strip():
            return f"Empty required field: {field}"

    # Validate event type
    if event["event_type"] not in VALID_EVENT_TYPES:
        return "Invalid event_type."

    # Validate event version
    if (
        isinstance(event["event_version"], bool)
        or not isinstance(event["event_version"], int)
        or event["event_version"] <= 0
    ):
        return "event_version must be a positive integer."

    # Validate timestamp
    try:
        datetime.fromisoformat(
            event["event_time"].replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return "Invalid event_time. Use ISO-8601 format."

    # Reversals do not need customer/product/amount details
    if event["event_type"] == "reversal":
        return None

    # Sale and update events require transaction details
    detail_fields = [
        "customer_id",
        "product_id",
        "quantity",
        "unit_price_cents",
        "currency",
    ]

    for field in detail_fields:
        if field not in event or event[field] is None:
            return f"Missing required field: {field}"

    # Validate quantity
    if (
        isinstance(event["quantity"], bool)
        or not isinstance(event["quantity"], int)
        or event["quantity"] <= 0
    ):
        return "quantity must be a positive integer."

    # Validate price
    if (
        isinstance(event["unit_price_cents"], bool)
        or not isinstance(event["unit_price_cents"], int)
        or event["unit_price_cents"] < 0
    ):
        return "unit_price_cents must be a non-negative integer."

    # Validate currency
    if event["currency"] not in VALID_CURRENCY:
        return "Unsupported currency."

    # Validate customer reference
    customer = connection.execute(
        "SELECT 1 FROM dim_customer WHERE customer_id = ?",
        (event["customer_id"],),
    ).fetchone()

    if customer is None:
        return "Unknown customer_id."

    # Validate product reference
    product = connection.execute(
        "SELECT 1 FROM dim_product WHERE product_id = ?",
        (event["product_id"],),
    ).fetchone()

    if product is None:
        return "Unknown product_id."

    return None

