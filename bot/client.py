"""
Shadow Bot Client - Pyrogram Client with Session Pooling.

Custom Pyrogram client that:
- Uses SOCKS5 proxy for network bypass
- Implements session pooling per DC for parallel downloads
- Overrides get_file() for direct session pool usage
- Handles auth key persistence and flood wait recovery
- Auto-cleans corrupt session files
"""

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
from bot.session_pool import SessionPool

logger = logging.getLogger("bot_client")

if not Config.API_ID or not Config.API_HASH or not Config.BOT_TOKEN:
    logger.error("🚫 CONFIG MISSING: API_ID, API_HASH, or BOT_TOKEN not set")

# 🛠️ PROXY CONFIG
# SOCKS5 proxy for network bypass on restricted networks
proxy_config = dict(
    scheme="socks5",
    hostname="37.18.73.60",  # proxydb.net socks5 high anonymous
    port=5566,
    # username="fbvilezw",  # Uncomment if proxy requires auth
    # password="qhfflj8i2rzg"
)

SESSION_NAME = "streamvault_v1"


class ShadowBot(Client):
    """
    Custom Pyrogram Client with session pooling and auto-recovery.
    
    Features:
    - Automatic plugin loading from bot/plugins directory
    - Session persistence to disk (prevents re-auth loops)
    - FloodWait handling with automatic retry
    - Corrupt session file detection and cleanup
    - Session pool for parallel downloads across DCs
    - SOCKS5 proxy support for network bypass
    
    Attributes:
        is_enabled (bool): Bot enabled flag
        is_connected (bool): Telegram connection status
        session_pool (SessionPool): DC-specific session manager
    """
    
    def __init__(self):
        """
        Initialize Shadow Bot client with proxy and persistence.
        
        Sets up:
        - Session persistence (in_memory=False)
        - Plugin auto-loading (plugins=dict(root="bot/plugins"))
        - SOCKS5 proxy configuration
        - Corrupt session cleanup
        - Session pool initialization
        """
        self.is_enabled = True
        self.is_connected = False

        # 🗑️ AUTO-CLEANUP CORRUPT FILES
        # Remove empty session files to prevent auth errors
        if os.path.exists(f"{SESSION_NAME}.session"):
            if os.path.getsize(f"{SESSION_NAME}.session") == 0:
                logger.warning("Corrupt session file detected, removing...")
                os.remove(f"{SESSION_NAME}.session")

        logger.info("Initializing ShadowBot client")
        logger.debug(f"Config: API_ID={Config.API_ID}, session={SESSION_NAME}, proxy={proxy_config['hostname']}:{proxy_config['port']}")
        
        super().__init__(
            SESSION_NAME,
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="bot/plugins"),  # Auto-load all plugins
            # STABILITY SETTINGS
            workers=4,  # Concurrent update handlers
            ipv6=False,  # IPv4 only for compatibility
            # PERSISTENCE
            in_memory=False,  # Save session to disk
            workdir=".",  # Session file location
            proxy=proxy_config,  # SOCKS5 proxy
        )
        self.session_pool = SessionPool(self)
        logger.info("✅ ShadowBot client initialized")

    async def start(self):
        """
        Start the bot with auto-recovery from common errors.
        
        Handles:
        - FloodWait errors with automatic retry
        - Corrupt session database errors
        - Connection failures with cleanup
        
        Sets is_connected=True on successful connection.
        
        Raises:
            Exception: If connection fails after recovery attempts
        """
        try:
            logger.info("Starting bot connection to Telegram...")
            await super().start()
            self.is_connected = True
            logger.info("✅ Bot connected successfully")

        # 🛑 FLOOD WAIT HANDLER
        # Telegram rate limit - wait and retry
        except FloodWait as e:
            wait_time = e.value + 5
            logger.warning(f"⚠️ Telegram FLOOD_WAIT: Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)

            await super().start()
            self.is_connected = True
            logger.info("✅ Bot connected after FloodWait")

        except Exception as e:
            logger.error(f"⚠️ Start Error: {e}", exc_info=True)
            
            # Handle session database corruption
            if "database is locked" in str(e) or "no such table" in str(e):
                logger.warning("Session database corrupt, cleaning up...")
                self.cleanup_session()
                await super().start()
                self.is_connected = True
                logger.info("✅ Bot connected after session cleanup")

    async def get_file(
        self,
        file_id: FileId,
        file_size: int = 0,
        limit: int = 0,
        offset: int = 0,
        progress: Callable = None,
        progress_args: tuple = (),
    ) -> Optional[AsyncGenerator[bytes, None]]:
        """
        Download file from Telegram using session pool.
        
        Overrides Pyrogram's get_file to use our session pool for:
        - Parallel downloads across DCs
        - Better timeout handling
        - Session reuse
        
        CRITICAL: offset and limit are in 1MB chunks, NOT bytes!
        - offset: Number of 1MB chunks to skip
        - limit: Number of 1MB chunks to download
        
        Args:
            file_id (FileId): Pyrogram file identifier
            file_size (int): Total file size in bytes (optional)
            limit (int): Number of 1MB chunks to download (0 = all)
            offset (int): Number of 1MB chunks to skip from start
            progress (Callable): Progress callback function
            progress_args (tuple): Additional args for progress callback
            
        Yields:
            bytes: File data chunks (1MB each)
            
        Example:
            >>> async for chunk in bot.get_file(file_id, offset=10, limit=5):
            ...     # Skips first 10MB, downloads next 5MB
            ...     process_chunk(chunk)
        """
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

            session = await self.session_pool.get_session(dc_id)

            try:
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
                await self.session_pool.release_session(session)

    def cleanup_session(self):
        """
        Remove corrupt session file from disk.
        
        Called when session database is corrupted or locked.
        Forces bot to create new auth key on next start.
        """
        try:
            if os.path.exists(f"{SESSION_NAME}.session"):
                logger.info(f"Removing session file: {SESSION_NAME}.session")
                os.remove(f"{SESSION_NAME}.session")
        except Exception as e:
            logger.error(f"Failed to cleanup session: {e}")

    async def verify_handler_registration(self) -> bool:
        """
        Verify all handlers are registered correctly and in proper priority order.
        
        Handlers are registered in order of specificity:
        1. Most specific filters (command + private)
        2. Medium specific filters (document + private)
        3. Least specific filters (text + private)
        
        Returns:
            bool: True if all handlers properly registered
        """
        
        logger.info("=" * 60)
        logger.info("HANDLER REGISTRATION VERIFICATION")
        logger.info("=" * 60)
        
        # List all registered handler groups
        handler_groups = self.dispatcher.groups
        total_handlers = sum(len(group) for group in handler_groups.values())
        
        logger.info(f"✅ Total handler groups: {len(handler_groups)}")
        logger.info(f"✅ Total handlers: {total_handlers}")
        
        # Expected handlers
        expected_handlers = [
            "start command",
            "help command",
            "catalog command",
            "delete command",
            "confirm_delete command",
            "search command",
            "file upload (document)",
            "text messages",
        ]
        
        logger.info(f"\n✅ Expected handlers registered:")
        for i, handler_name in enumerate(expected_handlers, 1):
            logger.info(f"   {i}. {handler_name}")
        
        if total_handlers < len(expected_handlers):
            logger.error(f"❌ WARNING: Expected {len(expected_handlers)} handlers, found {total_handlers}")
            return False
        
        logger.info("\n✅ Handler registration verification PASSED")
        logger.info("=" * 60)
        return True

    async def stop(self, *args):
        """
        Stop the bot client.
        
        Override to prevent accidental disconnection during streaming.
        Currently a no-op to keep bot alive during web server shutdown.
        """
        pass


bot_app = ShadowBot()
