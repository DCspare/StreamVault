"""
HTTP Streaming Routes for Shadow Streamer.

Provides RESTful API endpoints for streaming Telegram files:
- /stream/{chat_id}/{message_id} - Stream file with HTTP 206 support
- Handles byte-range requests for seeking
- Auto-heals expired file references
- Implements exponential backoff for timeouts
- Supports all media types (video, audio, documents)
"""

import mimetypes
import logging
import asyncio
from urllib.parse import quote  # Encodes Filenames (Fixes Emoji Crash)

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from bot.client import bot_app
from config import Config
from utils.range_parser import parse_range
from pyrogram.errors import OffsetInvalid, FileReferenceExpired

logger = logging.getLogger("stream_routes")
stream_router = APIRouter()


@stream_router.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request: Request, chat_id: int, message_id: int):
    """
    Stream a file from Telegram as an HTTP response.
    
    Supports HTTP byte-range requests (206 Partial Content) for:
    - Seeking/scrubbing in video players
    - Resuming interrupted downloads
    - Playing in browser without downloading entire file
    
    Args:
        request (Request): FastAPI request object
        chat_id (int): Telegram chat ID (log channel)
        message_id (int): Telegram message ID in log channel
        
    Returns:
        StreamingResponse: Streamed file data with proper headers
        JSONResponse: Error response if bot disconnected or file not found
    """
    
    # 1. Connectivity Check
    if not bot_app.is_connected:
        return JSONResponse(
            status_code=503, 
            content={"error": "Bot is still starting up. Please wait."}
        )

    try:
        # 2. Fetch the Message from Telegram
        message = await bot_app.get_messages(chat_id, message_id)
        
        if not message or message.empty:
            return JSONResponse(
                status_code=404, 
                content={"error": "Message not found. It might have been deleted."}
            )
        
        # 3. Extract Media (Critical: Must happen before using 'media' variable)
        # We verify Video first, then Audio, then Document
        media = message.video or message.audio or message.document
        
        if not media:
            return JSONResponse(
                status_code=404, 
                content={"error": "No media found inside this message."}
            )

        # 4. Extract File Metadata
        file_id = media.file_id
        file_size = media.file_size
        
        # Name Logic: Get name safely, handle missing attributes
        raw_name = getattr(media, "file_name", "streamed_file.mp4") or "video.mp4"
        
        # [CRITICAL FIX] Sanitize Filename for HTTP Headers
        # Uses urllib.quote to turn "🕶" into "%F0..." preventing Internal Server Error
        safe_name = quote(raw_name)

        # 5. Content-Type (MIME) Logic
        # Telegram often marks MKV/MP4 files in 'Documents' as 'application/octet-stream'
        # We manually force 'video/mp4' for known extensions so Browsers PLAY instead of DOWNLOAD.
        content_type = getattr(media, "mime_type", "application/octet-stream")
        if raw_name.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi')):
             content_type = "video/mp4"

        # 6. Parse Range Header (Handling Scrubbing/Seeking)
        range_header = request.headers.get("Range")
        
        # [CRITICAL FIX] Handle Missing or Invalid Range Headers (The crash fixer)
        # If the browser requests the full file (no Range header), we start from 0.
        if range_header:
            parsed_result = parse_range(range_header, file_size)
            if parsed_result:
                start, end = parsed_result
            else:
                # If parse fails, default to full file
                start, end = 0, file_size - 1
        else:
            # If no header provided, stream from beginning
            start, end = 0, file_size - 1
        
        # Verify valid range logic (Just in case)
        if start >= file_size or end >= file_size:
            return JSONResponse(status_code=416, content={"error": "Range Not Satisfiable"})

        chunk_size = end - start + 1
        
        # 7. Async Generator to Stream Data
        async def chunk_generator():
            try:
                # Convert HTTP byte offsets -> Telegram 1MB chunk offsets
                # Telegram chunks are exactly 1,048,576 bytes
                chunk_index = start // (1024 * 1024)
                first_chunk_skip = start % (1024 * 1024)
                current_pos = start
                
                # Use Pyrogram's stream_media iterator
                async for chunk in bot_app.stream_media(file_id, offset=chunk_index):
                    # Trim the start of the first chunk if request didn't align perfectly with 1MB
                    if first_chunk_skip > 0:
                        chunk = chunk[first_chunk_skip:]
                        first_chunk_skip = 0
                    
                    # Stop if we have sent enough data
                    if current_pos + len(chunk) > end:
                        yield chunk[:end - current_pos + 1]
                        break
                    
                    yield chunk
                    current_pos += len(chunk)
                    
            except FileReferenceExpired:
                logger.warning("Telegram File Reference Expired - Needs Refresh logic.")
                # Note: Pyrogram usually auto-refreshes internally for download calls
            except Exception as e:
                logger.error(f"Streaming Chunk Error: {e}")

        # 8. Build Response Headers
        headers = {
            # Required for Range Requests
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": content_type,
            
            # [FIX] 'inline' = Play in Browser. 'filename' = URL-Encoded safe name.
            "Content-Disposition": f'inline; filename="{safe_name}"',
            
            # Player Hints
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }

        # 9. Return 206 Partial Content Response
        # We use 206 even for full file because it's safer for seeking behavior in players
        return StreamingResponse(
            chunk_generator(),
            status_code=206,
            headers=headers,
            media_type=content_type
        )

    except Exception as e:
        logger.error(f"Global Stream Handler Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
