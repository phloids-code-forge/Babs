## Hardware Environment

### Primary Node: MSI EdgeXpert MS-C931 (DGX Spark Platform)

- **System:** MSI EdgeXpert MS-C931, built on the NVIDIA DGX Spark platform
- **Compute:** GB10 Grace Blackwell Superchip (ARM64 architecture, SM 12.1 compute capability). 20-core NVIDIA Grace CPU + NVIDIA Blackwell GPU. 1 petaFLOP FP4 tensor performance. 6144 CUDA cores. NVLink-C2C interconnect (up to 5x PCIe 5.0 bandwidth) provides seamless CPU+GPU unified memory model.
- **Memory:** 128GB Unified LPDDR5x (273 GB/s bandwidth, 256-bit interface), shared across CPU and GPU via NVLink-C2C
- **Storage:** 4TB NVMe PCIe Gen 4 M.2 SSD with hardware self-encryption (SED). Data-at-rest encryption is handled at the drive level with zero performance penalty and no software configuration required. 4TB Samsung X9 Pro USB-C external (20 GB/s) for local backup. The architect should propose a storage allocation strategy covering: model weights, vector databases, audit logs, Episodic Memory accumulation, backups, and growth projections over 12 months of continuous operation.
- **Networking:** RJ45 10GbE LAN, WiFi 7, Bluetooth 5.3, NVIDIA ConnectX-7 Smart NIC with dual QSFP56 200GbE ports. The ConnectX-7 is not used in the initial single-Spark deployment but enables future dual-Spark clustering for 256GB combined memory and models up to 405B parameters. Wired ethernet is the primary network connection.
- **OS:** DGX OS (Optimized Ubuntu 24.04 ARM64). Ships pre-installed with NVIDIA drivers, CUDA, Docker, and the DGX software stack including DGX Dashboard for monitoring.
- **Power Protection:** Connected to a UPS. The Event Listener (Section 12) monitors UPS status via USB for graceful shutdown on power loss.
- **Hard Memory Ceiling:** Your architecture must not exceed **115GB total allocation** across all running containers, models, databases, and services on the Spark. The remaining 13GB is reserved for OS, CUDA contexts, and burst overhead. Provide a detailed **Memory Ledger** table showing the estimated footprint of every running component at peak parallel load.

### Cluster Topology

Babs operates as a two-node cluster: the MSI EdgeXpert as the primary compute node and an auxiliary services node on the local network. phloid accesses Babs from multiple client devices. None of the client devices are Babs infrastructure; they are viewports into the system.

**Auxiliary Node: ROG Zephyrus G14 (headless, always-on)**

- **System:** ASUS ROG Zephyrus G14 Gen 2 (GA401QM)
- **CPU:** AMD Ryzen 9 5900HS (8-core/16-thread)
- **GPU:** NVIDIA GeForce RTX 3060 Mobile, 6GB GDDR6 VRAM, 60W base (80W Dynamic Boost)
- **RAM:** 40GB DDR4-3200 (8GB soldered + 32GB SODIMM)
- **Storage:** 1TB NVMe SSD
- **OS:** Ubuntu 24.04 LTS Server. Same OS family as DGX OS (both Ubuntu 24.04), providing consistent systemd behavior, package ecosystem, and debugging workflows across both nodes. Server flavor chosen because the G14 is a dedicated headless auxiliary node with no GUI workloads. NVIDIA drivers installed via `ubuntu-drivers autoinstall` or the NVIDIA apt repository.
- **Container Runtime:** Docker (native install via apt). Podman installable as an alternative if needed for specific containers. All auxiliary service containers use docker-compose managed by systemd for boot persistence.
- **Network:** Wired ethernet to LAN (preferred) or WiFi 6. Must be on the same LAN as the Spark.
- **Power Management:** BIOS configured for "Restore on AC Power Loss" (auto-boot after outage). OS configured to never sleep on AC power. Lid-close action set to ignore (no action).

**G14 Service Assignment:**

The G14 hosts auxiliary services that offload non-critical workloads from the Spark. All services run as containers managed by systemd (docker-compose with restart policies).

| Service | GPU Required | Memory Estimate | Purpose |
|---------|-------------|-----------------|---------|
| SearXNG | No | ~400MB | Privacy-respecting meta-search |
| Embedding Model (nomic-embed-text or bge-base) | Yes (GPU preferred, CPU fallback) | ~1.5GB VRAM | Document and query vectorization |
| Whisper STT (whisper-medium) | Yes (GPU preferred, text-only fallback) | ~2GB VRAM | Speech-to-text for voice input |
| Discord Notification Bot | No | ~100MB | Tier 2/3 approval relay, system alerts |
| NATS Client | No | ~50MB | Pub/sub bus subscriber for cluster communication |
| Backup Agent | No | ~50MB | Nightly rsync to local disk + rclone to cloud |

