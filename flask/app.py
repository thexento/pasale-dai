import functools
import re
import hmac
import hashlib
import base64
from pathlib import Path
import jinja2
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_from_directory, abort
)
from config import Config
from db import query_all, query_one, execute_write, get_kpi_metrics

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

app = Flask(__name__)
app.config.from_object(Config)

# Safe datetime formatter filter for Jinja
@app.template_filter("format_dt")
def format_datetime(val):
    if not val:
        return "—"
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M")
    return str(val)[:16]

discovered_dirs = set()
for candidate in [
    APP_DIR / "templates",
    PROJECT_ROOT / "templates",
    PROJECT_ROOT / "flask" / "templates"
]:
    if candidate.is_dir():
        discovered_dirs.add(str(candidate.resolve()))

for found in PROJECT_ROOT.glob("**/login.html"):
    discovered_dirs.add(str(found.parent.resolve()))

loader_dirs = list(discovered_dirs) if discovered_dirs else [str(APP_DIR / "templates")]
app.jinja_loader = jinja2.FileSystemLoader(loader_dirs)

static_candidates = [
    APP_DIR / "static",
    PROJECT_ROOT / "flask" / "static",
    PROJECT_ROOT / "static"
]
resolved_static = next((d for d in static_candidates if d.is_dir()), APP_DIR / "static")
app.static_folder = str(resolved_static.resolve())


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("is_authenticated"):
            return redirect(url_for("login", next=request.url))
        return view(**kwargs)
    return wrapped_view


@app.context_processor
def inject_global_metrics():
    if session.get("is_authenticated"):
        try:
            metrics = get_kpi_metrics()
        except Exception:
            metrics = {
                "gross_revenue": 0,
                "pending_fulfillment": 0,
                "completed_orders": 0,
                "low_stock_count": 0
            }
        return dict(kpi=metrics, current_path=request.path)
    return dict(kpi={}, current_path=request.path)


