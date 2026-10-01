import sys
import asyncio
import logging
import importlib.util
from pathlib import Path
import uvicorn
from werkzeug.serving import run_simple

from app.config import settings
from app.database.database import init_db, get_db_connection
from app.products.catalog import seed_products
from app.main import app as fastapi_app
from app.bot.discord_bot import bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pasale.runner")


def load_flask_app():
    flask_dir = Path(__file__).resolve().parent / "flask"
    if str(flask_dir) not in sys.path:
        sys.path.append(str(flask_dir))
    
    spec = importlib.util.spec_from_file_location("flask_admin_module", flask_dir / "app.py")
    flask_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flask_module)
    return flask_module.app


async def run_fastapi():
    config = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_flask_admin():
    flask_app = load_flask_app()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: run_simple("0.0.0.0", 5000, flask_app, use_reloader=False, threaded=True)
    )


async def run_discord_bot():
    if not settings.DISCORD_BOT_TOKEN:
        logger.warning("DISCORD_BOT_TOKEN is not set in environment. Discord bot will not start.")
        return

    try:
        await bot.start(settings.DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Discord bot encountered fatal error: {e}")


async def main():
    logger.info("Initializing SQLite database and catalog records...")
    init_db()
    with get_db_connection() as conn:
        seed_products(conn)

    logger.info("Starting Backend API (:8000), Admin Dashboard (:5000), and Discord Bot...")
    await asyncio.gather(
        run_fastapi(),
        run_flask_admin(),
        run_discord_bot()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Pasale Dai Collections system halted.")