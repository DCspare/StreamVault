context.md file

# 📂 Project: Stream Vault (Context & Roadmap)

**Codename:** Shadow Streamer | **Phase:** Stabilization & Persistence (V1 Final)

---

## 🏗️ Engineering Architecture (UPDATED)

The system has evolved to overcome strict Network Blockers, Event Loop conflicts, and Storage Permissions on free-tier hosting.

*   **Hosting:** Hugging Face Spaces (Docker SDK) - Dedicated Container.
*   **Networking:** **Direct SOCKS5 Tunnel** (High-Ports: 7030) + IPv4. Backbone/HTTP proxies were rejected due to packet filtering.
*   **Process Architecture (Bot-First):** Switched from `Uvicorn`-controlled loop to `asyncio.gather(web_server, idle)`. This gives Pyrogram the Main Loop priority, fixing the "Silent Bot" issue.
*   **Storage Strategy:** **Disk Persistence** enabled. Keys are saved to `/app` (Root) to prevent re-authentication loops (`Auth Key Thrashing`) which trigger Telegram Flood Bans.

---

## 🛠️ Tech Stack (V1 Live)

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core Application Logic |
| **Bot Client** | Pyrogram | **Live Connected** to Telegram API |
| **Web Server** | FastAPI + Uvicorn | High-performance Stream Routing |
| **Networking** | `pyrogram[socks]` | **Firewall Bypass/Proxy Injection (CRITICAL)** |
| **Engine** | `asyncio` | Forced Standard Loop (Removed `uvloop` by stripping `[standard]`) |

---

## 📂 Current File Structure (Final V1)

```text
StreamVault/
│
├── Dockerfile                  # Fixed Permissions: chmod/chown 1000:1000 on /app to allow Session writes.
├── requirements.txt            # CLEAN: Removed 'uvicorn[standard]' to kill uvloop conflict.
├── config.py                   # Secure Env Loader.
├── main.py                     # Bot-First Arch: Uses asyncio.gather to run Bot + Web concurrently.
│
├── utils/                      # Helper Modules
│   └── range_parser.py         # HTTP Range Header Math.
│
├── bot/                        # Telegram Logic
│   ├── client.py               # **Configured for Disk Persistence**. Renamed session to 'streamvault_v2'.
│   └── plugins/
│       └── start_handler.py    # Standard listener (Now working via idle() loop).
│
└── server/                     # Web Stream Logic
    └── stream_routes.py        # Logic: /stream/{chat_id}/{msg_id} - Includes Self-Healing logic for expired keys.
```

---

## 🚀 Status Report (ACHIEVED & PENDING)

### ✅ ACHIEVED & CONFIRMED WORKING
- [x] **Stable Hosting Found:** New HF Space on a functional IP address.
- [x] **Network Bypass Successful:** Switched to **Direct Connection Proxy** (High Port 7030) using SOCKS5. This verified connectivity (`Ping/Pong` logs).
- [x] **Silent Bot / Ghost Connection (FIXED):**
    *   **Problem:** Bot was logged in (Outbound ok) but couldn't receive messages (Inbound block).
    *   **Solution:** Removed `uvicorn[standard]` (uvloop) from requirements and switched `main.py` to use `idle()` instead of `server.serve()` as primary blocker.
- [x] **Stream Logic:** Streaming endpoints generate valid 206 Byte-Range responses.

---

## 🔴 CURRENT ISSUE: AUTH KEY THRASHING / FLOOD WAIT
- [ ] **Data Persistence Failure (The "Auth Loop"):**
- **SYMPTOM:** The bot logs `Start creating a new auth key` repeatedly. Video plays for 2s, buffers, then fails. Logs show `[400 OFFSET_INVALID]` or `[420 FLOOD_WAIT]`.
- **ROOT CAUSE:** Docker container wasn't allowing Pyrogram to **write the session file** to disk (`in_memory=True` or Bad Permissions).
    *   *Result 1:* Every network jitter creates a New Auth Key.
    *   *Result 2:* Video Player asks for file using Old Key -> Telegram says "Invalid".
    *   *Result 3:* Too many new keys in <10mins -> Telegram bans with `420 FLOOD_WAIT`.
- **SOLUTION (IN PROGRESS):**
    1.  **Docker:** `RUN chown -R 1000:1000 /app` to guarantee write access.
    2.  **Code:** Set `in_memory=False`, `workdir="."`.
    3.  **Bypass:** Renaming Session from `streamvault_v1` to `streamvault_v2` to escape the 2000s ban timer.

---

## 🔮 The Master Plan (Roadmap V2)

Since the code is proven, the plan moves beyond V1 completion to ensuring the project's permanent functionality and growth.

### **Phase 1: Stabilization & V1 Completion**
1.  **Immediate Priority:** Deploy Persistence fix to stabilize Streaming.
2.  **V1 Goal:** Final Confirmation of a successful file streaming test.

### **Phase 2: Data Persistence (MongoDB)**
- **Goal:** Implement MongoDB Atlas (Free Tier) to store all indexed files permanently.
- **Functionality:** This solves the current lack of a persistent file library, providing reliable links and making content browseable.

### **Phase 3: Front-End UI**
- **Goal:** Build the simple web interface.
- **Tech:** A basic React or HTML/JS frontend hosted on a free CDN (e.g., Netlify/Cloudflare Pages) connecting to the FastAPI API endpoints `/api/catalog`.

### **Phase 4: VC Integration & Mirror System**
- **Goal:** Add PyTgCalls (VC Playback) and deploy the separate Leech Bot for automated content injection.
