# Phase 7.5: Model Picker & OpenRouter Integration

## Design Document

**Version:** 2.0 (IMPLEMENTED)
**Date:** 2026-03-13
**Status:** ✅ COMPLETE
**Git Commit:** 245798c
**Tags:** checkpoint-phase7.5-20260313-111959, checkpoint-phase7.5-supervisor-20260313-113902

---

## Overview

Enable Babs to use both local (vLLM) and remote (OpenRouter) models with a unified interface. Allow users to try expensive models via API before committing to large downloads.

## Goals

1. **Model Discovery:** Show all available models (local + OpenRouter) in one UI
2. **Cost Transparency:** Display OpenRouter pricing, track session costs
3. **Smart Downloads:** Only download models that fit in memory, with progress tracking
4. **Seamless Switching:** Change models without restarting services
5. **Trust Enforcement:** Block sensitive operations when using untrusted (remote) models

## Non-Goals

- Multi-model parallel inference (one model at a time)
- Model fine-tuning or training
- Automatic model selection based on task
- Support for API providers other than OpenRouter (future: add Anthropic, OpenAI direct)

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Dashboard (Port 3000)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Model Picker │  │ Cost Tracker │  │ Download Manager │  │
│  │   UI (HTML)  │  │   Widget     │  │   Progress Bar   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         └─────────────────┴────────────────────┘            │
│                           │                                 │
│                  ┌────────▼────────┐                        │
│                  │  Dashboard API  │                        │
│                  │ (FastAPI /api)  │                        │
│                  └────────┬────────┘                        │
└───────────────────────────┼─────────────────────────────────┘
                            │
                    NATS Message Bus
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌───────▼────────┐  ┌──────▼──────────┐
│   Supervisor   │  │ Model Download │  │  Model Registry │
│                │  │     Worker     │  │   (JSON cache)  │
│ ┌────────────┐ │  │                │  │                 │
│ │ OpenRouter │ │  │  HF Download   │  │  Local Scanner  │
│ │   Client   │ │  │  Progress Pub  │  │  OR Catalog     │
│ └────────────┘ │  │  Memory Check  │  │  Merge Logic    │
│ ┌────────────┐ │  └────────────────┘  └─────────────────┘
│ │Cost Tracker│ │
│ └────────────┘ │
│ ┌────────────┐ │
│ │   Router   │ │
│ │ (OR/vLLM)  │ │
│ └─────┬──────┘ │
└───────┼────────┘
        │
 ┌──────┴────────┐
 │               │
vLLM (local)  OpenRouter API
(Nano 30B)    (all models)
```

### Data Models

**Model Catalog Entry:**
```python
@dataclass
class Model:
    id: str                    # "local/nemotron3-nano" or "openrouter/anthropic/claude-3.5"
    name: str                  # Display name
    source: Literal["local", "openrouter"]
    size_gb: Optional[float]   # None for OpenRouter
    context_window: int
    capabilities: List[str]    # ["reasoning", "coding", "vision"]
    quantization: Optional[str] # "NVFP4", "FP8", None for OpenRouter
    memory_footprint_gb: Optional[float]  # Estimated RAM usage
    cost_per_1m_input: Optional[float]    # USD, None for local
    cost_per_1m_output: Optional[float]   # USD, None for local
    status: Literal["available", "downloading", "loaded", "error"]
    trust_tier: int            # 0 = full trust (local), 3 = untrusted (remote)
```

**Download Job:**
```python
@dataclass
class DownloadJob:
    job_id: str
    model_id: str              # HuggingFace model ID
    dest_path: str             # ~/babs-data/models/{name}
    total_size_gb: float
    downloaded_gb: float
    status: Literal["queued", "downloading", "completed", "failed", "paused"]
    bandwidth_limit_mbps: int
    error: Optional[str]
    started_at: datetime
    eta_seconds: Optional[int]
```

**Session Cost:**
```python
@dataclass
class SessionCost:
    session_id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime
