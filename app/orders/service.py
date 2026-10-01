import sqlite3
import uuid
import logging
from typing import Optional, Tuple, List, Dict, Any
from app.database.models import Order, OrderStatus, Customer
from app.database.repositories import (
    OrderRepository,
    ProductRepository,
    PaymentRepository,
    CustomerRepository,
    InvoiceRepository
)
from app.payments.esewa import EsewaPaymentGateway
from app.invoices.generator import InvoiceGenerator

logger = logging.getLogger("pasale.orders")


class OrderService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.order_repo = OrderRepository(conn)
        self.product_repo = ProductRepository(conn)
        self.payment_repo = PaymentRepository(conn)
        self.customer_repo = CustomerRepository(conn)
        self.invoice_repo = InvoiceRepository(conn)
        self.esewa_gateway = EsewaPaymentGateway()

        self._ensure_tables_and_columns()

    def _ensure_tables_and_columns(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id TEXT NOT NULL REFERENCES products(id),
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL
            );
            """
        )
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN delivery_phone TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN delivery_location_link TEXT;")
        except sqlite3.OperationalError:
            pass

    def initiate_order(
        self,
        discord_user_id: str,
        discord_username: str,
        items: Optional[List[Dict[str, Any]]] = None,
        product_id: Optional[str] = None,
        quantity: int = 1
    ) -> Tuple[Optional[Order], Optional[dict], str]:
        cart: List[Dict[str, Any]] = []
        if items:
            cart.extend(items)
        elif product_id:
            cart.append({"product_id": product_id, "quantity": quantity})

        if not cart:
            return None, None, "No items specified for purchase."

        customer = self.customer_repo.get_or_create(discord_user_id, discord_username)

        # Cancel any previous uncompleted checkouts for this customer so ghost duplicate orders don't pile up
        self.conn.cursor().execute(
            """
            UPDATE orders 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE customer_id = ? AND status IN ('pending', 'payment_pending');
            """,
            (customer.id,)
        )

        validated_items = []
        grand_total = 0.0

        for it in cart:
            p_id = it.get("product_id")
            qty = max(1, int(it.get("quantity", 1)))
            product = self.product_repo.get_by_id(p_id)

            if not product or not product.active:
                return None, None, f"Product {p_id} is currently unavailable."
            if product.stock < qty:
                return None, None, f"Insufficient stock for {product.name}. Only {product.stock} items remaining."

            line_total = round(product.price * qty, 2)
            grand_total += line_total
            validated_items.append({
                "product": product,
                "quantity": qty,
                "unit_price": product.price,
                "total_price": line_total
            })

        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        cursor = self.conn.cursor()

        primary_prod_id = validated_items[0]["product"].id
        total_quantity = sum(i["quantity"] for i in validated_items)

        cursor.execute(
            """
            INSERT INTO orders (order_number, customer_id, product_id, quantity, total_amount, status, delivery_phone, delivery_address, delivery_location_link)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL);
            """,
            (order_number, customer.id, primary_prod_id, total_quantity, grand_total, OrderStatus.PAYMENT_PENDING)
        )
        order_id = cursor.lastrowid

        for vi in validated_items:
            cursor.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (order_id, vi["product"].id, vi["product"].name, vi["quantity"], vi["unit_price"], vi["total_price"])
            )

        cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
        order = Order(**dict(cursor.fetchone()))

        payment_data = self.esewa_gateway.create_payment_payload(order.order_number, order.total_amount)
        self.payment_repo.create(
            order_id=order.id,
            transaction_id=payment_data.transaction_uuid,
            product_code=payment_data.product_code,
            amount=order.total_amount
        )

        return order, payment_data.model_dump(), "Order initiated with full cart."

    def update_order_delivery_info(
        self,
        order_id: int,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        location_link: Optional[str] = None
    ) -> None:
        fields = []
        values = []
        if phone:
            fields.append("delivery_phone = ?")
            values.append(phone)
        if address:
            fields.append("delivery_address = ?")
            values.append(address)
        if location_link:
            fields.append("delivery_location_link = ?")
            values.append(location_link)

        if fields:
            values.append(order_id)
            query = f"UPDATE orders SET {', '.join(fields)} WHERE id = ?;"
            self.conn.cursor().execute(query, tuple(values))

    def get_order_delivery_info(self, order_id: int) -> Dict[str, Optional[str]]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT delivery_phone, delivery_address, delivery_location_link FROM orders WHERE id = ?;", (order_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
        return {"delivery_phone": None, "delivery_address": None, "delivery_location_link": None}

    def finalize_order_and_invoice(self, order_id: int) -> Tuple[bool, Optional[str], str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
        order_row = cursor.fetchone()
        if not order_row:
            return False, None, "Order not found."
        order = Order(**dict(order_row))

        if order.status == OrderStatus.CONFIRMED:
            existing_invoice = self.invoice_repo.get_by_order_id(order.id)
            return True, existing_invoice.file_path if existing_invoice else None, "Order already finalized."

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?;", (order_id,))
        item_rows = cursor.fetchall()

        items_for_invoice = []
        if item_rows:
            for row in item_rows:
                stock_ok = self.product_repo.update_stock(row["product_id"], row["quantity"])
                if not stock_ok:
                    return False, None, f"Insufficient stock to finalize {row['product_name']}."
            items_for_invoice = [dict(r) for r in item_rows]
        else:
            stock_ok = self.product_repo.update_stock(order.product_id, order.quantity)
            if not stock_ok:
                return False, None, "Insufficient stock."
            prod = self.product_repo.get_by_id(order.product_id)
            items_for_invoice = [{
                "product_name": prod.name if prod else "Item",
                "quantity": order.quantity,
                "unit_price": prod.price if prod else order.total_amount,
                "total_price": order.total_amount
            }]

        self.order_repo.update_status(order.id, OrderStatus.CONFIRMED)

        cursor.execute("SELECT * FROM customers WHERE id = ?;", (order.customer_id,))
        customer = Customer(**dict(cursor.fetchone()))

        deliv = self.get_order_delivery_info(order.id)
        if deliv.get("delivery_phone"):
            customer.phone = deliv["delivery_phone"]
        if deliv.get("delivery_address"):
            customer.address = deliv["delivery_address"]
        if deliv.get("delivery_location_link"):
            customer.location_link = deliv["delivery_location_link"]

        generator = InvoiceGenerator()
        invoice_number = f"INV-{order.order_number.replace('ORD-', '')}"
        invoice_path = generator.generate_pdf_invoice(
            invoice_number=invoice_number,
            order=order,
            customer=customer,
            items=items_for_invoice
        )

        self.invoice_repo.create(order.id, invoice_number, str(invoice_path))
        return True, str(invoice_path), "Order confirmed with full invoice."