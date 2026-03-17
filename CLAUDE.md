# Project Babs: Claude Code Context

## What This Is

Babs is a local-first autonomous AI assistant running on a two-node home cluster. This repo contains the architecture documents, configuration, scripts, and source code for the system. You are helping phloid build it.

## Hardware

- **Primary node (Spark):** MSI EdgeXpert MS-C931 (DGX Spark platform). GB10 Grace Blackwell Superchip, 128GB unified LPDDR5x, 4TB NVMe, DGX OS (Ubuntu 24.04 ARM64). Hostname: `spark`. This is where you are running.
- **Auxiliary node (G14):** ASUS ROG Zephyrus G14, headless Ubuntu 24.04 LTS Server, RTX 3060 Mobile 6GB, 40GB RAM, 1TB SSD. At `ssh g14` (Tailscale 100.101.118.78). OS and networking complete, service deployment pending.
- **Dev machine (PX13):** Dave's workstation. Windows. Connects via VS Code Remote SSH over Tailscale.

## Current State (2026-03-17 Updated, session 3)

### System Stability

- **earlyoom:** Installed and running (`systemctl status earlyoom`). Kills highest OOM-score process when free RAM < 10%. Prevents kernel from cascading into session infrastructure before hitting the real culprit.
- **ComfyUI memory cap:** 70GB Docker limit in `docker-compose.comfyui.yml`. `cicc` (CUDA JIT compiler) previously consumed 3.3GB uncapped and caused a full OOM cascade that required a reboot.

### What's Running

| Container / Service | Image / Binary | Port | Status |
|---------------------|----------------|------|--------|
| vllm-babs | avarok/vllm-dgx-spark:v11 | 8000 | Running stable. Nemotron 3 Nano 30B-A3B NVFP4. 65+ tok/s. |
| nats-babs | nats:latest | 4222, 8222, 6222 | Running. JetStream enabled. Data at ~/babs-data/nats. |
| babs-supervisor | docker-supervisor (custom) | -- | Running. Routes NATS -> vLLM, manages tools, retrieves from Procedural Memory. |
| qdrant-babs | qdrant/qdrant:latest | 6333, 6334 | Running. Procedural Memory collection (5 seed entries, re-embedded). |
| babs-dashboard | docker-dashboard (custom) | 3000 | Running. Primary interface. http://100.109.213.22:3000 |
| comfyui-babs | comfyui-spark:latest | 8188 | Running. NVFP4 active. 70GB memory cap. |
| babs-jupyter | custom | -- | Running. |
| openshell-gateway | k3s-in-Docker (managed by openshell) | -- | Running. NemoClaw gateway. Manages inference routing and sandbox policy enforcement. |
| nemoclaw-sandbox | openshell/sandbox-from:* | -- | Running. OpenClaw agent runtime with NemoClaw security plugin. Inference -> vllm-local (:8000). |
| openclaw-dashboard-tunnel | systemd (openclaw-dashboard-start.sh) | 18789 | Running. SSH port forward: Tailscale:18789 -> sandbox:18789. Dashboard at http://100.109.213.22:18789/ |
| open-webui | ghcr.io/open-webui/open-webui:main | 8080 | Stopped (replaced by dashboard). |

### Super Model Investigation (2026-03-17 Updated)

**Finding:** Nemotron 3 Super 120B-A12B NVFP4 previously ran at ~1 tok/s (unusable). Community patches now bring single-node Spark to 14-16 tok/s. Still not interactive-fast but the path forward is clear.

**Root cause summary:** Two-version trap:
- vLLM 0.16.x (avarok v23 base): Knows SM_121 is FP4-capable (avarok patches), but rejects MIXED_PRECISION quant during model config validation.
- vLLM 0.17.0rc0 (upstream): Accepts MIXED_PRECISION, model loads and serves, but treats SM_121 as FP4-incapable -- falls back to Marlin software-emulated FP4 at ~1 tok/s.

**Community patch update (2026-03-16):** namake-taro published vLLM 0.17.0 MXFP4 patches for DGX Spark (github.com/namake-taro/vllm-custom) that fix a shared memory race condition in the Marlin MoE 256-thread kernel on SM121. With these patches and the env vars below, single-node Super runs at 14-16 tok/s. Two-node TP=2 reaches 80 tok/s on gpt-oss-120b.