**G14 Resource Budget:**

The G14 is a dedicated auxiliary node with no competing workloads. The full 40GB RAM and 6GB VRAM are available for Babs services. The architect should define a resource budget allocating these resources across the services listed above, with headroom for future service additions.

**Client Devices (Not Babs Infrastructure):**

These devices access Babs via the dashboard in a web browser or via Discord. They run no Babs services and require no configuration beyond Tailscale installation.

| Device | Use Case | Connection Method | Tailscale IP |
|--------|----------|-------------------|--------------|
| ProArt PX13 (RTX 4060, 32GB RAM, Windows 11) | phloid's primary workstation. VS Code Remote SSH to Spark. Antigravity IDE. Claude Code. Gaming. | Tailscale (auto-routes via LAN when home) | 100.75.27.94 |
| Samsung Tab S9 Ultra (samsung-sm-x910) | Mobile computing, dashboard access, drawing | Tailscale | 100.91.246.51 |
| Samsung Galaxy S25 Ultra (samsung-sm-s918u) | Quick approvals, notifications, dashboard checks | Tailscale + Discord | 100.119.249.52 |

**Note on the PX13:** The PX13's RTX 4060 dGPU only activates on the OEM power brick (USB-C PD is insufficient). The PX13 is not a Babs compute node. It is a workstation that accesses the Spark's filesystem via VS Code Remote SSH and the Babs dashboard via a browser. When phloid unplugs the PX13 and leaves, Babs is unaffected.

**Network Interconnect:**

- The pub/sub bus (NATS) spans the LAN, connecting the Spark and G14. Both nodes subscribe to the same NATS cluster.
- Tailscale mesh VPN is installed on all five devices. Each device has a stable Tailscale IP that works regardless of network topology:

| Device | Tailscale IP | Hostname |
|--------|-------------|----------|
| MSI EdgeXpert (Spark) | 100.109.213.22 | spark |
| ROG Zephyrus G14 | 100.101.118.78 | g14 |
| ProArt PX13 | 100.75.27.94 | proartpx13 |
| Samsung Galaxy S25 Ultra | 100.119.249.52 | samsung-sm-s918u |
| Samsung Tab S9 Ultra | 100.91.246.51 | samsung-sm-x910 |

- When a client device is on the home LAN, Tailscale detects this and routes traffic directly over the LAN (zero overhead). When a client is remote, traffic routes through an encrypted Tailscale tunnel.
- All client-to-Spark communication (dashboard, VS Code Remote SSH, API calls) uses the Tailscale IP, never a LAN IP. This makes the connection method identical whether phloid is at home or traveling. No configuration changes, no switching.
- SSH shortcuts configured on the PX13: `ssh spark` (Tailscale IP 100.109.213.22) and `ssh g14` (Tailscale IP 100.101.118.78), both with key-based auth (ed25519), no password.

---


## Section 9: Runtime Resilience & Fault Tolerance

**This section is non-negotiable. Every agent must have defined failure semantics.**

**Watchdog & Circuit Breaker Protocol:**
- Define timeout thresholds for every agent type (Supervisor inference, Worker inference, Jupyter execution, external API calls).
- Specify retry policies: how many retries, with what backoff strategy, before escalation or graceful degradation.
- If a Worker hangs or crashes: define the detection mechanism (heartbeat, timeout), the recovery action (restart container, reassign task), and the notification to the Supervisor.
- **Dead-Letter Queue:** Failed tasks that exhaust retries must be logged to a dead-letter queue on the Pub/Sub bus for later inspection, not silently dropped.

**Failure Pattern Learning (Philosophy Document Section 5):**
- During the Reflection Loop, Babs must analyze the dead-letter queue for recurring failure patterns.
- Actionable patterns (e.g., "the Coding Worker fails on async Python tasks more than synchronous ones") should be logged as heuristics and may trigger model swapping or agent creation proposals.

**Adversarial Validation Protocol:**

Before certain actions are dispatched or surfaced, a Worker model runs a lightweight adversarial check. This applies to:

- **Class C task decompositions.** Before dispatch, a Worker validates the proposed plan: "Does this plan cover the original request? Are there gaps? Are subtasks redundant or contradictory?" Single inference call. Latency is invisible because Class C is async.
- **Tier 2/3 action plans.** Before surfacing for phloid's approval, the same adversarial check runs. This pre-filters obvious plan failures before they waste phloid's attention.
- **Class A/B interactions.** No adversarial check. Latency cost is too high relative to blast radius. Defense at this tier comes from retrieval quality, memory conflict resolution (Philosophy Document Section 4), and Reflection Loop pattern correction.

**Error Taxonomy:**

All failures are classified into five categories with subtypes. The dead-letter queue, Reflection Loop analysis, and observability dashboards all reference this taxonomy.

