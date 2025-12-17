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
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message
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

# State management for file uploads
upload_states = {}

class UploadState:
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
    def __init__(self, message: Message, file_info: Dict[str, Any]):
        self.message = message
        self.file_info = file_info
        self.custom_name = None
        self.created_at = datetime.utcnow()

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
    """Validate YouTube video before download"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Check duration
            duration = info.get('duration', 0)
            if duration > MAX_DURATION:
                hours = duration // 3600
                return False, f"Video too long: {hours}h {(duration % 3600) // 60}m\n⚠️ Maximum duration: {Config.MAX_VIDEO_DURATION_HOURS} hours", None
            
            # Check file size (if available)
            filesize = info.get('filesize') or info.get('filesize_approx', 0)
            if filesize and filesize > MAX_FILE_SIZE:
                size_mb = filesize // 1024 // 1024
                return False, f"Video too large: {size_mb}MB\n⚠️ Maximum size: {Config.MAX_FILE_SIZE_MB}MB (prevents timeout)", None
            
            return True, None, info
            
    except Exception as e:
        return False, f"❌ Download failed\n🔄 Reason: Unable to fetch video info\n💡 Try again in 1 minute", None

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
    """Download YouTube video and return file path"""
    temp_dir = tempfile.mkdtemp()
    
    # Attempt 1: Without cookies
    logger.info(f"[USER {user_id}] Attempting YouTube download (no cookies): {url}")
    if progress_hook:
        await progress_hook("📥 Downloading video... (attempt 1/2)")
    
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': 'best[filesize<500M]/best',
        'quiet': False,
        'no_warnings': False,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'progress_hooks': [progress_hook] if progress_hook else [],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"[USER {user_id}] Starting yt-dlp extraction")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Find the downloaded file
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    logger.info(
                        f"[USER {user_id}] ✅ YouTube download success (no cookies): "
                        f"title={info.get('title', 'Unknown')}, path={filename}"
                    )
                    return os.path.join(temp_dir, file)
            
            return None
            
    except Exception as e:
        error1 = str(e)
        logger.warning(f"[USER {user_id}] ⚠️ Download failed without cookies: {error1}")
    
    # Attempt 2: With cookies.txt
    cookies_path = Path("cookies.txt")
    if cookies_path.exists():
        logger.info(f"[USER {user_id}] Attempting YouTube download (with cookies): {url}")
        if progress_hook:
            await progress_hook("📥 Downloading video... (attempt 2/2, with cookies)")
        
        ydl_opts['cookiefile'] = str(cookies_path)
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"[USER {user_id}] Starting yt-dlp extraction (with cookies)")
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Find the downloaded file
                for file in os.listdir(temp_dir):
                    if file.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                        logger.info(
                            f"[USER {user_id}] ✅ YouTube download success (with cookies): "
                            f"title={info.get('title', 'Unknown')}"
                        )
                        return os.path.join(temp_dir, file)
                
                return None
            
        except Exception as e:
            error2 = str(e)
            logger.error(f"[USER {user_id}] ❌ Download failed even with cookies: {error2}")
    else:
        logger.warning(f"[USER {user_id}] ⚠️ No cookies.txt found, skipping cookies attempt")
    
    logger.error(f"[USER {user_id}] ❌ YouTube download completely failed")
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
        upload_states[message.from_user.id] = UploadState(message, file_info)
        logger.debug(f"Upload state created for user {message.from_user.id}")

        # Show confirmation and ask for custom name
        await message.reply_text(
            f"✅ **File received!**\n\n"
            f"📄 **Details:**\n"
            f"• Name: {file_name}\n"
            f"• Size: {file_size // (1024 * 1024)} MB\n"
            f"• Type: {file_type.upper()}\n\n"
            f"📝 **Please provide a Name for this file:**\n"
            f"(e.g., \"Matrix.mp4\")\n\n"
            f"⏭️ **Or type `/skip` to use default name.**",
            quote=True
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
async def handle_text_messages(client: Client, message: Message):
    """Handle text messages (YouTube URLs and custom names)"""
    
    # 1. IGNORE COMMANDS: If text starts with '/', let it pass to specific command handlers
    # (Except '/skip' which is part of our renaming logic)
    text_clean = message.text.strip()
    if text_clean.startswith("/") and text_clean.lower() != "/skip":
        message.continue_propagation()
        # This raises an internal Pyrogram exception to jump to the next handler
        # It must NOT be inside a general try/except block.

    try:
        user_id = message.from_user.id
        
        # Check if this is a custom name (or skip command) for a file upload
        if user_id in upload_states:
            state = upload_states[user_id]
            
            # 1. Handle Skip - Default to original filename or generated unique name
            if text_clean.lower() == "/skip":
                original_name = state.file_info.get("file_name")
                if original_name and original_name != "None":
                    custom_name = original_name
                else:
                    custom_name = f"StreamVault_Upload_{int(time.time())}"
                await message.reply_text(f"⏭️ Skipping rename. Using name: `{custom_name}`", quote=True)
                
            # 2. Handle Actual Custom Name
            else:
                custom_name = text_clean
                if len(custom_name) > 200:
                     await message.reply_text("❌ Name too long. Keep it under 200 characters.", quote=True)
                     return

            # Process the file upload with the finalized name
            await process_file_upload(client, state, custom_name)
            
            # Clean up upload state
            del upload_states[user_id]
            return
        
        # Check if this is a YouTube URL
        if is_youtube_url(message.text):
            await handle_youtube_download(client, message)
            return
            
        # Unknown text message
        await message.reply_text(
            "❓ Send me a **file** or **YouTube link** to get started!\n"
            "Use /help for more information.",
            quote=True
        )

    except Exception as e:
        logger.error(f"Error in text message handler: {e}", exc_info=True)


async def process_file_upload(client: Client, state: UploadState, custom_name: str):
    """Process file upload with custom name"""
    try:
        # Send progress message
        progress_msg = await state.message.reply_text(
            "⏳ **Processing...** Please wait\n"
            f"📝 Applying Name: {custom_name}\n"
            "📤 Copying to archive...",
            quote=True
        )
        
        # Forward to log channel with the new Custom Name
        forwarded_msg_id = await forward_to_log_channel(client, state.message, custom_name)
        if not forwarded_msg_id:
            await progress_msg.edit_text(
                "❌ **Upload failed**\n🔄 Reason: Unable to forward to archive\n💡 Try again or contact support"
            )
            return
        
        # Prepare file data for database
        file_data = {
            "message_id": forwarded_msg_id,
            "file_unique_id": state.file_info["file_unique_id"],
            "file_id": state.file_info["file_id"],
            "custom_name": custom_name,
            "file_size": state.file_info["file_size"],
            "file_type": state.file_info["file_type"],
            "source": state.file_info["source"],
            "uploaded_by": state.message.from_user.id,
            "stream_link": f"{Config.URL}/stream/{Config.LOG_CHANNEL_ID}/{forwarded_msg_id}"
        }
        
        # Save to database
        result_id = await db.save_file(file_data)
        if not result_id:
            await progress_msg.edit_text(
                "❌ **Database error**\nFile forwarded but indexing failed\n💡 Contact support"
            )
            return
        
        # Send success message
        await progress_msg.edit_text(
            "✅ **File indexed successfully!**\n\n"
            f"📊 **Details:**\n"
            f"• Name: {custom_name}\n"
            f"• Size: {state.file_info['file_size'] // 1024 // 1024} MB\n"
            f"• Message ID: {forwarded_msg_id}\n\n"
            f"🔗 **[Stream Ready ✨]({file_data['stream_link']})**"
        )
        
    except Exception as e:
        logger.error(f"File upload processing failed: {e}")
        await state.message.reply_text(
            "❌ **Processing failed**\n🔄 Please try again later\n💡 If problem persists, contact support",
            quote=True
        )

async def handle_youtube_download(client: Client, message: Message):
    """Handle YouTube video downloads with enhanced progress tracking and cookies fallback"""
    url = message.text.strip()
    user_id = message.from_user.id
    
    try:
        logger.info(f"[USER {user_id}] Starting YouTube download workflow")
        
        # Send initial message
        progress_msg = await message.reply_text(
            "✅ **Link received!**\n⏳ Processing... this may take a moment",
            quote=True
        )
        
        # Validate video
        is_valid, error_msg, video_info = await validate_youtube_video(url)
        if not is_valid:
            logger.warning(f"[USER {user_id}] Video validation failed: {error_msg}")
            await progress_msg.edit_text(error_msg)
            return
        
        # Progress callback to update status message
        async def update_progress(msg: str):
            try:
                await progress_msg.edit_text(f"⏳ {msg}")
            except Exception as e:
                logger.debug(f"Could not update progress: {e}")
        
        # Download progress callback
        download_started = False
        
        async def download_progress_hook(d):
            nonlocal download_started
            if d['status'] == 'downloading':
                if not download_started:
                    await update_progress(
                        f"📥 **Downloading video...**\n"
                        f"🎬 **{video_info.get('title', 'Video')}**\n\n"
                        f"[{'█' * 4}{'░' * 6}] 0%\nETA: calculating..."
                    )
                    download_started = True
                
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 1)
                percent = min(100, (downloaded / total) * 100)
                
                bar_length = 10
                filled = int(bar_length * percent / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                speed = d.get('speed', 0) or 0
                if speed:
                    speed_str = f"{speed // 1024 // 1024} MB/s"
                else:
                    speed_str = "calculating..."
                
                eta = d.get('eta', 0)
                if eta:
                    eta_str = f"{eta // 60}m {eta % 60}s"
                else:
                    eta_str = "calculating..."
                
                await update_progress(
                    f"📥 **Downloading video...**\n"
                    f"🎬 **{video_info.get('title', 'Video')}**\n\n"
                    f"[{bar}] {percent:.1f}%\n"
                    f"⚡ Speed: {speed_str}\n"
                    f"⏰ ETA: {eta_str}"
                )
            
            elif d['status'] == 'finished':
                await update_progress(
                    "✅ **Download complete!**\n"
                    "📤 **Uploading to archive...**"
                )
        
        # Download the video with user_id and enhanced logging
        logger.info(f"[USER {user_id}] Calling download_youtube_video()")
        file_path = await download_youtube_video(url, user_id, download_progress_hook)
        
        if not file_path:
            logger.error(f"[USER {user_id}] Download failed after both attempts")
            await progress_msg.edit_text(
                "❌ **Download failed**\n\n"
                "🔄 **Tried both methods:**\n"
                "• Attempt 1: Standard download\n"
                "• Attempt 2: With cookies (if available)\n\n"
                "💡 **Possible solutions:**\n"
                "• Video may be age-restricted\n"
                "• Video may not be available in your region\n"
                "• Try another YouTube video"
            )
            return
        
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        logger.info(
            f"[USER {user_id}] Download complete: "
            f"title={video_info.get('title', file_name)}, size={file_size}, path={file_path}"
        )
        
        # Upload to Telegram
        try:
            logger.info(f"[USER {user_id}] Starting upload to Telegram")
            
            # Forward the file to log channel
            forwarded_msg_id = await forward_file_to_log_channel(client, file_path, file_name, video_info)
            if not forwarded_msg_id:
                logger.error(f"[USER {user_id}] Upload to Telegram failed")
                await progress_msg.edit_text(
                    "❌ **Upload to archive failed**\n"
                    "🔄 Connection timeout\n"
                    "💡 Try again in 1 minute"
                )
                return
            
            logger.info(f"[USER {user_id}] Upload complete: message_id={forwarded_msg_id}")
            
            # Prepare file data for database
            duration = video_info.get('duration', 0)
            
            file_data = {
                "message_id": forwarded_msg_id,
                "file_unique_id": video_info.get('id', 'youtube'),
                "file_id": forwarded_msg_id,  # Use message ID as file ID for YouTube
                "custom_name": video_info.get('title', file_name),
                "file_size": file_size,
                "file_type": "video",
                "source": "youtube_link",
                "youtube_url": url,
                "duration": duration,
                "uploaded_by": user_id,
                "stream_link": f"{Config.URL}/stream/{Config.LOG_CHANNEL_ID}/{forwarded_msg_id}"
            }
            
            # Save to database
            result_id = await db.save_file(file_data)
            if not result_id:
                logger.error(f"[USER {user_id}] Failed to save YouTube to MongoDB")
                await progress_msg.edit_text(
                    "⚠️ **Partial success**\n"
                    "Video uploaded to archive but indexing failed\n"
                    "💡 Try again or contact support"
                )
                return
            
            logger.info(
                f"[USER {user_id}] YouTube indexed in MongoDB: "
                f"title={video_info.get('title', file_name)}, size={file_size}"
            )
            
            # Format duration for display
            if duration:
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                duration_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            else:
                duration_str = "Unknown"
            
            # Send success message
            stream_link = f"{Config.URL}/stream/{Config.LOG_CHANNEL_ID}/{forwarded_msg_id}"
            await progress_msg.edit_text(
                f"✅ **Upload complete!**\n\n"
                f"📊 **Details:**\n"
                f"• Title: {video_info.get('title', file_name)[:50]}\n"
                f"• Size: {file_size // 1024 // 1024} MB\n"
                f"• Duration: {duration_str}\n"
                f"• Message ID: {forwarded_msg_id}\n\n"
                f"🔗 **[Stream Ready ✨]({file_data['stream_link']})**"
                f"💡 Use /catalog to see all your files"
            )
            
        finally:
            # Clean up temp file
            try:
                os.remove(file_path)
                os.rmdir(os.path.dirname(file_path))
                logger.info(f"[USER {user_id}] Deleted local file: {file_path}")
            except Exception as e:
                logger.warning(f"[USER {user_id}] Could not delete file: {e}")
                
    except Exception as e:
        logger.error(
            f"[USER {user_id}] Unexpected error in YouTube handler: {str(e)}",
            exc_info=True
        )
        await message.reply_text(
            f"❌ **Unexpected error**\n"
            f"🔄 Error: {str(e)[:100]}\n"
            f"💡 Check logs or try again",
            quote=True
        )

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
            catalog_text += f"   └─ 🔗 `/stream_{file.get('message_id')}`\n\n"
        
        catalog_text += f"💡 **Use:** `/stream_[ID]` to get the direct link"
        
        await message.reply_text(catalog_text, quote=True)
        
    except Exception as e:
        logger.error(f"Catalog command failed: {e}")
        await message.reply_text(
            "❌ **Catalog error**\n🔄 Please try again later",
            quote=True
        )

@Client.on_message(filters.private & filters.command("delete"))
async def handle_delete(client: Client, message: Message):
    """Handle /delete command"""
    try:
        # Parse command arguments
        args = message.text.split()
        if len(args) < 2:
            await message.reply_text(
                "❌ **Invalid command**\n\n"
                "Usage: `/delete [message_id]`\n\n"
                "Get message_id from /catalog",
                quote=True
            )
            return
        
        try:
            message_id = int(args[1])
        except ValueError:
            await message.reply_text(
                "❌ **Invalid message ID**\n"
                "Message ID must be a number",
                quote=True
            )
            return
        
        # Get file info before deletion
        file_info = await db.get_file(message_id)
        if not file_info:
            await message.reply_text(
                f"❌ **File not found**\nMessage ID: {message_id}",
                quote=True
            )
            return
        
        # Show confirmation prompt
        file_name = file_info.get('custom_name', 'Unknown')
        await message.reply_text(
            f"⚠️ **Delete \"{file_name}\"?**\n"
            f"This action cannot be undone.\n\n"
            f"Reply: `/confirm_delete_{message_id}`",
            quote=True
        )
        
    except Exception as e:
        logger.error(f"Delete command failed: {e}")
        await message.reply_text(
            "❌ **Delete command error**\n🔄 Please try again",
            quote=True
        )

@Client.on_message(filters.private & filters.command("confirm_delete"))
async def handle_confirm_delete(client: Client, message: Message):
    """Handle /confirm_delete command"""
    try:
        # Parse command
        command_parts = message.text.split('_')
        if len(command_parts) < 3:
            await message.reply_text("❌ Invalid delete confirmation command.", quote=True)
            return
        
        try:
            message_id = int(command_parts[2])
        except ValueError:
            await message.reply_text("❌ Invalid message ID.", quote=True)
            return
        
        # Perform deletion
        success = await db.delete_file(message_id)
        
        if success:
            await message.reply_text(
                f"✅ **File deleted successfully**\nMessage ID: {message_id}",
                quote=True
            )
        else:
            await message.reply_text(
                f"❌ **Delete failed**\nMessage ID: {message_id}",
                quote=True
            )
            
    except Exception as e:
        logger.error(f"Confirm delete failed: {e}")
        await message.reply_text(
            "❌ **Delete confirmation error**\n🔄 Please try again",
            quote=True
        )

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
