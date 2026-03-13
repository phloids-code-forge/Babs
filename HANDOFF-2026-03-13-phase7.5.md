# Session Handoff: 2026-03-13 Phase 7.5 Start

**Timestamp:** 2026-03-13 14:45 CDT
**Phase:** Phase 7.5 (Model Picker & OpenRouter Integration)
**Session lead:** Claude Code

---

## Super Model Investigation: Complete

### Findings

Nemotron 3 Super 120B-A12B NVFP4 **cannot run** on current vLLM versions (tested v26.02 NVIDIA official container).

**Root Cause:**
- Model uses `MIXED_PRECISION` quantization (defined in `hf_quant_config.json`)
- Combines FP8 (attention layers) + NVFP4 (MoE experts)
- vLLM only supports homogeneous quantization: `FP8`, `FP8_PER_CHANNEL_PER_TOKEN`, `FP8_PB_WO`, or `NVFP4`
- Validation error occurs during engine config creation, before any CUDA kernels run

**Not a kernel issue. Not an SM121 issue. Not a driver issue.**

**Driver Status:**
- Already running 590.48.01 (confirmed via `nvidia-smi`)
- No upgrade needed

**Attempted Fixes:**
1. ✅ Updated test script to use NVIDIA official container (nvcr.io/nvidia/vllm:26.02-py3)
2. ❌ Removed `--quantization modelopt_fp4` flag (still fails, reads from config)
3. ❌ Tried with `--dtype auto` (still fails at config validation)

**Error Message:**
```
ValidationError: 1 validation error for VllmConfig
  Value error, ModelOpt currently only supports: ['FP8', 'FP8_PER_CHANNEL_PER_TOKEN', 'FP8_PB_WO', 'NVFP4']
  quantizations in vLLM. Please check the `hf_quant_config.json` file for your model's quant configuration.
```

### Options Going Forward

**Option 1: Download FP8-only variant** (recommended path)
```bash
hf download nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8 \
  --local-dir ~/babs-data/models/nemotron3-super-fp8
```
- Size: ~100GB (vs 75GB for NVFP4)
- Should work with both NVIDIA official and community vLLM containers
- Requires ~25GB additional disk space

**Option 2: Try community vLLM builds**
- Test avarok/vllm-dgx-spark:v11 with Super (may have patches)
- Risk: May still fail or have same CUBLAS crashes as before

**Option 3: Wait for vLLM MIXED_PRECISION support**
- Monitor vLLM releases for `MIXED_PRECISION` support
- Timeline unknown

**Option 4: Phase 7.5 (chosen)**
- Build model picker with OpenRouter integration
- Try Super 120B via OpenRouter API (no download needed)
- Evaluate quality before committing to FP8 download

### Current State

**Nano is back online and stable:**
```bash
docker ps --filter name=vllm-babs
# vllm-babs   avarok/vllm-dgx-spark:v11   Up 10 minutes
```

**Super weights preserved:**
- Path: ~/babs-data/models/nemotron3-super-nvfp4/ (75GB)
- Do not delete (may be useful if vLLM adds MIXED_PRECISION support)

---

## Phase 7.5: Model Picker & OpenRouter Integration

### Objective

Enable trying large models via OpenRouter API before committing to local downloads. Solve the "download 100GB to test a model" problem.

### Architecture

**Components:**

1. **OpenRouter Integration Service** (src/supervisor/openrouter.py)
   - Fetch model catalog from OpenRouter API
   - Route inference requests to OpenRouter
   - Track costs per session, per model
   - Cache model list (24h TTL)

