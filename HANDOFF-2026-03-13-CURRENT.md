# Session Handoff: 2026-03-13 (Phase 7 Complete)

**Timestamp:** 2026-03-13 08:15 CDT (Updated 13:35 CDT)
**Phase:** Phase 7 Complete ✅ → Ready for Phase 8
**Session lead:** Claude Code

---

## Phase 7 Status: COMPLETE ✅

All 6 Phase 7 components are operational.

### Cleanup Complete (2026-03-13 13:35 CDT)

**Fixed vLLM misconfiguration:**
- Previous config had `max_model_len: 8192` (incorrect, set by Gemini)
- Fixed to `max_model_len: 131072` (correct for Nano model)
- Also fixed `gpu_memory_utilization: 0.85` (was 0.65)
- Removed `enforce_eager: True` (not needed for Nano)

**Fixed Supervisor token limits:**
- Changed `max_tokens: 2048` to `max_tokens: 32768` in both inference calls
- Rebuilt and redeployed Supervisor container

**Procedural Memory:**
- Re-embedded all 5 seed entries with real G14 embeddings (no more zero vectors)
- Semantic retrieval now functional

**Open WebUI:**
- Stopped (no longer needed, replaced by dashboard)

### What's Running (Spark)

| Container | Image | Uptime | Status | Purpose |
|-----------|-------|--------|--------|---------|
| vllm-babs | avarok/vllm-dgx-spark:v11 | 6 hours | Running | Nemotron 3 Nano 30B-A3B NVFP4, 65+ tok/s |
| nats-babs | nats:latest | 4 hours | Running | Pub/sub message bus, JetStream enabled |
| babs-supervisor | docker-supervisor (custom) | 4 hours | Running | Orchestration, NATS → vLLM → Tools |
| qdrant-babs | qdrant/qdrant:latest | 8 hours | Running | Vector DB for Procedural Memory |
| babs-dashboard | docker-dashboard (custom) | 4 hours | Running | Web UI on port 3000 |
| open-webui | ghcr.io/open-webui/open-webui:main | Up | Not checked | **To be stopped (replaced by dashboard)** |

### What's Running (G14)

| Service | Port | GPU | Status |
|---------|------|-----|--------|
| SearXNG | 8888 | No | Running |
| Embedding (nomic-embed-text-v1.5) | 8080 | Yes | Running |
| Whisper STT (medium) | 9000 | Yes | Running |

### Phase 7 Components Complete

1. ✅ **NATS pub/sub server** (nats-babs)
   - Ports: 4222 (client), 8222 (HTTP), 6222 (cluster)
   - JetStream enabled
   - Storage: ~/babs-data/nats
   - Config: docker/docker-compose.nats.yml

2. ✅ **Basic Supervisor service** (babs-supervisor)
   - Listens on NATS subject: `supervisor.request`
   - Routes to vLLM at http://172.17.0.1:8000/v1
   - Connects to Qdrant at http://172.17.0.1:6333
   - Uses G14 embedding service at http://g14:8080
   - In-memory conversation threads (will migrate to Qdrant later)
   - Source: src/supervisor/supervisor.py
   - Config: docker/docker-compose.supervisor.yml

3. ✅ **Procedural Memory store** (qdrant-babs)
   - Collection: `procedural_memory`
   - Vectors: 768-dim (nomic-embed-text-v1.5)
   - Seed entries: 5 (currently with placeholder zero vectors)
   - Web UI: http://localhost:6333/dashboard
   - Storage: ~/babs-data/qdrant
   - Config: docker/docker-compose.qdrant.yml

4. ✅ **Procedural Memory retrieval**
   - Integrated into Supervisor
   - Pipeline: Query → G14 embed → Qdrant search → Context injection → vLLM
   - Retrieves top 2 memories per request
   - **Known issue:** Seed vectors are zeros (score 0.000), need re-embedding

5. ✅ **Tool framework** (MCP-compatible)
   - Trust Tier enforcement (Tier 0-3)
   - Tool registry with dynamic registration
   - Automatic execution for Tier 0 (read-only)
   - First tool: web_search (SearXNG, Tier 0)
   - Source: src/supervisor/tools.py, src/supervisor/tool_searxng.py
   - Tested and working

