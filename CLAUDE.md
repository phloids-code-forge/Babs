# Project Babs: Claude Code Context

## What This Is

Babs is a local-first autonomous AI assistant running on a two-node home cluster. This repo contains the architecture documents, configuration, scripts, and source code for the system. You are helping phloid build it.

## Hardware

- **Primary node (Spark):** MSI EdgeXpert MS-C931 (DGX Spark platform). GB10 Grace Blackwell Superchip, 128GB unified LPDDR5x, 4TB NVMe, DGX OS (Ubuntu 24.04 ARM64). Hostname: `spark`. This is where you are running.
- **Auxiliary node (G14):** ASUS ROG Zephyrus G14, headless Ubuntu 24.04 LTS Server, RTX 3060 Mobile 6GB, 40GB RAM, 1TB SSD. At `ssh g14` (Tailscale 100.101.118.78). OS and networking complete, service deployment pending.
- **Dev machine (PX13):** Dave's workstation. Windows. Connects via VS Code Remote SSH over Tailscale.

## Current State (2026-03-13)

### What's Running

| Container | Image | Port | Status |
|-----------|-------|------|--------|
| vllm-babs | avarok/vllm-dgx-spark:v11 | 8000 | Running stable. Nemotron 3 Nano 30B-A3B NVFP4. 65+ tok/s. |
| nats-babs | nats:latest | 4222, 8222, 6222 | Running. JetStream enabled. Data at ~/babs-data/nats. |
| babs-supervisor | docker-supervisor (custom) | -- | Running. Routes NATS -> vLLM, manages tools, retrieves from Procedural Memory. |
| qdrant-babs | qdrant/qdrant:latest | 6333, 6334 | Running. Procedural Memory collection (5 seed entries, need re-embedding). |
| babs-dashboard | docker-dashboard (custom) | 3000 | Running. Primary interface. http://100.109.213.22:3000 |
| open-webui | ghcr.io/open-webui/open-webui:main | 8080 | Running (to be stopped, replaced by dashboard). |

### What Happened

- Nemotron 3 Super 120B-A12B NVFP4 was the intended Supervisor model. It loads and serves at 14.8 tok/s but crashes with `cudaErrorIllegalInstruction` on SM121 during extended generation. Tried `--enforce-eager` but it did not fix the crash. The model launched 2026-03-11; SM121 kernel fixes are expected from the community.
- Fell back to Nemotron 3 Nano 30B-A3B NVFP4. Community-confirmed stable on the Spark. Working with `--reasoning-parser deepseek_r1`. Thinking must be enabled (`enable_thinking: true`); disabling it causes content to be null. **This is the day-one Supervisor model.**
- Super weights are still on disk at `~/babs-data/models/nemotron3-super-nvfp4/` (75GB). Do not delete.

### Dev Environment (2026-03-12)

- **Claude Code:** Installed and working. You are it.
- **VS Code Remote SSH:** Connected to this repo via Tailscale. Antigravity also connected.
- **Continue extension:** Configured in VS Code, pointing at vLLM via Tailscale IP.
- **Hostname:** Changed from `edgexpert-4272` to `spark`.

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

**Super Model Upgrade: Deferred.**
Nemotron 3 Super 120B crashes on SM121. Weights parked at ~/babs-data/models/nemotron3-super-nvfp4/.
Will revisit when a fix lands. Nano is the active Supervisor model and is running stable.

**Phase 7 Complete (2026-03-13).**
Full stack operational: Dashboard -> NATS -> Supervisor -> Procedural Memory + Tools -> vLLM.

**Next: Phase 8** (Workers and code execution) or cleanup (stop Open WebUI, re-embed Procedural Memory seeds).

**Latest handoff:** HANDOFF-2026-03-13-CURRENT.md

## Key Filesystem Paths

| Path | Purpose |
|------|---------|
| `~/babs/` | This git repo. Config, docker, src, docs, scripts, seeds, tests. |
| `~/babs-data/` | Runtime data. Not in git. Models, qdrant, memory, logs, nats, cache. |
| `~/babs-data/models/nemotron3-super-nvfp4/` | Super weights (75GB). Parked until SM121 fix. |
| `~/babs-data/models/nemotron3-nano-nvfp4/` | Nano weights (active). |
| `~/babs-data/cache/` | vLLM compilation cache + build artifacts. |
| `~/babs-data/open-webui/` | Open WebUI persistent data. |
| `~/babs/scripts/super_v3_reasoning_parser.py` | Reasoning parser for Super model (not used with Nano). |
| `~/.local/bin/hf` | HuggingFace CLI. |

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

**Super (parked, crashes on SM121):**
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
