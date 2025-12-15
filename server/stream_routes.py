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
        current_offset = start
        bytes_left = content_length
        
        while bytes_left > 0:
            try:
                # Streaming Loop
                async for chunk in bot_app.stream_media(message, offset=current_offset, limit=bytes_left):
                    if not chunk: break
                    yield chunk
                    current_offset += len(chunk)
                    bytes_left -= len(chunk)

            except (OffsetInvalid, FileReferenceExpired):
                logger.warning(f"⚠️ Auth Key/File Ref expired. refreshing...")
                await asyncio.sleep(1) # Let the proxy reconnection finish
                try:
                    # HEAL: Get new File Reference from Telegram
                    refresh_msg = await bot_app.get_messages(chat_id, message_id)
                    message.video = refresh_msg.video 
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