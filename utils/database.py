import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId

from config import Config

logger = logging.getLogger("database")

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        
    async def connect(self):
        """Initialize MongoDB connection"""
        try:
            self.client = AsyncIOMotorClient(Config.MONGO_URL)
            self.db = self.client[Config.MONGO_DB_NAME]
            self.collection = self.db.indexed_files
            
            # Create indexes for better query performance
            await self.collection.create_index([("message_id", 1)], unique=True)
            await self.collection.create_index([("uploaded_by", 1)])
            await self.collection.create_index([("created_at", -1)])
            await self.collection.create_index([("custom_name", "text")])
            
            logger.info("✅ MongoDB connected successfully")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise

    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB disconnected")

    async def save_file(self, file_data: Dict[str, Any]) -> Optional[ObjectId]:
        """Save file metadata to indexed_files collection"""
        try:
            # Add timestamps
            file_data["created_at"] = datetime.utcnow()
            file_data["is_active"] = True
            
            result = await self.collection.insert_one(file_data)
            logger.info(f"File indexed: message_id={file_data.get('message_id')}, name={file_data.get('custom_name')}, size={self._format_size(file_data.get('file_size', 0))}, user={file_data.get('uploaded_by')}")
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None

    async def get_file(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Get file metadata by message_id"""
        try:
            return await self.collection.find_one({"message_id": message_id, "is_active": True})
        except Exception as e:
            logger.error(f"Error getting file {message_id}: {e}")
            return None

    async def get_catalog(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Get paginated catalog of indexed files"""
        try:
            cursor = self.collection.find({"is_active": True}).sort("created_at", -1).skip(skip).limit(limit)
            files = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for file in files:
                file["_id"] = str(file["_id"])
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting catalog: {e}")
            return []

    async def get_catalog_count(self) -> int:
        """Get total count of indexed files"""
        try:
            return await self.collection.count_documents({"is_active": True})
        except Exception as e:
            logger.error(f"Error getting catalog count: {e}")
            return 0

    async def delete_file(self, message_id: int) -> bool:
        """Soft delete file by setting is_active = false"""
        try:
            result = await self.collection.update_one(
                {"message_id": message_id},
                {"$set": {"is_active": False}}
            )
            
            if result.modified_count > 0:
                logger.info(f"File deleted: message_id={message_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting file {message_id}: {e}")
            return False

    async def search_files(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search files by custom name"""
        try:
            cursor = self.collection.find({
                "is_active": True,
                "$text": {"$search": query}
            }).sort("created_at", -1).limit(limit)
            
            files = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for file in files:
                file["_id"] = str(file["_id"])
            
            return files
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return []

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

# Global database instance
db = DatabaseManager()