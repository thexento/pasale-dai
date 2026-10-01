import sqlite3
from dataclasses import fields
from typing import Optional, List, Any
from app.database.models import (
    Customer,
    Product,
    Order,
    Payment,
    Invoice,
    Conversation,
    OrderStatus,
    PaymentStatus
)


def _safe_dataclass_instance(cls, row: sqlite3.Row):
    """Instantiates a dataclass using only the keys that exist on the class."""
    if not row:
        return None
    valid_fields = {f.name for f in fields(cls)}
    row_dict = dict(row)
    filtered = {k: v for k, v in row_dict.items() if k in valid_fields}
    return cls(**filtered)


class CustomerRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_discord_id(self, discord_user_id: str) -> Optional[Customer]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE discord_user_id = ? LIMIT 1;", (str(discord_user_id),))
        row = cursor.fetchone()
        return _safe_dataclass_instance(Customer, row)

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ? LIMIT 1;", (customer_id,))
        row = cursor.fetchone()
        return _safe_dataclass_instance(Customer, row)

    def get_or_create(self, discord_user_id: str, discord_username: str) -> Customer:
        customer = self.get_by_discord_id(discord_user_id)
        if not customer:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO customers (discord_user_id, discord_username)
                VALUES (?, ?);
                """,
                (str(discord_user_id), discord_username)
            )
            customer = self.get_by_discord_id(discord_user_id)
        return customer

    def update_contact_info(
        self,
        customer_id: int,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        location_link: Optional[str] = None,
        name: Optional[str] = None,
        email: Optional[str] = None
    ) -> Optional[Customer]:
        fields_to_update: List[str] = []
        values: List[Any] = []

        if phone is not None:
            fields_to_update.append("phone = ?")
            values.append(phone)
        if address is not None:
            fields_to_update.append("address = ?")
            values.append(address)
        if location_link is not None:
            fields_to_update.append("location_link = ?")
            values.append(location_link)
        if name is not None:
            fields_to_update.append("name = ?")
            values.append(name)
        if email is not None:
            fields_to_update.append("email = ?")
            values.append(email)

        if not fields_to_update:
            return self.get_by_id(customer_id)

        fields_to_update.append("updated_at = CURRENT_TIMESTAMP")
        values.append(customer_id)
        query = f"UPDATE customers SET {', '.join(fields_to_update)} WHERE id = ?;"

        cursor = self.conn.cursor()
        cursor.execute(query, tuple(values))
        return self.get_by_id(customer_id)


class ProductRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_id(self, product_id: str) -> Optional[Product]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ? LIMIT 1;", (product_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["active"] = bool(data["active"])
        return _safe_dataclass_instance(Product, data)

    def get_all_active(self) -> List[Product]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products WHERE active = 1;")
        products = []
        for row in cursor.fetchall():
            data = dict(row)
            data["active"] = bool(data["active"])
            products.append(_safe_dataclass_instance(Product, data))
        return products

    def update_stock(self, product_id: str, quantity: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE products
            SET stock = stock - ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND stock >= ?;
            """,
            (quantity, product_id, quantity)
        )
        return cursor.rowcount > 0


class OrderRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_number(self, order_number: str) -> Optional[Order]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_number = ? LIMIT 1;", (order_number,))
        row = cursor.fetchone()
        return _safe_dataclass_instance(Order, row)

    def get_latest_order(self, customer_id: int) -> Optional[Order]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM orders
            WHERE customer_id = ?
            ORDER BY created_at DESC LIMIT 1;
            """,
            (customer_id,)
        )
        row = cursor.fetchone()
        return _safe_dataclass_instance(Order, row)

    def create(
        self,
        order_number: str,
        customer_id: int,
        product_id: str,
        quantity: int,
        total_amount: float
    ) -> Order:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO orders (order_number, customer_id, product_id, quantity, total_amount, status)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (order_number, customer_id, product_id, quantity, total_amount, OrderStatus.PAYMENT_PENDING)
        )
        order_id = cursor.lastrowid
        cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
        return _safe_dataclass_instance(Order, cursor.fetchone())

    def update_status(self, order_id: int, status: str) -> Optional[Order]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (status, order_id)
        )
        cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
        return _safe_dataclass_instance(Order, cursor.fetchone())


class PaymentRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        order_id: int,
        transaction_id: str,
        product_code: str,
        amount: float
    ) -> Payment:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO payments (order_id, transaction_id, product_code, amount, status)
            VALUES (?, ?, ?, ?, ?);
            """,
            (order_id, transaction_id, product_code, amount, PaymentStatus.PENDING)
        )
        payment_id = cursor.lastrowid
        cursor.execute("SELECT * FROM payments WHERE id = ?;", (payment_id,))
        return _safe_dataclass_instance(Payment, cursor.fetchone())

    def get_by_transaction_id(self, transaction_id: str) -> Optional[Payment]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE transaction_id = ? LIMIT 1;", (transaction_id,))
        row = cursor.fetchone()
        return _safe_dataclass_instance(Payment, row)

    def mark_success(self, payment_id: int, raw_response: str) -> Optional[Payment]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE payments
            SET status = ?, raw_response = ?, verified_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (PaymentStatus.SUCCESS, raw_response, payment_id)
        )
        cursor.execute("SELECT * FROM payments WHERE id = ?;", (payment_id,))
        return _safe_dataclass_instance(Payment, cursor.fetchone())


class InvoiceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, order_id: int, invoice_number: str, file_path: str) -> Invoice:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO invoices (order_id, invoice_number, file_path)
            VALUES (?, ?, ?);
            """,
            (order_id, invoice_number, file_path)
        )
        invoice_id = cursor.lastrowid
        cursor.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
        return _safe_dataclass_instance(Invoice, cursor.fetchone())

    def get_by_order_id(self, order_id: int) -> Optional[Invoice]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE order_id = ? LIMIT 1;", (order_id,))
        row = cursor.fetchone()
        return _safe_dataclass_instance(Invoice, row)


class ConversationRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add_message(self, customer_id: int, role: str, message: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO conversations (customer_id, role, message)
            VALUES (?, ?, ?);
            """,
            (customer_id, role, message)
        )

    def get_recent(self, customer_id: int, limit: int = 15) -> List[Conversation]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM conversations
            WHERE customer_id = ?
            ORDER BY created_at DESC LIMIT ?;
            """,
            (customer_id, limit)
        )
        rows = cursor.fetchall()
        messages = [_safe_dataclass_instance(Conversation, r) for r in rows]
        messages.reverse()
        return messages