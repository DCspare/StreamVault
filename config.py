import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    def get_env(key, default=""):
        value = os.environ.get(key, default)
        return value.strip() if value else default

    def get_int_env(key, default=0):
        val = os.environ.get(key)
        if not val or not val.strip().isdigit():
            return default
        return int(val)

    # Telegram Bot Configuration
    API_ID = get_int_env("API_ID", 0)
    API_HASH = get_env("API_HASH", "")
    BOT_TOKEN = get_env("BOT_TOKEN", "")

    # NEW: The Session String
    SESSION_STRING = get_env("SESSION_STRING", "")

    # Server Configuration
    PORT = get_int_env("PORT", 7860)
    HOST = "0.0.0.0"
    URL = get_env("URL", "http://localhost:7860").rstrip("/")

    # Telegram API Configuration
    TG_GETFILE_TIMEOUT = get_int_env("TG_GETFILE_TIMEOUT", 60)

    # Log Channel Indexing Configuration
    LOG_CHANNEL_ID = get_int_env("LOG_CHANNEL_ID", 0)
    MONGO_URL = get_env("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB_NAME = get_env("MONGO_DB_NAME", "streamvault")

    # File Upload Limits
    MAX_FILE_SIZE_MB = get_int_env("MAX_FILE_SIZE_MB", 500)
    MAX_VIDEO_DURATION_HOURS = get_int_env("MAX_VIDEO_DURATION_HOURS", 2)

    @classmethod
    def is_valid(cls):
        if cls.API_ID == 0 or not cls.API_HASH or not cls.BOT_TOKEN:
            print("⚠️ WARNING: Bot config missing.")
            return False
        if not cls.LOG_CHANNEL_ID:
            print("⚠️ WARNING: LOG_CHANNEL_ID missing - indexing disabled.")
            return False
        return True
