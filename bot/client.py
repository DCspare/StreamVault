import os
import logging
import asyncio
import functools
import inspect
from hashlib import sha256
from typing import Callable, Optional, AsyncGenerator

import pyrogram
from pyrogram import Client, raw, utils
from pyrogram.crypto import aes
from pyrogram.errors import FloodWait, CDNFileHashMismatch, VolumeLocNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session import Auth, Session

from config import Config

logger = logging.getLogger("bot_client")

if not Config.API_ID or not Config.API_HASH or not Config.BOT_TOKEN:
    logger.error("🚫 CONFIG MISSING")

# 🛠️ PROXY CONFIG
proxy_config = dict(
    scheme="socks5",
    hostname="37.18.73.60",  # proxydb.net socks5 high anonymous
    port=5566,
    # username="fbvilezw",
    # password="qhfflj8i2rzg"
)

SESSION_NAME = "streamvault_v1"


class ShadowBot(Client):
    def __init__(self):
        self.is_enabled = True
        self.is_connected = False

        # 🗑️ AUTO-CLEANUP CORRUPT FILES
        if os.path.exists(f"{SESSION_NAME}.session"):
            if os.path.getsize(f"{SESSION_NAME}.session") == 0:
                os.remove(f"{SESSION_NAME}.session")

        super().__init__(
            SESSION_NAME,
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="bot/plugins"),
            # STABILITY SETTINGS
            workers=4,
            ipv6=False,
            # PERSISTENCE
            in_memory=False,
            workdir=".",
            proxy=proxy_config,
        )

    async def start(self):
        try:
            await super().start()
            self.is_connected = True

        # 🛑 FLOOD WAIT HANDLER (The Fix)
        except FloodWait as e:
            wait_time = e.value + 5
            logger.warning(f"⚠️ Telegram FLOOD_WAIT: Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)

            await super().start()
            self.is_connected = True

        except Exception as e:
            logger.error(f"⚠️ Start Error: {e}")
            if "database is locked" in str(e) or "no such table" in str(e):
                self.cleanup_session()
                await super().start()
                self.is_connected = True

    async def get_file(
        self,
        file_id: FileId,
        file_size: int = 0,
        limit: int = 0,
        offset: int = 0,
        progress: Callable = None,
        progress_args: tuple = (),
    ) -> Optional[AsyncGenerator[bytes, None]]:
        async with self.get_file_semaphore:
            file_type = file_id.file_type

            if file_type == FileType.CHAT_PHOTO:
                if file_id.chat_id > 0:
                    peer = raw.types.InputPeerUser(
                        user_id=file_id.chat_id,
                        access_hash=file_id.chat_access_hash,
                    )
                else:
                    if file_id.chat_access_hash == 0:
                        peer = raw.types.InputPeerChat(
                            chat_id=-file_id.chat_id,
                        )
                    else:
                        peer = raw.types.InputPeerChannel(
                            channel_id=utils.get_channel_id(file_id.chat_id),
                            access_hash=file_id.chat_access_hash,
                        )

                location = raw.types.InputPeerPhotoFileLocation(
                    peer=peer,
                    photo_id=file_id.media_id,
                    big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
                )
            elif file_type == FileType.PHOTO:
                location = raw.types.InputPhotoFileLocation(
                    id=file_id.media_id,
                    access_hash=file_id.access_hash,
                    file_reference=file_id.file_reference,
                    thumb_size=file_id.thumbnail_size,
                )
            else:
                location = raw.types.InputDocumentFileLocation(
                    id=file_id.media_id,
                    access_hash=file_id.access_hash,
                    file_reference=file_id.file_reference,
                    thumb_size=file_id.thumbnail_size,
                )

            current = 0
            total = abs(limit) or (1 << 31) - 1
            chunk_size = 1024 * 1024
            offset_bytes = abs(offset) * chunk_size

            dc_id = file_id.dc_id

            session = Session(
                self,
                dc_id,
                await Auth(self, dc_id, await self.storage.test_mode()).create()
                if dc_id != await self.storage.dc_id()
                else await self.storage.auth_key(),
                await self.storage.test_mode(),
                is_media=True,
            )

            try:
                await session.start()

                if dc_id != await self.storage.dc_id():
                    exported_auth = await self.invoke(
                        raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                    )

                    await session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported_auth.id,
                            bytes=exported_auth.bytes,
                        )
                    )

                r = await session.invoke(
                    raw.functions.upload.GetFile(
                        location=location,
                        offset=offset_bytes,
                        limit=chunk_size,
                    ),
                    sleep_threshold=30,
                    timeout=Config.TG_GETFILE_TIMEOUT,
                )

                if isinstance(r, raw.types.upload.File):
                    while True:
                        chunk = r.bytes

                        yield chunk

                        current += 1
                        offset_bytes += chunk_size

                        if progress:
                            func = functools.partial(
                                progress,
                                min(offset_bytes, file_size)
                                if file_size != 0
                                else offset_bytes,
                                file_size,
                                *progress_args,
                            )

                            if inspect.iscoroutinefunction(progress):
                                await func()
                            else:
                                await self.loop.run_in_executor(self.executor, func)

                        if len(chunk) < chunk_size or current >= total:
                            break

                        r = await session.invoke(
                            raw.functions.upload.GetFile(
                                location=location,
                                offset=offset_bytes,
                                limit=chunk_size,
                            ),
                            sleep_threshold=30,
                            timeout=Config.TG_GETFILE_TIMEOUT,
                        )

                elif isinstance(r, raw.types.upload.FileCdnRedirect):
                    cdn_session = Session(
                        self,
                        r.dc_id,
                        await Auth(self, r.dc_id, await self.storage.test_mode()).create(),
                        await self.storage.test_mode(),
                        is_media=True,
                        is_cdn=True,
                    )

                    try:
                        await cdn_session.start()

                        while True:
                            r2 = await cdn_session.invoke(
                                raw.functions.upload.GetCdnFile(
                                    file_token=r.file_token,
                                    offset=offset_bytes,
                                    limit=chunk_size,
                                ),
                                timeout=Config.TG_GETFILE_TIMEOUT,
                            )

                            if isinstance(r2, raw.types.upload.CdnFileReuploadNeeded):
                                try:
                                    await session.invoke(
                                        raw.functions.upload.ReuploadCdnFile(
                                            file_token=r.file_token,
                                            request_token=r2.request_token,
                                        ),
                                        timeout=Config.TG_GETFILE_TIMEOUT,
                                    )
                                except VolumeLocNotFound:
                                    break
                                else:
                                    continue

                            chunk = r2.bytes

                            decrypted_chunk = aes.ctr256_decrypt(
                                chunk,
                                r.encryption_key,
                                bytearray(
                                    r.encryption_iv[:-4]
                                    + (offset_bytes // 16).to_bytes(4, "big")
                                ),
                            )

                            hashes = await session.invoke(
                                raw.functions.upload.GetCdnFileHashes(
                                    file_token=r.file_token,
                                    offset=offset_bytes,
                                ),
                                timeout=Config.TG_GETFILE_TIMEOUT,
                            )

                            for i, h in enumerate(hashes):
                                cdn_chunk = decrypted_chunk[
                                    h.limit * i : h.limit * (i + 1)
                                ]
                                CDNFileHashMismatch.check(
                                    h.hash == sha256(cdn_chunk).digest(),
                                    "h.hash == sha256(cdn_chunk).digest()",
                                )

                            yield decrypted_chunk

                            current += 1
                            offset_bytes += chunk_size

                            if progress:
                                func = functools.partial(
                                    progress,
                                    min(offset_bytes, file_size)
                                    if file_size != 0
                                    else offset_bytes,
                                    file_size,
                                    *progress_args,
                                )

                                if inspect.iscoroutinefunction(progress):
                                    await func()
                                else:
                                    await self.loop.run_in_executor(self.executor, func)

                            if len(chunk) < chunk_size or current >= total:
                                break
                    finally:
                        await cdn_session.stop()
            except pyrogram.StopTransmission:
                raise
            finally:
                await session.stop()

    def cleanup_session(self):
        try:
            if os.path.exists(f"{SESSION_NAME}.session"):
                os.remove(f"{SESSION_NAME}.session")
        except Exception:
            pass

    async def stop(self, *args):
        pass


bot_app = ShadowBot()