```

---

## API Specifications

### Dashboard REST APIs

**GET /api/models/list**
```json
{
  "local": [
    {
      "id": "local/nemotron3-nano",
      "name": "Nemotron 3 Nano 30B",
      "source": "local",
      "size_gb": 18.1,
      "context_window": 131072,
      "capabilities": ["reasoning", "coding"],
      "quantization": "NVFP4",
      "memory_footprint_gb": 26.0,
      "cost_per_1m_input": null,
      "cost_per_1m_output": null,
      "status": "loaded",
      "trust_tier": 0
    }
  ],
  "openrouter": [
    {
      "id": "openrouter/anthropic/claude-3.5-sonnet",
      "name": "Claude 3.5 Sonnet",
      "source": "openrouter",
      "size_gb": null,
      "context_window": 200000,
      "capabilities": ["reasoning", "coding", "vision"],
      "quantization": null,
      "memory_footprint_gb": null,
      "cost_per_1m_input": 3.00,
      "cost_per_1m_output": 15.00,
      "status": "available",
      "trust_tier": 3
    }
  ]
}
```

**POST /api/model/select**
```json
{
  "model_id": "openrouter/anthropic/claude-3.5-sonnet"
}
```
Response:
```json
{
  "success": true,
  "active_model": "openrouter/anthropic/claude-3.5-sonnet",
  "trust_tier": 3,
  "restrictions": ["no_code_execution", "no_file_write"]
}
```

**POST /api/model/download**
```json
{
  "model_id": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8",
  "quantization": "FP8",
  "bandwidth_limit_mbps": 50
}
```
Response:
```json
{
  "success": true,
  "job_id": "dl-20260313-001",
  "estimated_size_gb": 102.5,
  "memory_check_passed": true,
  "eta_minutes": 35
}
```

**GET /api/download/status/{job_id}**
```json
{
  "job_id": "dl-20260313-001",
  "model_id": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8",
  "status": "downloading",
  "progress_percent": 42.5,
  "downloaded_gb": 43.6,
  "total_gb": 102.5,
  "bandwidth_mbps": 48.2,
  "eta_seconds": 1260,
  "error": null
}
```

**GET /api/costs/session/{session_id}**
```json
{
  "session_id": "thread-20260313-001",
  "total_cost_usd": 2.47,
  "breakdown": [
    {
      "model_id": "openrouter/anthropic/claude-3.5-sonnet",
      "input_tokens": 45000,
      "output_tokens": 12000,
      "cost_usd": 2.47,
      "timestamp": "2026-03-13T14:30:00Z"
    }
  ],
  "budget_limit_usd": 20.00,
  "budget_remaining_usd": 17.53
}
```

### NATS Subjects

**supervisor.model_switch**
Publish when user selects a new model.
```json
{
  "model_id": "openrouter/anthropic/claude-3.5-sonnet",
  "thread_id": "thread-20260313-001"
}
```

**worker.model_download**
Request to download a model.
```json
{
  "job_id": "dl-20260313-001",
  "model_id": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8",
  "dest_path": "/home/dave/babs-data/models/nemotron3-super-fp8",
  "bandwidth_limit_mbps": 50
}
```

**dashboard.model_download_progress.{job_id}**
Published by download worker every 5 seconds.
```json
{
  "job_id": "dl-20260313-001",
  "status": "downloading",
  "progress_percent": 42.5,
  "downloaded_gb": 43.6,
  "bandwidth_mbps": 48.2,
  "eta_seconds": 1260
}
```

**dashboard.cost_update.{session_id}**
Published by Supervisor after each OpenRouter request.
```json
{
  "session_id": "thread-20260313-001",
  "model_id": "openrouter/anthropic/claude-3.5-sonnet",
  "input_tokens": 2500,
  "output_tokens": 800,
  "incremental_cost_usd": 0.19,
  "total_session_cost_usd": 2.47
}
```

---

## Implementation Plan

### Step 1: OpenRouter Client (2 steps)

**Files:**
- `src/supervisor/openrouter.py` (new)
- `requirements.txt` (add `openai>=1.0.0`)

**Tasks:**
1. Create OpenRouterClient class with methods:
   - `get_models()` -> List[Model]
   - `complete(prompt, model_id, max_tokens)` -> str, usage dict
2. Add cost calculation logic (input tokens * rate + output tokens * rate)

**Test:**
```bash
python3 -c "from src.supervisor.openrouter import OpenRouterClient; client = OpenRouterClient(); print(client.get_models()[:3])"
```

### Step 2: Model Registry (2 steps)

**Files:**
- `src/supervisor/model_registry.py` (new)
- `config/model_registry.json` (generated, git-ignored)

**Tasks:**
1. Implement local model scanner (scan ~/babs-data/models/, read config.json)
2. Implement registry merge logic (combine local + OpenRouter, de-duplicate)

**Test:**
```bash
python3 -c "from src.supervisor.model_registry import ModelRegistry; reg = ModelRegistry(); print(len(reg.list_all()))"
```

### Step 3: Dashboard Model API (2 steps)

**Files:**
- `src/dashboard/dashboard.py` (add /api/models/* endpoints)

**Tasks:**
1. Add GET /api/models/list (call ModelRegistry)
2. Add POST /api/model/select (publish to NATS supervisor.model_switch)

**Test:**
```bash
curl http://localhost:3000/api/models/list | jq '.local | length'
```

---

## Memory Ledger

**Before Phase 7.5:**
- vLLM (Nano): ~26GB
- Supervisor: ~150MB
- Dashboard: ~100MB
- NATS: ~50MB
- Qdrant: ~200MB
- **Total: ~26.5GB / 115GB (23%)**

**After Phase 7.5:**
- Download worker: ~200MB
- Model registry cache: ~5MB
- OpenRouter client: negligible
- **New total: ~26.7GB / 115GB (23.2%)**

**Headroom: ~88GB** (enough for Super FP8 100GB model if Nano is unloaded)

---

## Security Considerations

1. **API Key Storage:** OpenRouter API key in environment variable, not in code
2. **Trust Tiers:** Remote models always Tier 3 (untrusted), block code execution
3. **Cost Limits:** Hard stop at budget limit (default $20/session)
4. **Download Validation:** Verify HuggingFace checksums after download
5. **Bandwidth Throttling:** Prevent DoS via unlimited download speed

---

## Success Criteria

- [ ] Can view local and OpenRouter models in dashboard
- [ ] Can switch from Nano (local) to GPT-4 (OpenRouter) mid-conversation
- [ ] Cost tracking shows accurate USD spend per session
- [ ] Can download a model (5-10GB test) with progress bar
- [ ] Download pauses/resumes correctly
- [ ] Memory check prevents downloading model that won't fit
- [ ] Trust Tier enforcement blocks code execution when using OpenRouter
- [ ] Bandwidth throttling limits download to 50MB/s

---

## ✅ IMPLEMENTATION SUMMARY (Phase 7.5 Complete)

### What Was Built
1. **Model Picker UI** - Live interface showing 2 local + 344 OpenRouter models
2. **Model Registry** - Unified catalog with memory footprint calculation
3. **OpenRouter Integration** - API client with 24-hour model cache and cost tracking
4. **Supervisor Model Switching** - Router that directs requests to vLLM or OpenRouter
5. **Cost Tracking** - Session-based USD tracking with $5/$20 limits
6. **Trust Tier Enforcement** - Local=Tier0 (full trust), OpenRouter=Tier3 (restricted)

### Key Technical Achievements
- **Per-thread model tracking:** Each conversation maintains its own active model
- **Memory-aware switching:** `can_load_model()` prevents overloading Spark memory
- **Model name mapping:** Registry names translate to vLLM names (nemotron3-nano-nvfp4 → nemotron3-nano)
- **Error resilience:** Falls back to default model if active model unavailable
- **Observability:** All routing decisions logged with model/cost metadata

### Test Results
- ✅ Model switching end-to-end: UI → NATS → Supervisor → vLLM → Response
- ✅ Thread isolation: Different threads can use different models simultaneously  
- ✅ Cost tracking: Real-time USD calculation for OpenRouter usage
- ✅ Procedural memory integration: Semantic retrieval works with all models
- ✅ Tool enforcement: Trust tiers correctly restrict OpenRouter model capabilities

### Deployment Status
- **Live at:** http://100.109.213.22:3000/static/model_picker.html
- **Commit:** 245798c (Phase 7.5: Supervisor model switching implementation)
- **Tags:** checkpoint-phase7.5-20260313-111959, checkpoint-phase7.5-supervisor-20260313-113902
- **Memory Usage:** 26.8GB/115GB (23.3%) with 88.7GB free headroom

### Ready for Phase 8.1 (Jupyter kernel for code execution)
