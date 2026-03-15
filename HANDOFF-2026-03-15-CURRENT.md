# Handoff: 2026-03-15 — Supervisor Hardening & Infrastructure

## What Happened This Session

Two distinct work blocks:

**Block 1: ComfyUI OOM protection**
ComfyUI hung during a generation and took the whole system down. Root cause: `cicc` (CUDA JIT compiler, UID 0 in container) consumed 3.3GB RAM uncapped. The kernel OOM killer had no good targets (container had oom_score_adj:0, session processes had 200), so it cascaded through pipewire, dbus, and systemd before the system became unresponsive. Required a hard reboot.

Fixes applied:
- `earlyoom` installed and running as a system service. Kills highest-scoring process when free RAM drops below 10%, before the kernel has to.
- `docker/docker-compose.comfyui.yml`: Added `memory: 70g` under `deploy.resources.limits`. Container now has a high OOM score so Docker kills it cleanly before session infrastructure is affected.

**Block 2: Supervisor infrastructure improvements**

Audited the actual source code (not just docs) and found the real state of the codebase. Fixed everything found, in order:

---

## Changes Made

### Bug Fixes

**`src/supervisor/workers.py`**
- Added `import logging` and `logger = logging.getLogger(__name__)`. The `record_success` and `record_violation` methods called `logger` but it was never imported -- would crash on first trust tier promotion.

**`src/supervisor/supervisor.py`**
- `route_to_openrouter()` was calling `self.openrouter_client.complete()` (sync) directly inside an `async def`, blocking the entire event loop for the duration of the API call. Wrapped in `loop.run_in_executor(None, lambda: ...)`.
- Removed two unused imports: `NATSTimeoutError`, `ScoredPoint`.

**`src/supervisor/reflection.py`**
- `summarize_thread()` was passing `self.supervisor.model_name` (e.g. `local/nemotron3-nano-nvfp4`) directly to vLLM, which expects `nemotron3-nano`. The model name mapping existed in the supervisor but the reflection loop bypassed it. Fixed to call `_map_to_vllm_model_name()`. Dreaming now actually works.

---

### Episodic Memory Retrieval

Added `retrieve_episodic_memory()` to `supervisor.py` (mirrors `retrieve_procedural_memory()`). Both routing paths (`route_to_vllm`, `route_to_openrouter`) now retrieve procedural and episodic memories in parallel (`asyncio.gather`) and inject both into the system prompt:

```
# Relevant Past Conversations
## <timestamp>
<LLM-generated summary of past thread>

# Relevant Procedural Memory
## <id> (domain: <domain>)
<instruction content>
```

The episodic collection will populate naturally as the dreaming loop runs (every 5 min, on non-default threads with 4+ messages).

---

### Babs Identity

Rewrote both worker system prompts grounded in `docs/babs-design-philosophy-v1_5.md`.

**`general_worker`** -- Oracle archetype. Situational awareness, calm under pressure, dry wit, direct communication, loyalty without sycophancy. Work mode default. She is the interface; she synthesizes external information in her own voice.

**`coding_worker`** -- Same identity, coding focus. Code Before Memory rule explicit: if a deterministic computation can answer the question, write the code and run it. Execution discipline: write, run, report actual output, iterate on errors.

---

### New Tools

**`src/supervisor/tool_files.py`**
- `read_file` (Tier 0): reads any text file, optional line range, truncates at 500 lines. Both workers have access.
- `write_file` (Tier 2): creates/overwrites files, requires approval. Coding worker only.

**`src/supervisor/tool_shell.py`**
- `shell` (Tier 2): runs arbitrary shell commands via `bash -c`, captures stdout/stderr, configurable timeout (default 60s, max 300s), requires approval. Coding worker only.

Tool registration in supervisor (all five tools now log at startup):
```
Registered tool: web_search (Tier 0)
Registered tool: execute_python (Tier 1)
Registered tool: read_file (Tier 0)
Registered tool: write_file (Tier 2)
Registered tool: shell (Tier 2)
```

---

### Persistent Thread Storage

**`src/supervisor/thread_store.py`** -- new SQLite-backed store.

- Database: `/home/dave/babs-data/threads.db` (absolute path required -- container runs as root, `~` expands to `/root` not `/home/dave`)
- Schema: `messages` table (thread_id, seq, message JSON, created_at) + `thread_meta` (thread_id, updated_at)
- Lazy load: on first access, thread is loaded from DB if not in memory cache
- Save: after each complete request cycle in both routing paths
- Operations: `load()`, `save()`, `list_threads()`, `delete()`, `close()`

Threads now survive supervisor restarts. Previously all conversation context was lost on any restart.

---

## Current Tool Inventory

| Tool | Tier | Workers | Description |
|------|------|---------|-------------|
| `web_search` | 0 | general, coding | SearXNG via G14 |
| `read_file` | 0 | general, coding | Read any text file |
| `execute_python` | 1 | coding | Jupyter kernel execution |
| `write_file` | 2 | coding | Create/overwrite files |
| `shell` | 2 | coding | Run shell commands |

---

## What's Running

| Container | Status | Notes |
|-----------|--------|-------|
| `vllm-babs` | Running | Nemotron 3 Nano NVFP4, 65+ tok/s |
| `nats-babs` | Running | |
| `babs-supervisor` | Running | All 5 tools registered, threads persisted |
| `qdrant-babs` | Running | procedural_memory (5 seeds), episodic_memory, artifacts |
| `babs-dashboard` | Running | http://100.109.213.22:3000 |
| `babs-jupyter` | Running | Python execution kernel |
| `comfyui-babs` | Running | http://100.109.213.22:8188 -- 70GB memory cap |

---

## Known Issues / Next Session

- **Voice interface (Whisper):** Running on G14 at port 9000, wired to nothing. Straightforward to connect to dashboard mic input.
- **Thread context growth:** No pruning strategy yet. Long threads will eventually exceed the model's context window. Need a sliding window or summarization-based truncation.
- **Dreaming loop:** Now works correctly with the model name fix. Will generate first real episodic memories as threads accumulate.
- **Super model:** Still parked. Check avarok for v24 image periodically.
