from pathlib import Path
import sqlite3
from typing import List, Optional, Dict, Any
from app.config import settings
from app.database.models import Product
from app.database.repositories import ProductRepository


class ProductService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.repo = ProductRepository(conn)

    def get_catalog(self) -> List[Product]:
        return self.repo.get_all_active()

    def get_product(self, product_id: str) -> Optional[Product]:
        return self.repo.get_by_id(product_id)

    def validate_stock_availability(self, product_id: str, quantity: int) -> bool:
        if quantity <= 0:
            return False
        product = self.repo.get_by_id(product_id)
        if not product or not product.active:
            return False
        return product.stock >= quantity

    def resolve_product_image_path(self, raw_path: Optional[str]) -> Optional[Path]:
        """Validates that the requested image path is safe and strictly inside the allowed products directory."""
        if not raw_path:
            return None

        clean_path = raw_path.strip().lstrip("/\\")
        candidate = (settings.BASE_DIR / clean_path).resolve()
        products_root = settings.PRODUCTS_DIR.resolve()

        if products_root in candidate.parents and candidate.exists():
            return candidate
        return None

    def get_catalog_summary_for_ai(self) -> List[Dict[str, Any]]:
        """Returns safe, minimal product data formatted strictly for the AI salesperson prompt."""
        products = self.repo.get_all_active()
        return [
            {
                "product_id": p.id,
                "name": p.name,
                "price": p.price,
                "currency": p.currency,
                "in_stock": p.stock > 0,
                "description": p.description,
                "image_file": p.image_path
            }
            for p in products
        ]