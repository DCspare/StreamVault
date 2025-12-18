# 📂 Project: Shadow Streamer (Stream Vault) - Context & Progress

**Codename:** Shadow Streamer | **Phase:** Production Ready (V1 Complete + Documentation)

---

## 🏗️ Engineering Architecture

Shadow Streamer is a zero-budget media server stack built for Hugging Face's Docker runtime:

* **Hosting:** Hugging Face Spaces (Docker SDK) - Dedicated Container
* **Networking:** Direct SOCKS5 Tunnel (High-Ports: 5566) + IPv4 for firewall bypass
* **Process Architecture:** Bot-First via `asyncio.gather(web_server, idle())` - Pyrogram owns main loop
* **Storage Strategy:** Disk Persistence enabled - session files saved to `/app` to prevent re-auth loops
* **Database:** MongoDB Atlas (Free Tier) for persistent file indexing
* **UX Strategy:** Interactive State Management (Buttons/Callbacks) vs Commands

---

## 🛠️ Tech Stack (V1 Production)

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core Application Logic |
| **Bot Client** | Pyrogram | Live connection to Telegram API |
| **Web Server** | FastAPI + Uvicorn | High-performance HTTP streaming |
| **Database** | Motor (async MongoDB) | File metadata & catalog storage |
| **Networking** | `pyrogram[socks]` | Firewall bypass via SOCKS5 proxy |
| **Engine** | `asyncio` | Standard event loop (no uvloop) |
| **YouTube** | yt-dlp | Video download & metadata extraction |

---

## 📂 Current File Structure (Documented V1)

```text
StreamVault/
│
├── Dockerfile                      # Docker image with ffmpeg, yt-dlp, proper permissions
├── requirements.txt                # All dependencies (Pyrogram, FastAPI, Motor, yt-dlp)
├── config.py                       # ✅ Documented: Environment variable loader with validation
├── main.py                         # Bot-First: asyncio.gather(server, idle())
│
├── utils/                          # Helper Modules
│   ├── database.py                 # ✅ Documented: MongoDB operations manager
│   └── range_parser.py             # ✅ Documented: HTTP Range header parser
│
├── bot/                            # Telegram Logic
│   ├── client.py                   # ✅ Documented: ShadowBot with session pooling
│   ├── session_pool.py             # Session pool for parallel downloads
│   └── plugins/
│       └── indexing_handler.py     # ✅ Documented: Interactive Menu's, Visual Progress, YT_COOKIES, File upload, YouTube, catalog, search, delete
│
└── server/                         # Web Stream Logic
    └── stream_routes.py            # ✅ Documented: HTTP 206 streaming with auto-healing
```

---

## ✅ ACHIEVED MILESTONES

### Task 1: Session Pooling (Dec 15, 2025)
**Problem:** 10-15 second auth delays on every stream request  
**Solution:** Implemented per-DC session pooling in `bot/session_pool.py`  
**Impact:** Zero auth delays, parallel downloads, stable streaming

### Task 2: Log Channel Indexing System (Dec 16, 2025)
**Problem:** No file persistence, users couldn't manage uploads  
**Solution:** Complete indexing system with MongoDB  
**Features Implemented:**
- ✅ File upload with custom naming
- ✅ YouTube video download with progress tracking
- ✅ MongoDB persistent storage with indexes
- ✅ `/catalog` command with pagination
- ✅ `/delete` command (soft delete)
- ✅ `/search` command (full-text search)
- ✅ Stream link generation: `https://bot.hf.space/stream/{log_id}/{message_id}`
- ✅ Size & duration validation (500MB, 2 hours defaults)
- ✅ Emoji-rich user messages

**MongoDB Schema:**
```javascript
{
  message_id: 159,                    // Telegram message ID in LOG_CHANNEL
  file_unique_id: "xyz123abc",        // Telegram unique file ID  
  file_id: "CAACAgIAAxkBAAIB...",     // Telegram file ID for streaming
  custom_name: "Avengers_Endgame",    // User-given name
  file_size: 1574507,                 // Size in bytes
  file_type: "video",                 // video, audio, file
  source: "direct_upload",            // direct_upload, youtube_link
  youtube_url: null,                  // Original YouTube link if applicable
  duration: 8100,                     // Duration in seconds
  uploaded_by: 5228293685,            // User Telegram ID
  created_at: 2025-12-16T06:18:24Z,   // Timestamp
  stream_link: "https://bot.hf.space/stream/log_ID/msg_ID",
  is_active: true                     // Soft delete flag
}
```