**Env vars that improve single-node Super performance:**
```
VLLM_NVFP4_GEMM_BACKEND=marlin
VLLM_TEST_FORCE_FP8_MARLIN=1
VLLM_MARLIN_USE_ATOMIC_ADD=1
--kv-cache-dtype fp8
--load-format fastsafetensors
```

**What was built (2026-03-15):**
- `docker/Dockerfile.vllm-super`: avarok/dgx-vllm-nvfp4-kernel:v23 base + vLLM 0.17.0rc0+cu130 aarch64 wheel + flashinfer pinned to 0.6.3
- Image tag: `vllm-super` (built and cached on Spark)
- The image works -- model loads 17 shards (69.5 GiB), serves requests correctly.
- FlashInfer TRTLLM/CUTLASS backends fail at JIT compile time on SM_121a with 0.17.0rc0.
- Marlin backend works but is software FP4 emulation (hence the low speed without patches).

**What fully unlocks this:**
- avarok v24+ image shipping vLLM 0.17.x with SM_121 FP4 kernel patches applied. v23 is still latest as of 2026-03-17.
- OR apply namake-taro patches manually to the vllm-super image.

**NemoClaw angle:** The `nvidia-nim` provider in NemoClaw points at NVIDIA cloud Nemotron Super via API. When Super becomes the local active model, switch the inference route: `openshell inference set --provider vllm-local --model nemotron3-super`.

**Decision:** Parked. Nano is the active local model. Do not delete `vllm-super` image. Do not delete Super weights (75GB at `~/babs-data/models/nemotron3-super-nvfp4/`).

### Dev Environment (2026-03-14 Updated)

- **Claude Code:** Installed and working. You are it. Has passwordless sudo (`/etc/sudoers.d/dave-nopasswd`).
- **VS Code Remote SSH:** Connected to this repo via Tailscale. Antigravity also connected.
- **Continue extension:** Configured in VS Code, pointing at vLLM via Tailscale IP.
- **Hostname:** Changed from `edgexpert-4272` to `spark`.
- **Samba share:** `smbd` running on Spark. `~/babs-data` shared as `\\100.109.213.22\babs-data`. Mapped as `Z:` on PX13. Auth required (user: dave). Bound to all interfaces (Tailscale is the security boundary). Config: `/etc/samba/smb.conf`, setup script: `scripts/samba-setup.sh`.

### Bootstrap Progress

**Phases Complete:**
- ✅ Phase 0-2: Hardware validation, Docker, model serving (Nano stable at 65+ tok/s)
- ✅ Phase 3: Open WebUI configured, Babs personality loaded
- ✅ Phase 4: Coding tools (Claude Code, VS Code Remote SSH, Continue, Antigravity)
- ✅ Phase 5: SearXNG deployed on G14 (port 8888, JSON API enabled)
- ✅ Phase 6: Architecture context loaded into Open WebUI knowledge base
- ✅ Phase 7: Real backend infrastructure (COMPLETE 2026-03-13)

**Phase 7 - Real Backend (COMPLETE ✅):**
1. ✅ NATS pub/sub server (nats-babs, JetStream, ~/babs-data/nats)
2. ✅ Supervisor service (babs-supervisor, Python, NATS -> vLLM routing, in-memory threads)
3. ✅ Procedural Memory store (qdrant-babs, 5 seed entries, 768-dim vectors)
4. ✅ Procedural Memory retrieval (G14 embedding -> Qdrant search -> context injection)
5. ✅ Tool framework (MCP-compatible, SearXNG web search, Trust Tier enforcement)
6. ✅ Dashboard (babs-dashboard, port 3000, replaces Open WebUI)

**G14 Auxiliary Services Live:**
- SearXNG (port 8888, web search)
- Embedding model (port 8080, nomic-embed-text-v1.5, 768-dim)
- Whisper STT (port 9000, whisper-medium on GPU)
- GPU utilization: 425MB / 6GB (7%)

**Phase 7 Complete (2026-03-13).**
Full stack operational: Dashboard -> NATS -> Supervisor -> Procedural Memory + Tools -> vLLM.

**Phase 7.5 - Model Picker & Dashboard Enhancements (COMPLETE ✅):**
1. ✅ OpenRouter API integration (model discovery, routing, cost tracking)
2. ✅ Model picker UI in dashboard (local + OpenRouter models, filtering, search)
3. ✅ Model switching (hot-swap without restart, thread isolation)
4. ✅ Cost tracking & budget alerts (session costs, comparison to local)
5. ✅ Trust Tier integration (enforce local-only for sensitive operations)
6. ✅ Dashboard Home Navigation (persistent home access)
7. ✅ Thinking Transparency (WebSocket streaming of supervisor reasoning)
8. ✅ Multi-modal Input (File/Image attachment parsing and uploads)
9. ✅ Artifact Display System (Qdrant storage and real-time visualization rendering)

