# 📂 Phase 2 Blueprint: Web Frontend & UX
**Filename:** `docs/v2_blueprint/context_02_frontend_ux.md`
**Role:** The Visual Layer (Next.js Website) hosted on Oracle (Docker).

---

## 🎨 1. Design System (Identity)

### Visual Style: "Obsidian Glass"
- [ ] **Color Palette**
  Deep Midnight Void (`#050505`) background. Text is off-white (`#ececec`). Accents use Cyberpunk Neon (Cyan/Pink) for high-contrast Call-to-Actions (CTAs).
- [ ] **Glassmorphism Logic (Desktop)**
  Heavily blurred translucent layers (`backdrop-filter: blur(24px)`) for Navbars, Sidebars, and Modals with 1px semi-transparent borders.
- [ ] **Mobile Performance Mode**
  CSS logic (`@media (max-width: 768px)`) that forces solid colors instead of heavy blurs on mobile devices to maintain 60FPS scrolling.
- [ ] **Motion Engine**
  **Framer Motion** handles layout transitions (Bento Grids expanding) and Page Transitions (Fade/Slide) to feel like a Native App.

### Page Structure
- [ ] **The "Hub" (Homepage)**
  Featured "Hero" Banner (Parallax), "Continue Watching" Rail (Local Storage), and Trending "Bento Grid" (Mixed aspect ratio cards).
- [ ] **Catalog & Search**
  Debounced "Instant Search" dropdown (glass overlay). Advanced filters (Genre, Quality, Audio Lang) with infinite scrolling.
- [ ] **Movie/Series Page**
  Full-width Backdrop Glow. Metadata Pills (Rating, Year). **Quality Preview Gallery** (FFmpeg Screenshots) carousel to prove video quality.
- [ ] **The Player**
  Distraction-free "Cinema Mode". Overlay controls for Audio/Subtitle switching.
- [ ] **User Dashboard**
  - **History Tab:** Synced Watch Progress.
  - **Wishlist Tab:** Status of requested movies.
  - **Referral Widget:** "Invite 3 friends to unlock 4K" progress bar + unique invite link copy button.

---

## 🏗️ 2. Functional Logic (The Engine)

### A. Authentication: "Public First" Model
- [ ] **Guest Mode (Default)**
  Auto-generates a `guest_id` via Cookie. Allowed to stream (capped at 720p speed). History saved to Browser LocalStorage.
- [ ] **Turnstile Gate**
  **Cloudflare Turnstile** widget integrated into the "Play" button for Guests to verify "Humanity" and stop scraping bots.
- [ ] **Account Linking (Magic Link)**
  - **Auth Logic:** User enters a code or scans QR to bind their Guest Session to a permanent ID via the Backend API.
  - **Magic Link Handler:** Page routes for `/auth/callback?token=...` that exchange the Bot-Generated JWT for a permanent Secure HttpOnly cookie.
  - **Privacy:** Pure token exchange. No Telegram widgets, no phone number sharing on the UI.

### B. Streaming & Downloads
- [ ] **The "Bucket" Modal**
  Download/Play button opens a Modal listing all DB versions (4K, 1080p, 720p). Shows file size and codec details.
- [ ] **Zip-Stream Trigger**
  "Download Season Pack" button logic. Checks size -> If >5GB, triggers Shortener flow -> Opens backend Zip Engine stream.
- [ ] **Adaptive Player (Plyr/ArtPlayer)**
  Configured for HTTP 206 Scrubbing. Dynamic injection of `<track>` tags for Soft Subtitles (`/api/subs/...`).
- [ ] **Failover Logic**
  Javascript event listener on `<video error>`: if Primary Stream (Telegram) fails, auto-swaps `src` to the Backup Mirror (Abyss.to).

### C. Series & Ongoing Content
- [ ] **Status Indicators**
  Visual tags on posters: "🟢 New Episode" (Ongoing) or "🔴 Complete" (Ended).
- [ ] **Season Tabs**
  AJAX-loaded episode lists separated by Season Tabs to handle long-running shows (e.g., One Piece) without DOM lag.

---

## 🔒 3. Obfuscation & Security

### A. Privacy Layer
- [ ] **White-Label Image Proxy**
  Renders all TMDB/Telegram images via `/api/image/{id}` route. Browser sees *StreamVault* URL, not *Telescope* URL.
- [ ] **Header Stripping**
  Removes `Server: Next.js` and other identifying headers.

### B. User Safety & Error States
- [ ] **"Broken Link" Modal**
  Context-aware report button. Options: "Wrong Audio", "Buffering", "Dead Link". Submits to Admin Bot.
- [ ] **DMCA Compliance Page**
  Formal "Safe Harbor" text page with a web form for rights holders.
- [ ] **Maintenance Mode (503)**
  A dedicated static "Glass" splash screen that activates if the API is unreachable (during Docker Restarts), preventing ugly browser error pages.

---

## 💰 4. Monetization Strategy

### A. The Ad Stack
- [ ] **Ad-Block "Soft Wall"**
  Detects ad-script failure. Displays non-intrusive Glass Toast: "Please allow ads to help us pay server costs."
- [ ] **Smart Pop-Unders**
  Injects 1 Pop-under script click listener on the first "Interaction" (Play/Download) per session.
- [ ] **Shortener Gateway (Ad-Link)**
  Logic applied to "Heavy Downloads". Modal: "Verify to Unlock" -> Redirects to Shortener -> Callback sets 1-hour cookie.

---

## 🔍 5. Organic Growth (SEO)

- [ ] **Automated Sitemaps**
  Server-side script generating `sitemap.xml` daily based on MongoDB "Available" movies. Pings Google Console.
- [ ] **JSON-LD Schema**
  Injects "Movie" and "TVSeries" structured data into HTML `<head>` for rich search results.
- [ ] **Social Meta Tags**
  Dynamic OpenGraph (OG) images generation so shared links show the Movie Poster.

---