### Task 3: Plugin Loading Fix & Comprehensive Documentation (Dec 16, 2025)
**Problem:** Plugin loading unclear, no code documentation, insufficient logging  
**Solution:** Enhanced plugin loading, added comprehensive docs to all files

**Improvements Made:**

#### 1. Plugin Loading & Verification
- ✅ Explicit plugin auto-loading via `plugins=dict(root="bot/plugins")` in StreamVault
- ✅ Startup logging: "✅ Bot Connected"
- ✅ Handler registration verified at startup
- ✅ Clear log messages for plugin loading success/failure

#### 2. Help Command Enhancement
- ✅ Updated `/help` to include `/catalog`, `/delete`, `/search` commands
- ✅ Added stream link format: `https://yourbot.hf.space/stream/[log_id]/[message_id]`
- ✅ Documented all features: file upload, YouTube, catalog, limits, interactive buttons
- ✅ Troubleshooting tips for users

#### 3. MongoDB Schema Verification
- ✅ `_verify_schema()` function in `utils/database.py`
- ✅ Checks collection and indexes at startup
- ✅ Logs: "✅ MongoDB schema verified - all indexes present"
- ✅ Warns if indexes missing but doesn't fail

#### 4. Comprehensive Logging (All Levels)
**Added logging to all 6 core files:**

**config.py:**
- INFO: Configuration validation success
- DEBUG: Config values (API_ID, LOG_CHANNEL_ID, file limits)
- ERROR: Missing config values

**utils/database.py:**
- INFO: Connection success, file indexed, search results
- DEBUG: Query parameters, file metadata
- WARNING: Missing indexes, file not found
- ERROR: Connection failures, save errors (with exc_info=True)

**utils/range_parser.py:**
- Module docstring explaining HTTP 206 support
- Function docstrings with examples

**bot/client.py:**
- INFO: Bot initialization, connection success, session cleanup
- DEBUG: Config details, proxy settings
- WARNING: Corrupt session, FloodWait
- ERROR: Connection failures (with exc_info=True)

**bot/plugins/indexing_handler.py:**
- INFO: File upload received, file indexed, YouTube download progress
- DEBUG: Upload state created, progress calculations
- WARNING: File rejected (size), download timeout
- ERROR: Processing failures

**server/stream_routes.py:**
- INFO: Stream request with full params
- DEBUG: Range parsing, file metadata, chunk calculations, response headers
- WARNING: Bot not connected, file ref expired, timeout retries
- ERROR: Meta fetch failed, stream broken (with exc_info=True)

#### 5. Developer Documentation
**Added comprehensive docstrings to EVERY function:**

**Format Used:**
```python
def function_name(param: type) -> return_type:
    """
    Brief description of function purpose.
    
    Detailed explanation of what it does and how it works.
    
    Args:
        param (type): Description of parameter
        
    Returns:
        return_type: Description of return value
        
    Raises:
        ExceptionType: When this exception occurs
        
    Example:
        >>> function_name("test")
        result
    """
```

**Files Documented:**
- ✅ `config.py` - All methods with type hints and examples
- ✅ `utils/database.py` - All methods with MongoDB schema details
- ✅ `utils/range_parser.py` - HTTP 206 explanation with examples
- ✅ `bot/client.py` - ShadowBot class, session pooling, get_file override
- ✅ `bot/plugins/indexing_handler.py` - All handlers with workflow explanations
- ✅ `server/stream_routes.py` - Stream endpoint with HTTP 206 details

**Documentation Highlights:**
- Module-level docstrings explain file purpose
- Class docstrings describe attributes and features
- Function docstrings include Args, Returns, Raises, Examples
- Inline comments explain complex logic (chunk calculations, offset handling)
- No excessive commenting - only where needed

### Task 6: Handler Conflict Resolution & Codebase Audit (Dec 16, 2025)
**Problem:** Critical handler conflicts, security risks, and code integrity issues
**Solution:** Deleted conflicting files, secured logging, and performed full audit

**Issues Resolved:**

