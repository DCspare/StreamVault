Designing a MongoDB schema for a streaming service requires balancing **Read Speed** (Fast Website) vs. **Write Complexity** (Bot Indexing). Since our website reads 1,000x more than the bot writes, we optimize for **Read Performance**.

We will use **4 Core Collections**: `movies`, `series`, `users`, `workers`, `reports` and `users`.

---

### 1. The `movies` Collection (The Metadata Hub)
*Role:* Stores Single-File entities. Aggregates all qualities into one document to allow the "Bucket Modal" on the frontend.

```json
{
  "_id": "tmdb_299534",             // PRIMARY KEY: Locked to TMDB ID to prevent duplicates
  "title": "Avengers: Endgame",
  "clean_title": "avengers endgame", // For "Fuzzy Search" logic (stripped of symbols)
  "year": 2019,
  "genres": ["Action", "Sci-Fi"],
  "rating": 8.3,
  "status": "available",            // Status: available | processing | banned (DMCA) | repairing (Dead Link)

  // 🖼️ VISUALS (Obfuscated Links)
  "visuals": {
    "poster": "AgADxxxx",           // Telegram File ID for the Poster
    "backdrop": "AgADxxxx",         // Telegram File ID for the Background
    "screenshots": [                // Generated during ingestion
       "AgADxxx_frame1", 
       "AgADxxx_frame2" 
    ]
  },

  // 🎞️ THE FILES BUCKET (Qualities)
  "files": [
    {
      "quality": "2160p",
      "label": "4K HDR [HEVC]",     // What user sees on the button
      "size_human": "14.2 GB",
      "size_bytes": 15248102831,
      "telegram_id": "BAACAgUAAxk...", // File_ID to stream
      "file_hash": "a1b2c3d4",       // Nginx Cache Key
      "backup_url": "https://abyss.to/x/123", // Failover link
      
      // Subtitle Tracks found inside this file
      "subtitles": [
      { 
        "lang": "eng",      // ISO Code for Player logic
        "label": "English", // UI Label
        "index": 3          // FFmpeg Map Index (Stream #0:3) - Critical for extraction
      },
      { 
        "lang": "spa", 
        "label": "Español", 
        "index": 4 
      }
    ]
  }
] 
    },
    {
      "quality": "1080p",
      "label": "1080p [x264]",
      "size_human": "2.8 GB",
      "size_bytes": 3006477107,
      "telegram_id": "BAACAgUAAxk_LOW_RES...",
      "file_hash": "x9y8z7",
      "subtitles": [ "eng" ]
    }
  ],
  
  "created_at": ISODate("2025-12-21T10:00:00Z"),
  "views": 45200
}
```

**🔑 Design Strategy:**
*   **The Array Strategy (`files: []`):** We don't make separate DB entries for 1080p vs 4K. We nest them. The Frontend fetches *one* document and has everything it needs to build the "Quality Selector Modal."
*   **The Index Mapping:** When the Frontend requests `/api/subs/eng`, the backend looks up `index: 3` and runs `ffmpeg -map 0:3`, ensuring we extract the correct track instead of accidentally extracting the Audio track.

---

### 2. The `series` Collection (The Hierarchy)
*Role:* Stores structured TV Shows. Must handle "Episodes" and "Season Packs" distinctly.

```json
{
  "_id": "tmdb_1399", 
  "title": "Game of Thrones",
  "year": 2011,
  "status": "ended",                // "ended" or "ongoing" (Used for the UI Tag)
  "total_seasons": 8,
  
  "visuals": { "poster": "AgAD...", "backdrop": "AgAD..." },

  // 📦 THE PACKS (Download Buttons)
  "season_packs": [
    {
      "season": 1,
      "zip_file_id": "BAACAg...",   // Pre-zipped file on Telegram
      "size": "25 GB"
    }
  ],

  // 📺 THE STREAMING FILES (Episodes)
  "seasons": {
    "1": [                         // Dictionary Key = Season Number
      {
        "episode": 1,
        "title": "Winter Is Coming",
        "file_id": "BAACAg...",
        "quality": "1080p"
      },
      { "episode": 2, "..." }
    ],
    "2": [ ... ]
  }
}
```

**🔑 Design Strategy:**
*   **Seasons as Keys (`seasons.1`):** Using an object/dictionary instead of an array makes looking up a specific season faster (`db.series.find({"_id": "...", "seasons.1": {$exists: true}})`).

---

### 3. The `users` Collection (Identity & Permissions)
*Role:* Handles both "Guest" Cookies and "Logged-In" Telegram Users.

```json
{
  "_id": 123456789,                 // Int (Telegram ID) or String "guest_8a2b3c"
  "type": "telegram",               // "telegram" or "guest"
  "first_name": "John",
  "joined_at": ISODate(...),

  // 👮 ACCESS CONTROL
  "role": "free",                   // free | premium | admin | banned
  "is_banned": false,
  "premium_exp": ISODate("2026-01-01"),

  // 🤝 GROWTH ENGINE
  "referral": {
    "code": "john_x92",             // Unique Invite Code
    "invited_count": 5,             // Tracker for "Invite 3 to unlock 4K"
    "invited_by": 987654321
  },

  // 🍿 EXPERIENCE
  "history": [                      // The "Continue Watching" Row
    {
      "tmdb_id": "tmdb_299534",
      "timestamp": 3405,            // Stopped at 56:45
      "last_watched": ISODate(...)
    }
  ],
  "wishlist": ["tmdb_550", "tmdb_99"]
}
```

