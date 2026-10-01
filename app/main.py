import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.database import init_db, get_db_connection
from app.products.catalog import seed_products
from app.api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pasale.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup initialization: initialize SQLite tables and verify sample catalog."""
    logger.info("Initializing database schema...")
    init_db()
    with get_db_connection() as conn:
        seed_products(conn)
    logger.info(f"{settings.STORE_NAME} backend initialized successfully.")
    yield


app = FastAPI(
    title=f"{settings.STORE_NAME} API",
    description="Automated AI clothing store backend with direct Gemini REST & eSewa integration",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)