#### 1. Handler Priority Conflict
- ❌ **Problem:** `start_handler.py` caught ALL private messages, blocking file indexing
- ✅ **Fix:** Deleted `start_handler.py`, centralized logic in `indexing_handler.py`
- ✅ **Verification:** Handlers now registered in correct order (Specific → General)

#### 2. Security: MongoDB URL Exposure
- ❌ **Problem:** Full connection string with password exposed in logs
- ✅ **Fix:** Modified `utils/database.py` to mask credentials
- ✅ **Result:** Logs now show `✅ Connecting to MongoDB cluster: cluster-name`

#### 3. Complete Codebase Audit
- ✅ **Duplicate Handlers:** Verified zero conflicts in `bot/plugins/`
- ✅ **Error Handling:** Added `try/except` blocks to all async handlers
- ✅ **Logging:** Standardized on `logger.info/error` (no print statements)
- ✅ **Imports:** Verified no circular or unused imports
- ✅ **Handler Verification:** Added `verify_handler_registration()` startup check

**Handler Registration Map:**
1. `/start` command (private & log channel specific)
2. `/help` command
3. `/catalog`, `/delete`, `/search` `/stream` commands
4. Document upload (medium specific)
5. Text messages (least specific - catches YouTube + names)

### Task 6: Interactive UX & State Management (Dec 17, 2025)
**Problem:** CLI-like commands were clunky, renaming was difficult, UI was bland.
**Solution:** Implemented robust state machine (`FileState`, `YouTubeState`) with Interactive Buttons.
**Features Implemented:**
- ✅ **Visual Progress Bar:** "Hackery" style `[★★☆☆☆] 40%` with real-time speed/ETA.
- ✅ **Refresh Button:** Added callback button to progress messages to check bot liveliness.
- ✅ **YouTube Menu:** Interactive keyboard to select resolution (1080p, 720p, 480p).
- ✅ **Smart Renaming:** Logic to handle `/skip` or custom input for both files and videos.
- ✅ **Styled Captions:** Rich metadata formatting (`User`, `Size`, `Quality`, `#Hashtags`).
- ✅ **Hidden Stream Links:** Markdown masking `[Click Here to Stream](url)` instead of raw URLs.

### Task 7: Network Resilience & YouTube 403 Fixes (Dec 18, 2025)
**Problem:** `yt-dlp` failing with `HTTP 403 Forbidden` and DNS errors on HF Spaces.
**Solution:** implemented advanced evasion techniques.
**Technical Implementations:**
- ✅ **Android Client Spoofing:** `extractor_args: player_client=['android']` to bypass Datacenter blocks.
- ✅ **IPv4 Forcing:** Solves `[Errno -5] No address associated with hostname`.
- ✅ **Secret Cookies:** Auto-creation of `cookies.txt` from HF Secrets `YT_COOKIES` only when needed.
- ✅ **Proxy Injection:** Auto-detection of `PROXY_URL` (SOCKS5/HTTP) from environment.
- ✅ **Permission Caching:** New `/start` logic to cache "Access Hash" for Private Log Channels.

**Updated MongoDB Schema:**
```javascript
{
  message_id: 159,
  file_unique_id: "xyz123abc",
  custom_name: "Ramayana_Intro",
  file_size: 7654321,
  file_type: "video",
  quality: "1080p",            
  task_by: usr_mention,    // Added
  uploaded_by: 5228293685,    // Added
  created_at: 2025-12-18T...,
  stream_link: "https://bot.hf.space/stream/-100.../159"
}
```

---

## 📊 Current System Status

### Operational Features
- ✅ **Visual Interface:** Interactive Buttons for Cancel/Refresh/Delete.
- ✅ **Quality Control:** User selects YouTube resolution (fallback loop included).
- ✅ **Robust Downloading:** Cookies + Android Client + Proxy + IPv4 stack.
- ✅ **Smart Renaming:** Unified flow for renaming or skipping.
- ✅ Bot token authentication via Pyrogram
- ✅ File upload with custom rename and validation
- ✅ YouTube link download (size/duration validation)
- ✅ Private log channel forwarding and indexing
- ✅ MongoDB persistence with full-text search
- ✅ HTTP streaming with byte-range support (HTTP 206)
- ✅ Catalog browsing with pagination (`/catalog`)
- ✅ File deletion with soft delete (`/delete`)
- ✅ File search by name (`/search`)
- ✅ Session pooling (no auth delays)
- ✅ Clean user-friendly messages with emojis
- ✅ Comprehensive logging (INFO, DEBUG, WARNING, ERROR)
- ✅ Full code documentation for developers

