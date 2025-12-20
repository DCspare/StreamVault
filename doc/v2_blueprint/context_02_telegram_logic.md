# 📂 Project Context: Telegram Ecosystem & Bots
**Component:** The Application Logic
**Role:** Ingestion, Indexing, User Management, and "Swarm" Coordination.
**Technology:** Python 3.10+, Pyrogram (MTProto), asyncio.

---

## 🐝 1. Architecture: The "Hive" Model

We strictly separate **Administrative Logic** from **Heavy Transfer Logic** to prevent cascading bans.

### Service A: The Manager Bot (The Brain)
*   **Role:** Single point of contact for Admin and Web Frontend. It *never* downloads files. It manages data.
*   **Identity:** `StreamVaultBot` (Public, branded).

### Service B: The Worker Swarm (The Muscle)
*   **Role:** 10+ Rotating Physical SIM accounts. They perform the heavy downloads and streaming.
*   **Identity:** `Worker1`, `Worker2`... (Private, invisible to users).
*   **Architecture:** Running as a single Docker Service (`workers`) spawing async tasks for each session.

---

## 🤖 2. The Manager Bot Features

### 🔐 Auth & Compliance
- [ ] **Magic Link Authenticator**
  Generates `jwt_token` links (`/login`) enabling passwordless website login.
  *Ensures zero-credential leaks and seamlessly links Telegram Identity to Web Session.*
- [ ] **Global Kill Switch**
  Executes `/takedown [TMDB_ID]`, triggering a unified purge across DB, Nginx, and Telegram Source channels.
  *The core compliance tool for Oracle/DMCA abuse handling.*
- [ ] **User Gatekeeper**
  Validates User Perms (Premium/Free/Banned) and enforces rate limits before signing secure stream URLs.
  *Protects the infrastructure from abuse and scrapers.*

### 📚 Content Management
- [ ] **Metadata "Hoarder"**
  Silent proxy that queries TMDB/OMDB API for Posters/Plots and caches them to MongoDB.
  *Decouples Frontend from public APIs to prevent key revocation and usage tracking.*
- [ ] **Content Indexer (Forward-to-Index)**
  Instantly processes files "Forwarded" from other Telegram channels without re-uploading (Clone).
  *Allows rapid library expansion by mapping existing file IDs to the internal database.*
- [ ] **Broken Link "Medic"**
  Receives User/Frontend "Dead Link" reports, checks HTTP Head, and triggers the Re-Leech queue.
  *Self-maintains library health by automating the repair cycle.*
- [ ] **Manual Override Console**
  `/edit [TMDB_ID]` command allows manual Admin fix of bad metadata matches or wrong covers.
  *Fallback control for when automation misidentifies a file.*

### 📢 Growth & Revenue
- [ ] **Broadcast Publisher**
  Auto-posts "New Release Cards" (Poster + Website Link) to the Public Update Channel.
  *Automates community engagement and drives traffic to the web player.*
- [ ] **Ad-Link Generator**
  Integrates URL Shortener APIs (e.g., GPlinks) to tokenize downloads for heavy files.
  *Subsidizes server costs by monetizing high-demand file transfers.*
- [ ] **Wishlist Notifier**
  Tracks user requests (`/request Movie`) and auto-DMs them when the file is added.
  *Boosts user retention by creating a personalized notification loop.*

---

## 🚜 3. The Worker Bot Features (Leech & Stream)

### 📥 Ingestion & Mirroring
- [ ] **Dual-Path Ingestion**
  Processes files via two simultaneous logic paths: (1) Raw Video for Streaming, (2) Zip Archive for Packs.
  *Utilizes unlimited Telegram storage to provide two distinct download products.*
- [ ] **Crowdsourced Ingestion Engine**
  Public mode accepting user links/torrents into a "Quarantine/Dump Channel" pending Admin approval.
  *Safety mechanism allowing users to build the library without polluting the verified database.*
- [ ] **Multi-Source Mirroring**
  Simultaneously uploads to Backup Hosts (Abyss.to / StreamWish) alongside Telegram.
  *Creates a RAID-1 redundancy layer; if Telegram bans a file, the site auto-switches to the backup.*
- [ ] **Smart Renaming Engine**
  Standardizes filenames (PTN Parser) to remove spam tags (`[x265]`, `www.site.com`) before upload.
  *Keeps the Private Library clean, professional, and brand-agnostic.*

### 🎞️ Processing Logic
- [ ] **Subtitle Stream Prober**
  Analyzes input files with `ffprobe` to map embedded subtitle tracks (Eng, Spa, Fre) for web extraction.
  *Enables "Soft Subtitle" support on the web player without burning in text.*
- [ ] **Auto-Screenshot Extraction**
  Extracts 3-5 frames during the download process and hosts them on a private channel.
  *Provides visual proof of quality for the website's "Preview" section.*
- [ ] **Proxy/Network Tunneller**
  Configurable SOCKS5 support for workers to bypass ISP blocks on specific trackers/sites.
  *Ensures leeching works even for region-locked torrents.*

### ⚖️ Load Management
- [ ] **Swarm Rotation Logic**
  Algorithm (in Redis) that distributes tasks to the "Least Busy" worker session.
  *Prevents Flood Wait bans by spreading 1,000 requests across 10 accounts.*
- [ ] **Queue System**
  Limits concurrent heavy tasks (e.g., Unzipping/Mirroring) to ~5 threads to protect VPS CPU.
  *Prioritizes system stability over download speed.*

---

## 💾 4. Data Strategy & Channels

### Channel Hierarchy
- **Channel A: Public Updates** (Clean, Links to Website, "Join Us").
- **Channel B: Private Logs** (Storage of verified Videos & Images).
- **Channel C: Dump/Quarantine** (User uploads pending review).
- **Channel D: Admin Alerts** (System Health, DMCA Reports, Login notifications).

### Safety Features
- **Hash-Based Blocking:** Ingestion phase calculates hash; if matches CSAM/Illegal list, drop immediately.
- **Identity Isolation:** Worker API Keys are separate from Manager keys. A ban on a worker does not affect the Manager's ability to chat with users.

---
