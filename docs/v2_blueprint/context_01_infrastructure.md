# 📂 Project Context: Infrastructure & Backend
**Component:** The Engine Room (Oracle VPS + Docker Swarm)
**Role:** Reliability, Storage, Caching, and Microservice Orchestration.

---

## 🏛️ 1. High-Level Architecture (The Bird's Eye View)

We are running a **Single-Node Docker Microservices Architecture** (orchestrated via Docker Compose) on a dedicated Bare Metal Server.

*   **The Philosophy:** "Host nothing, Index everything, Cache the viral."
*   **The Hardware:** Oracle Cloud Infrastructure (Always Free Tier).
    *   **Shape:** VM.Standard.A1.Flex (Ampere ARM64).
    *   **Specs:** 4 OCPUs, 24 GB RAM.
    *   **Network:** 4 Gbps (10 TB/Month Outbound Bandwidth).
    *   **Storage:** 200 GB Block Volume (Persistent).

---

## 🐳 2. The Docker Service Swarm (Compose Definition)

Instead of a monolithic app, the system runs as 6+ interconnected containers.

### A. Core Services
| Service Name | Technology | Description | RAM Budget |
| :--- | :--- | :--- | :--- |
| `gateway` | **Nginx** | The entry point. Handles SSL, Reverse Proxying, and **File Caching**. | 2 GB |
| `manager-api` | **Python (FastAPI)** | The brain. Generates stream links, handles User Auth (`/login`), and Database interactions. | 1 GB |
| `stream-engine` | **Go/Python** | The muscle. Handles `HTTP 206` Byte-Streaming. Connects to Worker sessions to pull data. | 4 GB |
| `mongo-db` | **MongoDB** | Cold Storage. Stores File Indexes (`tmdb_123`), User Profiles, and Logs. | 2 GB |
| `redis-cache` | **Redis** | Hot Storage. Manages Active Sessions, Queues, and "Busy/Free" status of Worker Bots. | 1 GB |

### B. Worker Services (The "Hidden" Swarm)
These containers run the "Session Swarm" (the 10 physical SIM accounts).
*   **Structure:** We do *not* run 10 separate containers. We run **1 Container (`workers`)** that spawns **10 Asyncio Tasks** internally.
*   **Reasoning:** Saves RAM OS-overhead vs running 10 full containers.
*   **Networking:** Each worker task rotates internally via `redis` instructions.

### C. Monitoring Stack (The Cockpit)
| Service Name | Description |
| :--- | :--- |
| `prometheus` | Collects raw metrics (CPU usage, Bandwidth, Disk IO). |
| `grafana` | Visual Dashboard accessible at `monitor.streamvault.net`. |
| `portainer` | Web GUI to restart/manage containers from Mobile. |

---

## 💾 3. The "Smart Cache" System (Nginx Logic)

This is the most critical infrastructure piece for reducing Telegram Reliance and increasing Speed.

### Storage Strategy
*   **Volume:** `/data/cache` mounted to the Host's 200GB Persistent Disk.
*   **Method:** **Slice Caching** (HTTP Range Request Caching).

### The Nginx Configuration Logic
1.  **Incoming Request:** User asks for `bytes=1000-2000` of Movie X.
2.  **Slice Check:** Nginx checks `/data/cache` for this specific slice hash.
3.  **Cache Miss (First View):**
    *   Nginx requests backend: "Fetch bytes 1000-2000 from Telegram".
    *   Nginx saves this 1MB chunk to disk.
    *   Nginx serves User.
4.  **Cache Hit (Viral View):**
    *   Nginx serves bytes directly from NVMe Disk.
    *   **Result:** Backend/Telegram is **IDLE**. Bandwidth used = 0.
5.  **Clean Up:** `inactive=72h` rule. If a chunk isn't watched for 3 days, delete it to make room for new movies.

---

## 🔌 4. Networking & Security Layer

### Access Points
We do **not** expose ports 8080/5000 directly.
*   **Public Access:** ONLY Port `80` (HTTP) and `443` (HTTPS) via Cloudflare.
*   **SSH Access:** Port `22` (Key Authentication Only).
*   **Monitoring Access:** Protected via internal Reverse Proxy with Basic Auth.

### The Cloudflare "Mask"
We use **Cloudflare DNS Proxy ("Orange Cloud")** in front of Oracle.
*   **User sees:** `streamvault.net` (Cloudflare IP).
*   **Cloudflare sees:** Oracle Public IP (`129.x.x.x`).
*   **Benefit:** DDoS protection and ISP Throttling evasion.

### Backend Data Tunneling (Bypass Strategy)
To avoid the backend traffic (Downloading from Telegram) being flagged:
1.  **IP Rotation:** (Optional) Use IPv6 rotation if supported by Oracle region.
2.  **SOCKS5 Injection:** The Worker Containers support `PYROGRAM_PROXY` env vars to route Telegram traffic through a residential proxy *if* Oracle IPs get flood-limited (Fallback plan).

---

## 🛡️ 5. Persistence & File Hierarchy

Since Docker containers are ephemeral, we must mount vital data to the Host (Oracle OS).

**Folder Structure (On Oracle VPS):**
```text
/home/ubuntu/streamvault/
├── docker-compose.yml     # The Blueprint
├── .env                   # Secrets (Tokens, Passwords)
│
├── data/                  # PERSISTENT DATA (Volume Mounts)
│   ├── mongo/             # Database Files
│   ├── redis/             # Session Keys
│   └── cache/             # 200GB Video Slices (Nginx)
│
├── config/                # Configuration Files
│   ├── nginx.conf         # Caching Rules
│   ├── prometheus.yml     # Monitoring Targets
│   └── worker_accounts/   # The Physical Session Files (.session)
```

**Permission Handling:**
*   The logic must include: `RUN chown -R 1000:1000 /app` in Dockerfiles.
*   This ensures the Container User (ID 1000) has permission to read/write the Session Files stored on the Host Volume.

---

## 📜 6. Development Workflow (CI/CD)

**How we push updates to this Infrastructure:**

1.  **Development:**
    *   Code locally or via **VS Code Remote SSH**.
    *   Commit changes to GitHub Main.
2.  **Automated Deploy (GitHub Actions):**
    *   GitHub Runner SSHs into Oracle.
    *   `git pull` (Download changes).
    *   `docker compose up -d --build --no-deps <service>` (Hot Reload).
    *   **Result:** 10-second downtime max.
3.  **Emergency Management:**
    *   If auto-deploy fails, use **Portainer (Mobile Web UI)** to rollback to the `latest` stable image immediately.

---