# -------------------------------------------------------------
# PUBLIC CHECKOUT & ESEWA INTEGRATION (FIXES 404 ON BOT LINKS)
# -------------------------------------------------------------
@app.route("/checkout/<order_ref>")
def checkout(order_ref: str):
    """
    Public checkout route requested by the Discord bot.
    Accepts both order_number (e.g. ORD-EAD2FD89) or database id.
    """
    clean_ref = order_ref.strip()

    # Query order details
    order = query_one("""
        SELECT 
            o.*,
            c.name AS customer_name,
            c.discord_username,
            c.phone AS customer_phone
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.order_number = ? OR o.id = ?
    """, (clean_ref, clean_ref))

    if not order:
        return render_template("404_order.html", order_ref=clean_ref), 404

    # Query line items
    items = query_all("""
        SELECT oi.*, p.sku 
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    """, (order["id"],))

    # Generate eSewa HMAC signature for v2 API
    # total_amount,transaction_uuid,product_code
    total_amount_str = f"{float(order['total_amount']):.2f}"
    product_code = Config.ESEWA_MERCHANT_CODE
    transaction_uuid = f"{order['order_number']}-{order['id']}"

    # Generate signature
    data_to_sign = f"total_amount={total_amount_str},transaction_uuid={transaction_uuid},product_code={product_code}"
    secret_key_bytes = Config.ESEWA_SECRET_KEY.encode("utf-8")
    signature = base64.b64encode(
        hmac.new(secret_key_bytes, data_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    esewa_params = {
        "amount": total_amount_str,
        "tax_amount": "0",
        "total_amount": total_amount_str,
        "transaction_uuid": transaction_uuid,
        "product_code": product_code,
        "product_service_charge": "0",
        "product_delivery_charge": "0",
        "success_url": f"{Config.BASE_URL}/payment/success",
        "failure_url": f"{Config.BASE_URL}/payment/failure",
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
        "esewa_url": Config.ESEWA_PAYMENT_URL
    }

    return render_template(
        "checkout.html",
        order=order,
        items=items,
        esewa=esewa_params
    )


@app.route("/payment/success")
def payment_success():
    """Callback for verified eSewa payments."""
    data = request.args.get("data")
    if not data:
        flash("No verification data provided by gateway.", "error")
        return redirect(url_for("dashboard"))

    try:
        import json
        decoded = base64.b64decode(data).decode("utf-8")
        payload = json.loads(decoded)
        
        # payload structure: { "transaction_uuid": "ORD-XXXX-ID", "status": "COMPLETE", "total_amount": "...", ... }
        tx_uuid = payload.get("transaction_uuid", "")
        order_ref = tx_uuid.split("-")[0] + "-" + tx_uuid.split("-")[1]

        # Update order status in DB
        execute_write("""
            UPDATE orders 
            SET status = 'paid', updated_at = CURRENT_TIMESTAMP 
            WHERE order_number = ?
        """, (order_ref,))

        # Record payment
        order = query_one("SELECT id FROM orders WHERE order_number = ?", (order_ref,))
        if order:
            execute_write("""
                INSERT INTO payments (order_id, transaction_id, product_code, amount, currency, status, verified_at, raw_response)
                VALUES (?, ?, ?, ?, 'NPR', 'success', CURRENT_TIMESTAMP, ?)
            """, (order["id"], payload.get("transaction_code", tx_uuid), Config.ESEWA_MERCHANT_CODE, payload.get("total_amount", 0), data))

        return render_template("payment_result.html", success=True, payload=payload)
    except Exception as exc:
        return render_template("payment_result.html", success=False, error=str(exc))


@app.route("/payment/failure")
def payment_failure():
    return render_template("payment_result.html", success=False, error="Payment was cancelled or rejected by user.")


# -------------------------------------------------------------
# AUTH & ADMIN ROUTES
# -------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_authenticated"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session.clear()
            session["is_authenticated"] = True
            session["admin_user"] = username
            session.permanent = True
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))
        
        flash("Invalid administrative credentials provided.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    status_filter = request.args.get("status", "all").strip().lower()
    search_query = request.args.get("q", "").strip()

    base_sql = """
        SELECT 
            o.id,
            o.order_number,
            o.customer_id,
            o.total_amount,
            o.currency,
            o.status AS order_status,
            o.delivery_phone,
            o.delivery_address,
            o.delivery_location_link,
            o.created_at,
            c.discord_username,
            c.name AS customer_name,
            p.status AS payment_status,
            p.transaction_id AS payment_tx_id,
            i.file_path AS invoice_file,
            i.invoice_number,
            COALESCE(GROUP_CONCAT(oi.product_name || ' (x' || oi.quantity || ')', ', '), 'No items listed') AS purchased_items_summary
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        LEFT JOIN (
            SELECT order_id, status, transaction_id, MAX(id)
            FROM payments
            GROUP BY order_id
        ) p ON o.id = p.order_id
        LEFT JOIN invoices i ON o.id = i.order_id
        LEFT JOIN order_items oi ON o.id = oi.order_id
    """
    
    conditions = []
    params = []

    if status_filter != "all":
        conditions.append("o.status = ?")
        params.append(status_filter)

    if search_query:
        search_like = f"%{search_query}%"
        conditions.append("""
            (o.order_number LIKE ? 
             OR c.discord_username LIKE ? 
             OR c.name LIKE ? 
             OR o.delivery_phone LIKE ? 
             OR o.delivery_address LIKE ?)
        """)
        params.extend([search_like, search_like, search_like, search_like, search_like])

    if conditions:
        base_sql += " WHERE " + " AND ".join(conditions)

    base_sql += " GROUP BY o.id ORDER BY o.created_at DESC"

    try:
        orders = query_all(base_sql, tuple(params))
    except Exception as exc:
        orders = []
        flash(f"Database error loading orders: {str(exc)}", "error")

    valid_statuses = [
        "all", "pending", "payment_pending", "paid",
        "confirmed", "processing", "shipped", "delivered", "cancelled"
    ]

    return render_template(
        "dashboard.html",
        orders=orders,
        current_status=status_filter,
        search_query=search_query,
        valid_statuses=valid_statuses
    )


@app.route("/api/orders/<int:order_id>")
@login_required
def get_order_details(order_id: int):
    order = query_one("""
        SELECT 
            o.*,
            c.discord_user_id,
            c.discord_username,
            c.name AS customer_name,
            c.email AS customer_email,
            c.phone AS customer_phone,
            c.address AS customer_address,
            c.location_link AS customer_location_link
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.id = ?
    """, (order_id,))

    if not order:
        return jsonify({"error": "Order not found"}), 404

    items = query_all("""
        SELECT 
            oi.id,
            oi.product_id,
            oi.product_name,
            oi.quantity,
            oi.unit_price,
            oi.total_price,
            p.sku
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    """, (order_id,))

    payments = query_all("""
        SELECT 
            id, transaction_id, product_code, amount, 
            currency, status, verified_at, created_at, raw_response
        FROM payments 
        WHERE order_id = ?
        ORDER BY id DESC
    """, (order_id,))

    invoice = query_one("""
        SELECT id, invoice_number, file_path, created_at 
        FROM invoices 
        WHERE order_id = ?
        ORDER BY id DESC LIMIT 1
    """, (order_id,))

    return jsonify({
        "order": dict(order),
        "items": [dict(i) for i in items],
        "payments": [dict(p) for p in payments],
        "invoice": dict(invoice) if invoice else None
    })


@app.route("/api/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id: int):
    payload = request.get_json(silent=True) or request.form
    new_status = payload.get("status", "").strip().lower()

    allowed = [
        "pending", "payment_pending", "paid", "confirmed",
        "processing", "shipped", "delivered", "cancelled"
    ]
    if new_status not in allowed:
        return jsonify({"error": f"Invalid status: {new_status}"}), 400

    rows = execute_write("""
        UPDATE orders 
        SET status = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, (new_status, order_id))

    if rows == 0:
        return jsonify({"error": "Order not found or unchanged"}), 404

    return jsonify({"success": True, "order_id": order_id, "new_status": new_status})


@app.route("/payments")
@login_required
def payments_ledger():
    try:
        payments = query_all("""
            SELECT 
                p.id,
                p.transaction_id,
                p.order_id,
                p.product_code,
                p.amount,
                p.currency,
                p.status,
                p.verified_at,
                p.created_at,
                o.order_number,
                c.discord_username
            FROM payments p
            LEFT JOIN orders o ON p.order_id = o.id
            LEFT JOIN customers c ON o.customer_id = c.id
            ORDER BY p.created_at DESC
        """)
    except Exception as exc:
        payments = []
        flash(f"Error loading ledger: {str(exc)}", "error")

    return render_template("payments.html", payments=payments)


@app.route("/inventory")
@login_required
def inventory():
    try:
        products = query_all("""
            SELECT id, sku, name, description, price, currency, image_path, stock, active, updated_at
            FROM products
            ORDER BY id ASC
        """)
    except Exception as exc:
        products = []
        flash(f"Error loading inventory: {str(exc)}", "error")

    return render_template("inventory.html", products=products)


@app.route("/api/inventory/<product_id>/update", methods=["POST"])
@login_required
def update_inventory(product_id: str):
    data = request.get_json(silent=True) or request.form
    updates = []
    params = []

    if "stock" in data:
        try:
            stock_val = int(data["stock"])
            if stock_val < 0:
                return jsonify({"error": "Stock cannot be negative"}), 400
            updates.append("stock = ?")
            params.append(stock_val)
        except ValueError:
            return jsonify({"error": "Invalid stock quantity integer"}), 400

    if "active" in data:
        active_val = 1 if str(data["active"]).lower() in ("1", "true", "yes") else 0
        updates.append("active = ?")
        params.append(active_val)

    if not updates:
        return jsonify({"error": "No update fields supplied"}), 400

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(product_id)

    query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
    affected = execute_write(query, tuple(params))

    if affected == 0:
        return jsonify({"error": "Product not found or unchanged"}), 404

    updated_product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    return jsonify({"success": True, "product": dict(updated_product)})


@app.route("/invoices/<path:filename>")
@login_required
def view_invoice(filename: str):
    safe_pattern = re.compile(r"^INV-[A-Za-z0-9_\-]+\.pdf$")
    if not safe_pattern.match(filename):
        abort(404, description="Invalid invoice filename format requested.")

    invoice_path = (Config.INVOICES_DIR / filename).resolve()
    try:
        invoice_path.relative_to(Config.INVOICES_DIR.resolve())
    except ValueError:
        abort(403, description="Access outside invoice directory forbidden.")

    if not invoice_path.is_file():
        abort(404, description="Invoice file not found on disk.")

    return send_from_directory(
        Config.INVOICES_DIR,
        filename,
        mimetype="application/pdf",
        as_attachment=False
    )