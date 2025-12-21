# 📂 Phase 2 Blueprint: Telegram Ecosystem & Bots
**Filename:** `docs/v2_blueprint/context_02_telegram_logic.md`
**Role:** Application Logic, Content Ingestion, User Management, and "Swarm" Coordination.
**Technology:** Python 3.10+, Pyrogram (MTProto), asyncio, Motor (MongoDB), Redis.

---

## 🐝 1. Architecture: The "Hive" Model

We strictly separate **Administrative Logic** from **Heavy Transfer Logic** to prevent cascading bans.

### Service A: The Manager Bot (The Brain)
*   **Role:** Single point of contact for Admin and Web Frontend. It *never* downloads files. It manages data and commands.
*   **Identity:** `StreamVaultBot` (Public, branded).
*   **Infrastructure:** Runs in the `manager-api` container (shared with FastAPI).

### Service B: The Worker Swarm (The Muscle)
*   **Role:** 10+ Rotating Physical SIM accounts. They perform the heavy downloads, uploads, and streaming.
*   **Identity:** `Worker1`, `Worker2`... (Private, invisible to users).
*   **Infrastructure:** Runs in the `worker-hive` container as parallel `asyncio` tasks.

---

## 🤖 2. The Manager Bot Features

### 🔐 Auth & Compliance
- [ ] **Auth Token Generator (Magic Link)**
  Generates anonymized `jwt_token` links (`streamvault.net/auth?token=...`) that allow the website to adopt the Telegram User ID for "Premium" status without the user logging in directly.
- [ ] **Global Kill Switch (`/takedown`)**
  Executes the abuse protocol: instantly wipes specific content ID from MongoDB, triggers Nginx Cache Purge on host, and deletes the source message in Telegram.
- [ ] **User Gatekeeper**
  Validates User Permissions (Free/Premium/Banned) and enforces rate limits before signing secure stream URLs for the Frontend.

### 📚 Content Management
- [ ] **Metadata "Hoarder"**
  Silent proxy that queries TMDB/OMDB API for Posters/Plots and caches them to MongoDB. *Decouples Frontend from public APIs.*
- [ ] **Direct Forward Indexing**
  Instantly processes files "Forwarded" from other Telegram channels without re-uploading (Cloning), mapping existing File IDs to new Database Entries.
- [ ] **Broken Link "Medic"**
  Receives User/Frontend "Dead Link" reports, checks HTTP Head validity, and triggers the Re-Leech queue if the file is truly gone.
- [ ] **Manual Override Console**
  `/edit [TMDB_ID]` command allows manual Admin correction of bad metadata matches or replacing cover art directly from chat.

### 📢 Growth & Revenue
- [ ] **Referral Engine (Viral Loop)**
  Tracks unique invite links (`/start?ref=123`). Validates "New User" criteria (to prevent self-invite cheating) and auto-rewards the inviter with "7-Day 4K Premium" status upon hitting quotas.
- [ ] **Broadcast Publisher**
  Auto-posts "New Release Cards" (Poster + Website Link) to the **Public Update Channel** immediately after ingestion.
- [ ] **Ad-Link Generator**
  Integrates URL Shortener APIs (e.g., GPlinks) to tokenize downloads for heavy files (Season Packs), creating valid Access Cookies for the web.
- [ ] **Wishlist Notifier**
  Tracks user requests (`/request Movie`) and automatically DMs them when the requested content is added to the library.

### 📊 Admin Analytics
- [ ] **Daily Stat Reporter**
  Scheduled cron job that sends a summary to the Admin Private Channel at 12:00 AM:
  *   Total New Users
  *   Total Bandwidth Consumed (Oracle)
  *   Number of Dead Links Fixed
  *   Storage Used (Cache %)

---

## 🚜 3. The Worker Bot Features (Leech & Stream)

### 📥 Ingestion & Mirroring
- [ ] **Dual-Path Ingestion**
  Processes files via two simultaneous logic paths:
  1.  **Stream Path:** Extracts video for streaming.
  2.  **Zip Path:** Creates a `.7z` archive (no compression) for "Season Packs" upload.
- [ ] **Crowdsourced Ingestion Engine**
  Public mode accepting user links/torrents into a "Quarantine/Dump Channel". Files remain pending until Admin clicks "Approve".
- [ ] **Multi-Source Mirroring**
  Simultaneously uploads copies to Backup Hosts (Abyss.to / StreamWish) to create a RAID-1 redundancy layer in case of Telegram bans.
- [ ] **Smart Renaming Engine**
  Standardizes filenames (PTN Parser) to remove spam tags (`[x265]`, `www.site.com`) and injects "StreamVault" branding before upload.

### 🎞️ Processing Logic
- [ ] **Subtitle Stream Prober**
  Analyzes input files with `ffprobe` to map embedded subtitle tracks (Eng, Spa, Fre) indices (`0:3`, `0:4`) so the Web Player can extract them on-demand.
- [ ] **Auto-Screenshot Extraction**
  Extracts 3-5 frames during the download process using FFmpeg and hosts them on a private channel for the Website's "Quality Preview" gallery.
- [ ] **Proxy/Network Tunneller**
  Configurable SOCKS5 support (`pyrogram[socks]`) allowing specific workers to route traffic through proxies to bypass ISP blocks on torrent trackers.

### ⚖️ Load Management
- [ ] **Swarm Rotation Logic**
  Redis-backed algorithm that distributes tasks to the "Least Busy" worker session. Prevents Flood Wait bans by spreading 1,000 requests across 10 accounts.
- [ ] **Queue System**
  Limits concurrent heavy tasks (e.g., Unzipping/Mirroring) to ~5 active threads to protect the Oracle VPS CPU.

---

## 💾 4. Data Strategy & Channels

### Channel Hierarchy (Buckets)
- **Channel A: Public Updates** (Safe. Clean. Links only to Website. No files.)
- **Channel B: Private Logs** (Storage of verified Videos & Images. Segmented by Genre: Action, Horror, etc.)
- **Channel C: Dump/Quarantine** (Holding area for Crowdsourced User uploads).
- **Channel D: Admin Alerts** (System Health, DMCA Reports, Login notifications).

### Safety Features
- **Hash-Based Blocking:** Ingestion phase calculates file hash; cross-references against `global_blocklist` (CSAM/Illegal) before upload.
- **Identity Isolation:** Worker API Keys/Hashes are separate from Manager keys. A ban on a worker does not affect the Manager's ability to chat with users.

---