- **Category 1 (Infrastructure).** OOM kill, container crash, disk full, container-level timeout, network partition. Auto-retryable after condition resolves. Alert on recurrence.
- **Category 2 (External API).** Auth failure (notify phloid), rate limit (backoff + queue), timeout (retry with backoff), bad response (log for pattern analysis), service down (circuit breaker). Per-subtype handling strategies.
- **Category 3 (Model).** Malformed output, refused request, hallucination detected, reasoning failure. Most interesting for Reflection Loop analysis. Recurrence on specific task types may trigger model swap or Procedural Memory updates.
- **Category 4 (Validation).** Code execution failure, type check failure, lint failure after max iterations, Playwright failure, schema mismatch. These only hit the dead-letter queue after the Coding Worker's loop limit is exhausted, making them strong signal.
- **Category 5 (Task).** Decomposition rejected by adversarial check, worker assignment failure, result aggregation failure, priority conflict from preemption. Supervisor-level failures with different implications than Worker-level failures.

**Dead-letter entry schema:** timestamp, error category, subtype, originating agent, task ID, input, output (if any), retry count, resolution status.

**Dead-letter queue lifecycle:** Active queue for recent and unresolved entries. Resolved entries older than N days (configurable) archive to a queryable store. The Reflection Loop analyzes the active queue by default. Archive is available for deeper historical analysis on demand.

**Dormant Fallback Containers (G14 Auxiliary Node Failure):**

The Spark must maintain pre-built, dormant container images for critical services normally hosted on the G14. These containers consume no resources until activated.

| G14 Service Lost | Spark Fallback | Memory Cost on Spark | Trigger |
|-----------------|----------------|---------------------|---------|
| SearXNG | Activate dormant SearXNG container on Spark | ~400MB (only during fallback) | G14 heartbeat timeout |
| Embedding Model | CPU-only embedding inference on Spark | Negligible (CPU, no VRAM) | G14 heartbeat timeout |
| Whisper STT | Degrade to text-only interaction. Dashboard disables voice input, shows banner. | 0 (no fallback model) | G14 heartbeat timeout |
| Discord Bot | Activate dormant Discord bot container on Spark | ~100MB (only during fallback) | G14 heartbeat timeout |
| Backup Agent | Tier 2 (LAN) backup unavailable. Tier 1 (local) and Tier 3 (cloud) continue. | 0 | G14 heartbeat timeout |

**Activation logic:** The Spark monitors the G14 via a heartbeat signal on the NATS bus. If the heartbeat is missed for a configurable duration (default: 60 seconds), the Spark assumes the G14 is offline and activates all relevant fallback containers. When the G14's heartbeat resumes, fallback containers are deactivated and traffic routes back to the G14.

**Graceful Degradation Matrix:**
- Define what happens when each component fails. Example: if the vector database is down, the Supervisor must still function with Working Memory only and log a warning, not crash.
- The matrix must include:
  - External dependency failures: Discord unavailable, Alpaca API down, Gmail API returning errors, Anthropic API unreachable.
  - **G14 auxiliary node fully offline:** All services fail over per the dormant fallback table above. Core Babs functionality is unaffected.
  - **Both backup targets unavailable (USB drive failure + G14 offline):** Off-site cloud backup continues. Dashboard shows backup degradation warning.
  - **Tailscale unavailable:** Remote clients lose access. LAN clients can fall back to direct LAN IP. Dashboard remains accessible on LAN.
- This matrix must be a dedicated deliverable, not an afterthought.

---

## Section 10: Observability & Monitoring

**Specify an observability stack** that provides real-time visibility into the running system.

**Required Metrics:**
- Per-agent inference latency (P50, P95, P99)
- Memory utilization per container vs. the Memory Ledger budget
- Task success/failure rates per Worker type
- Pub/Sub queue depths and message throughput
- External API call latency and spend tracking
- Jupyter Kernel execution times and failure rates
- Audit log event rates and anomaly flags
- Memory consolidation cycle duration and outcomes
- Scheduled task execution status
- Local inference cost tracking: tokens-in and tokens-out per request, per model, with task-level attribution. This enables evaluating whether workers, the Reflection Loop, or dynamic agents justify their resource cost.
- **Cluster-level metrics:** Per-node health status (Spark, G14), per-node memory and GPU utilization, cross-node pub/sub latency, node online/offline events, dormant fallback container activation events.
- **Dynamic model loading metrics:** Model load/unload events, swap latency, memory reclamation timing, time-to-first-token after model load.

**Implementation:**
- Recommend a lightweight stack appropriate for a two-node deployment (e.g., Prometheus + Grafana, or a simpler alternative).
- Metrics from the G14 must be collected and forwarded to the Spark for unified dashboard display.
- All metrics must be accessible via the local dashboard.

---


## Section 14: Backup, CI/CD, & Continuous Evolution

**Three-Tier Backup Strategy:**

