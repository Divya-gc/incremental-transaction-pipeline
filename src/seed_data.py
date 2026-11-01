
from src.database import get_connection


def seed_reference_data():
    """Insert sample customers and products into the database."""

    customers = [
        ("C001", "Customer One"),
        ("C002", "Customer Two"),
        ("C003", "Customer Three"),
        ("C004", "Customer Four"),
        ("C005", "Customer Five"),
    ]

    products = [
        ("P001", "Laptop"),
        ("P002", "Mobile Phone"),
        ("P003", "Headphones"),
        ("P004", "Keyboard"),
        ("P005", "Mouse"),
    ]

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT OR IGNORE INTO dim_customer
            (customer_id, customer_name)
            VALUES (?, ?)
            """,
            customers,
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO dim_product
            (product_id, product_name)
            VALUES (?, ?)
            """,
            products,
        )

    print("Reference data inserted successfully.")


if __name__ == "__main__":
    seed_reference_data()
