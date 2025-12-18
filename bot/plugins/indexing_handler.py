"""
File Indexing Handler Plugin for Shadow Streamer.

This plugin handles:
- Direct file uploads with custom naming
- YouTube video downloads with progress tracking
- Catalog browsing and pagination
- File deletion (soft delete)
- File search by name

All uploaded files are forwarded to LOG_CHANNEL and indexed in MongoDB
for persistent storage and streaming access.
"""

import os
import asyncio
import re
import logging
import tempfile
import time
import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, MessageIdInvalid

from config import Config
from utils.database import db

logger = logging.getLogger("indexing")
MAX_FILE_SIZE = Config.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
MAX_DURATION = Config.MAX_VIDEO_DURATION_HOURS * 3600  # Convert to seconds

# Parse Log Channel ID safely
try:
    LOG_CHANNEL = int(Config.LOG_CHANNEL_ID)
except:
    LOG_CHANNEL = Config.LOG_CHANNEL_ID # Handle if username string

# YouTube URL patterns
YOUTUBE_PATTERNS = [
    r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
    r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
    r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
    r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+'
]

# --- 1. VISUAL FORMATTING & PROGRESS HELPERS ---

def humanbytes(size):
    """Convert bytes to human readable string (MB, GB)"""
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def time_formatter(milliseconds: int) -> str:
    """Format milliseconds to MM:SS"""
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours: return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"

async def show_progress(current, total, message, start_time, stage="Task"):
    """
    Cool 'Hackery' Style Progress Bar with Refresh Button
    """
    now = time.time()
    # Update only every 3 seconds to avoid FloodWait
    if hasattr(show_progress, "last_update"):
        if now - show_progress.last_update < 3 and current != total:
            return
    show_progress.last_update = now

    percent = current * 100 / total
    elapsed = now - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    # Visual Bar
    bar_length = 10
    filled = int(percent / 100 * bar_length)
    bar = "★" * filled + "☆" * (bar_length - filled)
    
    stats = (
        f"🚧 **{stage} in Progress...**\n\n"
        f"**Task By:** {message.chat.first_name}\n"
        f"[{bar}] {percent:.1f}%\n"
        f"**Processed:** {humanbytes(current)} of {humanbytes(total)}\n"
        f"**Speed:** {humanbytes(speed)}/s\n"
        f"**ETA:** {time_formatter(eta * 1000)}\n\n"
        f"**Status:** 🔼 Running..."
    )
    
    # Button to refresh
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("♻️ Refresh Stats", callback_data="status_refresh")]
    ])
    
    try:
        await message.edit_text(stats, reply_markup=buttons)
    except:
        pass

# --- 2. STATE MANAGEMENT ---

class FileState:
    """
    Temporary state tracker for multi-step file upload process.
    
    Workflow:
    1. User sends file → State created
    2. Bot asks for custom name
    3. User sends name → State retrieved and processed
    4. State deleted after completion
    
    Attributes:
        message (Message): Original file upload message
        file_info (Dict): File metadata (ID, size, MIME type, etc.)
        custom_name (str): User-provided custom name (set later)
        created_at (datetime): State creation timestamp
    """
    def __init__(self, message, file_info):
        self.type = "file"
        self.message = message
        self.file_info = file_info
        self.custom_name = None

class YouTubeState:
    def __init__(self, message, info_dict, url):
        self.type = "youtube"
        self.message = message
        self.info = info_dict # Full metadata from YT
        self.url = url
        self.quality = 720 # Default
        self.custom_name = None
        self.last_msg = None # Status message to update

# Unified State Dictionary (Replaces upload_states)
user_states = {}

def is_youtube_url(text: str) -> bool:
    """
    Check if text contains a YouTube URL.
    
    Supports standard YouTube URL formats:
    - youtube.com/watch?v=VIDEO_ID
    - youtu.be/VIDEO_ID
    - youtube.com/embed/VIDEO_ID
    - youtube.com/shorts/VIDEO_ID
    
    Args:
        text (str): Text to check for YouTube URL
        
    Returns:
        bool: True if YouTube URL detected, False otherwise
        
    Example:
        >>> is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        True
        >>> is_youtube_url("Just some text")
        False
    """
    if not text:
        return False
    
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in YOUTUBE_PATTERNS)