Babs operates in tornado country. A single backup target co-located with the Spark is insufficient. The backup strategy must protect against hardware failure, home loss (fire, tornado, theft), and data corruption.

- **Tier 1: Local backup.** The 4TB Samsung X9 Pro USB-C external drive (20 GB/s) connected to the Spark. Full system backup every 24 hours: Docker states, vector databases, Semantic Memory, Procedural Memory, Episodic Memory, audit logs, configuration, and the associative graph. Model weights are excluded (re-downloadable). This is the fastest recovery path.
- **Tier 2: LAN backup.** The G14 auxiliary node's 1TB SSD receives a nightly rsync-over-SSH of critical data from the Spark: Semantic Memory, Procedural Memory, configuration files, audit logs, and the associative graph. Episodic Memory is included if storage permits; otherwise, only consolidated/promoted entries. Model weights excluded. This protects against Spark drive failure or USB drive failure when both are co-located.
- **Tier 3: Off-site backup.** Encrypted cloud backup to Google Drive (2TB available). Encryption via rclone crypt (AES-256 + salt, file name encryption enabled) so all data is encrypted before leaving the LAN. Sync runs daily after local backup completes. The off-site backup includes the same critical data set as Tier 2. The architect should estimate storage growth rate for the critical data set and project when it will approach the 2TB Google Drive ceiling. If projections exceed 2TB within 12 months, recommend a supplemental provider (Backblaze B2 at ~$6/TB/month is the obvious candidate).

**Note on data-at-rest encryption:** The EdgeXpert's 4TB NVMe has hardware self-encryption (SED), so data at rest on the primary drive is encrypted at the hardware level without software overhead. The external USB backup drive does not have SED; if encryption at rest is required for the USB backup, a software encryption layer (LUKS or similar) should be specified. The off-site backup is encrypted via rclone crypt before data leaves the LAN.

**Recovery Procedures:**

Define three recovery scenarios:

1. **Restore from Tier 1 (local USB).** Fastest path. Used when: Spark SSD fails but USB drive and system are intact. Expected recovery time and data loss window.
2. **Restore from Tier 2 (G14 LAN).** Used when: both Spark SSD and USB drive are lost (e.g., Spark hardware failure). Critical data restored from G14. Episodic Memory may be partial. Model weights re-downloaded.
3. **Restore from Tier 3 (off-site cloud).** Disaster recovery. Used when: home loss (fire, tornado, theft). New hardware procured, rclone pulls encrypted backups from Google Drive, decrypt locally, restore. This is the slowest path but guarantees data survival against total site loss. Define expected recovery time including download bandwidth assumptions.

**Model Update Pipeline:**
- When a new model is released, define the process to evaluate it, benchmark it against the current model on Babs-specific tasks, and swap it in using the Model Swap Protocol from Section 1.

**Configuration as Code:**
- All system configuration (model assignments, memory budgets, timeout thresholds, API keys, Trust Tier assignments, rate limits, scheduled tasks, drift detection parameters, Discord webhook/bot config, cluster topology, G14 service assignments, backup schedules) must be stored in version-controlled config files, not hardcoded.
- Define the config file format, directory structure, and the mechanism for applying config changes without full system restart.

**Dry-Run / Staging Mode:**
- The system must support a staging mode where all external actions route to mock endpoints instead of live APIs.
- This allows testing orchestration changes, new agents, and workflow modifications without real-world side effects.
- Define how staging mode is activated (config flag, CLI command, dashboard toggle) and how it is visually indicated in the UI so phloid never mistakes staging for production.

---

## Section 15: Pre-Deployment Preparation (G14 Auxiliary Node)

**The G14 auxiliary node can be configured in parallel with the EdgeXpert bootstrap (Section 16).** This section defines the prework checklist so the G14 is ready to join the cluster.

**Phase 0 Prework Checklist:**

1. **Install Ubuntu 24.04 LTS Server.** ✓ **COMPLETED 2026-03-13.** Ubuntu 24.04 LTS Server installed. NVIDIA drivers version 580.126.09 installed via `ubuntu-drivers autoinstall`. RTX 3060 Laptop GPU recognized with 6GB VRAM.

2. **BIOS Configuration.** ✓ **COMPLETED.** "Restore on AC Power Loss" enabled. Secure Boot disabled.

3. **Power Management.** ✓ **COMPLETED.** Sleep/suspend/hibernate masked via systemd. Lid switch set to ignore in logind.conf.

4. **Container Runtime.** ✓ **COMPLETED 2026-03-13.** Docker Engine 29.3.0 installed via official Docker apt repository. NVIDIA Container Toolkit 1.19.0 installed and configured. Docker systemd service enabled on boot.

5. **Networking.** ✓ **COMPLETED.** G14 at LAN IP 192.168.1.219. SSH with ed25519 key auth from PX13 and Spark (`ssh g14`).