**Phase 8 - Supervisor Hardening & Tool Expansion (COMPLETE ✅ 2026-03-15):**
1. ✅ Bug fixes: workers.py logger import, blocking OpenRouter call (run_in_executor)
2. ✅ Episodic memory retrieval wired in -- past conversation summaries now injected alongside procedural memory
3. ✅ Babs identity -- Oracle archetype (Barbara Gordon) system prompts in both workers, grounded in design philosophy
4. ✅ New tools: read_file (Tier 0), write_file (Tier 2), shell (Tier 2)
5. ✅ Persistent thread storage -- SQLite at ~/babs-data/threads.db, conversations survive supervisor restarts
6. ✅ Reflection loop model name fix -- dreaming now works correctly with Nano

**Phase 9 - NemoClaw/OpenClaw Integration (COMPLETE ✅ 2026-03-17):**

**Context:** NVIDIA announced OpenClaw and NemoClaw at GTC 2026 (2026-03-16). OpenClaw is the community open-source agent platform. NemoClaw is NVIDIA's security layer on top: OpenShell (Landlock + seccomp + netns sandbox), a privacy router (local/cloud inference switching), and Nemotron model integration. Decision: adopt OpenClaw/NemoClaw as the agent runtime and wrap Babs integration around it, following the official DGX Spark playbook. Rationale: community troubleshooting resources, standard configuration, career familiarity.

1. ✅ OpenShell v0.0.6 installed at /usr/local/bin/openshell (static aarch64 binary)
2. ✅ NemoClaw v0.1.0 cloned at ~/NemoClaw and installed globally via npm
3. ✅ Docker daemon patched: default-cgroupns-mode=host (required for k3s-in-Docker on cgroup v2)
4. ✅ OpenShell gateway started (name: nemoclaw, Ready)
5. ✅ nvidia-nim provider configured (NVIDIA cloud, Nemotron Super via integrate.api.nvidia.com)
6. ✅ vllm-local provider configured (auto-detected our vllm-babs Docker container on :8000)
7. ✅ NemoClaw sandbox built and running (openclaw@2026.3.11 + NemoClaw plugin inside)
8. ✅ vLLM endpoint verified: inference routes OpenShell -> host.openshell.internal:8000 -> vllm-babs. Confirmed via vLLM access logs.
9. ✅ Babs workspace seeded: SOUL.md, IDENTITY.md, USER.md, TOOLS.md in /sandbox/.openclaw/workspace/. Source in ~/babs/openclaw-workspace/.
10. ✅ OpenClaw web dashboard accessible via Tailscale at http://100.109.213.22:18789/ (systemd service: openclaw-dashboard-tunnel). Script: /usr/local/bin/openclaw-dashboard-start.sh.
11. ✅ Gateway CORS fixed: added http://100.109.213.22:18789 to gateway.controlUi.allowedOrigins in /sandbox/.openclaw/openclaw.json.
12. ✅ OpenRouter provider configured in OpenClaw: Claude Sonnet 4.6, Opus 4.6, Gemini 2.5 Pro, Llama 3.3 70B, Nemotron 4 340B, DeepSeek R1, DeepSeek V3 Chat. API key stored in sandbox openclaw.json (not committed to git).
13. ✅ vllm-local added to OpenClaw model picker: Nemotron 3 Nano 30B (local, 65 tok/s, free).
14. ✅ Babs personality rewrite: SOUL.md, IDENTITY.md, USER.md updated -- personality always on, content creator duo context added, "no filler" clarified as AI catchphrases not personality.
15. ✅ Babs Bridge built: ~/babs/src/bridge/babs-bridge.py, HTTPS on port 7222, cert at /etc/babs-bridge-tls/, token in /etc/babs-bridge.env. NOT reachable from sandbox -- OpenShell 0.0.6 proxy has SSRF protection blocking all sandbox→private-IP connections. Parked until OpenShell adds host routing support.
16. ✅ Sandbox rebuilt in Proxy mode (OPENSHELL_SANDBOX_POLICY env var). Network policies active: babs_bridge, openrouter, nvidia, github, clawhub, openclaw_api, npm_registry, telegram. Policy at /tmp/nemoclaw-policy.yaml (re-apply after rebuild: openshell policy set nemoclaw --policy /tmp/nemoclaw-policy.yaml --wait).
17. ✅ Directory structure: ~/projects/ (dev work, CONTEXT.md convention), ~/lab/ (experiments, Babs stays out by default).
18. ✅ Model switcher: ~/babs/scripts/babs-model.sh. Subcommands: nano, sonnet, opus, deepseek, deepseek-r1, gemini, llama, list. Alias: babs-model. Updates /sandbox/.openclaw/openclaw.json + openshell inference routing.
19. ✅ Babs git access: /sandbox/babs cloned from github.com/phloids-code-forge/Babs.git. Credentials in /sandbox/.git-credentials (600). Babs can read, edit, commit, push directly. This is the primary way she accesses and modifies the repo.
20. ✅ babs-sync.sh: deprecated -- Babs uses git directly now. Script kept for reference.