2. **Model Registry** (src/supervisor/model_registry.py)
   - Unified model catalog (local + OpenRouter)
   - Metadata: size, quantization, context window, cost
   - Memory footprint calculator (estimate RAM usage)
   - Local model scanner (detect what's downloaded)

3. **Model Picker UI** (src/dashboard/static/model_picker.html)
   - Table view: Name, Source (local/OpenRouter), Size, Cost, Status
   - Filters: Size, capability (reasoning/coding/vision), cost tier
   - Search bar (fuzzy match on model name)
   - Actions: Select, Download (if OpenRouter), Delete (if local)

4. **Download Agent** (src/workers/model_download_worker.py)
   - NATS subject: `worker.model_download`
   - Progress updates: `dashboard.model_download_progress.{job_id}`
   - HuggingFace CLI wrapper (hf download with progress)
   - Memory headroom check (ensure 115GB limit not exceeded)
   - Bandwidth throttling (max 50MB/s to avoid saturating network)
   - Pause/resume support (stateful progress tracking)

5. **Model Switcher** (Supervisor enhancement)
   - Support multiple inference backends (local vLLM + OpenRouter)
   - Route based on selected model
   - Graceful handoff (finish in-flight requests before switch)
   - Model warmup detection (wait for /health before routing)

6. **Cost Tracker** (src/supervisor/cost_tracker.py)
   - Session-level cost accumulation
   - Budget alerts (warn at $5, $10, $20 thresholds)
   - Cost comparison UI ("This conversation: $2.50 on OR vs $0 local")

7. **Trust Tier Enforcement** (Supervisor policy)
   - Tier 2/3 operations (code exec, file write) require local models
   - Dashboard shows trust level of current model
   - Block restricted operations if using OpenRouter

### Data Flow

**Model Selection:**
```
User clicks model in dashboard
  -> POST /api/model/select {"model_id": "openrouter/anthropic/claude-3.5"}
  -> Dashboard publishes to NATS: supervisor.model_switch
  -> Supervisor updates active_model config
  -> Supervisor responds with new model status
  -> Dashboard updates UI
```

**OpenRouter Inference:**
```
User sends message
  -> Dashboard publishes to NATS: supervisor.request
  -> Supervisor checks active_model
  -> If OpenRouter: route to OpenRouter API
  -> If local: route to vLLM
  -> Cost tracker updates session costs
  -> Response flows back via NATS
```

**Model Download:**
```
User clicks "Download" on OpenRouter model
  -> POST /api/model/download {"model_id": "nvidia/nemotron-3-super-fp8"}
  -> Dashboard checks memory headroom
  -> Dashboard publishes to NATS: worker.model_download
  -> Download agent picks up job
  -> Agent publishes progress: dashboard.model_download_progress.{job_id}
  -> Dashboard shows progress bar (real-time)
  -> On completion: agent updates model registry
  -> Dashboard refreshes model list
```

### File Structure

```
~/babs/
├── src/
│   ├── supervisor/
│   │   ├── supervisor.py (enhanced with model switching)
│   │   ├── openrouter.py (new)
│   │   ├── model_registry.py (new)
│   │   └── cost_tracker.py (new)
│   ├── workers/
│   │   └── model_download_worker.py (new)
│   └── dashboard/
│       ├── dashboard.py (add model APIs)
│       └── static/
│           ├── model_picker.html (new)
│           └── index.html (add model picker tab)
├── docker/
│   ├── docker-compose.model-download-worker.yml (new)
│   └── Dockerfile.model-download-worker (new)
└── config/
    └── model_registry.json (persisted catalog, git-ignored)
```

### Environment Variables

Add to `.env` (not in git):
```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
COST_BUDGET_WARNING_THRESHOLD=5.00
COST_BUDGET_LIMIT_THRESHOLD=20.00
MAX_DOWNLOAD_BANDWIDTH_MBPS=50
```

### Dependencies

**Python packages (add to requirements.txt):**
```
openai>=1.0.0  # OpenRouter uses OpenAI-compatible API
huggingface-hub>=0.20.0  # For hf download CLI
```

### Memory Ledger Impact

**New components:**
- Download agent: ~200MB (Python + HF CLI)
- Model registry cache: ~5MB (JSON)
- OpenRouter client: negligible (requests only)

**Total new footprint:** ~205MB / 115GB (0.2%)

**Still within budget.**

### Implementation Order

1. OpenRouter integration (API client, cost tracking)
2. Model registry (local scanner + OpenRouter catalog merge)
3. Dashboard model picker UI (read-only view first)
4. Model switching in Supervisor (route to OR or local)
5. Download agent (background worker with progress)
6. Smart download features (memory check, throttling, pause/resume)

### Testing Strategy

**Phase 1: OpenRouter only**
- Manually set OpenRouter API key
- Test inference routing
- Verify cost tracking
- No downloads yet

**Phase 2: Model picker UI**
- Display local + OpenRouter models
- Filter/search functionality
- Model selection (UI only, no switching)

**Phase 3: Model switching**
- Switch between Nano (local) and GPT-4 (OpenRouter)
- Verify graceful handoff
- Test Trust Tier enforcement

**Phase 4: Download agent**
- Download a small model (~5GB) to test pipeline
- Verify progress reporting
- Test pause/resume
- Test memory headroom check

**Phase 5: End-to-end**
- Try model via OpenRouter
- Decide to download
- Switch to local after download completes
- Verify cost savings in UI

---

## Current System State

### Containers Running

| Container | Status | Uptime |
|-----------|--------|--------|
| vllm-babs (Nano) | Running | 10 min |
| nats-babs | Running | 5 hours |
| babs-supervisor | Running | 5 hours |
| qdrant-babs | Running | 9 hours |
| babs-dashboard | Running | 5 hours |

### Known Issues

None. All Phase 7 components operational.

### Next Steps

1. Create OpenRouter API client (src/supervisor/openrouter.py)
2. Add /api/models/list endpoint to dashboard (merge local + OR)

---

## Files Modified This Session

- CLAUDE.md (updated Super findings, added Phase 7.5)
- scripts/test_nemotron_super.sh (fixed to use NVIDIA official container)
- HANDOFF-2026-03-13-phase7.5.md (this file)

## Commands for Next Session

**Check system status:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
curl http://localhost:3000/api/health
```

**Start Phase 7.5 development:**
```bash
cd ~/babs
# Create new files as outlined in File Structure section
```

**Rollback if needed:**
```bash
git log --oneline -5
git reset --hard de39182  # Last checkpoint before this session
```

---

**Session end:** 2026-03-13 14:45 CDT
**Phase 7.5 status:** Architecture defined, implementation pending
**Ready for:** OpenRouter integration development
