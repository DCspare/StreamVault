import os
import logging
import asyncio # Needed for sleeping
from pyrogram import Client
from pyrogram.errors import FloodWait
from config import Config

logger = logging.getLogger("bot_client")

if not Config.API_ID or not Config.API_HASH or not Config.BOT_TOKEN:
    logger.error("🚫 CONFIG MISSING")

# 🛠️ PROXY CONFIG
proxy_config = dict(
    scheme="socks5",
    hostname="37.18.73.60", # proxydb.net socks5 high anonymous 
    port=5566,
   # username="fbvilezw",
   # password="qhfflj8i2rzg"
)

SESSION_NAME = "streamvault_v1"

class ShadowBot(Client):
    def __init__(self):
        self.is_enabled = True
        self.is_connected = False
        
        # 🗑️ AUTO-CLEANUP CORRUPT FILES
        if os.path.exists(f"{SESSION_NAME}.session"):
            if os.path.getsize(f"{SESSION_NAME}.session") == 0:
                os.remove(f"{SESSION_NAME}.session")

        super().__init__(
            SESSION_NAME,
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="bot/plugins"),
            
            # STABILITY SETTINGS
            workers=4,
            ipv6=False,
            
            # PERSISTENCE
            in_memory=False,   
            workdir=".",       
            
            proxy=proxy_config  
        )

    async def start(self):
        try:
            await super().start()
            self.is_connected = True
        
        # 🛑 FLOOD WAIT HANDLER (The Fix)
        except FloodWait as e:
            wait_time = e.value + 5 # Add buffer
            logger.warning(f"⚠️ Telegram FLOOD_WAIT: Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)
            
            # Retry after sleep
            await super().start()
            self.is_connected = True

        except Exception as e:
            # General Database Cleanup & Retry
            logger.error(f"⚠️ Start Error: {e}")
            if "database is locked" in str(e) or "no such table" in str(e):
                self.cleanup_session()
                await super().start()
                self.is_connected = True
    
    def cleanup_session(self):
        try:
            if os.path.exists(f"{SESSION_NAME}.session"):
                os.remove(f"{SESSION_NAME}.session")
        except:
            pass

    async def stop(self, *args):
        pass

bot_app = ShadowBot()
