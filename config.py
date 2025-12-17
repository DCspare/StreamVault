import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("config")


class Config:
    """
    Configuration manager for Shadow Streamer.
    
    Loads all environment variables and provides type-safe accessors.
    Validates critical config values at startup.
    """
    
    def get_env(key, default=""):
        """
        Get string environment variable.
        
        Args:
            key (str): Environment variable name
            default (str): Default value if not found
            
        Returns:
            str: Environment variable value (trimmed) or default
        """
        value = os.environ.get(key, default)
        return value.strip() if value else default

    def get_int_env(key: str, default: int) -> int:
        """
        Get integer environment variable (handels negative numbers).
        
        Args:
            key (str): Environment variable name
            default (int): Default value if not found or invalid
            
        Returns:
            int: Parsed integer value or default
        """
        try:
            value = os.getenv(key)
            if value is None:
                return default
            return int(value)  # Simple - handles negatives automatically
        except (ValueError, TypeError):
            print(f"⚠️ Invalid {key}: '{value}' - using default: {default}")
            return default

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
    # DEBUG: Print LOG ID or ERROR
    import sys
    print(f"DEBUG: LOG_CHANNEL_ID from env = {LOG_CHANNEL_ID}", file=sys.stderr)
    print(f"DEBUG: Raw env var = {os.getenv('LOG_CHANNEL_ID', 'NOT FOUND')}", file=sys.stderr)

    MONGO_URL = get_env("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB_NAME = get_env("MONGO_DB_NAME", "streamvault")

    # File Upload Limits
    MAX_FILE_SIZE_MB = get_int_env("MAX_FILE_SIZE_MB", 500)
    MAX_VIDEO_DURATION_HOURS = get_int_env("MAX_VIDEO_DURATION_HOURS", 2)

    @classmethod
    def is_valid(cls):
        """
        Validate critical configuration values.
        
        Checks that:
        - Telegram API credentials are present
        - Bot token is configured
        - Log channel ID is set (required for indexing)
        
        Returns:
            bool: True if all required config present, False otherwise
        """
        if cls.API_ID == 0 or not cls.API_HASH or not cls.BOT_TOKEN:
            logger.error("⚠️ WARNING: Bot config missing (API_ID, API_HASH, or BOT_TOKEN)")
            return False
        if not cls.LOG_CHANNEL_ID:
            logger.warning("⚠️ WARNING: LOG_CHANNEL_ID missing - indexing disabled")
            return False
        
        logger.info("✅ Configuration validated successfully")
        logger.debug(f"Config: API_ID={cls.API_ID}, LOG_CHANNEL_ID={cls.LOG_CHANNEL_ID}, MAX_FILE_SIZE={cls.MAX_FILE_SIZE_MB}MB")
        return True