**🔑 Design Strategy:**
*   **Unified ID:** By treating Guests (`guest_...`) and Telegram Users (`123...`) in the same collection, the code logic (`get_user(id)`) works exactly the same for both. If a Guest eventually logs in via Magic Link, we just **Merge** the document.

---

### 4. The `workers` Collection (Infrastructure Health)
*Role:* Manage the Swarm. Determine which SIM card account is alive/dead.

```json
{
  "_id": "worker_01",
  "phone": "+1999888777",
  "api_id": 123456,
  
  // 🩺 HEALTH CHECK
  "status": "active",               // active | busy | flood_wait | dead
  "last_active": ISODate(...),
  "current_task": "upload_avengers_4k", // What is it doing right now?

  // 🚨 ERROR TRACKING
  "flood_wait_until": null,         // If set, manager ignores this bot until time
  "error_count": 0,                 // Auto-kill if > 10 errors
  
  // 📊 LOAD BALANCING
  "total_uploads": 450,
  "storage_channel_id": -100999999  // Where this worker dumps files
}
```
---

### 5. The `reports` Collection (The Medic Queue)
*Role:* Stores user complaints about broken links/audio so the "Medic Bot" can track repairs.

```json
{
  "_id": "report_882910",
  "tmdb_id": "tmdb_299534",        // The Movie Page
  "file_id": "file_hash_1080p",    // The specific broken file
  "reported_by": 123456789,        // User ID (Telegram/Guest)
  
  "issue": "dead_link",            // dead_link | out_of_sync | wrong_file
  "status": "pending",             // pending | repairing | fixed | ignored
  
  "created_at": ISODate("..."),
  "auto_fix_attempted": false      // Has the bot tried to fix it yet?
}
```
**🔑 Design Strategy:**
*   **Status Workflow:** This field drives the Admin Dashboard.
    *   `pending`: Show red badge in Admin Panel.
    *   `repairing`: Bot is currently Leeching a replacement.
    *   `fixed`: Bot automatically notifies `reported_by` (User) via DM: "Your movie is fixed!"

---

### 6. Updated `users` Collection (Iron Dome Security)
*Role:* Adds the "Anti-Sharing" lock fields to prevent account abuse.

```json
"security": {
  "active_sessions": 2,               // Current open tabs (Redis check)
  "last_ip": "122.10.45.11",          // Most recent access IP
  
  // 🛡️ DEVICE FINGERPRINT
  "bound_device": {
    "hash": "xh78_chrome_windows",    // Hash(UserAgent + Screen + OS)
    "locked_at": ISODate("...")
  },
  
  // 🍪 MAGIC LINK INTEGRITY
  "auth_token_secret": "xyz_salt",    // Random salt changed on password reset/logout
                                      // Invalidates all old JWTs instantly
}
```
**🔑 Design Strategy:**
*   **`bound_device` Logic:** This supports the **"First-Touch Lock"**.
    *   If `bound_device` is empty -> Accept connection + Write Hash.
    *   If `bound_device` exists -> Compare Hash. If mismatch -> Block (prevent sharing).
*   **`auth_token_secret`:** If you ban a user, you simply regenerate this string in the DB. Instantly, *every* valid JWT link they have ever shared stops working.

---

**The `books` Collection:** 
```json
{
  "_id": "manga_onepiece",
  "type": "manga",             // manga | comic | novel
  "title": "One Piece",
  "read_direction": "rtl",     // Right-To-Left
  "chapters": [
     { "chap": 1050, "file_id": "telegram_file_id_x", "pages": 18 },
     { "chap": 1051, "file_id": "telegram_file_id_y", "pages": 20 }
  ]
}
```
**The Backend Route (`/api/read/{file_id}/{page}`)**
Instead of streaming video, the Manager Bot:
1.  Downloads the specific 300MB `.cbz` file (Video Workers do this easily).
2.  Unzips it in RAM.
3.  Returns specific `image_001.jpg` to the Frontend.

---

### 🔭 The Indexing Strategy (How to search 10,000 files instantly)

MongoDB is fast, but only if you index correctly. For `StreamVault`, run these commands in your Compass/Shell:

1.  **Search Index (The User Search Bar):**
    We need a **Compound Text Index** so users can search "Avengers" OR "2019" OR "Action".
    ```javascript
    db.movies.createIndex({
        "title": "text",
        "clean_title": "text",
        "genres": "text"
    })
    ```

2.  **Duplicate Guard (The Integrity):**
    Prevent accidentally adding the same movie twice (Leech Bot safety).
    ```javascript
    db.movies.createIndex({ "title": 1 }, { unique: true })
    ```

3.  **Swarm Performance:**
    Make sure Redis can find an "active" worker instantly without scanning.
    ```javascript
    db.workers.createIndex({ "status": 1 })
    ```