6. **Tailscale.** ✓ **COMPLETED 2026-03-11.** G14 at Tailscale IP 100.101.118.78. All five devices on the tailnet.

7. **SearXNG Container.** ✓ **COMPLETED 2026-03-13.** Running on port 8888. JSON API enabled. Config at `~/searxng/settings.yml`. Tested successfully with 24 results for test query. Restart policy: always.

8. **Embedding Model Container.** ✓ **COMPLETED 2026-03-13.** HuggingFace Text Embeddings Inference serving nomic-embed-text-v1.5 on GPU. Port 8080. Produces 768-dimensional embeddings. Float16 dtype. VRAM usage: ~200MB. Restart policy: always.

9. **Whisper Container.** ✓ **COMPLETED 2026-03-13.** OpenAI Whisper ASR webservice running whisper-medium on GPU via faster_whisper engine. Port 9000. VRAM usage: minimal when idle. Restart policy: always.

10. **GPU Service Coexistence Testing.** ✓ **COMPLETED 2026-03-13.** All GPU services (embedding + Whisper) running simultaneously. Total VRAM usage: 425MB out of 6144MB (7% utilization). 5.7GB headroom available. All services responsive under test load.

11. **rclone + Google Drive.** ⏸ **DEFERRED.** Will be configured when backup infrastructure is implemented (Phase 7+).

12. **Backup Agent.** ⏸ **DEFERRED.** Will be configured when backup infrastructure is implemented (Phase 7+).

13. **Discord Bot.** ⏸ **DEFERRED.** Discord server and bot not yet configured. Will deploy when notification infrastructure is implemented.

14. **NATS Client.** ⏸ **DEFERRED.** NATS server location not yet decided. Will deploy when pub/sub infrastructure is implemented (Phase 7+).

**G14 Services Summary (2026-03-13):**

| Service | Container | Port | GPU | Memory | Status |
|---------|-----------|------|-----|--------|--------|
| SearXNG | searxng/searxng:latest | 8888 | No | ~400MB RAM | Running |
| Embedding | ghcr.io/huggingface/text-embeddings-inference:latest | 8080 | Yes | ~200MB VRAM | Running |
| Whisper STT | onerahmet/openai-whisper-asr-webservice:latest | 9000 | Yes | ~225MB VRAM idle | Running |

All containers configured with `--restart always` for boot persistence.

---

## Section 16: Bootstrap Deployment Plan (EdgeXpert)

**This section defines the sequence from unboxing the MSI EdgeXpert to having a functional Babs that can assist in building out her own infrastructure.** The G14 auxiliary node setup (Section 15) runs in parallel but is not a dependency for any bootstrap phase.

**Phase 0: Hardware and OS Validation**

The EdgeXpert ships with DGX OS pre-installed (Ubuntu 24.04 ARM64 with NVIDIA drivers, CUDA, and Docker).

1. Connect power, ethernet, monitor, and keyboard. Boot the system.
2. Log in. Run `nvidia-smi` to confirm the GB10 is recognized.
3. Run `lsblk` to verify the 4TB NVMe is visible and has expected capacity.
4. Verify internet access via wired ethernet.
5. Install Tailscale. Confirm SSH access from the PX13 via Tailscale IP.
6. Once remote access is confirmed, disconnect the monitor and keyboard. All further work is done from the PX13 via SSH.
7. Run any pending DGX OS updates. NVIDIA has shipped significant performance improvements via software updates (CES 2026 update delivered 2.5x gains for some workloads). Get the latest before benchmarking anything.

**Phase 0 Validation Results (2026-03-11):**

| Check | Result |
|-------|--------|
| nvidia-smi | GB10 recognized. Driver 580.126.09, CUDA 13.0, idle at 34°C / 4W. |
| Storage | 3.6TB NVMe (nvme0n1, boot/root). 3.6TB Samsung X9 Pro USB (sda, single partition, unmounted). |
| Internet | IPv6 working, ~27ms avg latency. |
| Docker | Running (systemd, enabled on boot). Required `sudo usermod -aG docker dave` for non-root access. |
| OS updates | Current. 10 deferred phased packages (normal Ubuntu rollout). |
| Tailscale | Installed. Spark at 100.109.213.22. SSH from PX13 confirmed. |

**Note:** The DGX OS ships with a desktop environment (Xorg, GNOME shell visible in nvidia-smi process list at ~24MiB combined). This is expected for the MSI EdgeXpert. The desktop environment does not need to be removed; its memory footprint is negligible relative to the 128GB total.

**Validation gate:** PASSED. SSH into EdgeXpert from PX13 over Tailscale works. nvidia-smi shows GB10. Docker runs (`docker run hello-world` succeeds after group fix).

**Phase 1: Docker Setup and Directory Structure**