async def validate_file_size(file_size: int) -> tuple[bool, Optional[str]]:
    """
    Validate file size against configured limits.
    
    Prevents Telegram upload timeouts by rejecting files over MAX_FILE_SIZE.
    
    Args:
        file_size (int): File size in bytes
        
    Returns:
        tuple: (is_valid, error_message)
            - is_valid (bool): True if file is within limits
            - error_message (str): User-friendly error message if invalid, None if valid
            
    Example:
        >>> await validate_file_size(100 * 1024 * 1024)  # 100MB
        (True, None)
        >>> await validate_file_size(600 * 1024 * 1024)  # 600MB
        (False, "File too large: 600MB...")
    """
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size // 1024 // 1024
        return False, f"File too large: {size_mb}MB\n⚠️ Maximum size: {Config.MAX_FILE_SIZE_MB}MB (prevents timeout)\n💡 Suggestion: Split the file or use external hosting"
    return True, None

async def validate_youtube_video(url: str) -> tuple[bool, Optional[str], Optional[Dict]]:
    """Validate YouTube video before download with Cloud-fixes (IPv4/Proxy)"""
    
    # 1. Base Options: Force IPv4 to fix "[Errno -5]" DNS errors
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_ipv4': True,      # CRITICAL FIX for Cloud Containers
        'geo_bypass': True,
        'nocheckcertificate': True
    }
    
    # 2. Proxy Check: Load PROXY_URL from secrets/env if available
    # Set this in your HF Secrets as: http://user:pass@ip:port
    proxy_url = os.environ.get("PROXY_URL") or os.environ.get("HTTP_PROXY")
    if proxy_url:
        ydl_opts['proxy'] = proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Check duration
            duration = info.get('duration', 0)
            if duration > MAX_DURATION:
                hours = duration // 3600
                return False, f"Video too long: {hours}h {(duration % 3600) // 60}m\n⚠️ Limit: {Config.MAX_VIDEO_DURATION_HOURS}h", None
            
            # Check file size (if available)
            filesize = info.get('filesize') or info.get('filesize_approx', 0)
            if filesize and filesize > MAX_FILE_SIZE:
                size_mb = filesize // 1024 // 1024
                return False, f"Video too large: {size_mb}MB\n⚠️ Limit: {Config.MAX_FILE_SIZE_MB}MB", None
            
            return True, None, info
            
    except Exception as e:
        logger.warning(f"YouTube Validation Error: {e}")
        return False, f"❌ Link Error: {str(e)[:50]}...", None

async def forward_to_log_channel(client: Client, message: Message, custom_name: str) -> Optional[int]:
    """
    Forward file to log channel using copy().
    renames via caption and handles caching issues.
    """
    try:
        # Create a clean caption with the Custom Name
        file_size_mb = getattr(message.document or message.video or message.audio, "file_size", 0) // (1024 * 1024)
        
        caption_text = (
            f"🎬 **{custom_name}**\n\n"
            f"💾 **Size:** {file_size_mb} MB\n"
            f"👤 **Uploaded By:** {message.from_user.mention}\n"
            f"📅 **Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"⚠️ **Files Provided By StreamVault**"
        )

        # Using copy() handles media types automatically (Video vs Document)
        sent = await message.copy(
            chat_id=LOG_CHANNEL,
            caption=caption_text
        )
        logger.info(f"✅ File copied to log channel: {sent.id}")
        return sent.id

    except (ValueError, KeyError) as e:
        logger.error(
            f"❌ Peer Invalid Error ({e}). The Bot doesn't 'know' the Log Channel ID yet.\n"
            f"FIX: Go to your Log Channel ({LOG_CHANNEL}) and send '/start' or any message."
        )
        return None
        
    except FloodWait as e:
        logger.warning(f"Flood wait during send: {e.value}s")
        await asyncio.sleep(e.value + 5)
        return await forward_to_log_channel(client, message, custom_name)
        
    except Exception as e:
        logger.error(f"Failed to send to log channel: {e}", exc_info=True)
        return None