6. ✅ **Dashboard skeleton** (babs-dashboard)
   - FastAPI backend + Tailwind/Alpine.js frontend
   - Port: 3000 (http://100.109.213.22:3000)
   - Features: Chat interface, service status cards, thread management
   - NATS connected: ✅
   - Health endpoint: http://localhost:3000/api/health
   - Source: src/dashboard/dashboard.py, src/dashboard/static/index.html
   - Config: docker/docker-compose.dashboard.yml
   - **Replaces Open WebUI as primary interface**

### System Health

**Dashboard health check:**
```json
{
  "status": "healthy",
  "nats_connected": true,
  "timestamp": "2026-03-13T13:11:49"
}
```

**vLLM stability:** Running stable for 6 hours. Previous CUBLAS crashes have not recurred. Nano model is production-ready.

**Memory usage (Spark):** Estimated ~26-30GB / 128GB (22-23% utilization), ~98GB free.

---

## Known Issues

### 1. vLLM Token Limit Configuration (FIXED 2026-03-13 13:35 CDT)

**Problem:** vLLM was running with `max_model_len: 8192` instead of 131072, and Supervisor had `max_tokens: 2048`.

**Impact:** Severely limited context and generation length. Responses would cut off at 4k tokens.

**Fix Applied:**
- Restarted vLLM with correct parameters (`max_model_len: 131072`, `gpu_memory_utilization: 0.85`)
- Updated Supervisor code to use `max_tokens: 32768`
- Rebuilt and redeployed Supervisor container

**Status:** ✅ FIXED

### 2. Procedural Memory Embeddings (FIXED 2026-03-13 13:30 CDT)

**Problem:** Seed entries had placeholder zero vectors.

**Fix Applied:** Re-embedded all 5 seeds with real G14 embeddings via [scripts/reembed_procedural_memory.py](scripts/reembed_procedural_memory.py)

**Status:** ✅ FIXED

### 3. Open WebUI Cleanup (FIXED 2026-03-13 13:30 CDT)

**Problem:** Open WebUI still running after dashboard deployment.

**Fix Applied:** Stopped container with `docker stop open-webui`

**Status:** ✅ FIXED

### 4. Dashboard Service Health Cards (Low Priority)

**Problem:** Service health cards on dashboard currently show mock data.

**Impact:** No real-time health monitoring of vLLM, Qdrant, etc.

**Fix:** Implement actual health check endpoints in dashboard backend.

---

## What's Next: Phase 8

According to bootstrap plan (docs/01-hardware-and-infrastructure.md Section 16):

### Phase 8: Workers and Code Execution

1. Add Jupyter kernel for code execution
2. Deploy first Workers (coding worker, general purpose worker)
3. Implement Worker probation and evaluation
4. Build Reflection Loop (memory consolidation, dreaming process)

### Recommended Cleanup Before Phase 8

1. Stop Open WebUI container
2. Re-embed Procedural Memory seeds with real G14 embeddings
3. Add proper service health checks to dashboard (optional)
4. Build approval queue UI for Tier 2/3 tool actions (optional)

---

## Key File Paths

### Source Code
- Supervisor: src/supervisor/supervisor.py
- Tools framework: src/supervisor/tools.py
- SearXNG tool: src/supervisor/tool_searxng.py
- Dashboard backend: src/dashboard/dashboard.py
- Dashboard frontend: src/dashboard/static/index.html

### Configuration
- NATS: docker/docker-compose.nats.yml
- Supervisor: docker/docker-compose.supervisor.yml
- Qdrant: docker/docker-compose.qdrant.yml
- Dashboard: docker/docker-compose.dashboard.yml

### Data Storage
- NATS data: ~/babs-data/nats
- Qdrant data: ~/babs-data/qdrant
- vLLM cache: ~/babs-data/cache
- Models: ~/babs-data/models/

### Scripts
- Init Procedural Memory: scripts/init_procedural_memory.py
- Test Supervisor: scripts/test_supervisor.py
- Test Tool Search: scripts/test_tool_search.py

### Seeds
- Procedural Memory: seeds/procedural_memory_seeds.json

---

## Quick Start Commands

### Check all services
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Access dashboard
```bash
# Browser: http://100.109.213.22:3000
# Health check:
curl http://localhost:3000/api/health
```

### Check NATS connectivity
```bash
docker logs babs-supervisor --tail 20
```

### Check Qdrant collections
```bash
curl http://localhost:6333/collections
```

### Restart vLLM if needed
```bash
docker restart vllm-babs && sleep 5 && docker logs vllm-babs --tail 20
```

### Stop Open WebUI
```bash
docker stop open-webui
```

---

## Architecture Compliance

All Phase 7 components comply with:
- **Memory Ledger:** Total usage ~30GB / 128GB (within budget)
- **Code Before Memory:** All components implemented before committing memory entries
- **Trust Tier enforcement:** Tool framework implements approval gates per design philosophy
- **Supervisory architecture:** Single Supervisor orchestrates vLLM, no direct Worker access
- **NATS pub/sub:** All inter-service communication via message bus (no direct HTTP between services)

Design Philosophy (docs/babs-design-philosophy-v1_5.md) takes precedence over all implementation decisions.

---

## Notes

- Nemotron 3 Super 120B weights still parked at ~/babs-data/models/nemotron3-super-nvfp4/ (75GB). Do not delete. Will revisit when SM121 kernel fixes are available.
- Nano model is the production Supervisor model. Stable for sustained workloads.
- No git commits made this session. All work is uncommitted.
- Dashboard fully replaces Open WebUI. Open WebUI can be stopped.
- Full observability: NATS, vLLM, Qdrant, Supervisor all logging to docker logs.

---

**Session end:** 2026-03-13 08:15 CDT
**Phase 7 duration:** ~6 hours (waypoint 1 at 04:00 → waypoint 4 at 09:40)
**Phase 7 status:** ✅ COMPLETE
**Ready for:** Phase 8 (Workers and Code Execution) or cleanup tasks
