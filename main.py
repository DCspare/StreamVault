import asyncio
import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import idle
from config import Config
from bot.client import bot_app
from server.stream_routes import stream_router

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

    # 1. Start the Bot FIRST
    logger.info("--- 🤖 Connecting to Telegram... ---")
    try:
        await bot_app.start()
        me = await bot_app.get_me()
        logger.info(f"--- ✅ Bot Connected as {me.first_name} ---")
        await bot_app.session_pool.init_pool()
    except Exception as e:
        logger.error(f"--- ❌ Bot Failed: {e} ---")
        return

    # 2. Start the Web Server SECOND
    logger.info("--- 🚀 Starting Web Server ---")
    
    # We run both the "idle" (which keeps bot alive) and "server" (web) at the same time
    await asyncio.gather(
        start_web_server(),
        idle()  # This creates the 'Keep-Alive' loop for Pyrogram
    )

    await bot_app.stop()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Crash: {e}")