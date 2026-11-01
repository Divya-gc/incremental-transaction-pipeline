
from collections import defaultdict

from src.database import get_connection


def calculate_expected_metrics(connection):
    """Independently calculate expected metrics from current transactions."""

    product_expected = defaultdict(
        lambda: {
            "transaction_count": 0,
            "total_quantity": 0,
            "gross_revenue_cents": 0,
            "net_revenue_cents": 0,
            "reversal_count": 0,
        }
    )

    customer_expected = defaultdict(
        lambda: {
            "transaction_count": 0,
            "total_quantity": 0,
            "net_revenue_cents": 0,
        }
    )

    transactions = connection.execute(
        "SELECT * FROM transaction_current"
    ).fetchall()

    for transaction in transactions:
        amount = (
            transaction["quantity"]
            * transaction["unit_price_cents"]
        )

        product_key = (
            transaction["metric_date"],
            transaction["product_id"],
        )

        product = product_expected[product_key]
        product["gross_revenue_cents"] += amount

        if transaction["status"] == "reversed":
            product["reversal_count"] += 1
            continue

        product["transaction_count"] += 1
        product["total_quantity"] += transaction["quantity"]
        product["net_revenue_cents"] += amount

        customer_key = (
            transaction["metric_date"],
            transaction["customer_id"],
        )

        customer = customer_expected[customer_key]
        customer["transaction_count"] += 1
        customer["total_quantity"] += transaction["quantity"]
        customer["net_revenue_cents"] += amount

    return product_expected, customer_expected


def compare_metrics(expected, actual, metric_name):
    """Compare expected metric dictionaries with published database rows."""

    differences = []

    if set(expected) != set(actual):
        differences.append(
            f"{metric_name}: metric keys do not match."
        )

    for key in set(expected) | set(actual):
        if expected.get(key) != actual.get(key):
            differences.append(
                f"{metric_name}: mismatch for {key}. "
                f"Expected={expected.get(key)}, "
                f"Actual={actual.get(key)}"
            )

    return differences


def run_reconciliation():
    connection = get_connection()

    try:
        product_expected, customer_expected = (
            calculate_expected_metrics(connection)
        )

        product_rows = connection.execute(
            "SELECT * FROM daily_product_metric"
        ).fetchall()

        customer_rows = connection.execute(
            "SELECT * FROM daily_customer_metric"
        ).fetchall()

        product_actual = {
            (row["metric_date"], row["product_id"]): {
                "transaction_count": row["transaction_count"],
                "total_quantity": row["total_quantity"],
                "gross_revenue_cents": row["gross_revenue_cents"],
                "net_revenue_cents": row["net_revenue_cents"],
                "reversal_count": row["reversal_count"],
            }
            for row in product_rows
        }

        customer_actual = {
            (row["metric_date"], row["customer_id"]): {
                "transaction_count": row["transaction_count"],
                "total_quantity": row["total_quantity"],
                "net_revenue_cents": row["net_revenue_cents"],
            }
            for row in customer_rows
        }

        differences = []

        differences.extend(
            compare_metrics(
                product_expected,
                product_actual,
                "Product metrics",
            )
        )

        differences.extend(
            compare_metrics(
                customer_expected,
                customer_actual,
                "Customer metrics",
            )
        )

        # Basic transaction-level integrity checks.
        invalid_statuses = connection.execute(
            """
            SELECT COUNT(*)
            FROM transaction_current
            WHERE status NOT IN ('active', 'reversed')
            """
        ).fetchone()[0]

        if invalid_statuses:
            differences.append(
                f"Found {invalid_statuses} transactions with invalid status."
            )

        if differences:
            print("\nRECONCILIATION FAILED")
            for difference in differences:
                print("-", difference)
            return False

        print("\nRECONCILIATION PASSED")
        print("--------------------")
        print(f"Current transactions: {len(connection.execute('SELECT transaction_id FROM transaction_current').fetchall())}")
        print(f"Product metric rows: {len(product_rows)}")
        print(f"Customer metric rows: {len(customer_rows)}")
        print("Published metrics match independently calculated values.")

        return True

    finally:
        connection.close()


if __name__ == "__main__":
    success = run_reconciliation()

    if not success:
        raise SystemExit(1)
