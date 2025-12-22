### 📦 1. New File: `context_04_database.md` (The Data Bible)
*This is the new master reference for all Data Structures.*

# 📂 Phase 2 Blueprint: Master Database Schema
**Filename:** `docs/v2_blueprint/context_04_database.md`
**Role:** Definitive JSON Schemas for MongoDB (Atlas) ensuring compatibility between StreamVault (Video) and ReadVault (Manga).

---

## 📽️ Collection: `library` (Movies, Series & Books)
*A unified collection handled by the Manager Bot to populate the website catalog.*

### A. Movie Entity
```json
{
  "_id": "tmdb_299534",             // Primary Key
  "media_type": "movie",            // movie | series | manga
  "title": "Avengers: Endgame",
  "clean_title": "avengers endgame",
  "year": 2019,
  "genres": ["Action", "Sci-Fi"],
  "rating": 8.3,
  "status": "available",            // available | processing | banned | repairing

  // 🖼️ VISUALS
  "visuals": {
    "poster": "AgADxxxx",           // Telegram File ID
    "backdrop": "AgADxxxx",
    "screenshots": ["AgAD...1", "AgAD...2"]
  },

  // 🎞️ VIDEO BUCKETS
  "files": [
    {
      "quality": "2160p",
      "label": "4K HDR",
      "size_human": "14.2 GB",
      "telegram_id": "BAACAg...",
      "file_hash": "nginx_cache_key",
      
      // Critical for Soft Subtitles
      "subtitles": [
        { "lang": "eng", "index": 3 }, // Stream #0:3
        { "lang": "spa", "index": 4 }
      ]
    }
  ]
}
```

### B. Series Entity
```json
{
  "_id": "tmdb_1399",
  "media_type": "series",
  "title": "Game of Thrones",
  "total_seasons": 8,
  
  // 📦 SEASON PACKS
  "season_packs": [
    { "season": 1, "zip_file_id": "BAACAg...", "size": "25 GB" }
  ],

  // 📺 EPISODES
  "seasons": {
    "1": [
      { "episode": 1, "title": "Winter Is Coming", "file_id": "BAACAg...", "quality": "1080p" }
    ]
  }
}
```

### C. Manga/Book Entity (ReadVault)
```json
{
  "_id": "manga_solo_leveling",
  "media_type": "manga",
  "content_rating": "safe",        // safe | 18+
  "chapter_count": 179,

  // 📖 CHAPTERS
  "chapters": [
    {
      "chap": 1.0,
      "title": "I'm Used to It",
      "storage_id": "-100xxxx",    // Log Channel ID
      "pages": ["file_id_p1", "file_id_p2"]
    }
  ]
}
```

---

## 👥 Collection: `users` (Identity & Progress)
```json
{
  "_id": 123456789,                // Telegram ID OR "guest_hash"
  "type": "telegram",              // telegram | guest
  "role": "free",                  // free | premium | admin
  
  // 🛡️ SECURITY & ANTI-SHARE
  "security": {
    "auth_token_secret": "salt_xyz",
    "active_sessions": 1,          // Redis counter sync
    "bound_device": {
       "hash": "useragent_hash",
       "locked_at": ISODate(...) 
    }
  },

  // 🍿 WATCH/READ HISTORY
  "history": {
    "tmdb_299534": { "timestamp": 3405, "updated_at": ISODate(...) }, // Video
    "manga_solo": { "last_chap": 55, "last_page": 3 }                 // Manga
  },

  // 🤝 REFERRAL
  "referral": { "code": "john_x", "invited_count": 5, "invited_by": 987 }
}
```

---

## 🏗️ Collection: `workers` (The Swarm)
```json
{
  "_id": "worker_01",
  "api_id": 123456,
  "status": "active",             // active | flood_wait | dead
  "current_task": "leeching_avengers",
  "flood_wait_until": ISODate(...) 
}
```

---

## 🚑 Collection: `reports` (The Medic)
```json
{
  "_id": "rep_1",
  "target_id": "tmdb_299534",
  "issue": "dead_link",           // dead_link | wrong_audio | missing_pages
  "status": "pending"             // pending | fixed
}
```

---

## ⚡ Indexing Commands (Run these in Mongo Compass)
1.  **Unified Search:** `db.library.createIndex({ title: "text", author: "text" })`
2.  **User Lookup:** `db.users.createIndex({ "referral.code": 1 })`
3.  **Content Filter:** `db.library.createIndex({ media_type: 1, content_rating: 1 })`
```