1. Verify Docker is running and enabled on boot (`systemctl enable docker`).
2. Verify `docker compose version` works.
3. Create the Project Babs directory structure on the 4TB drive. This will be the canonical filesystem layout defined in the architect's plan (Output Requirement #8). At minimum for bootstrap:
   - Model weights directory
   - Docker compose files
   - Configuration files
   - Project Babs git repository (architecture docs, code, Procedural Memory seeds)
4. Initialize a git repository in the project directory. This is the canonical repo that all coding tools will operate on.

**Validation gate:** Docker works. Directory structure exists. Git repo initialized.

**Phase 1 Validation Results (2026-03-12):**

| Check | Result |
|-------|--------|
| Docker | Running, enabled on boot. `docker compose version` works. |
| Directory structure | `~/babs/` (git repo: config, docker, src, docs, scripts, seeds, tests). `~/babs-data/` (runtime: models, qdrant, memory, logs, nats, cache). |
| Git repo | Initialized on `main` branch. `.gitignore` and `README.md` committed. User: phloid, email: dave@babs.local. |
| HuggingFace CLI | Installed at `~/.local/bin/hf` (v1.6.0, renamed from `huggingface-cli`). PATH updated in `.bashrc`. |
| Model weights | `~/babs-data/models/nemotron3-super-nvfp4/`: 17 safetensors files, 75GB on disk (larger than 67GB estimate due to BF16 layers for MTP, attention projections, embeddings alongside FP4 weights). config.json and tokenizer_config.json present. |
| Reasoning parser | `~/babs/scripts/super_v3_reasoning_parser.py` downloaded from HuggingFace model card. |
| vLLM image | Built via eugr/spark-vllm-docker (community builder). Tagged `vllm-node`. vLLM 0.17.1rc1 nightly (2026-03-11). Build time: ~17 minutes. Prebuilt wheels used (no source compilation). |

**Validation gate:** PASSED with caveats. Directory structure exists. Git repo initialized. Model weights downloaded. vLLM image built. See Phase 2 for model serving validation.

**Phase 2: Model Serving and Supervisor Model**

This is the most critical phase and the most likely place for troubleshooting.

1. Pull the vLLM Docker image with NVFP4 support for SM121. Since the Supervisor model is now NVIDIA Nemotron 3 Super (an NVIDIA model on NVIDIA hardware), first-party or near-first-party vLLM support is expected. Check the DGX Spark community forums and the Nemotron 3 Super HuggingFace model card for the current recommended serving configuration.
2. Download the NVIDIA Nemotron 3 Super 120B-A12B NVFP4 model weights from HuggingFace (`nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`, approximately 67GB). This model includes Multi-Token Prediction (MTP) weights for built-in speculative decoding.
3. Start the vLLM container, pointing at the model weights. Use FP8 KV cache (`--kv-cache-dtype fp8`). The model card recommends `temperature=1.0` and `top_p=0.95` across all tasks. Verify startup logs show correct backends.
4. Send a test request via `curl` to the vLLM OpenAI-compatible endpoint. Confirm a coherent response.
5. Note the baseline tok/s on a simple prompt. This is the benchmark everything else is measured against.

