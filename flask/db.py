import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from config import Config

def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with Row factory enabled."""
    conn = sqlite3.connect(
        Config.DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        timeout=15.0
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db():
    """Context manager for safe transactional database operations."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def query_all(query: str, params: tuple = ()) -> List[sqlite3.Row]:
    """Execute a parameterized query and return all matching rows."""
    with get_db() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall()

def query_one(query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    """Execute a parameterized query and return the first matching row."""
    with get_db() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchone()

def execute_write(query: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return the affected row count."""
    with get_db() as conn:
        cursor = conn.execute(query, params)
        return cursor.rowcount

def get_kpi_metrics() -> Dict[str, Any]:
    """Calculate the 4 core business metrics for the persistent top bar."""
    with get_db() as conn:
        # 1. Total Gross Revenue (paid, confirmed, processing, shipped, delivered)
        rev_row = conn.execute("""
            SELECT COALESCE(SUM(total_amount), 0) AS revenue 
            FROM orders 
            WHERE status IN ('paid', 'confirmed', 'processing', 'shipped', 'delivered')
        """).fetchone()
        revenue = rev_row["revenue"] if rev_row else 0

        # 2. Pending Fulfillment (paid or confirmed orders not yet dispatched)
        ful_row = conn.execute("""
            SELECT COUNT(*) AS count 
            FROM orders 
            WHERE status IN ('paid', 'confirmed', 'processing')
        """).fetchone()
        pending_fulfillment = ful_row["count"] if ful_row else 0

        # 3. Completed Orders (shipped or delivered)
        comp_row = conn.execute("""
            SELECT COUNT(*) AS count 
            FROM orders 
            WHERE status IN ('shipped', 'delivered')
        """).fetchone()
        completed_orders = comp_row["count"] if comp_row else 0

        # 4. Low Stock Alerts (active products with stock < 5)
        stock_row = conn.execute("""
            SELECT COUNT(*) AS count 
            FROM products 
            WHERE active = 1 AND stock < 5
        """).fetchone()
        low_stock_count = stock_row["count"] if stock_row else 0

    return {
        "gross_revenue": revenue,
        "pending_fulfillment": pending_fulfillment,
        "completed_orders": completed_orders,
        "low_stock_count": low_stock_count
    }