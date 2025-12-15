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

    API_ID = get_int_env("API_ID", 0)
    API_HASH = get_env("API_HASH", "")
    BOT_TOKEN = get_env("BOT_TOKEN", "")

    # NEW: The Session String
    SESSION_STRING = get_env("SESSION_STRING", "")

    PORT = get_int_env("PORT", 7860)
    HOST = "0.0.0.0"
    URL = get_env("URL", "http://localhost:7860").rstrip("/")

    TG_GETFILE_TIMEOUT = get_int_env("TG_GETFILE_TIMEOUT", 60)

    @classmethod
    def is_valid(cls):
        if cls.API_ID == 0 or not cls.API_HASH or not cls.BOT_TOKEN:
            print("⚠️ WARNING: Config missing.")
            return False
        return True
