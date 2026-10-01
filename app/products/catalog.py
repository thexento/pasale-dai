from pathlib import Path
import sqlite3
from PIL import Image, ImageDraw
from app.config import settings
from app.database.database import get_db_connection, init_db

SAMPLE_PRODUCTS = [
    {
        "id": "PROD001",
        "sku": "SHIRT-BLUE-001",
        "name": "Blue Oversized Shirt",
        "description": "Comfortable 100% premium cotton oversized shirt with a relaxed silhouette and breathable weave. Ideal for everyday casual styling.",
        "price": 1499.0,
        "currency": "NPR",
        "image_path": "products/blue-shirt.png",
        "stock": 25,
        "active": 1
    },
    {
        "id": "PROD002",
        "sku": "HOODIE-BLK-002",
        "name": "Black Minimalist Hoodie",
        "description": "Heavyweight fleece hoodie in deep jet black. Features double-stitched kangaroo pockets, fitted rib cuffs, and a thermal-lined hood.",
        "price": 2899.0,
        "currency": "NPR",
        "image_path": "products/black-hoodie.png",
        "stock": 18,
        "active": 1
    },
    {
        "id": "PROD003",
        "sku": "TSHIRT-WHT-003",
        "name": "White Classic Crewneck T-Shirt",
        "description": "Essential organic combed cotton crewneck t-shirt. Pre-shrunk durable fabric offering an ultra-soft feel and tailored regular fit.",
        "price": 899.0,
        "currency": "NPR",
        "image_path": "products/white-tshirt.png",
        "stock": 40,
        "active": 1
    },
    {
        "id": "PROD004",
        "sku": "JACKET-DNM-004",
        "name": "Vintage Denim Trucker Jacket",
        "description": "Classic rugged indigo denim jacket featuring washed patina accents, metal shank buttons, and deep internal utility pockets.",
        "price": 3799.0,
        "currency": "NPR",
        "image_path": "products/denim-jacket.png",
        "stock": 12,
        "active": 1
    }
]


def ensure_placeholder_image(rel_path: str, label: str) -> None:
    """Generate a clean visual placeholder image if the image file does not yet exist."""
    full_path = settings.BASE_DIR / rel_path
    if not full_path.exists():
        full_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (600, 600), color=(30, 41, 59))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(20, 20), (580, 580)], outline=(99, 102, 241), width=4)
        draw.text((60, 280), f"{label}\nPasale Dai Collections", fill=(248, 250, 252))
        img.save(full_path)


def seed_products(conn: sqlite3.Connection) -> None:
    """Populate database with sample clothing items and verify image assets exist."""
    cursor = conn.cursor()
    for item in SAMPLE_PRODUCTS:
        cursor.execute("SELECT id FROM products WHERE id = ?;", (item["id"],))
        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO products (id, sku, name, description, price, currency, image_path, stock, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item["id"],
                    item["sku"],
                    item["name"],
                    item["description"],
                    item["price"],
                    item["currency"],
                    item["image_path"],
                    item["stock"],
                    item["active"]
                )
            )
        ensure_placeholder_image(item["image_path"], item["name"])


if __name__ == "__main__":
    init_db()
    with get_db_connection() as connection:
        seed_products(connection)
        print("Product catalog successfully seeded with SQLite3.")