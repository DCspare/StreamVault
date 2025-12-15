import mimetypes
import logging
import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from bot.client import bot_app
from utils.range_parser import parse_range
from pyrogram.errors import OffsetInvalid, FileReferenceExpired

logger = logging.getLogger("stream_routes")
stream_router = APIRouter()

@stream_router.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request: Request, chat_id: int, message_id: int):
    # 1. Connection Check
    if not bot_app.is_connected:
        try: await bot_app.start()
        except: return JSONResponse(status_code=503, content={"error": "Bot Disconnected"})

    # 2. Initial Metadata
    try:
        message = await bot_app.get_messages(chat_id, message_id)
        if not message or not message.media: raise HTTPException(status_code=404)
        
        file = message.document or message.video or message.audio
        file_size = file.file_size
        file_name = getattr(file, "file_name", "video.mp4")
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type: mime_type = "application/octet-stream"

    except Exception:
        raise HTTPException(status_code=400, detail="Meta fetch failed")

    # 3. Ranges
    range_header = request.headers.get("Range")
    start, end = 0, file_size - 1
    if range_header:
        parsed = parse_range(range_header, file_size)
        if parsed: start, end = parsed
    
    content_length = (end - start) + 1

    # --- SELF-HEALING STREAMER ---
    async def media_stream_generator():
        CHUNK_SIZE = 1024 * 1024  # 1MB chunks (Telegram's chunk size)
        current_byte_offset = start
        bytes_left = content_length
        
        # FIX: Convert byte offset to chunk offset to avoid OFFSET_INVALID
        # Pyrogram's stream_media expects offset as number of chunks to skip,
        # not bytes. Telegram API uses 1MB chunks internally.
        chunk_offset = start // CHUNK_SIZE
        bytes_to_skip_in_first_chunk = start % CHUNK_SIZE
        
        first_chunk = True
        
        while bytes_left > 0:
            try:
                # Calculate how many chunks we need
                chunks_needed = (bytes_left + bytes_to_skip_in_first_chunk + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                # Streaming Loop
                async for chunk in bot_app.stream_media(message, offset=chunk_offset, limit=chunks_needed):
                    if not chunk: break
                    
                    # Skip bytes in the first chunk if we're starting mid-chunk
                    if first_chunk and bytes_to_skip_in_first_chunk > 0:
                        chunk = chunk[bytes_to_skip_in_first_chunk:]
                        first_chunk = False
                        bytes_to_skip_in_first_chunk = 0  # Reset after skipping
                    
                    # Trim chunk if it's more than we need
                    if len(chunk) > bytes_left:
                        chunk = chunk[:bytes_left]
                    
                    yield chunk
                    current_byte_offset += len(chunk)
                    bytes_left -= len(chunk)
                    
                    if bytes_left <= 0:
                        break

            except (OffsetInvalid, FileReferenceExpired):
                logger.warning(f"⚠️ Auth Key/File Ref expired. refreshing...")
                await asyncio.sleep(1) # Let the proxy reconnection finish
                try:
                    # HEAL: Get new File Reference from Telegram
                    refresh_msg = await bot_app.get_messages(chat_id, message_id)
                    message.video = refresh_msg.video 
                    # Recalculate chunk offset for the current position
                    chunk_offset = current_byte_offset // CHUNK_SIZE
                    bytes_to_skip_in_first_chunk = current_byte_offset % CHUNK_SIZE
                    first_chunk = True
                    # Loop continues automatically with new message ref
                except:
                    break
            except Exception as e:
                logger.error(f"Stream Broken: {e}")
                break

    # 4. Headers (Strictly Chunked, NO Content-Length to avoid Proxy crashes)
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_name}"'
    }

    return StreamingResponse(
        media_stream_generator(),
        status_code=206,
        headers=headers,
        media_type=mime_type
    )