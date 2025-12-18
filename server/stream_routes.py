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
from urllib.parse import quote

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
        
    Status Codes:
        206: Partial Content (success)
        400: Bad Request (invalid message/file)
        404: Not Found (message/media not found)
        503: Service Unavailable (bot disconnected)
        
    Example:
        GET /stream/5228293685/159 HTTP/1.1
        Range: bytes=1540096-
        
        Response:
        206 Partial Content
        Content-Range: bytes 1540096-1574506/1574507
        Content-Type: video/mp4
    """
    # Ensure bot is connected before attempting to fetch
    if not bot_app.is_connected:
        logger.warning("Bot not connected, attempting to start...")
        try:
            await bot_app.start()
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            return JSONResponse(status_code=503, content={"error": "Bot Disconnected"})

    try:
        # Fetch message from Telegram (contains file metadata)
        logger.debug(f"Fetching message: chat_id={chat_id}, message_id={message_id}")
        message = await bot_app.get_messages(chat_id, message_id)
        if not message or not message.media:
            logger.warning(f"Message not found or has no media: chat_id={chat_id}, message_id={message_id}")
            raise HTTPException(status_code=404)

        # Extract file and its properties
        file = message.document or message.video or message.audio
        file_size = file.file_size
        file_name = getattr(file, "file_name", "video.mp4")
        
        # Determine MIME type for proper browser handling
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        logger.debug(f"File metadata: name={file_name}, size={file_size}, type={mime_type}")

    except Exception as e:
        # Failed to fetch file metadata
        logger.error(f"Meta fetch failed for chat_id={chat_id}, message_id={message_id}: {e}")
        raise HTTPException(status_code=400, detail="Meta fetch failed")

        # Safe Name Logic (Fixes UnicodeEncodeError)
        # Use filename if available, or generate a safe generic one
        raw_name = getattr(media, "file_name", "streamed_file.mp4") or "video.mp4"
        safe_name = quote(raw_name)  # Encodes "🕶" to "%F0%9F..."

    # Parse HTTP Range header for partial content requests
    # Format: "bytes=start-end" (e.g., "bytes=0-1023" or "bytes=1024-")
    range_header = request.headers.get("Range")
    start, end = 0, file_size - 1
    if range_header:
        parsed = parse_range(range_header, file_size)
        if parsed:
            start, end = parsed
            logger.debug(f"Range header parsed: {range_header} -> start={start}, end={end}")

    # Calculate content length for this chunk
    content_length = (end - start) + 1

    # Calculate Chunks
    chunk_size = end - start + 1

    # Smart Content-Type (Fixes 'Download instead of Play')
        # Telegram often marks MKV/MP4 as 'application/octet-stream' in Documents.
        # We assume known extensions are videos to force browser playback.
    content_type = getattr(media, "mime_type", "application/octet-stream")
    if raw_name.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi')):
        content_type = "video/mp4"

    # Convert byte offset to 1MB chunk offset
    # Telegram API uses 1MB chunks internally
    # chunk_offset = which 1MB chunk to start from
    # initial_skip = bytes to skip within that chunk
    initial_chunk_offset = start // (1024 * 1024)
    initial_skip = start % (1024 * 1024)

    logger.info(
        f"Stream request: chat_id={chat_id}, message_id={message_id}, "
        f"range={range_header}, start={start}, end={end}, size={file_size}, "
        f"chunk_offset={initial_chunk_offset}, skip={initial_skip}"
    )

    async def media_stream_generator():
        """
        Generator function that yields file chunks from Telegram.
        
        Handles:
        - Byte-range requests (HTTP 206)
        - Chunk offset calculations (1MB chunks)
        - Timeout retries with exponential backoff
        - Session reconnection on token expiry
        - First chunk skipping for range requests
        
        Yields:
            bytes: File data chunks to send to client
            
        Error Recovery:
        - OffsetInvalid/FileReferenceExpired: Refresh message and retry
        - TimeoutError: Exponential backoff (1s, 2s, 4s, 8s, 16s, 30s max)
        - OSError: Network errors with same backoff strategy
        """
        nonlocal message

        CHUNK_SIZE = 1024 * 1024  # 1MB - Telegram's internal chunk size
        current_byte_offset = start
        bytes_left = content_length

        timeout_failures = 0

        while bytes_left > 0:
            chunk_offset = current_byte_offset // CHUNK_SIZE
            bytes_to_skip_in_first_chunk = current_byte_offset % CHUNK_SIZE
            chunks_needed = (
                bytes_left + bytes_to_skip_in_first_chunk + CHUNK_SIZE - 1
            ) // CHUNK_SIZE

            logger.debug(
                "TG stream byte_offset=%s chunk_offset=%s bytes_to_skip=%s chunks_needed=%s bytes_left=%s timeout=%ss",
                current_byte_offset,
                chunk_offset,
                bytes_to_skip_in_first_chunk,
                chunks_needed,
                bytes_left,
                Config.TG_GETFILE_TIMEOUT,
            )

            try:
                first_chunk = True

                async for chunk in bot_app.stream_media(
                    message, offset=chunk_offset, limit=chunks_needed
                ):
                    if not chunk:
                        break

                    if first_chunk and bytes_to_skip_in_first_chunk > 0:
                        chunk = chunk[bytes_to_skip_in_first_chunk:]
                        first_chunk = False
                        bytes_to_skip_in_first_chunk = 0

                    if len(chunk) > bytes_left:
                        chunk = chunk[:bytes_left]

                    yield chunk
                    current_byte_offset += len(chunk)
                    bytes_left -= len(chunk)

                    if bytes_left <= 0:
                        break

                if bytes_left > 0:
                    raise TimeoutError("Stream ended early")

                timeout_failures = 0

            except (OffsetInvalid, FileReferenceExpired):
                # Token expired or offset invalid - refresh message
                # This happens when session token expires or file reference changes
                logger.warning("⚠️ File ref/offset invalid. Refreshing message...")
                await asyncio.sleep(1)

                try:
                    message = await bot_app.get_messages(chat_id, message_id)
                    logger.info("Message refreshed successfully")
                except Exception as e:
                    logger.error(f"Failed to refresh message: {e}")
                    break

                timeout_failures = 0

            except TimeoutError as e:
                # GetFile timeout - retry with exponential backoff
                # Happens on slow networks or Telegram server issues
                timeout_failures += 1
                if timeout_failures > 6:
                    logger.error(f"Stream failed after repeated timeouts: {e}")
                    break

                # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
                backoff = min(2 ** (timeout_failures - 1), 30)
                logger.warning(
                    f"⚠️ GetFile timeout (attempt {timeout_failures}). "
                    f"Backing off {backoff}s..."
                )
                await asyncio.sleep(backoff)

            except OSError as e:
                # Network error - retry with exponential backoff
                # Covers connection reset, socket errors, etc.
                timeout_failures += 1
                if timeout_failures > 6:
                    logger.error(f"Stream failed after repeated network errors: {e}")
                    break

                backoff = min(2 ** (timeout_failures - 1), 30)
                logger.warning(
                    f"⚠️ GetFile network error (attempt {timeout_failures}): {e}. "
                    f"Backing off {backoff}s..."
                )
                await asyncio.sleep(backoff)

            except Exception as e:
                # Unexpected error - log and exit
                logger.error(f"Stream broken: {e}", exc_info=True)
                break

    # Prepare response headers for HTTP 206 Partial Content
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",  # Tell client which bytes we're sending
        "Accept-Ranges": "bytes",  # Tell client we support range requests
        "Content-Length": str(chunk_size),
        "Content-Type": content_type,
        "Content-Disposition": f'inline; filename="{file_name}"',  # Suggest filename for download
        "Cache-Control": "no-cache",
        "Connection": "keep-alive"
    }

    logger.debug(f"Returning StreamingResponse with headers: {headers}")
    
    return StreamingResponse(
        media_stream_generator(),
        status_code=206,  # 206 Partial Content (required for range requests)
        headers=headers,
        media_type=mime_type,
    )
