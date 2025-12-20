# 📂 Project Context: Frontend & User Interface
**Component:** The Visual Layer (`streamvault.net`)
**Role:** User Experience, Content Delivery, Traffic Obfuscation, and Revenue Generation.
**Architecture:** Server-Side Rendered (SSR) Next.js application self-hosted on Oracle (Docker), protected by Cloudflare.

---

## 🎨 1. Design System & UX Strategy

**Visual Identity: "Obsidian Glass"**
*   **Base Color:** Deep Midnight Void (`#050505` to `#0a0a0b`). No pure black.
*   **Glass Physics:** All overlay panels (Modals, Navbars, Sidebars) utilize `backdrop-filter: blur(16px)` with high-transparency white borders (`border-white/10`).
*   **Component Library:** **Aceternity UI** + **Tailwind CSS** + **Framer Motion**.
    *   *Hero Section:* Cinematic "Hero Parallax" or "Background Beams" effect.
    *   *Grid:* "Bento Grid" layout (mixed aspect ratios) rather than static rows.

**Page Structure:**
1.  **Homepage:** Hero Banner (Trending), Continue Watching Row (Local Storage/Auth Sync), Trending Movies (Grid), Latest Series (Grid).
2.  **Catalog/Search:** Instant-search (Debounced) dropdown + Advanced Filters (Genre, Year, Quality, Audio Lang).
3.  **Title Page (The Hub):** 
    *   Backdrop Glow effect (extracted from TMDB backdrop).
    *   Metadata: Title, Year, Rating (Pill format), Cast (Horizontal scroll).
    *   **The "Play" Station:** Primary Stream Button + "Quality Bucket" Selector + "Download Pack" Button.
4.  **Watch Page:** Distraction-free theatre mode.
5.  **User Dashboard:** Glass panel tracking History, Wishlist, and Ticket Status (Broken Links).

---

## 🏗️ 2. Core Features & Functional Logic

### A. The "Bucket" Modal (Quality Selection)
Instead of treating files as separate movies, the UI aggregates them under the TMDB ID.
*   **Trigger:** User clicks "Download/Play".
*   **Logic:**
    1.  Frontend fetches `GET /api/meta/{tmdb_id}`.
    2.  Modal renders specific options found in MongoDB:
        *   `[ 4K HDR | 14.2 GB | HEVC ]` (Disabled if network is slow/User is free).
        *   `[ 1080p  | 2.4 GB  | x264 ]` (Default).
        *   `[ 720p   | 800 MB  | HEVC ]` (Data Saver).
*   **Action:** Clicking an option routes the player/downloader to the specific `file_id` hash associated with that quality.

### B. Series Management (The Zip-Stream Logic)
*   **The Interface:** A tabbed view for Season 1, Season 2.
*   **Download Option:** "Download Season Pack" button.
    *   *Backend trigger:* Opens a direct stream to the **Pre-Zipped** Telegram file (Primary) OR triggers the **On-The-Fly Stream-Zip** pipe (Secondary/Fallback).
*   **Visual Feedback:** Shows a deterministic progress bar (using `Content-Length` header) even for on-the-fly zips.

### C. The Web Player (HTML5 + Extensions)
*   **Engine:** **ArtPlayer** or **Plyr.io**.
*   **Capabilities:**
    *   **Byte-Range Scrubbing:** Sending `Range: bytes=X-Y` headers to allow instant seeking.
    *   **Soft Subtitles:** Frontend fetches `/api/subs/{id}/{lang}` and injects `<track kind="captions">`. Does not burn-in text.
    *   **Audio Tracks:** For files with dual-audio, uses EME (Encrypted Media Extensions) logic or separate stream probing to allow switching audio tracks if supported by browser codec (Chromium).
*   **Fallback Logic (The "fail-safe"):**
    *   *Event:* Player receives `404` or `403` from Main Stream.
    *   *Reaction:* Auto-switches source to `Abyss.to` or `StreamWish` iframe link embedded via the backend backup field.
    *   *UX:* User sees a generic "Switching Source..." loader, not an error screen.

### D. Smart Search & Pagination
*   **Type-Ahead Search:** hits `/api/search?q=...` on every keystroke (300ms delay).
*   **Glass Dropdown:** Renders results *over* the current content.
*   **Pagination:** Infinite Scroll (Load More) for Catalog pages to save bandwidth vs "Page Number" buttons.

---

## 🔒 3. Security, Obfuscation & Auth

### A. The "White-Label" Image Proxy
*   **The Problem:** Loading images directly from `https://cdn4.telesco.pe/...` reveals the Telegram source to DevTools/Ad-Networks.
*   **The Solution:** All `<img>` tags point to our own API.
    *   `src="/api/image/proxy?id=telegram_file_id"`
*   **Backend Logic:** The Next.js API route fetches the image bytes from Telegram (via Manager Bot) and streams them to the browser with standard `Cache-Control` headers.
*   **Result:** Frontend looks like a standard hosted site; origin is hidden.

### B. "Magic Link" Authentication
*   **Trigger:** User sends `/login` to Telegram Bot.
*   **Payload:** Bot generates `jwt_token` containing `user_id` and `timestamp`.
*   **The Link:** `https://streamvault.net/auth/callback?token=...`
*   **Frontend Action:**
    1.  Validates JWT signature.
    2.  Sets an `HttpOnly` Secure Cookie.
    3.  Syncs local `localStorage` (History) with Database `history`.
*   **QR Login:** `/auth/qr` page displays a unique socket ID represented as a QR code. Bot scanning it triggers a server-side session approval.

### C. Ad-Block & Abuse Shield
*   **Soft Wall:** "Glass Toast" notification if Ad-Blocker prevents revenue scripts from loading. "Please allow ads to support server costs."
*   **Report System:** Under-player button opens a Modal:
    *   *Reasons:* Dead Link, Wrong Audio, Low Quality.
    *   *Action:* Submits `POST /api/report` -> Triggering the Manager Bot's "Medic" routine.

---

## 💰 4. Monetization Integration (Frontend Side)

### A. The "Pop-Under" Layer
*   **Hook:** `onClick` event on the Main "Play" button and the "Download" button.
*   **Logic:**
    1.  Check `sessionStorage` for "HasSeenAd".
    2.  **If False:** Prevent Play, trigger Ad Script (New Tab/Pop-under), Set "HasSeenAd = True".
    3.  **If True:** Allow Play immediately.

### B. Shortener Enforcement (Dynamic)
*   **Context:** Used for heavy files (4K Remuxes / Season Packs) to cover bandwidth "opportunity cost."
*   **UI Flow:**
    *   Button shows: "Verify to Download".
    *   User clicks -> Redirects to Shortener.
    *   Callback -> Sets temporary "Premium" cookie for 1 hour.
    *   Button changes to: "Download Now".

---

## 📃 5. Legal Compliance (Frontend)
*   **DMCA / Removal Page:**
    *   Standard form requesting Content Name and Proof.
    *   Submits directly to internal Admin queue, **NOT** public visibility.
*   **TOS / Privacy:** Explicitly states "StreamVault is an indexing engine; no files hosted on this domain." (The Standard Defense).

---
