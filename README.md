# 🎥 Shadow Streamer (The Zero-Budget Media Ecosystem) 

> **A Unified Telegram Bot Architecture for High-Speed Media Streaming inside and outside Telegram.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Hugging%20Face-Docker-orange?style=for-the-badge&logo=huggingface)](https://huggingface.co/spaces)
[![Database](https://img.shields.io/badge/MongoDB-Atlas-green?style=for-the-badge&logo=mongodb)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/License-MIT-red?style=for-the-badge)](https://opensource.org/licenses/MIT)

## 📖 Overview

**Shadow Streamer** is an advanced engineering solution designed to turn a Telegram Channel into a functional Media Server (like a personal Netflix) with a **$0.00 operational cost**. 

It overcomes the limitations of free cloud tiers by splitting workloads into specific micro-functions. It enables:
1.  **Internal Streaming:** Watching videos/music in Telegram Group Voice Chats.
2.  **External Streaming:** Generating high-speed HTTP links for Telegram files to play in VLC, Chrome, or Smart TVs without downloading the file locally.
3.  **Indexing:** A system to catalog media in a private "Log Channel" for permanent access.

---

### 1. The Technology Stack
We will use one robust server (Hugging Face) acting as the brain, storage, and streamer, utilizing **asynchronous multi-clienting**.

*   **Hosting:** **Hugging Face Spaces** (Docker SDK).
    *   *Specs:* 2 vCPU, 16GB RAM (Free).
    *   *Why:* The only free provider that allows `FFmpeg` installation (required for transcoding) and has enough RAM to buffer video.
*   **Database:** **MongoDB Atlas** (Shared Free Tier).
    *   *Purpose:* Stores Session Strings (so you don't re-login every restart) and Cookies (for YouTube).
*   **Internal Engine (VC):** `PyTgCalls` + `Pyrogram`.
    *   *Role:* Acts as a virtual user to stream into Group Calls.
*   **External Engine (Link):** `FastAPI` + `Uvicorn`.
    *   *Role:* Runs a lightweight web server inside the bot to handle HTTP requests.
*   **Uptime Keeper:** **Cron-Job.org**.
    *   *Role:* Pings the bot every 5 mins to prevent Hugging Face from sleeping.

---

## 🏗️ Architecture: "The Triad System"
*To ensure zero latency and preventing buffering on free servers, the system operates on a Distributed Microservice architecture:*

***📜 Evolution & Changelogs***

*Below is the complete history of our architectural decisions, prompts, and deployment strategies. Click on a version to expand the details:*

<details>
<summary><b>🔻 Version v.01: The "Triad" Architecture & Initial $0 Strategy</b></summary>
<br>

Here is the executive summary, the deployment checklist, and the Master System Prompt you can use to generate the exact code for this "Distributed $0" architecture.

### Executive Summary: The "Triad" Architecture
We are bypassing paid hosting by splitting the bot's functions into three free specialized services:
1.  **Hugging Face Spaces (Docker):** Acts as the **"Brain."** It handles heavy tasks (FFmpeg transcoding) to stream video inside Telegram Voice Chats. It also hosts the `FastAPI` server for external streaming (because Vercel has timeout limits for long movie streams, HF is better suited for the heavy lifting here).
2.  **MongoDB Atlas:** Acts as the **"Memory."** It stores user session strings and settings so the ephemeral servers don't lose data on restart.
3.  **Cron-Job.org:** Acts as the **"Heartbeat."** It pings the Hugging Face server every 5 minutes to prevent it from sleeping, ensuring 24/7 uptime.

---

### The Master System Prompt

Copy and paste the text below into a high-level coding AI (like ChatGPT-o1, Claude 3.5 Sonnet, or DeepSeek Coder) to generate the files.

***

**System Prompt:**

```text
You are an expert Python Backend Engineer and DevOps specialist. I need you to build a sophisticated Telegram Bot with zero budget that functions as both a VC Player (Voice/Video Chat) and a Direct Link Generator (External HTTP Stream).

**Architecture Requirements:**
1. **Platform:** The bot must run on **Hugging Face Spaces (Docker SDK)**.
2. **Database:** Use **MongoDB** (motor/pymongo) for storing session data and ensuring state persistence across restarts.
3. **Core Library:** Use `Pyrogram` (async) and `PyTgCalls` (for VC streaming).
4. **Web Framework:** Use `FastAPI` (running on port 7860) within the same container to serve the HTTP video streams and perform health checks.

**Specific Technical Constraints (Crucial):**
1. **No Buffering (Byte-Range Support):** The HTTP Streamer function must NOT download the file to the server disk. It must use Pyrogram's `stream_media` (or `ByteStream` method) to pipe the file chunks from Telegram servers directly to the User's browser request using `yield` and standard HTTP Byte Range headers (206 Partial Content). This allows the user to seek/skip video without crashing the server.
2. **Concurrent Processes:** You must use `asyncio` to run the Telegram Bot client (`idle()`) and the FastAPI Uvicorn server simultaneously in the same `main.py` entry point.
3. **FFmpeg Handling:** The VC player part needs `FFmpeg` installed via the Dockerfile. It must be configured with presets `-tune zerolatency` and `-preset ultrafast` to run on free tier hardware without lag.
4. **Link Generation:** The bot should generate links in the format: `https://[hf-space-url]/stream/[file_id]`.

**Required Output:**
Please provide the full code structure including:
1. `Dockerfile` (Must allow permission for chmod, install ffmpeg, python, and pip).
2. `requirements.txt` (Include pyrogram, tgcrypto, pytgcalls, fastapi, uvicorn, motor, uvloop).
3. `env.py` (For loading config variables).
4. `clients.py` (Logic to initialize the Userbot for streaming and the Bot for interactions).
5. `server.py` (The FastAPI logic to handle Byte-Range video streaming requests).
6. `main.py` (The entry point connecting the Bot + Server).

*build everything but, I don't have a User Session String yet. Create the FileStream/HTTP part of the bot using only the Bot Token. Leave a placeholder for the PyTgCalls module to be added later*

The code must be production-ready, error-handled, and optimized for low memory usage.
```
</details>

<details>
<summary><b>🔻 Version v.02: Research & Code Refinements (GitHub Repo Analysis)</b></summary>
<br>

I have analyzed the four repositories you provided. They are the standard-bearers for Telegram Python bot development. Seeing them confirms you have done excellent research and helps me refine the engineering requirements exactly.

Here is my breakdown of **why you picked them** and **what we must "steal" (borrow)** from each to make your Custom Bot perfect.

---

### Part 1: Analysis of Our Sources

#### 1. **[VCPlayerBot (SubinPS)](https://github.com/subinps/VCPlayerBot) & [YukkiMusicBot (TeamYukki)](https://github.com/TeamYukki/YukkiMusicBot)**
*   **What they do:** These cover the **"Inside Telegram"** (Group Call) part of your requirement.
*   **The Difference:**
    *   **VCPlayerBot** is older and more "raw." It focuses heavily on video capability but the code structure is less modular.
    *   **Yukki** is the modern standard. It is "pretty," uses modules effectively, and supports extensive music platforms.
*   **What we take for your project:**
    *   We reject *Yukki's* complexity. It has too many features (lyrics, sudo users, extensive database checks) that will bloat your Hugging Face instance.
    *   We take *VCPlayerBot's* **FFmpeg implementation**. It handles video resizing better than Yukki (which often forces specific resolutions that lag on free servers).
    *   **Crucial Lesson:** Yukki proves that **YouTube requires Cookies**. Standard `yt-dlp` gets blocked by YouTube on data center IPs (like Hugging Face/Amazon). **Modification to Plan:** Your bot must support uploading a `cookies.txt` file, or YouTube links will fail after 3 days.

#### 2. **[TG-FileStreamBot (EverythingSuckz)](https://github.com/EverythingSuckz/TG-FileStreamBot)**
*   **What it does:** This is the gold standard for **"Outside Telegram"** (HTTP Links).
*   **The Genius Part:** It utilizes `Multi-Client` support (balancing load across several bot tokens) and creates a robust `StreamResponse` class.
*   **What we take:**
    *   We **MUST** copy its `stream_routes.py` logic. This code specifically handles "Range Headers" (The HTTP 206 status). Without this specific logic, iPhones (Safari) and VLC won't play your links.
    *   **Correction:** We should strip out the "Web UI" parts of this bot (the fancy HTML pages it generates) and keep only the API link generator to save RAM.

#### 3. **[TgindexPro (rayanfer32)](https://github.com/rayanfer32/TgindexPro)**
*   **What it does:** Creates a permanent web catalog of files.
*   **Verdict for us:** **Discard.**
    *   Why? This bot is designed to Index *Channels*, not stream *On-Demand*. It uses a different philosophy (Web serving) that is too heavy for a Unified Bot. It tries to replace Google Drive. We just want to replace Netflix.

---

### Part 1: Modifications to our Architecture Plan

Based on these repositories, here are the **3 Critical Changes** to the previous plan to ensure stability and "Peak Intelligence":

#### Modification A: The "Cookies" Issue (Crucial)
None of our previous prompts mentioned YouTube Blocking. Since *YukkiMusic* struggles with this constantly, we must address it.
*   **Change:** The logic must include a mechanism to inspect `yt-dlp` options.
*   **Implementation:** We need a variable `COOKIE_FILE_URL` in our env. You upload a `cookies.txt` (exported from your browser) to a secret gist or pastebin, and the bot loads it on boot. **Without this, YouTube streaming will not work.**

#### Modification B: Session Isolation (The "FloodWait" Fix)
*TG-FileStreamBot* teaches us that if you use the *same account* to Stream HTTP bytes (Upload) and Play VC Video (Download) simultaneously, Telegram will slap you with a "FloodWait" error (Ban for 2000 seconds).
*   **Change:** Our System Prompt must strictly request **TWO** Session Strings:
    1.  `USER_SESSION_STRING`: Exclusively for the **VC Player** (PyTgCalls).
    2.  `BOT_TOKEN` / `STREAMER_SESSION`: Exclusively for **Generating Links** and fetching bytes for the web player.
    *   *Note: Using a Bot Token for the streaming part is actually faster and safer than a User Session.*

#### Modification C: RAM Optimization (The "Kill Switch")
Hugging Face (free) gives 16GB RAM, but it kills processes that spike CPU too fast.
*   *VCPlayerBot* uses "MPV" which is lighter.
*   **Change:** In our `Dockerfile`, we will strictly specify `ffmpeg` but limit the **concurrent streams** to 2. We cannot allow 50 people to stream via HTTP while a video call is active. The code must have a `Semaphore` lock to queue users if the load is too high.

---

### Part 2: The Updated System Prompt

This prompt incorporates the logic from *FileStreamBot* (for range handling) and *VCPlayer* (for FFmpeg) while avoiding the bloat of *Yukki*.

**Copy this to the AI Coder:**

```text
You are an expert Python Backend Engineer specialized in Telegram MTProto. I need to build a single Unified Telegram Bot that combines the functionality of 'YukkiMusicBot' (VC Streaming) and 'TG-FileStreamBot' (External HTTP Streaming).

**Project Constraints (The "Zero Budget" Stack):**
1. **Host:** Hugging Face Spaces (Docker SDK) - Free Tier.
2. **Persistence:** MongoDB Atlas (Free Tier) - Store active playlist and authorized users.
3. **Language:** Python 3.10+.

**Core Libraries Required:**
- `Pyrogram` (Client)
- `PyTgCalls` (VoIP Integration - **Must use the latest version**)
- `FastAPI` + `Uvicorn` (Web Server for the HTTP Stream)
- `yt-dlp` (For YouTube link extraction)

**The Engineering Architecture (Strict Requirements):**
1. **The "Dual Core" Approach:**
   - **Worker 1 (Voice Chat):** Uses `USER_SESSION_STRING`. Joins Group Calls. Uses `ffmpeg` to transcode video input to `raw` format for PyTgCalls. *CRITICAL: Include support for a 'cookies.txt' file loading for yt-dlp to bypass YouTube limits.*
   - **Worker 2 (HTTP Streamer):** Uses `BOT_TOKEN` (via Pyrogram). It acts as a bridge. It receives a FileID -> Get file chunks from TG servers -> Yield chunks to FastAPI Response.
   - **The Conflict:** These two must run in the SAME `asyncio` loop without blocking each other.

2. **The "FileStream" Logic (Borrowed from EverythingSuckz):**
   - The FastAPI route `/stream/{file_id}` MUST support HTTP Range Headers (`206 Partial Content`). 
   - Code must calculate `Content-Range` based on the requested byte offset so video players (VLC, MX Player) can seek/skip forward without downloading the whole file.

3. **RAM Safety:**
   - Implement a semaphore to limit max concurrent HTTP streams to 3.
   - Implement a semaphore to allow only 1 active VC stream at a time.

**Deliverables:**
Provide the complete file structure code for:
1. `Dockerfile` (Ubuntu based, installing ffmpeg, python3, and generic system libs).
2. `requirements.txt`.
3. `env.py` (Config loader).
4. `bot.py` (The entry point managing the asyncio loop for both FastAPI and PyTgCalls).
5. `plugins/stream.py` (The logic for generating the direct HTTP link).
6. `plugins/vc_player.py` (The logic for handling user commands /play and joining VCs).

*build everything but, I don't have a User Session String yet. Create the FileStream/HTTP part of the bot using only the Bot Token. Leave a placeholder for the PyTgCalls module to be added later*

**Attention:** Ensure the code handles `FloodWait` exceptions gracefully, must be modular and production ready.
```

**Next Step:** You can run this prompt now. It will produce the exact hybrid bot you need. Once the code is generated, we will move to the deployment checklist.
</details>

<details>
<summary><b>🔻 Version v.03: The Combined "Master Design" (Merging v.01 + v.02)</b></summary>
<br>

This is your final **Master Design Document**. It consolidates our Distributed Architecture theory, the Repo Analysis (`TG-FileStreamBot` + `VCPlayerBot`), and the "Zero Budget" execution strategy into one unified guide.

You can now delete all previous context. This is the only roadmap you need.

---

# Project: "Shadow Streamer" (The Unified Bot)
**Goal:** A single Telegram bot that joins Voice Chats to stream video (Internal) and generates Direct HTTP Links for browsers/VLC (External).
**Budget:** $0.00 / month.
**Architecture Type:** Monolithic Docker Container via Hugging Face.

---

### 1. The Logic Architecture
We are merging the "Best Parts" of the repositories you shared:

1.  **From TG-FileStreamBot:**
    *   We steal the **HTTP 206 (Partial Content)** logic.
    *   The bot will NOT download the file to the server. It opens a download stream from Telegram and *immediately* pipes the bytes to the Web Request.
    *   *Benefit:* 0 latency, 0 storage usage, infinite seeking support (Skip forward/backward).
2.  **From VCPlayer/Yukki:**
    *   We steal the **FFmpeg Wrappers**.
    *   We strip out the "downloading" feature. The bot will stream directly from the YouTube URL into `FFmpeg` and then into `PyTgCalls`.

---

### 2. The "One-Shot" System Prompt
Copy and paste this exact text into a coding AI (ChatGPT-4o / Claude 3.5 / DeepSeek) to generate your codebase.

```text
You are a Lead Python Backend Architect. I need a robust, unified Telegram Bot that performs two distinct streaming functions on a $0 budget.

**Environment & Stack:**
- **Platform:** Hugging Face Spaces (Docker SDK - Linux/Ubuntu).
- **Language:** Python 3.10+.
- **Database:** MongoDB (Motor driver).
- **Libs:** Pyrogram, PyTgCalls, FastAPI, Uvicorn, Yt-dlp.

**Architecture - The "Dual Engine" System:**
The code must run a single asyncio loop in `main.py` that starts TWO concurrent workers:

1. **The Web Streamer (The "Bridge"):**
   - Modeled after 'TG-FileStreamBot'.
   - Runs `Uvicorn` on port 7860.
   - Endpoint: `/stream/{message_id}`.
   - **Critical Logic:** It must support **Byte-Range Requests (HTTP 206)**. It should NOT download the file to disk. It must use Pyrogram's `client.stream_media()` generator to yield chunks directly to the HTTP response.
   - Use the Bot Token client for this worker (higher throughput).

2. **The VC Player (The "Brain"):**
   - Modeled after 'YukkiMusicBot' / 'VCPlayer'.
   - Joins Group Voice Chats to play Video/Audio.
   - **Critical Logic:** Use `yt-dlp` to extract links.
   - **Feature:** Must support loading a `cookies.txt` file (via a COOKIE_LINK env variable) to bypass YouTube server-side blocking.
   - Use the User String Session client for this worker (required for VCs).
   - Use FFmpeg parameters: `-preset ultrafast -tune zerolatency` to save CPU.

**Safety & Constraints:**
- Implement a **Semaphore** to limit concurrent Web Streams to 3 (to protect RAM).
- Implement a **Lock** so only 1 VC stream happens at a time.
- Handle `FloodWait` exceptions automatically.

**Deliverables (File Structure):**
1. `Dockerfile`: Must accept CHMOD permissions, install ffmpeg, and python dependencies.
2. `requirements.txt`: Standard deps + `pynacl` (for audio).
3. `config.py`: Loads `API_ID`, `API_HASH`, `BOT_TOKEN`, `SESSION_STRING`, `MONGO_URL`, `COOKIE_LINK`.
4. `server/routes.py`: The FastAPI implementation for Range-based streaming.
5. `bot/vc_core.py`: The PyTgCalls wrapper + FFMPEG logic.
6. `main.py`: The entry point utilizing `asyncio.gather` to run the Bot and the Server.

*build everything but, I don't have a User Session String yet. Create the FileStream/HTTP part of the bot using only the Bot Token. Leave a placeholder for the PyTgCalls module to be added later*

Code must be production-ready and modular.
```

---

### 3. Deployment Guide (How to Build)

1.  **Hugging Face Setup:**
    *   Create Space -> Select **Docker** -> **Blank**.
    *   Go to **Settings** -> **Secrets**.
    *   Add your keys: `API_ID`, `BOT_TOKEN`, `SESSION_STRING` (User), `MONGO_URL`, and `COOKIE_LINK` (Raw URL to your text file).

2.  **The Files:**
    *   Create the files generated by the AI Prompt above (`main.py`, `Dockerfile`, etc.).
    *   Commit them to the Space.

3.  **The Dockerfile Nuance:**
    *   *Important:* Hugging Face runs as a non-root user (user 1000). Ensure the AI adds this line to your Dockerfile to avoid permission errors:
        ```dockerfile
        RUN chown -R 1000:1000 /app
        USER 1000
        ```

4.  **Launch & Ping:**
    *   Once built, you will see "Running".
    *   You will see a small link: `Embed this space`. That is your App URL (e.g., `https://huggingface.co/spaces/user/bot`).
    *   Copy the Direct URL (`https://user-bot.hf.space`) and paste it into **Cron-Job.org** (Every 5 minutes).

### 6. Usage (How it will work)

*   **To Stream Externally:**
    *   Forward file to bot.
    *   Bot replies: `https://user-bot.hf.space/stream/1234`
    *   Paste into VLC. Zero latency streaming starts.
*   **To Stream Internally (VC):**
    *   User types `/play [Song Name/Link]`.
    *   Bot joins VC and plays using the User Account.
    *   *Thanks to Hugging Face*, the IP is fast enough to support 720p Video.
</details>

<details>
<summary><b>🔻 Version v.04: Final Integration (Log Channels, Renaming & Web Frontend)</b></summary>
<br>

This elevates the project from a simple "Tool" to a full "Platform." This is absolutely achievable on the $0 stack, but it requires precise architectural decisions to avoid server crashes.

Here is the breakdown of these new requirements and how we integrate them into the **Shadow Streamer**.

---

### 1. The "Netflix Style" Website (Frontend)
**Can we do it?** Yes.
**Cost:** $0 (Hosted on **Vercel** or **Netlify**).

**How it works structurally:**
You cannot host the website *on* Hugging Face (it's not optimized for serving React/HTML UI). You will build a separate "Frontend" that talks to your "Backend" (Hugging Face).

*   **The Backend (Your HF Bot):** We enable `CORS` in FastAPI. It provides an API endpoint: `/api/files` (returns list of movies from MongoDB) and `/stream/{id}` (video).
*   **The Frontend (Vercel):** A nice looking interface (HTML/Next.js). It fetches the JSON list from the bot and creates a movie grid. When clicked, it opens a video player utilizing the shadow stream link.

**Benefits:**
*   **Monetization:** You can place Google AdSense or Pop-under ads on this website.
*   **UX:** Much better than scrolling through a Telegram chat.

---

### 2. The "Dump & Log" System (Index Channel)
**Can we do it?** Yes. This is standard "File Store" bot behavior.

**The Workflow:**
1.  **User Actions:** User sends a file or a YouTube link.
2.  **The Rename Logic:**
    *   *Bot asks:* "Send the new name for this file."
    *   *User sends:* "Avengers_Endgame_720p.mp4".
3.  **The Backend Action:**
    *   **If File:** Bot downloads the file header (small), modifies the filename attribute, and **forwards** it to your private **Log Channel**.
    *   **If Link:** Bot uses `yt-dlp` to download the video to the Hugging Face disk, then **uploads** it to the Log Channel as a file, then deletes it from the disk to free space.
4.  **The Indexing:**
    *   Once sent to the Log Channel, Telegram assigns a new `Message_ID`.
    *   The bot saves this `(Message_ID, File_Name, Chat_ID)` to MongoDB.
5.  **Result:** The user (or the website) can now request this file forever. It never expires because it's saved in your private channel.

**The Critical Constraint (The Danger Zone):**
Downloading a YouTube link and *uploading* it to Telegram is extremely heavy.
*   **Constraint:** Hugging Face Free Tier has decent internet, but **Upload Speeds** to Telegram servers are notoriously slow for bots.
*   **Limit:** You must code a "Hard Limit" (e.g., Max 500MB or 30 mins video) for *Links-to-File* conversion. If you try to upload a 2GB movie, the process will time out or crash your bot.
*   *Solution:* Use the bot mostly for forwarding existing Telegram files (Instant) and small YouTube clips (fast).

---

### Revised "Master Prompt" (Integrates Website API + Log Channel)

This is the updated prompt. Use this to generate the *Complete V2* system.

```text
You are a Lead Python Full-Stack Architect. Update the previous "Shadow Streamer" plan to V2 features.

**Core Changes:**
1.  **Storage Logic (The Dump Channel):**
    - Define a variable `LOG_CHANNEL_ID`.
    - When a user sends a video, specific logic:
      - Ask user for a custom filename (Rename).
      - **Forward** the video to the `LOG_CHANNEL_ID`.
      - Store the *Log Channel's* `Message_ID`, `File_Unique_ID`, and `Custom Name` into MongoDB.
    - If user sends a LINK (Youtube/Direct):
      - Use `yt-dlp` to download locally.
      - **Upload** to `LOG_CHANNEL_ID` (limit file size to 500MB to prevent timeout).
      - Delete local file.
      - Save metadata to MongoDB.

2.  **Web API (Frontend Connection):**
    - The FastAPI server must now enable `CORSMiddleware` (Allow All Origins).
    - Create a new route `@app.get("/api/catalog")`:
      - Fetch all indexed files from MongoDB (Name + Stream_Link).
      - Return JSON list so a Vercel frontend can display them.

3.  **Update Config:**
    - Add `LOG_CHANNEL_ID` and `OWNER_ID` to config.

**The Tech Stack Remains:**
- Pyrogram (Bot), PyTgCalls (VC), FastAPI (Stream/API), MongoDB.
- Hosting: Hugging Face Spaces (Docker).

**Deliverables Update:**
- Update `server/routes.py` to include the JSON Catalog endpoint.
- Update `bot/core.py` to handle the Rename/Forward/Upload logic.
- **Bonus:** Write a simple `index.html` file (with fetch logic) that I can upload to Netlify to test the video catalog UI.

*build everything but, I don't have a User Session String yet. Create the FileStream/HTTP part of the bot using only the Bot Token. Leave a placeholder for the PyTgCalls module to be added later*.

Code must be strictly asynchronous to prevent blocking the stream while uploading.
```

---

### Summary of the "Full Ecosystem"

By implementing this, you effectively have two products:

1.  **Shadow Streamer Bot:**
    *   The "Engine" (Hosted on Hugging Face).
    *   Manages downloading, transcoding to Voice Chat, and streaming to HTTP.
    *   Manages the "Log Channel" (The storage).

2.  **Shadow Web (Client):**
    *   A simple HTML/JS site (Hosted on Vercel).
    *   Connects to Shadow Streamer Bot URL.
    *   Shows a Netflix-like grid of your Log Channel.
    *   Plays video directly in the browser (Video flows from Telegram -> Bot -> Browser).

**Addressing your User Privacy/Earnings Question with this setup:**
*   **Earning:** Put "PopAds" or "Adsterra" codes on the **index.html** page. You will earn money every time someone clicks to watch a movie on your site.
*   **Privacy:** Since you are now "Indexing" files into a Log Channel, ensure that Log Channel is **Private**. Only the Bot and You should be in it. The API exposes the *links* to the public, which is fine (that's the purpose), but no one can join the channel and mass-report your files.
</details>

---

### The "Zero-Dollar" Checklist

**Phase 1: Accounts & Credentials (The Prep)**
- [ ] Create a **Telegram API ID & Hash** (via `my.telegram.org`).
- [ ] Create a **Telegram Bot Token** (via `@BotFather`).
- [ ] Create a **MongoDB Atlas** account (Free Shared Tier).
- [ ] Create a cluster, whitelist IP `0.0.0.0/0`, and copy the Connection String (`mongodb+srv://...`).
- [ ] Create a **Hugging Face** account.
- [ ] Generate a "Write" Access Token in settings.

**Phase 2: The Core Deployment (Hugging Face)**
- [ ] Create a new **Space** on Hugging Face.
- [ ] Select **Docker** (not standard Python) and choose the "Blank" template.
- [ ] **Secrets:** In Space Settings -> "Repository Secrets", add:
  - `API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_DB_URL`, `SESSION_STRING`.
- [ ] **Files:** You will need to upload `Dockerfile`, `requirements.txt`, and `main.py` (The prompt below generates these).

**Phase 3: The Keep-Alive (Uptime)**
- [ ] Wait for the HF Space to build and run. It will provide a URL (e.g., `https://username-space.hf.space`).
- [ ] Go to **Cron-Job.org**, create a job that sends a `GET` request to that URL every 5 minutes

---

## 🛠️ Deployment Checklist

### Step 1: The Code
1.  Use the prompt above to generate the file structure.
2.  Save files: `main.py`, `Dockerfile`, `requirements.txt`, etc.

### Step 2: Hosting (Hugging Face)
1.  Create a New Space -> **Docker** -> **Blank Template**.
2.  Navigate to **Settings** -> **Secrets (Environment Variables)**.
3.  Add the following:
    - `API_ID`: Your ID.
    - `API_HASH`: Your Hash.
    - `BOT_TOKEN`: From BotFather.
    - `SESSION_STRING`: The Userbot Pyrogram String.
    - `MONGO_URL`: Database connection.
    - `LOG_CHANNEL_ID`: ID of your storage channel (e.g. -100xxxx).
    - `COOKIE_LINK`: Raw URL to your exported cookies text file.

### Step 3: Keep-Alive
1.  Once built, your Space will have a URL (e.g., `https://shadow-stream.hf.space`).
2.  Go to **[Cron-Job.org](https://cron-job.org)**.
3.  Create a job to GET request your Space URL every **5 minutes**.

---

## ⚠️ The Operational Ecosystem

To ensure stability, we do **not** use the Shadow Streamer for heavy downloading.

**1. The Mirror Bot (Bot #1):** 
- Host a standard "Aria2/WZML Mirror Bot" on a *separate* Free HF Space or Google Colab.
- Use this bot to download Torrents/Links and upload them to your **Log Channel**.

**2. The Shadow Streamer (Bot #2 - This Repo):**
- It only "Reads" from the Log Channel.
- It provides the Playback features (VC & HTTP).

*Separating these prevents the heavy download process from crashing your active video stream.*

---


## ❓ Frequently Asked Questions (FAQ)

### 🛑 Risk & Safety

**Q1: What are the risks regarding User Accounts & Privacy?**
> **A:** Using a `Pyrogram` String Session creates a direct backdoor to the account. If the host environment variables are leaked, the account can be compromised. Furthermore, Telegram's Anti-Spam systems may flag accounts that stream audio 24/7.
> *Recommendation:* **NEVER** use your primary personal Telegram account. Create a "Burner" (Secondary) account to act as the Userbot.

**Q2: How do I create a "Burner Account" if I don't have a spare SIM?**
> **A:** You have three options:
> 1.  **Family Method (Free):** Use a phone number of a family member who doesn't use Telegram (enable 2FA immediately).
> 2.  **VoIP Apps (Hit or Miss):** Apps like TextNow or 2ndLine sometimes work, though Telegram often blocks them.
> 3.  **SMS Services (Cheap):** Use services like 5sim or SMS-Activate (~$0.20) to get a temporary number for verification.

### 💰 Scalability & Monetization

**Q3: Can I earn money with this project?**
> **A:** Yes, but not by charging for the bot directly (which risks bans).
> *Strategy:* Deploy the **Web Frontend (Version v.04)**. Users browse your library on a website. You can place ad networks (AdSense, Adsterra, PopAds) on that website.
> *Capacity:* The "External Link" feature can handle roughly 20-50 simultaneous users on free Vercel/HF tiers.

**Q4: Can we create a "Netflix-style" website for better UX?**
> **A:** Yes. Since we updated the architecture to include a REST API (`/api/catalog`), you can host a static React/HTML site on **Vercel**. It fetches the movie list from the bot's database and plays the stream in the browser using the bot's direct link.

### ⚙️ Technical Capabilities

**Q5: What is the Video and Audio Quality?**
> **A:**
> *   **External Stream (VLC/Browser):** **Original Source Quality.** If the Telegram file is 4K, the stream is 4K. The bot acts as a transparent tunnel.
> *   **Internal Stream (Voice Chat):** **Max 720p / 30fps.** Telegram aggressively compresses video in Group Calls.

**Q6: Does it support Pause, Seek, and Skip?**
> **A:** Yes.
> *   **External:** Our code implements `HTTP 206 Partial Content`. This allows video players to request specific byte ranges, meaning you can jump instantly to 1:45:00 without downloading the start of the movie.
> *   **Internal:** Supported via chat commands (`/pause`, `/resume`, `/seek 30`).

**Q7: How does "Storage" work? Is the file saved on the server?**
> **A:** No. The bot has limited disk space. It uses a **Log Channel (Dump)**.
> When a user sends a file, the bot forwards it to a private Telegram Channel and saves that `Message_ID` in MongoDB. The "File" lives on Telegram's servers forever; the bot just remembers where it is.

**Q8: Does it handle both Direct Links (YouTube) and Files?**
> **A:**
> *   **For Voice Chats:** Yes, it supports YouTube/Twitch/Spotify links and Telegram files.
> *   **For External Links:** It is optimized for Telegram Files. Streaming YouTube -> Bot -> VLC is inefficient; use the bot to convert Telegram Files into Streamable Links.

### 🛠️ Operational Architecture

**Q9: Do we need a separate "Mirror/Leech" bot?**
> **A:** **YES.** Do not try to download massive files on the Streamer Bot.
> *   **Reason:** Transcoding video requires high CPU. If you try to download a 2GB Torrent on the same server, the CPU will spike, causing the active stream to buffer or crash. Host a separate Mirror Bot on a different free space.

**Q10: Why do we need the "Heartbeat" (Cron Job)?**
> **A:** Hugging Face Spaces (Free Tier) will "sleep" (shut down) after 48 hours of inactivity. The Cron Job sends a web request every 5 minutes to trick the server into thinking it is constantly being used, ensuring 24/7 uptime.