async def download_youtube_video(url: str, user_id: int, progress_hook=None) -> Optional[str]:
    """Download YouTube video with robust network handling (IPv4/Proxy/Cookies)"""
    temp_dir = tempfile.mkdtemp()
    
    # 1. Base Options
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': 'best[filesize<500M]/best', # Prioritize size limit
        'quiet': False,
        'retries': 10,
        'fragment_retries': 10,
        'force_ipv4': True,      # CRITICAL FIX
        'geo_bypass': True,
        'nocheckcertificate': True,
        'progress_hooks': [progress_hook] if progress_hook else [],
    }
    
    # 2. Proxy Check (from Secrets)
    proxy_url = os.environ.get("PROXY_URL") or os.environ.get("HTTP_PROXY")
    if proxy_url:
        logger.info(f"[USER {user_id}] Using Proxy for download.")
        ydl_opts['proxy'] = proxy_url

    # 3. Cookie Handling (Optional but recommended)
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    # 4. Attempt Download
    try:
        logger.info(f"[USER {user_id}] Starting YT download (Proxy: {bool(proxy_url)}, IPv4: True)")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Double check file existence
            if os.path.exists(filename):
                return filename
            
            # Fallback: Search dir for specific extensions if filename match fails
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    return os.path.join(temp_dir, file)
                    
            return None

    except Exception as e:
        logger.error(f"[USER {user_id}] Download Error: {e}")
        return None

async def send_progress_message(client: Client, message: Message, text: str) -> Message:
    """Send or edit progress message"""
    if hasattr(send_progress_message, 'progress_msg') and send_progress_message.progress_msg:
        try:
            return await send_progress_message.progress_msg.edit_text(text)
        except:
            pass
    
    send_progress_message.progress_msg = await message.reply_text(text, quote=True)
    return send_progress_message.progress_msg