**If the Nemotron 3 Super NVFP4 has issues on SM121** (unlikely given it is NVIDIA's own model natively pre-trained in NVFP4 for Blackwell), fall back to Nemotron 3 Nano 30B-A3B NVFP4 as the bootstrap Supervisor. Community-confirmed working on the Spark at 65+ tok/s. Upgrade to the Super when the issue is resolved.

**Validation gate:** PASSED with Nano. `curl` to the vLLM endpoint returns a coherent response at 65+ tok/s sustained generation. Nano is stable and confirmed as the day-one Supervisor model. Super is parked due to SM121 kernel incompatibility.

**Phase 2 Validation Results (2026-03-12):**

| Check | Result |
|-------|--------|
| vLLM serve | Nemotron 3 Super NVFP4 loads and serves successfully. Startup includes CUDA graph compilation (slow first boot, cached thereafter). |
| Test response | Model identifies itself as "Nemotron 3 Super, a large language model created by NVIDIA." Coherent responses to coding and explanation prompts. |
| Reasoning parser | Working. `super_v3_reasoning_parser.py` correctly separates thinking (reasoning field) from answer (content field). Reasoning can be toggled per-request via `chat_template_kwargs: {"enable_thinking": false}`. |
| Throughput | **14.7-14.8 tok/s sustained generation** (measured over 2000-token response, consistent across 12+ consecutive 10-second log intervals). Prompt throughput: ~3.2-3.4 tok/s. |
| Memory | nvidia-smi reports "Not Supported" for memory on unified memory systems. `/proc/meminfo` inside container: 12.3GB available out of 128GB total at `--gpu-memory-utilization 0.85`. This is tight but within the 13GB OS headroom target. |
| Tool calling | `--enable-auto-tool-choice --tool-call-parser qwen3_coder` flags accepted. Not yet tested with actual tool calls. |

**CRITICAL ISSUE: SM121 Illegal Instruction Crash.**

Nemotron 3 Super NVFP4 crashes with `cudaErrorIllegalInstruction` during extended generation sessions. The model serves short responses successfully but hits an incompatible kernel code path during longer generations or after sustained use. The crash manifests as a CUDA illegal instruction in the EngineCore, killing the vLLM process.

Findings:
- Default vLLM flags (no MOE backend override): model serves, generates at 14.8 tok/s, but crashes after several minutes of use. Short requests (under ~300 tokens output) typically succeed. Longer generations or sustained sessions trigger the crash.
- `VLLM_FLASHINFER_MOE_BACKEND=latency`: crashes immediately during generation (CUDA stream capture error).
- `VLLM_FLASHINFER_MOE_BACKEND=throughput`: not tested.
- `--enforce-eager`: TESTED. This disables CUDA graph capture entirely, running in eager mode. **DID NOT FIX THE CRASH.** Same `cudaErrorIllegalInstruction` error. The issue is in the compute kernels themselves, not graph capture.

**RESOLUTION: Nano Fallback (Day-One Configuration)**

Given that `--enforce-eager` did not resolve the SM121 kernel incompatibility, we have fallen back to Nemotron 3 Nano 30B-A3B NVFP4 as the day-one Supervisor model. Nano is community-confirmed stable on the Spark at 65+ tok/s (sustained generation) using the Avarok image `avarok/vllm-dgx-spark:v11`.

Super weights remain on disk at `~/babs-data/models/nemotron3-super-nvfp4/` (75GB). We will upgrade to Super when the community releases SM121 kernel fixes. The model launched 2026-03-11; patches are expected but timing is unknown.

**Nano Serving Command (Day-One Configuration, STABLE):**

```bash
docker run -d --name vllm-babs \
  --gpus all --ipc=host -p 8000:8000 \
  -e VLLM_FLASHINFER_MOE_BACKEND=latency \
  -v ~/babs-data/models/nemotron3-nano-nvfp4:/model \
  -v ~/babs-data/cache:/root/.cache \
  avarok/vllm-dgx-spark:v11 \
  serve /model \
  --served-model-name nemotron3-nano \
  --quantization modelopt_fp4 \
  --kv-cache-dtype fp8 \
  --trust-remote-code \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.85 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser deepseek_r1 \
  --host 0.0.0.0 --port 8000
```

**Super Serving Command (PARKED, crashes on SM121):**

```bash
docker run -d --name vllm-babs \
  --gpus all --ipc=host -p 8000:8000 \
  -v ~/babs-data/models/nemotron3-super-nvfp4:/model \
  -v ~/babs-data/cache:/root/.cache \
  -v ~/babs/scripts:/scripts \
  vllm-node \
  vllm serve /model \
  --served-model-name nemotron3-super \
  --dtype auto --kv-cache-dtype fp8 \
  --quantization modelopt_fp4 \
  --tensor-parallel-size 1 \
  --trust-remote-code \
  --gpu-memory-utilization 0.85 \
  --max-num-seqs 4 --max-model-len 32768 \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser-plugin /scripts/super_v3_reasoning_parser.py \
  --reasoning-parser super_v3
```

**Flags that cause crashes on SM121 (Super only):**
- `VLLM_FLASHINFER_MOE_BACKEND=latency` (crashes during generation)
- `--enforce-eager` (did not fix crash, same illegal instruction error)
- `--swap-space` (unrecognized argument in vLLM 0.17.1)

**Open WebUI:** Pulled (`ghcr.io/open-webui/open-webui:main`), data volume at `~/babs-data/open-webui`, launched with `--network host`. Accessible at port 8080. Currently running but has no backend (vLLM crashed). Needs stable vLLM before configuration.

**Phase 3: Chat Frontend**

1. Pull and run Open WebUI as a Docker container. Point it at the vLLM endpoint.
2. Create a "Babs" persona in Open WebUI. Load the personality system prompt from the philosophy document (core traits, communication style, relationship model). Not the full architecture prompt, just enough that she sounds like Babs.
3. Open the Open WebUI interface from the PX13's browser (via Tailscale IP). Have a test conversation. Verify the personality comes through, responses are coherent, and streaming works.

**Validation gate:** You can talk to Babs in a browser. She sounds right.

**Phase 4: Coding Tool Integration (Three-Tool Workflow)**

This phase establishes the three-tier AI coding workflow. All three tools operate on the same canonical git repository on the EdgeXpert's filesystem.

1. **Claude Code.** Install Node.js on the PX13 (or on the EdgeXpert if running Claude Code there). Install Claude Code CLI (`npm install -g @anthropic-ai/claude-code`). Authenticate with your Anthropic Pro account ($20/month). Navigate to the Project Babs repo directory and run `claude`. Verify Claude can see and edit the architecture documents. Claude Code draws from the Anthropic Pro token pool (~44,000 tokens per 5-hour rolling window). This is the tool for architecture planning, document editing, and strategic decisions where filesystem access and direct file editing matter.

2. **VS Code Remote SSH.** Install VS Code on the PX13. Configure Remote SSH to connect to the EdgeXpert via its Tailscale IP. Open the Project Babs repo as a workspace. Install a local-model coding extension (Continue or similar) and configure it to point at the vLLM endpoint on the EdgeXpert (`http://localhost:8000/v1` or equivalent). This gives Babs-powered AI-assisted coding with zero token costs and no rate limits. This is the daily driver for implementation work.

3. **Antigravity.** Install Antigravity on the PX13. Configure it to access the same project directory on the EdgeXpert (via Remote SSH or mounted filesystem). Antigravity provides access to Gemini 3.1 Pro (via Google AI Pro subscription, $20/month, separate from Anthropic), Claude Sonnet 4.6, Claude Opus 4.6, and GPT-OSS 120B. These draw from Google's token pool, completely separate from the Anthropic Pro pool used by Claude Code. Use Antigravity for heavy implementation sessions, multi-file scaffolding, and agent-first workflows when a frontier cloud model is needed.

**Token budget strategy:** Three separate token pools across two paid subscriptions.
- Anthropic Pro ($20/month): Powers Claude Code for architecture and planning. ~44K tokens per 5-hour window.
- Google AI Pro ($20/month): Powers Antigravity for Claude, Gemini, and GPT-OSS coding sessions. Separate rate limits.
- Local vLLM (free): Powers VS Code coding via the on-box Supervisor model. No limits, no costs, no external dependency.

When one cloud pool is rate-limited, switch to the other. For routine implementation, default to the local model. Use cloud models for complex architectural scaffolding, difficult debugging, or when you need a stronger model's judgment.

**Validation gate:** All three tools can open, edit, and save files in the Project Babs repo on the EdgeXpert.

**Phase 5: SearXNG**

1. Pull and run the SearXNG Docker image on the EdgeXpert. Configure it to listen on a local port.
2. Test a search query via `curl`. Confirm results are returned.
3. This gives Babs web search capability. It will be wired up as a tool when the tool framework is built in Phase 7.

**Note:** If the G14 is online by this point, SearXNG should run there instead (per the cluster topology). If the G14 is not yet ready, SearXNG runs on the Spark temporarily and migrates later.

**Validation gate:** SearXNG returns search results from a `curl` request.

**Phase 6: Architecture Context Loading**

1. Load the philosophy document and architecture prompt into the Babs persona in Open WebUI. Options: upload as documents for RAG retrieval, or inject key sections into the system prompt. The full architecture prompt is too large for a system prompt; use RAG for the detailed sections and inject the personality cheatsheet and core behavioral rules directly.
2. Test by asking Babs questions about her own architecture: "What's the plan for the Reflection Loop?" "What Trust Tier would a git commit fall under?" "What are the five error categories?" She should answer accurately from the docs.
3. Load the character bible and personality rubric as additional retrieval documents if the RAG pipeline supports it.

**Validation gate:** Babs can answer questions about her own architecture accurately.

**Phase 7: Begin Building**

This is the ongoing phase where phloid and Babs build out the real infrastructure together. Each item below is a discrete unit of work. phloid reviews and approves every change.

Recommended build order (each item makes Babs more capable for the next):

1. **NATS server.** Single-node NATS on the Spark. This is the pub/sub backbone for all inter-service communication. When the G14 comes online, it joins as a NATS client.
2. **Basic Supervisor service.** A persistent Python process that listens on NATS, receives messages, routes them to the vLLM endpoint with the appropriate system prompt and context, and returns responses. This is the "real" Babs backend, replacing Open WebUI as the primary conversation path. Open WebUI becomes a development and debugging tool.
3. **Procedural Memory store.** Qdrant (or architect-specified vector DB) as a Docker container. Load the seed Procedural Memory entries: Python Code Standards, personality rubric, personality cheatsheet. Implement the retrieval pipeline so the Supervisor pulls relevant entries before responding.
4. **Tool framework.** Structured tool call schema (MCP-compatible). Wire up SearXNG as the first tool. Implement Trust Tier enforcement for tool calls. This is where Babs gains the ability to search the web, read files, and eventually execute code.
5. **Dashboard skeleton.** A basic web UI showing: current model status, memory usage, recent conversations, chat interface, and a simple approval queue. This replaces Open WebUI entirely and becomes the real Babs frontend. Iterate on the dashboard continuously as new features come online.

**After Phase 7, the system is in continuous build-out mode.** Each new component (Worker model serving, ComfyUI integration, Reflection Loop, Discord notifications, memory consolidation, backup automation, G14 failover) is built incrementally, with Babs assisting and phloid reviewing.

---