### Free Tier Capacity (Theory)
- **Concurrent Users:** 15-20 (safe), 30-40 (with optimization)
- **Bandwidth:** ~667MB/day (20GB/month Hugging Face limit)
- **Storage:** Unlimited (files stored in Telegram)
- **Database:** 512MB (MongoDB Atlas Free Tier)
- **Monthly Earning Potential:** $5-75 (depending on usage and ads)

### Known Limitations
- If No YouTube cookies (some videos blocked after 3 days)
- No Voice Chat support (needs burner account session string)
- Proxy timeouts on poor networks (auto-retry with backoff)
- 500MB file size limit (prevents Telegram upload timeout)
- 2 hour video duration limit (prevents download timeout)

---

## 🎯 NEXT PRIORITY FEATURES

### Priority 1: ✅ COMPLETED - Log Channel Indexing System
- File rename/forward logic ✅
- YouTube download handling ✅
- MongoDB indexing ✅
- User-friendly messages ✅
- Catalog/delete/search commands ✅

### Priority 2: ✅ COMPLETED - Code Documentation & Logging
- Comprehensive docstrings ✅
- Logging improvements ✅
- MongoDB schema verification ✅
- Help command update ✅

### Priority 3: NEXT - Web API Catalog Endpoint
**Why:** Enables Vercel frontend for Netflix-style UI  
**Impact:** Monetization via ads on frontend  
**Complexity:** Low  
**Timeline:** 2-3 hours  

**Components:**
- `/api/catalog` endpoint returning JSON list
- `/api/search?q=query` endpoint for search
- CORS middleware for Vercel access (already configured)
- Stream link generation with metadata
- Pagination support

**Example Response:**
```json
{
  "total": 42,
  "page": 1,
  "per_page": 20,
  "files": [
    {
      "message_id": 159,
      "custom_name": "Avengers_Endgame",
      "file_size": 1574507,
      "file_type": "video",
      "duration": 8100,
      "stream_link": "https://bot.hf.space/stream/5228293685/159",
      "created_at": "2025-12-16T06:18:24Z"
    }
  ]
}
```

### Priority 4: VC Feature Foundation (Blocked)
**Why:** Enables voice chat streaming for music/podcasts  
**Status:** ⏸️ Blocked - needs burner account (Session String)  
**Timeline:** After burner account acquired  

**Requirements:**
- PyTgCalls installation
- User account session string (not bot token)
- Separate container for VC bot (different from file bot)

### Priority 5: Mirror Bot Separation (Optional)
**Why:** Prevents heavy downloads from blocking stream requests  
**Status:** 💡 Optional - implement at 20+ concurrent users  
**Timeline:** 4-6 hours when needed

---

## 📅 Development Timeline

```
Dec 15: Task 1 - Session Pooling                    ✅ DONE
Dec 16: Task 2 - Log Channel Indexing               ✅ DONE
Dec 16: Task 3 - Plugin Loading & Docs              ✅ DONE
Dec 16: Task 4 - Handler Conflicts & Audit          ✅ DONE
Dec 16: Task 5 - Web API Catalog                    🚀 NEXT
Dec 17: Task 6 - VC Feature (blocked)               📋 PLANNED
Dec 18: Task 7 - Frontend UI (Vercel)               📋 PLANNED
```

---

## 🔧 Critical Implementation Details
### YouTube Network Evasion Strategy
Hugging Face IPs are flagged by YouTube. We use a 4-layer bypass:
1.  **Client Spoof:** We set `extractor_args` to `android` client. This API is lenient.
2.  **DNS Fix:** `force_ipv4=True` prevents IPv6 resolution failures in Docker.
3.  **Cookies via Secrets:** The bot checks `os.environ["YT_COOKIES"]`. If present, it writes a temporary `cookies.txt`, uses it for auth/age-gating, and immediately deletes it.
4.  **Proxy Fallback:** If `PROXY_URL` exists, it routes requests through SOCKS5.