# --- UPDATED: Allow /start in Log Channel to cache Peer ID ---
@Client.on_message((filters.private | filters.chat(LOG_CHANNEL)) & filters.command("start"))
async def handle_start(client: Client, message: Message):
    """Handle /start command (Allowed in Log Channel)"""
    
    # If this message is from the Log Channel, reply specifically to confirm connection
    if message.chat.id == LOG_CHANNEL:
        await message.reply_text(
            "✅ **Bot Connected!**\nAccess Hash cached successfully.\nForwarding will now work.",
            quote=True
        )
        return
    
    """Handle /start command (Allowed in private(bot chat)"""
    try:
        welcome_text = """👋 **Welcome to Shadow Streamer!**

Here's what you can do:
1️⃣ **Send any file** → I'll index it for streaming
2️⃣ **Send a YouTube link** → I'll download and archive it
3️⃣ **Request /catalog** → See all indexed files
4️⃣ **Request `/delete [ID]`** → Remove a file from archive

⚠️ **Limits:**
• Max file size: {max_size}MB
• Max video duration: {max_hours} hours
• Storage is permanent (stored in private channel)

🔗 **Stream Links:** Available after file indexing"""

        await message.reply_text(
            welcome_text.format(
                max_size=Config.MAX_FILE_SIZE_MB,
                max_hours=Config.MAX_VIDEO_DURATION_HOURS
            ),
            quote=True
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")


@Client.on_message(filters.private & filters.command("help"))
async def handle_help(client: Client, message: Message):
    """
    Handle /help command.
    
    Displays comprehensive bot usage instructions including:
    - File upload process
    - YouTube download feature
    - Catalog management commands
    - Stream link format
    - File limits and troubleshooting
    
    Args:
        client (Client): Pyrogram bot client
        message (Message): User's /help command message
    """
    try:
        help_text = """🆘 **Help - Shadow Streamer Commands**

**📁 File Upload:**
Send any file → I'll ask for a custom name → File gets indexed and stream link generated

**🎬 YouTube Downloads:**
Send YouTube URL → I'll download and archive it → Stream link generated

**📚 Catalog Management:**
/catalog - View all indexed files with pagination
`/delete [message_id]` - Remove file from archive (soft delete)
`/search [query]` - Search files by name using keywords

**🔗 Stream Links:**
Format: `https://yourbot.hf.space/stream/[chat_id]/[message_id]`
Example: `{url}/stream/{log_channel}/159`

Links support:
• Browser playback (Chrome, Firefox, Safari)
• Media players (VLC, MPV)
• HTTP byte-range requests (seeking/scrubbing)

**⚠️ File Limits:**
• Maximum size: {max_size}MB (prevents Telegram timeout)
• Maximum duration: {max_hours} hours
• Supported: videos, audio, documents

**❓ Need Help?**
File too large? → Split into smaller parts
Download failing? → Wait 1 minute and try again
Stream buffering? → Try different player or lower quality
Still stuck? → Contact support""".format(
            max_size=Config.MAX_FILE_SIZE_MB,
            max_hours=Config.MAX_VIDEO_DURATION_HOURS,
            url=Config.URL,
            log_channel=Config.LOG_CHANNEL_ID
        )
        
        await message.reply_text(help_text, quote=True)
    except Exception as e:
        logger.error(f"Error in help command: {e}")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file_upload(client: Client, message: Message):
    """
    Handle direct file uploads from users (documents, videos, and audio).
    
    Workflow:
    1. User sends a file to the bot (document, video, or audio)
    2. Bot validates file size (max 500MB by default)
    3. Bot asks user for a custom name
    4. Bot stores upload state temporarily awaiting custom name
    
    Args:
        client (Client): Pyrogram bot client
        message (Message): User's file upload message
        
    Flow:
        - Extract file metadata (size, name, ID) from any supported file type
        - Check against MAX_FILE_SIZE limit
        - Store in upload_states dictionary for tracking
        - Send prompt asking for custom name
    """
    try:
        # Extract file from whichever type was sent (document, video, or audio)
        file = message.document or message.video or message.audio
        if not file:
            await message.reply_text("❌ No file found in message", quote=True)
            return

        # Log file reception
        file_type = type(file).__name__.lower()
        logger.info(
            f"File upload received: type={file_type}, "
            f"size={getattr(file, 'file_size', 'unknown')}, "
            f"user={message.from_user.id}"
        )

        # Get file size
        file_size = getattr(file, 'file_size', 0)
        if not file_size:
            await message.reply_text("❌ Could not determine file size", quote=True)
            return

        # Validate file size against configured limit
        is_valid, error_msg = await validate_file_size(file_size)
        if not is_valid:
            size_mb = file_size // (1024 * 1024)
            logger.warning(f"File rejected (too large): {size_mb}MB, user={message.from_user.id}")
            await message.reply_text(error_msg, quote=True)
            return

        # Get file name
        file_name = getattr(file, "file_name", None) or f"file_{int(time.time())}"

        # Store file info temporarily while waiting for custom name
        file_info = {
            "file_id": file.file_id,
            "file_unique_id": getattr(file, "file_unique_id", ""),
            "file_size": file_size,
            "file_name": file_name,
            "mime_type": getattr(file, "mime_type", ""),
            "source": "direct_upload",
            "file_type": file_type
        }
        
        # Create upload state and store for this user
        user_states[message.from_user.id] = FileState(message, file_info)
        logger.debug(f"Upload state created for user {message.from_user.id}")
        
        # Cancel BUTTON 
        cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Upload", callback_data="state_cancel")]])

        # Show confirmation and ask for custom name
        await message.reply_text(
            f"✅ **File received!**\n\n"
            f"📄 **Details:**\n"
            f"• Name: {file_name}\n"
            f"• Size: {file_size // (1024 * 1024)} MB\n"
            f"• Type: {file_type.upper()}\n\n"
            f"📝 **Please provide a Name for this file:**\n"
            f"(e.g., \"Matrix.mp4\")\n\n"
            f"⏭️ **Or type /skip to use default name.**",
            quote=True,
        reply_markup=cancel_btn
        )
    except Exception as e:
        logger.error(f"Error in file upload handler: {str(e)}", exc_info=True)
        await message.reply_text(
            f"❌ **Error processing file**\n"
            f"🔄 Reason: {str(e)[:100]}\n"
            f"💡 Try again or contact support",
            quote=True
        )


@Client.on_message(filters.private & filters.text)
async def handle_text(client: Client, message: Message):
    text = message.text.strip()
    
    # 1. Ignore Commands / YT Check / Renaming check... (Keep your previous logic)
    if text.startswith("/") and text.lower() != "/skip":
        message.continue_propagation()
        return

    if is_youtube_url(text):
        await handle_youtube_download(client, message)
        return

    # 2. State Routing
    user_id = message.from_user.id
    if user_id in user_states:
        state = user_states[user_id]
        
        # Naming Logic...
        if text.lower() == "/skip":
            if state.type == "file": name = state.file_info["file_name"]
            else: name = state.info.get("title", f"Video_{int(time.time())}")
        else:
            name = text

        state.custom_name = str(name).replace("/", "_")[:200]
        
        # Route
        if state.type == "file":
            # Direct files don't fail, so we can run and clean up.
            await process_file_final(client, state)
            del user_states[user_id] # Clean file state
            
        elif state.type == "youtube":
            # YT might need to retry, so 'process_youtube_final' will handle the 'del user_states'
            await process_youtube_final(client, state)
        
        return

async def handle_youtube_download(client: Client, message: Message):
    """
    Step 1: Fetch Video Info
    Step 2: Show Resolution Keyboard (Menu)
    """
    url = message.text.strip()
    user_id = message.from_user.id
    status_msg = await message.reply_text("🔎 **Analyzing Link...**\nChecking available resolutions...", quote=True)
    
    # 1. Fetch Metadata
    # We validate here using your robust validation function
    is_valid, error, info = await validate_youtube_video(url)
    if not is_valid:
        await status_msg.edit_text(error)
        return

    # 2. Interactive Menu (Quality Buttons)
    buttons = [
        [
                InlineKeyboardButton("🌟 1080p (Best)", callback_data="yt_1080"),
            InlineKeyboardButton("📺 720p (HD)", callback_data="yt_720")
        ],
        [
            InlineKeyboardButton("📱 480p (SD)", callback_data="yt_480"),
            InlineKeyboardButton("📉 360p (Saver)", callback_data="yt_360")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="yt_cancel")]
    ]
    
    # 3. Store Info (So we can download it AFTER renaming)
    user_states[user_id] = YouTubeState(message, info, url)
    user_states[user_id].last_msg = status_msg
    
    title = info.get('title', 'Unknown Video')
    duration_str = time_formatter(info.get('duration', 0) * 1000)
    
    await status_msg.edit_text(
        f"🎬 **Found:** {title}\n"
        f"⏱️ **Duration:** {duration_str}\n\n"
        f"👇 **Select Quality to Download:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    
async def process_youtube_final(client: Client, state: YouTubeState):
    """Download loop. On failure, asks user to retry Quality."""
    msg = state.last_msg
    try:
        await msg.edit_text(f"⏳ **Starting Download...**\nQuality: {state.quality}p")
    except:
        msg = await state.message.reply_text("⏳ **Starting...**")

    start_time = time.time()
    
    # Sync Hook wrapper
    def dl_progress(d):
        if d['status'] == 'downloading':
            try:
                current = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)
                client.loop.create_task(
                    show_progress(current, total, msg, start_time, stage=f"Downloading ({state.quality}p)")
                )
            except: pass

    # 1. Attempt Download
    file_path = await download_yt_res(state.url, state.quality, dl_progress)
    
    # --- FAILURE HANDLER (Retry Logic) ---
    if not file_path:
        # Re-define buttons for retry
        buttons = [
            [InlineKeyboardButton("📺 720p", callback_data="yt_720"), InlineKeyboardButton("📱 480p", callback_data="yt_480")],
            [InlineKeyboardButton("📉 360p", callback_data="yt_360"), InlineKeyboardButton("❌ Cancel", callback_data="yt_cancel")]
        ]
        
        await msg.edit_text(
            f"❌ **Download Failed for {state.quality}p**\n\n"
            f"📉 The file might be too large or the quality unavailable.\n"
            f"👇 **Please select a lower quality:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        # CRITICAL: We DO NOT delete 'user_states[id]' here. 
        # The user stays in the state to click the new button.
        return

    # --- SUCCESS HANDLER ---
    # 2. Upload Wrapper
    f_size = os.path.getsize(file_path)
    file_name = f"{state.custom_name}.mp4" 
    
    log_caption = (
        f"🎬 **{state.custom_name}**\n\n"
        f"👤 **Task By:** {state.message.from_user.mention}\n"
        f"💿 **Quality:** {state.quality}p\n"
        f"📦 **Size:** {humanbytes(f_size)}\n"
        f"📅 **Date:** {datetime.now().strftime('%Y-%m-%d')}\n"
        f"#StreamVault"
    )

    try:
        start_up = time.time()
        async def up_progress(current, total):
            await show_progress(current, total, msg, start_up, stage="Uploading to Cloud")

        with open(file_path, 'rb') as f:
            sent = await client.send_document(
                chat_id=int(Config.LOG_CHANNEL_ID),
                document=f,
                file_name=file_name,
                caption=log_caption,
                progress=up_progress
            )
        
        # 3. DB Save
        link = f"{Config.URL}/stream/{Config.LOG_CHANNEL_ID}/{sent.id}"
        file_data = {
            "message_id": sent.id,
            "custom_name": state.custom_name,
            "file_size": f_size,
            "file_type": "video",
            "quality": f"{state.quality}p",
            "uploaded_by": state.message.from_user.id,
            "stream_link": link
        }
        await db.save_file(file_data)
        
        await msg.edit_text(
            f"✅ **Success!**\n"
            f"🎬 Name: {state.custom_name}\n"
            f"💿 Quality: {state.quality}p\n\n"
            f"🔗 **[Click Here to Stream]({link})**",
            disable_web_page_preview=True
        )
        
        # CLEANUP STATE (Only on Success)
        del user_states[state.message.from_user.id]

    except Exception as e:
        logger.error(f"YT Process: {e}")
        await msg.edit_text(f"❌ Upload Failed: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)
        try: os.rmdir(os.path.dirname(file_path))
        except: pass
    
async def download_yt_res(url, height, hook):
    """
    Download with logic:
    1. Try Standard (Fast, uses IPv4 + Android Spoof)
    2. If 403 Forbidden -> Create Cookies from Secret & Retry
    """
    temp_dir = tempfile.mkdtemp()
    
    # 1. Setup Base Options
    if str(height).isdigit():
        fmt_str = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
    else:
        fmt_str = "best"
    
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': fmt_str,
        'quiet': False,
        'force_ipv4': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'retries': 3, # Lower retries since we handle logic manually
        'progress_hooks': [hook] if hook else [],
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
    }

    proxy = os.environ.get("PROXY_URL") or os.environ.get("HTTP_PROXY")
    if proxy: ydl_opts['proxy'] = proxy

    # Helper to run the download
    def run_download(options):
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            return e # Return the error to check it

    # Attempt 1: Standard
    logger.info(f"Attempting download for {height}p (No Cookies)...")
    result = run_download(ydl_opts)
    
    # Check success
    if isinstance(result, str) and os.path.exists(result):
        return result
        
    # Check for 403 Forbidden (needs Cookies)
    if isinstance(result, Exception) and "HTTP Error 403" in str(result):
        logger.warning("Got 403 Forbidden. Retrying with Cookies...")
        
        # --- RETRY WITH SECRETS COOKIES ---
        secret_cookies = os.environ.get("YT_COOKIES")
        cookie_path = "cookies.txt"
        created = False
        
        if secret_cookies:
            with open(cookie_path, "w") as f: f.write(secret_cookies)
            ydl_opts['cookiefile'] = cookie_path
            created = True
            
            # Attempt 2
            result = run_download(ydl_opts)
            
            # Cleanup Secret File
            if created and os.path.exists(cookie_path):
                os.remove(cookie_path)
                
            if isinstance(result, str) and os.path.exists(result):
                return result
                
    return None
        
async def process_file_final(client: Client, state: FileState):
    """
    Handle direct file indexing.
    Replaces the old 'process_file_upload'.
    """
    msg = await state.message.reply_text("⏳ **Indexing File...**", quote=True)
    
    # 1. Prepare Styled Caption (The "New Look")
    size_str = humanbytes(state.file_info["file_size"])
    log_caption = (
        f"🎬 **{state.custom_name}**\n\n"
        f"👤 **User:** {state.message.from_user.mention}\n"
        f"💾 **Size:** {size_str}\n"
        f"📅 **Date:** {datetime.now().strftime('%Y-%m-%d')}\n"
        f"#StreamVault"
    )

    try:
        # 2. Forward to Log (Using copy + new caption)
        # This acts exactly like your old forward function but natively supports renaming
        log_msg = await state.message.copy(
            chat_id=LOG_CHANNEL,
            caption=log_caption
        )
        
        # 3. Save to Database
        link = f"{Config.URL}/stream/{LOG_CHANNEL}/{log_msg.id}"
        file_data = {
            "message_id": log_msg.id,
            "custom_name": state.custom_name,
            "file_size": state.file_info["file_size"],
            "file_type": state.file_info["file_type"],
            "uploaded_by": state.message.from_user.id,
            "stream_link": link
        }
        await db.save_file(file_data)
        
        # 4. Success Message (Hidden Link Style)
        await msg.edit_text(
            f"✅ **Indexed Successfully!**\n"
            f"🎬 Name: {state.custom_name}\n\n"
            f"🔗 **[Click Here to Stream]({link})**",
            disable_web_page_preview=True
        )

    except (ValueError, KeyError):
        # Specific Catch for the "Peer Invalid" / Private Channel Cache issue
        await msg.edit_text(f"❌ **Server Cache Error**\nPlease send `/start` inside your Log Channel to fix the permission link.")
    except Exception as e:
        logger.error(f"File process error: {e}")
        await msg.edit_text(f"❌ System Error: {e}")

# CLEANUP (Since this flow always ends here)
    if state.message.from_user.id in user_states:
        del user_states[state.message.from_user.id]
        
# Callback Queries -----

@Client.on_callback_query(filters.regex(r"^yt_"))
async def handle_yt_buttons(client: Client, callback: CallbackQuery):
    """Handles Quality Selection Clicks"""
    user_id = callback.from_user.id
    data = callback.data
    
    if data == "yt_cancel":
        if user_id in user_states: del user_states[user_id]
        await callback.message.edit_text("❌ **Task Cancelled.**")
        return

    # Check State validity
    if user_id not in user_states or user_states[user_id].type != "youtube":
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    state = user_states[user_id]
    target_res = int(data.split("_")[1]) # Extracts 1080 from "yt_1080"
    state.quality = target_res
    
    # NEW: Add Cancel Button to renaming phase
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Task", callback_data="state_cancel")]])
    
    await callback.message.edit_text(
        f"✅ Selected: **{target_res}p**\n\n"
        f"📝 **Renaming:**\n"
        f"Send a name for the video, or type /skip.\n\n"
        f"Video: `{state.info.get('title')}`",
        reply_markup=cancel_btn
    )
    
@Client.on_callback_query(filters.regex("^state_cancel$"))
async def cancel_state_handler(client: Client, callback: CallbackQuery):
    """Generic Cancel button handler for any State (File or YT)"""
    user_id = callback.from_user.id
    if user_id in user_states:
        del user_states[user_id]
        await callback.message.edit_text("❌ **Process Cancelled by User.**")
    else:
        await callback.answer("Nothing to cancel.", show_alert=True)

async def forward_file_to_log_channel(client: Client, file_path: str, file_name: str, video_info: Dict) -> Optional[int]:
    """Forward downloaded file to log channel"""
    try:
        # Send file to log channel
        with open(file_path, 'rb') as f:
            sent_msg = await client.send_document(
                chat_id=Config.LOG_CHANNEL_ID,
                document=f,
                file_name=file_name,
                caption=f"📹 {video_info.get('title', file_name)}\n🔗 Source: YouTube\n👤 User: From private upload"
            )
        return sent_msg.id
        
    except FloodWait as e:
        logger.warning(f"Flood wait during YouTube upload: {e.value}s")
        await asyncio.sleep(e.value + 5)
        return await forward_file_to_log_channel(client, file_path, file_name, video_info)
    except Exception as e:
        logger.error(f"Failed to forward YouTube file: {e}")
        return None

@Client.on_message(filters.private & filters.command("catalog"))
async def handle_catalog(client: Client, message: Message):
    """Handle /catalog command"""
    try:
        # Get files from database
        files = await db.get_catalog(limit=50)
        total_count = await db.get_catalog_count()
        
        if not files:
            await message.reply_text(
                "📚 **Your Archive is empty**\n\n"
                "Send me a file or YouTube link to get started!",
                quote=True
            )
            return
        
        # Format catalog message
        catalog_text = f"📚 **Your Archive** ({total_count} files):\n\n"
        
        for i, file in enumerate(files, 1):
            size_mb = file.get('file_size', 0) // 1024 // 1024
            size_str = f"{size_mb} MB"
            
            # Add warning for large files
            if size_mb > 100:
                size_str += " ⚠️ Large file"
            
            # Add file type emoji
            file_type = file.get('file_type', 'file')
            emoji = "🎬" if file_type == "video" else "🎵" if file_type == "audio" else "📄"
            
            catalog_text += f"{i}. {emoji} **{file.get('custom_name', 'Unknown')}** ({size_str})\n"
            catalog_text += f"   └─ 🔗 /stream_{file.get('message_id')}\n\n"
        
        catalog_text += f"💡 **Use:** `/stream_[ID]` to get the direct link"
        
        await message.reply_text(catalog_text, quote=True)
        
    except Exception as e:
        logger.error(f"Catalog command failed: {e}")
        await message.reply_text(
            "❌ **Catalog error**\n🔄 Please try again later",
            quote=True
        )
        
@Client.on_message(filters.private & filters.regex(r"^/stream_(\d+)"))
async def handle_stream_command(client: Client, message: Message):
    """Handle dynamic /stream_[id] commands"""
    try:
        # Extract message_id from the regex match (Group 1)
        message_id = int(message.matches[0].group(1))
        
        # Verify file exists in DB
        file_info = await db.get_file(message_id)
        if not file_info:
            await message.reply_text("❌ **File not found in database.**", quote=True)
            return
            
        # Generate link
        stream_link = file_info.get('stream_link') or f"{Config.URL}/stream/{Config.LOG_CHANNEL_ID}/{message_id}"
        custom_name = file_info.get('custom_name', 'Video')
        
        # Reply with the hidden link
        await message.reply_text(
            f"🎬 **{custom_name}**\n\n"
            f"🔗 **[Click Here to Stream]({stream_link})**",
            quote=True,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Stream command error: {e}")

@Client.on_message(filters.private & filters.command("delete"))
async def handle_delete(client: Client, message: Message):
    """Delete command with Button Confirmation"""
    try:
        # Check if ID provided
        if len(message.command) < 2:
            await message.reply_text("ℹ️ Usage: `/delete [Message_ID]`", quote=True)
            return

        mid = message.command[1]
        
        # 1. Fetch file info for confirmation (Make it look good)
        file_info = await db.get_file(int(mid))
        if not file_info:
            await message.reply_text("❌ File not found in Database.", quote=True)
            return

        file_name = file_info.get('custom_name', 'Unknown')
        
        # 2. Show Buttons
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🗑️ Yes, Delete", callback_data=f"del_conf_{mid}"),
                InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")
            ]
        ])
        
        await message.reply_text(
            f"⚠️ **Confirm Deletion?**\n\n"
            f"📂 File: **{file_name}**\n"
            f"🆔 ID: `{mid}`\n\n"
            f"This will remove it from the Index.",
            reply_markup=buttons,
            quote=True
        )
    except ValueError:
        await message.reply_text("❌ ID must be a number.", quote=True)