**OpenClaw primary interface:** Use http://100.109.213.22:18789/#token=4a4569fb23163c74cd4a4124e02e467fd844141a2708d67b for Babs conversations.

**Re-seed after sandbox rebuild (pod restarts wipe /sandbox):**
```bash
ssh openshell-nemoclaw "mkdir -p /sandbox/.openclaw/workspace /sandbox/.ssh"
ssh openshell-nemoclaw "cat > /sandbox/.openclaw/openclaw.json" < /tmp/openclaw-post-rebuild.json
for f in SOUL IDENTITY USER TOOLS; do ssh openshell-nemoclaw "cat > /sandbox/.openclaw/workspace/${f}.md" < ~/babs/openclaw-workspace/${f}.md; done
ssh openshell-nemoclaw "cat > /sandbox/.git-credentials && chmod 600 /sandbox/.git-credentials" <<< 'https://TOKEN@github.com'
ssh openshell-nemoclaw "cd /sandbox && git clone https://github.com/phloids-code-forge/Babs.git babs"
ssh openshell-nemoclaw "git config --global credential.helper store && git config --global user.name 'Babs' && git config --global user.email 'babs@openclaw'"
openshell inference set --no-verify --provider vllm-local --model nemotron3-nano
sudo systemctl restart openclaw-dashboard-tunnel
```

**Latest handoff:** HANDOFF-2026-03-17-NEMOCLAW-4.md

## Key Filesystem Paths

| Path | Purpose |
|------|---------|
| `~/babs/` | This git repo. Config, docker, src, docs, scripts, seeds, tests. |
| `~/babs-data/` | Runtime data. Not in git. Models, qdrant, memory, logs, nats, cache. |
| `~/babs-data/models/nemotron3-super-nvfp4/` | Super weights (75GB). Parked until SM121 fix. |
| `~/babs-data/models/nemotron3-nano-nvfp4/` | Nano weights (active). |
| `~/babs-data/cache/` | vLLM compilation cache + build artifacts. |
| `~/babs-data/threads.db` | Persistent conversation thread storage (SQLite). |
| `~/babs-data/open-webui/` | Open WebUI persistent data. |
| `~/babs/scripts/super_v3_reasoning_parser.py` | Reasoning parser for Super model (not used with Nano). |
| `~/.local/bin/hf` | HuggingFace CLI. |
| `~/NemoClaw/` | NemoClaw source repo (v0.1.0, installed from here). |
| `~/.nemoclaw/credentials.json` | NemoClaw credentials (NVIDIA_API_KEY, mode 600). |
| `~/.openclaw/` | OpenClaw agent config (host-side; also present inside sandbox at /sandbox/.openclaw). |
| `~/.ssh/config` | Contains openshell-nemoclaw SSH entry for sandbox access. |
| `/sandbox/.openclaw/openclaw.json` | OpenClaw main config inside sandbox: providers, gateway CORS, OpenRouter key. Template (redacted) at ~/babs/openclaw-workspace/openclaw.template.json. |
| `~/babs/openclaw-workspace/` | Babs workspace seed files (version controlled). Deployed to /sandbox/.openclaw/workspace/ via SSH after rebuild. |
| `~/babs/src/bridge/babs-bridge.py` | HTTPS command relay (sandbox -> Spark). Port 7222, cert /etc/babs-bridge-tls/, token /etc/babs-bridge.env. Parked: OpenShell SSRF blocks sandbox->host. |
| `~/babs/scripts/babs-model.sh` | Model switcher. `babs-model <nano|sonnet|opus|deepseek|deepseek-r1|gemini|llama|list>` |
| `/tmp/nemoclaw-policy.yaml` | Active sandbox network policy. Re-apply after rebuild: `openshell policy set nemoclaw --policy /tmp/nemoclaw-policy.yaml --wait` |
| `/tmp/openclaw-post-rebuild.json` | openclaw.json with real keys. Use to restore after sandbox pod restart. |
| `~/projects/` | Dev projects. CONTEXT.md convention: no CONTEXT.md = read-only for Babs. |
| `~/lab/` | Personal experiments. Babs stays out by default. |
| `/sandbox/babs/` | Babs' live git clone of the repo. She reads/edits/pushes directly from here. |
| `/sandbox/.openclaw/workspace/` | Babs' workspace: SOUL.md, IDENTITY.md, USER.md, TOOLS.md. Re-seed after pod restart. |
| `/sandbox/.git-credentials` | GitHub PAT for Babs' git push access (mode 600). Re-seed after pod restart. |
| `/etc/babs-bridge-tls/` | Self-signed TLS cert + key for babs-bridge HTTPS. |

