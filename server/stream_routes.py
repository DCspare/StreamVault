import mimetypes
import logging
import asyncio

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
    if not bot_app.is_connected:
        try:
            await bot_app.start()
        except Exception:
            return JSONResponse(status_code=503, content={"error": "Bot Disconnected"})

    try:
        message = await bot_app.get_messages(chat_id, message_id)
        if not message or not message.media:
            raise HTTPException(status_code=404)

        file = message.document or message.video or message.audio
        file_size = file.file_size
        file_name = getattr(file, "file_name", "video.mp4")
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = "application/octet-stream"

    except Exception:
        raise HTTPException(status_code=400, detail="Meta fetch failed")

    range_header = request.headers.get("Range")
    start, end = 0, file_size - 1
    if range_header:
        parsed = parse_range(range_header, file_size)
        if parsed:
            start, end = parsed

    content_length = (end - start) + 1

    initial_chunk_offset = start // (1024 * 1024)
    initial_skip = start % (1024 * 1024)

    logger.info(
        "Stream request chat_id=%s message_id=%s range=%s start=%s end=%s size=%s chunk_offset=%s skip=%s",
        chat_id,
        message_id,
        range_header,
        start,
        end,
        file_size,
        initial_chunk_offset,
        initial_skip,
    )

    async def media_stream_generator():
        nonlocal message

        CHUNK_SIZE = 1024 * 1024
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
                logger.warning("⚠️ File ref/offset invalid. Refreshing message...")
                await asyncio.sleep(1)

                try:
                    message = await bot_app.get_messages(chat_id, message_id)
                except Exception:
                    break

                timeout_failures = 0

            except TimeoutError as e:
                timeout_failures += 1
                if timeout_failures > 6:
                    logger.error("Stream failed after repeated timeouts: %s", e)
                    break

                backoff = min(2 ** (timeout_failures - 1), 30)
                logger.warning(
                    "⚠️ GetFile timeout (attempt %s). Backing off %ss...",
                    timeout_failures,
                    backoff,
                )
                await asyncio.sleep(backoff)

            except OSError as e:
                timeout_failures += 1
                if timeout_failures > 6:
                    logger.error("Stream failed after repeated network errors: %s", e)
                    break

                backoff = min(2 ** (timeout_failures - 1), 30)
                logger.warning(
                    "⚠️ GetFile network error (attempt %s): %s. Backing off %ss...",
                    timeout_failures,
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)

            except Exception as e:
                logger.error("Stream broken: %s", e)
                break

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_name}"',
    }

    return StreamingResponse(
        media_stream_generator(),
        status_code=206,
        headers=headers,
        media_type=mime_type,
    )
