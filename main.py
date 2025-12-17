import asyncio
import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import idle
from config import Config
from bot.client import bot_app
from server.stream_routes import stream_router
from utils.database import db

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- WEB SERVER SETUP ---
web_app = FastAPI()
web_app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, 
    allow_methods=["*"], allow_headers=["*"],
)
web_app.include_router(stream_router)

@web_app.get("/")
async def health_check():
    return {"status": "Online", "service": "StreamVault"}

# --- SERVER AS A TASK ---
async def start_web_server():
    """Runs Uvicorn as a background asyncio task"""
    config = uvicorn.Config(
        app=web_app, 
        host=Config.HOST, 
        port=Config.PORT, 
        log_level="warning",
        # NOTE: loop argument removed here to inherit the main loop
    )
    server = uvicorn.Server(config)
    await server.serve()

# --- MAIN EXECUTION ---
async def main():
    if not bot_app.is_enabled:
        return

    # 0. Initialize Database Connection
    logger.info("--- 💾 Connecting to Database... ---")
    try:
        await db.connect()
        logger.info("--- ✅ Database Connected ---")
    except Exception as e:
        logger.error(f"--- ❌ Database Failed: {e} ---")
        # Continue without database - indexing features will be disabled

    # 1. Start the Bot FIRST
    logger.info("--- 🤖 Connecting to Telegram... ---")
    try:
        await bot_app.start()
        me = await bot_app.get_me()
        logger.info(f"--- ✅ Bot Connected as {me.first_name} ---")
        await bot_app.session_pool.init_pool()
        
        # Verify handlers
        await bot_app.verify_handler_registration()
        
        # Add detailed startup logging
        logger.info("=" * 70)
        logger.info("✅ BOT STARTED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info("Handlers registered:")
        logger.info("  ✅ /start - Welcome message")
        logger.info("  ✅ /help - Help with commands")
        logger.info("  ✅ /catalog - View indexed files")
        logger.info("  ✅ /delete - Remove files")
        logger.info("  ✅ /search - Search files")
        logger.info("  ✅ Document uploads (document filter)")
        logger.info("  ✅ Video uploads (video filter)")
        logger.info("  ✅ Audio uploads (audio filter)")
        logger.info("  ✅ YouTube URLs (text filter)")
        logger.info("  ✅ Custom names for uploads (text filter)")
        logger.info("=" * 70)
        logger.info(f"Log Channel: {Config.LOG_CHANNEL_ID}")
        logger.info(f"MongoDB: Connected to {Config.MONGO_DB_NAME}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"--- ❌ Bot Failed: {e} ---")
        return

    # 2. Start the Web Server SECOND
    logger.info("--- 🚀 Starting Web Server ---")
    
    try:
        # We run both the "idle" (which keeps bot alive) and "server" (web) at the same time
        await asyncio.gather(
            start_web_server(),
            idle()  # This creates the 'Keep-Alive' loop for Pyrogram
        )
    except Exception as e:
        logger.error(f"--- ❌ Server Error: {e} ---")
    finally:
        # Cleanup database connection
        await db.disconnect()

    await bot_app.stop()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Crash: {e}")