# Callback for the Delete Buttons
@Client.on_callback_query(filters.regex(r"^del_"))
async def delete_callback_handler(client: Client, callback: CallbackQuery):
    data = callback.data
    
    if data == "del_cancel":
        await callback.message.edit_text("❌ **Deletion Cancelled.**")
        return
        
    if data.startswith("del_conf_"):
        mid = int(data.split("_")[2])
        if await db.delete_file(mid):
            await callback.message.edit_text(f"✅ **Deleted Successfully!**\nID: `{mid}` has been removed.")
        else:
            await callback.message.edit_text("❌ Error: Could not delete (maybe already gone).")

@Client.on_message(filters.private & filters.command("search"))
async def handle_search(client: Client, message: Message):
    """Handle /search command"""
    try:
        # Parse search query
        query = message.text.replace('/search', '').strip()
        if not query:
            await message.reply_text(
                "❌ **No search query**\n\n"
                "Usage: `/search [filename]`\n\n"
                "Example: `/search avengers`",
                quote=True
            )
            return
        
        # Search files
        files = await db.search_files(query, limit=20)
        
        if not files:
            await message.reply_text(
                f"❌ **No files found**\nQuery: `{query}`",
                quote=True
            )
            return
        
        # Format results
        search_text = f"🔍 **Search Results** for `{query}` ({len(files)} files):\n\n"
        
        for i, file in enumerate(files, 1):
            size_mb = file.get('file_size', 0) // 1024 // 1024
            size_str = f"{size_mb} MB"
            
            # Add file type emoji
            file_type = file.get('file_type', 'file')
            emoji = "🎬" if file_type == "video" else "🎵" if file_type == "audio" else "📄"
            
            search_text += f"{i}. {emoji} **{file.get('custom_name', 'Unknown')}** ({size_str})\n"
            search_text += f"   └─ 🔗 `/stream_{file.get('message_id')}`\n\n"
        
        await message.reply_text(search_text, quote=True)
        
    except Exception as e:
        logger.error(f"Search command failed: {e}")
        await message.reply_text(
            "❌ **Search error**\n🔄 Please try again",
            quote=True
        )