### State Management (`user_states`)
We moved from a simple dictionary to Class-based states:
*   **`FileState`:** Handles direct uploads (File Object + metadata).
*   **`YouTubeState`:** Handles YT workflow (Info Dict + URL + Selected Quality).
This prevents variable mismatch errors and allows cleaner switching between flows in `handle_text_messages`.

### Private Channel Permission Cache
**Issue:** On HF restart, bot forgets "Access Hash" for private channels, causing `PeerInvalid`.
**Fix:** The new `/start` handler allows execution **inside the Log Channel**. Sending `/start` there once forces Telegram to send an update, which caches the Access Hash for the session lifespan.

### Telegram Streaming Offset Handling
**CRITICAL:** Pyrogram's `stream_media(offset, limit)` expects:
- `offset`: Number of 1MB chunks to skip (NOT bytes)
- `limit`: Number of chunks to stream (NOT bytes)

Telegram API uses 1MB (1024 * 1024 bytes) chunks internally. When handling HTTP byte-range requests, always convert byte offsets to chunk offsets:
- `chunk_offset = byte_offset // (1024 * 1024)`
- `bytes_to_skip_in_first_chunk = byte_offset % (1024 * 1024)`

Passing byte offsets directly causes OFFSET_INVALID errors because Pyrogram multiplies the offset by 1MB, resulting in offsets far beyond the file size.

### MongoDB Indexes Required
```python
await collection.create_index([("message_id", 1)], unique=True)
await collection.create_index([("uploaded_by", 1)])
await collection.create_index([("created_at", -1)])
await collection.create_index([("custom_name", "text")])
```

### Environment Variables Required
```bash
# Telegram Bot Config
API_ID=12345678
API_HASH=abcdef1234567890
BOT_TOKEN=123456:ABCdefGHIjklMNOpqrsTUVwxyz

# Server Config with proxy(hardcoded in client.py)
hostname="0.0.0.0",
PORT=7860,

URL=https://yourbot.hf.space

# Database Config
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net
MONGO_DB_NAME=cluster name
LOG_CHANNEL_ID=-1005154862 (using IDBot or similar)

# Proxy for YT
PROXY_URL (if http use)
http://user:pass@ip:port OR http://ip:port
PROXY_URL (if socks5 use)
socks5://user:pass@ip:port OR socks5://ip:port

# Cookies for YT Downloads (code handles cookies.txt file creation you need to put cookie data by using cookie-editor, export in Netscape format:
YT_COOKIES
# Netscape HTTP Cookie File.... (a long text)

# File Limits (hardcoded for now)
MAX_FILE_SIZE_MB=500
MAX_VIDEO_DURATION_HOURS=2
TG_GETFILE_TIMEOUT=60
```

---

## 🎓 Code Style & Conventions

### Docstring Format
- Module-level: Brief purpose + features list
- Class-level: Features + attributes
- Function-level: Description, Args, Returns, Raises, Example
- Use Google-style docstrings

### Logging Levels
- **INFO:** Important events (connection, file indexed, search results)
- **DEBUG:** Detailed info (calculations, state changes, payloads)
- **WARNING:** Recoverable issues (timeout, retry, missing indexes)
- **ERROR:** Failures with full stack trace (`exc_info=True`)

### Comment Style
- Inline comments for complex logic only
- No excessive commenting for self-explanatory code
- Use descriptive variable names
- Follow existing patterns in codebase

---

## 🔗 Related Documentation

- **README.md** - Complete project architecture and setup guide
- **context.md** - This file (current status and achievements)
- **Code Comments** - In every function with docstrings
- **Memory** - Agent's persistent memory with implementation details

---

## 🏆 Key Achievements Summary

1. ✅ **Session Pooling** - Eliminated 10-15s auth delays, enabled parallel downloads
2. ✅ **Log Channel Indexing** - Full file management system with MongoDB
3. ✅ **Comprehensive Documentation** - Every function documented with examples
4. ✅ **Enhanced Logging** - Complete visibility into bot operations
5. ✅ **MongoDB Schema Verification** - Automatic index checking at startup
6. ✅ **Help Command Update** - Complete command reference with examples
7. ✅ **Plugin Loading Fix** - Clear startup logs and handler verification

**Current Status:** Production Ready V1 - Fully Documented & Operational 🚀

**Next Steps:** Web API catalog endpoint → Vercel frontend → Monetization