## Architecture Documents

The architecture is defined in two companion documents:

- **Design Philosophy** (`docs/babs-design-philosophy-v1_5.md`): Defines identity, autonomy, memory philosophy, learning constraints. Higher authority. If it conflicts with the architecture prompt, philosophy wins.
- **Architecture Prompt** (split across `docs/00-preamble-and-meta.md` through `docs/05-open-questions.md` plus `docs/INDEX.md`): The master engineering specification. Assembled via `scripts/assemble.sh`.

These docs are the source of truth. Read them before making architectural decisions.

## Working Preferences

- **Two steps at a time.** Don't give phloid long multi-step sequences.
- **No em dashes.** Ever. Use commas, periods, or restructure.
- **No corporate speak.** Write like an engineer.
- **phloid is direct and appreciates pushback.** Don't hedge. If something is wrong, say so.
- **115GB memory ceiling** on the Spark is a hard physical constraint. Every component must fit in the Memory Ledger.
- **Philosophy doc wins conflicts** with the architecture prompt. Always.

## Git

- Branch: `main`
- User: Dave / dave@babs.local
- Commit messages: imperative mood, concise.

## Serving Commands Reference

**Nano (current, stable):**
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

**Super (parked -- 14-16 tok/s single-node with Marlin patches, not yet interactive-fast):**
```bash
docker run -d --name vllm-babs \
  --gpus all --ipc=host -p 8000:8000 \
  -e VLLM_NVFP4_GEMM_BACKEND=marlin \
  -e VLLM_TEST_FORCE_FP8_MARLIN=1 \
  -e VLLM_MARLIN_USE_ATOMIC_ADD=1 \
  -v ~/babs-data/models/nemotron3-super-nvfp4:/model \
  -v ~/babs-data/cache:/root/.cache \
  -v ~/babs/scripts:/scripts \
  vllm-super \
  vllm serve /model \
  --served-model-name nemotron3-super \
  --dtype auto --kv-cache-dtype fp8 \
  --quantization modelopt_fp4 \
  --load-format fastsafetensors \
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

## NemoClaw Commands Reference

**Check gateway and sandbox status:**
```bash
openshell status
openshell sandbox list
```

**Switch inference route (local vLLM vs NVIDIA cloud):**
```bash
# Use our local vLLM (Nano or Super)
openshell inference set --no-verify --provider vllm-local --model nemotron3-nano

# Use NVIDIA cloud (Super via API -- useful while local Super is slow)
openshell inference set --provider nvidia-nim --model nvidia/nemotron-3-super-120b-a12b
```

**Run an OpenClaw agent query:**
```bash
ssh openshell-nemoclaw "openclaw agent --agent main --local -m 'your message' --session-id s1"
```

**Connect interactively to sandbox:**
```bash
openshell sandbox connect nemoclaw
# then inside: openclaw tui
```

**Rebuild sandbox after NemoClaw changes:**
```bash
export NVIDIA_API_KEY=$(python3 -c "import json; print(json.load(open('/home/dave/.nemoclaw/credentials.json'))['NVIDIA_API_KEY'])")
cd ~/NemoClaw && bash scripts/setup.sh
```

**Monitor network egress from sandbox:**
```bash
openshell term
```
