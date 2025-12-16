"""
MongoDB Database Manager for Shadow Streamer.

Handles all database operations including:
- File metadata storage and retrieval
- Catalog management with pagination
- Search functionality
- Soft delete support
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId

from config import Config

logger = logging.getLogger("database")

class DatabaseManager:
    """
    MongoDB operations manager for file indexing.
    
    Manages the 'indexed_files' collection with schema:
    - message_id: Telegram message ID in LOG_CHANNEL
    - file_id: Telegram file ID for streaming
    - custom_name: User-provided file name
    - file_size: Size in bytes
    - source: "direct_upload" or "youtube_link"
    - uploaded_by: User's Telegram ID
    - created_at: Timestamp
    - is_active: Soft delete flag
    """
    
    def __init__(self):
        """Initialize database manager with empty connections."""
        self.client = None
        self.db = None
        self.collection = None
        
    async def connect(self):
        """
        Initialize MongoDB connection and create indexes.
        
        Creates the following indexes for performance:
        - message_id (unique): Fast lookups by Telegram message
        - uploaded_by: Filter files by user
        - created_at (descending): Sort by newest first
        - custom_name (text): Full-text search support
        
        Raises:
            Exception: If connection fails or indexes cannot be created
        """
        try:
            logger.info("Connecting to MongoDB at %s", Config.MONGO_URL)
            self.client = AsyncIOMotorClient(Config.MONGO_URL)
            self.db = self.client[Config.MONGO_DB_NAME]
            self.collection = self.db.indexed_files
            
            # Create indexes for better query performance
            logger.debug("Creating database indexes...")
            await self.collection.create_index([("message_id", 1)], unique=True)
            await self.collection.create_index([("uploaded_by", 1)])
            await self.collection.create_index([("created_at", -1)])
            await self.collection.create_index([("custom_name", "text")])
            
            # Verify schema
            await self._verify_schema()
            
            logger.info("✅ MongoDB connected successfully")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}", exc_info=True)
            raise

    async def _verify_schema(self):
        """
        Verify MongoDB collection schema and indexes.
        
        Checks that:
        - Collection 'indexed_files' exists
        - All required indexes are present
        - Index structure is correct
        
        Logs warnings for missing indexes but does not fail.
        """
        try:
            # Check collection exists
            collections = await self.db.list_collection_names()
            if 'indexed_files' not in collections:
                logger.warning("⚠️ Collection 'indexed_files' not found yet (will be created on first insert)")
                return
            
            # Check indexes
            indexes = await self.collection.list_indexes().to_list(length=None)
            index_names = [idx['name'] for idx in indexes]
            
            required = ['message_id_1', 'uploaded_by_1', 'created_at_-1', 'custom_name_text']
            missing = [idx for idx in required if idx not in index_names]
            
            if missing:
                logger.warning(f"⚠️ Missing indexes: {missing}")
            else:
                logger.info("✅ MongoDB schema verified - all indexes present")
                
        except Exception as e:
            logger.error(f"Schema verification failed: {e}", exc_info=True)

    async def disconnect(self):
        """
        Close MongoDB connection gracefully.
        
        Should be called during application shutdown.
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB disconnected")

    async def save_file(self, file_data: Dict[str, Any]) -> Optional[ObjectId]:
        """
        Save file metadata to the indexed_files collection.
        
        This function stores information about uploaded files in MongoDB,
        including file IDs, custom names, sizes, and source information.
        
        Args:
            file_data (Dict): File metadata containing:
                - message_id (int): Telegram message ID in LOG_CHANNEL
                - custom_name (str): User-provided file name
                - file_size (int): File size in bytes
                - source (str): "direct_upload" or "youtube_link"
                - uploaded_by (int): User's Telegram ID
                - And other metadata fields
                
        Returns:
            ObjectId: MongoDB document ID if successful, None if failed
            
        Example:
            >>> file_data = {
            ...     "message_id": 159,
            ...     "custom_name": "My_Video",
            ...     "file_size": 1574507,
            ...     "source": "direct_upload"
            ... }
            >>> result = await db.save_file(file_data)
        """
        try:
            # Add timestamps for audit trail
            file_data["created_at"] = datetime.utcnow()
            file_data["is_active"] = True  # For soft delete support
            
            logger.debug(f"Saving file to database: {file_data.get('custom_name')}")
            
            # Insert into MongoDB collection
            result = await self.collection.insert_one(file_data)
            
            # Log successful save with key details
            logger.info(
                f"File indexed: message_id={file_data.get('message_id')}, "
                f"name={file_data.get('custom_name')}, "
                f"size={self._format_size(file_data.get('file_size', 0))}, "
                f"user={file_data.get('uploaded_by')}"
            )
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Error saving file: {e}", exc_info=True)
            return None

    async def get_file(self, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Get file metadata by message_id.
        
        Args:
            message_id (int): Telegram message ID in LOG_CHANNEL
            
        Returns:
            Dict: File metadata if found and active, None otherwise
            
        Example:
            >>> file = await db.get_file(159)
            >>> print(file['custom_name'])
        """
        try:
            logger.debug(f"Fetching file with message_id={message_id}")
            return await self.collection.find_one({"message_id": message_id, "is_active": True})
        except Exception as e:
            logger.error(f"Error getting file {message_id}: {e}", exc_info=True)
            return None

    async def get_catalog(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """
        Get paginated catalog of indexed files.
        
        Returns files sorted by creation date (newest first).
        
        Args:
            limit (int): Maximum number of files to return (default: 50)
            skip (int): Number of files to skip for pagination (default: 0)
            
        Returns:
            List[Dict]: List of file metadata dictionaries
            
        Example:
            >>> files = await db.get_catalog(limit=20, skip=0)
            >>> for file in files:
            ...     print(file['custom_name'])
        """
        try:
            logger.debug(f"Fetching catalog: limit={limit}, skip={skip}")
            cursor = self.collection.find({"is_active": True}).sort("created_at", -1).skip(skip).limit(limit)
            files = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for file in files:
                file["_id"] = str(file["_id"])
            
            logger.info(f"Catalog fetched: {len(files)} files returned")
            return files
            
        except Exception as e:
            logger.error(f"Error getting catalog: {e}", exc_info=True)
            return []

    async def get_catalog_count(self) -> int:
        """
        Get total count of active indexed files.
        
        Returns:
            int: Total number of active files in database
            
        Example:
            >>> count = await db.get_catalog_count()
            >>> print(f"Total files: {count}")
        """
        try:
            count = await self.collection.count_documents({"is_active": True})
            logger.debug(f"Catalog count: {count} active files")
            return count
        except Exception as e:
            logger.error(f"Error getting catalog count: {e}", exc_info=True)
            return 0

    async def delete_file(self, message_id: int) -> bool:
        """
        Soft delete file by setting is_active = False.
        
        Does not remove from database - allows for undelete functionality.
        
        Args:
            message_id (int): Telegram message ID to delete
            
        Returns:
            bool: True if file was deleted, False if not found or error
            
        Example:
            >>> success = await db.delete_file(159)
            >>> print("Deleted" if success else "Not found")
        """
        try:
            logger.debug(f"Deleting file with message_id={message_id}")
            result = await self.collection.update_one(
                {"message_id": message_id},
                {"$set": {"is_active": False}}
            )
            
            if result.modified_count > 0:
                logger.info(f"File deleted: message_id={message_id}")
                return True
            
            logger.warning(f"File not found for deletion: message_id={message_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting file {message_id}: {e}", exc_info=True)
            return False

    async def search_files(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search files by custom name using full-text search.
        
        Uses MongoDB text index for fast searching.
        
        Args:
            query (str): Search query string
            limit (int): Maximum results to return (default: 20)
            
        Returns:
            List[Dict]: List of matching file metadata
            
        Example:
            >>> results = await db.search_files("avengers")
            >>> for file in results:
            ...     print(file['custom_name'])
        """
        try:
            logger.debug(f"Searching files with query='{query}', limit={limit}")
            cursor = self.collection.find({
                "is_active": True,
                "$text": {"$search": query}
            }).sort("created_at", -1).limit(limit)
            
            files = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for file in files:
                file["_id"] = str(file["_id"])
            
            logger.info(f"Search completed: {len(files)} files found for query '{query}'")
            return files
            
        except Exception as e:
            logger.error(f"Error searching files with query '{query}': {e}", exc_info=True)
            return []

    def _format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.
        
        Converts bytes to KB, MB, GB, TB, or PB as appropriate.
        
        Args:
            size_bytes (int): File size in bytes
            
        Returns:
            str: Formatted size string (e.g., "1.5 MB")
            
        Example:
            >>> db._format_size(1574507)
            '1.5 MB'
        """
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

# Global database instance
db = DatabaseManager()