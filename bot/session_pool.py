import asyncio
import logging
from collections import defaultdict
from typing import Dict, List

from pyrogram.session import Auth, Session
from pyrogram import raw

logger = logging.getLogger("SessionPool")

class SessionPool:
    def __init__(self, client):
        self.client = client
        self.sessions: Dict[int, List[Session]] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def init_pool(self):
        """Pre-initialize sessions for the main DC."""
        try:
            dc_id = await self.client.storage.dc_id()
            if not dc_id:
                logger.warning("Cannot init pool: No DC ID found (not logged in?)")
                return
            
            logger.info(f"Initializing session pool for Main DC {dc_id}...")
            # Create 2 sessions for main DC
            for i in range(2):
                session = await self._create_and_start_session(dc_id)
                self.sessions[dc_id].append(session)
                logger.info(f"Pooled session {i+1}/2 ready for DC {dc_id}")
                
        except Exception as e:
            logger.error(f"Failed to init pool: {e}")

    async def get_session(self, dc_id: int) -> Session:
        async with self.lock:
            while self.sessions[dc_id]:
                session = self.sessions[dc_id].pop(0)
                logger.info(f"♻️ Reusing pooled session for DC {dc_id}")
                # Only return running sessions?
                # Since we don't have a cheap check, we assume it works.
                # If we implemented a health check, we would do it here.
                return session

        # If no session available, create one
        logger.info(f"Pool empty/miss for DC {dc_id}, creating new session")
        return await self._create_and_start_session(dc_id)

    async def release_session(self, session: Session):
        if not session:
            return

        async with self.lock:
            # Limit pool size per DC to avoid memory leaks if we connect to many DCs
            # Keeping 3 sessions per DC seems reasonable for streaming
            if len(self.sessions[session.dc_id]) < 3:
                self.sessions[session.dc_id].append(session)
                logger.debug(f"Session returned to pool for DC {session.dc_id}")
            else:
                logger.debug(f"Pool full for DC {session.dc_id}, stopping session")
                await session.stop()

    async def _create_and_start_session(self, dc_id: int) -> Session:
        is_main_dc = dc_id == await self.client.storage.dc_id()
        
        auth_key = None
        if is_main_dc:
            auth_key = await self.client.storage.auth_key()
        else:
             logger.info(f"Creating Auth Key for DC {dc_id}...")
             auth_key = await Auth(self.client, dc_id, await self.client.storage.test_mode()).create()

        session = Session(
            self.client,
            dc_id,
            auth_key,
            await self.client.storage.test_mode(),
            is_media=True,
        )

        await session.start()

        if not is_main_dc:
            try:
                logger.info(f"Importing authorization for DC {dc_id}")
                exported_auth = await self.client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                )

                await session.invoke(
                    raw.functions.auth.ImportAuthorization(
                        id=exported_auth.id,
                        bytes=exported_auth.bytes,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to import auth for DC {dc_id}: {e}")
                await session.stop()
                raise e
        
        return session
