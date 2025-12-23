# 📂 Phase 3 Blueprint: Future Roadmap & Expansions
**Filename:** `docs/v2_blueprint/context_05_future_roadmap.md`
**Role:** Specification for "Day 2" features that expand ecosystem accessibility beyond the browser (External Apps, TV Automation, RSS).
**Prerequisites:** Requires V2 (Oracle) or Lite (ReadVault) to be operational.

---

## 📚 1. OPDS Standard Support (ReadVault Expansion)
**Objective:** Allow users to read Manga/Books using native applications (Mihon, Tachiyomi, Moon+ Reader) instead of the browser.

### A. Architecture
The Backend (FastAPI) acts as an **OPDS Feed Server**. It translates MongoDB metadata into the **Atom XML** standard required by e-reader apps.

*   **Compatibility Target:** Mihon (Android), Paperback (iOS), Moon+ Reader.
*   **Security:** Uses "URL Token Authentication" (`/opds/{user_api_key}/catalog`) since generic readers struggle with custom Cookie logic.

### B. Endpoints Strategy
- [ ] **The Root Catalog**
  *   `GET /opds/{token}/catalog`
  *   Returns the top-level categories: "Latest Updates", "Popular Manga", "All Books", "Search".
- [ ] **Feed Generation (XML)**
  *   Logic to convert a MongoDB Book Entity into an Atom Entry `<entry>`.
  *   Must populate `<link type="image/jpeg" rel="http://opds-spec.org/image" href="...">` pointing to the ReadVault **Image Proxy**.
- [ ] **Search Bridge**
  *   `GET /opds/{token}/search?q={query}`
  *   Maps the Reader App's search bar query directly to the MongoDB Text Index.
- [ ] **Manifest & Pagination**
  *   Implementation of "Next Page" links in XML to support browsing libraries with 10,000+ titles.

### C. Chapter Serving
Unlike web browsers, OPDS readers need specific navigation for "Page 1 -> Page 2".
- [ ] **Page Streaming Logic:** The `<link rel="http://opds-spec.org/acquisition" ...>` must point to a dedicated zip stream or a standard **Image Manifest** endpoint that lists all page URLs in order.

---

## 🧩 2. Stremio Addon Server (StreamVault Expansion)
**Objective:** Allow users to watch movies/series on Smart TVs (Android TV/Firestick) via the popular Stremio app interface.

### A. The "Manifest"
- [ ] **Route:** `GET /stremio/manifest.json`
- [ ] **Role:** Advertises the "StreamVault" addon to the Stremio ecosystem.
- [ ] **Structure:** Defines which content types we provide (`movie`, `series`) and which catalogs we populate.

### B. Catalog & Meta Handling
- [ ] **Catalog Service:** `GET /stremio/catalog/{type}/{id}.json`
- [ ] **Meta Service:** Maps MongoDB data to the "Cinemeta" standard used by Stremio. Critical for making the "Episodes" tab appear correctly for TV Series.

### C. Stream Resolving (The Money Shot)
- [ ] **Stream Service:** `GET /stremio/stream/{type}/{id}.json`
- [ ] **Logic:**
    1.  User clicks "Play" on TV.
    2.  Stremio requests stream for `tmdb:12345`.
    3.  Manager Bot checks Database.
    4.  **Response:** Returns a JSON Object containing the **Direct Stream URL** (`streamvault.net/stream/{file_id}`).
    *   *Ad Integration Note:* Stremio makes injecting ads harder. This is a "Premium Only" feature.

---

## 🤖 3. Automated "Sonarr" Intelligence (RSS)
**Objective:** Remove the need for manual Leech commands. The bot "Self-Feeds" new content.

### A. The RSS Watcher
- [ ] **Feed Source:** Admin adds "Target Feeds" (e.g., Nyaa.si (Anime), MagnetDL (Movies), ShowRSS (Series)) to MongoDB.
- [ ] **Filter Logic:** Regex based filters (e.g., `/(One Piece|Demon Slayer).+1080p/i`).
- [ ] **Frequency:** Manager Bot checks feed every 15 minutes.

### B. The Auto-Grabber
- [ ] **Dupe Check:** Checks MongoDB to ensure we haven't already indexed this episode.
- [ ] **Ingestion Trigger:** Automatically dispatches the Magnet Link to a "Free" Worker in the swarm.
- [ ] **Notification:** Auto-posts "New Episode Landed" card to the Public Update Channel once processing is complete.

---

## 🗳️ 4. The Request Hub (Ombi Style)
**Objective:** A social "Upvote" system for filling content gaps.

### A. Frontend Interface
- [ ] **Discover Page:** "Popular/Trending" rail showing content *missing* from our DB (sourced via TMDB Discover API).
- [ ] **Action:** "Request This" button.

### B. Backend Logic
- [ ] **Request Queue:** MongoDB Collection `requests` tracks user demand.
- [ ] **Voting:** If User B requests a movie User A already asked for, `votes` count increments to 2.
- [ ] **Threshold Automation:** If `votes > 10`, automatically promote the Request to the **RSS Watcher** or **Leech Queue** to find it.

---

## 🗃️ 5. Collections & Reading Lists
**Objective:** Curated bundling of content for "Binge" consumption.

### A. Data Relation
- [ ] **Tagging System:** DB Support for a `collections` array (e.g., `["marvel_phase_1", "halloween_special"]`).
- [ ] **Admin Tools:** Simple UI to select 50 movies and assign them a Collection Tag.

### B. UI Experience
- [ ] **Carousel Row:** Dedicated Home Page rows for active collections ("Featured: The MCU Saga").
- [ ] **Smart Playlist:** When a user plays Movie 1 in a collection, the "Up Next" button automatically routes to Movie 2.

---

**End of Phase 3 Blueprint.**
This file represents the long-term scaling path once the Phase 2 (Oracle) system is stable.
