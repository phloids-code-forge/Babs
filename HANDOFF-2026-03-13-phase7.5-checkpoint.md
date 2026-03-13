# Session Handoff: Phase 7.5 Checkpoint

**Timestamp:** 2026-03-13 16:10 CDT  
**Phase:** Phase 7.5 Model Picker - Core Implementation Complete  
**Session lead:** Claude Code  

## ✅ Phase 7.5 Core Infrastructure Complete

### What's Working

**OpenRouter Integration (src/supervisor/openrouter.py):**
- Connects to OpenRouter API (344 models available)
- Cost tracking with $5 warning / $20 hard limit per session
- 24-hour cache for model catalog
- Usage stats tracking per completion

**Model Registry (src/supervisor/model_registry.py):**
- Scans local models at `~/babs-data/models/`
- Merges local + OpenRouter catalogs
- Memory footprint calculation (Nano: 26.3GB, Super: 97.3GB)
- Memory headroom checks (88GB free with Nano loaded)
- Persistent cache at `~/babs/config/model_registry.json`

**Dashboard APIs (src/dashboard/dashboard.py):**
- `GET /api/models/list` - Returns local + OpenRouter models
- `POST /api/model/select` - Publishes to NATS `supervisor.model_switch`
- `GET /api/costs/session/{id}` - Session cost tracking
- `GET /api/memory/summary` - Memory usage stats

**Model Picker UI (src/dashboard/static/model_picker.html):**
- Alpine.js + Tailwind interface
- Real-time search and filtering (Local/OpenRouter)
- Memory stats dashboard (shows 88GB free)
- Active model tracking (Nemotron 3 Nano)
- Trust tier display (colors: green=full, red=untrusted)
- Notification system for actions

**Docker Configuration:**
- Updated docker-compose.dashboard.yml with OpenRouter API key
- Static file serving via FastAPI `app.mount("/static", StaticFiles)`
- Environment variables: `MODELS_DIR`, `CACHE_FILE`, `OPENROUTER_API_KEY`

### URLs Live

- **Dashboard:** http://100.109.213.22:3000
- **Model Picker:** http://100.109.213.22:3000/static/model_picker.html
- **API Endpoint:** http://100.109.213.22:3000/api/models/list

### Current System State

**Containers Running:**
- ✅ vllm-babs (Nano 30B) - Stable, 65+ tok/s
- ✅ nats-babs - JetStream enabled
- ✅ babs-supervisor - Listening for `model_switch` messages
- ✅ qdrant-babs - Procedural Memory (5 entries)
- ✅ babs-dashboard - Phase 7.5 APIs + UI live

**OpenRouter Models Available:** 344
- x-ai/grok-4.20-multi-agent-beta ($2/$6 per 1M tokens)
- openrouter/hunter-alpha (Free tier)
- anthropic/claude-3.5-sonnet
- google/gemini-2.0-flash-thinking-exp
- meta-llama/llama-3.3-70b-instruct

**Local Models Detected:**
1. `local/nemotron3-nano-nvfp4` (17.5GB, loaded, 26.3GB RAM)
2. `local/nemotron3-super-nvfp4` (74.8GB, available, 97.3GB RAM)

**Memory Status:**
- Total capacity: 115GB
- Nano loaded: 26.3GB
- Free: 88GB
- Super footprint: 97.3GB (cannot load alongside Nano)

### What's Next

**Pending for Full Phase 7.5:**
1. **Supervisor Model Switching** - Handle `supervisor.model_switch` messages
2. **Download Agent** - Background NATS worker for HuggingFace downloads
3. **Cost Widget** - Add cost tracker to main dashboard UI
4. **Trust Tier Enforcement** - Block sensitive ops on untrusted models

**Implementation Priority:**
1. **Supervisor enhancement** - Route to OpenRouter vs vLLM based on active model
2. **Download endpoints** - `/api/model/download` with progress tracking
3. **Cost UI** - Real-time cost display in main chat interface

### Files Modified This Session

**New Files:**
- `src/supervisor/openrouter.py` - OpenRouter client + cost tracker
- `src/supervisor/model_registry.py` - Unified model catalog
- `src/dashboard/static/model_picker.html` - Model picker UI
- `requirements.txt` - Added `openai>=1.0.0`, `huggingface-hub>=0.20.0`

**Modified Files:**
- `src/dashboard/dashboard.py` - Added model APIs, static file serving
- `src/dashboard/static/index.html` - Added Model Picker button
- `docker/docker-compose.dashboard.yml` - Added environment variables
- `CLAUDE.md` - Updated Phase 7.5 status
- `docker/Dockerfile.dashboard` - Fixed static file copy

### Git Changes Summary

```
Added:
- src/supervisor/openrouter.py (329 lines)
- src/supervisor/model_registry.py (325 lines)  
- src/dashboard/static/model_picker.html (210 lines)
- requirements.txt (20 lines)

Modified:
- src/dashboard/dashboard.py (+125 lines)
- src/dashboard/static/index.html (+ Model Picker button)
- docker/docker-compose.dashboard.yml (+ OPENROUTER_API_KEY)
- CLAUDE.md (+ Phase 7.5 status)
```

### Commands for Next Session

**Check system status:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
curl http://100.109.213.22:3000/api/health
curl http://100.109.213.22:3000/api/models/list | jq '.openrouter | length'
```

**Test model switching (once Supervisor enhanced):**
```bash
# Switch to OpenRouter model
curl -X POST http://localhost:3000/api/model/select \
  -H "Content-Type: application/json" \
  -d '{"model_id": "openrouter/hunter-alpha"}'

# Switch back to local
curl -X POST http://localhost:3000/api/model/select \
  -H "Content-Type: application/json" \
  -d '{"model_id": "local/nemotron3-nano-nvfp4"}'
```

**Start Supervisor enhancement:**
```bash
cd ~/babs
# Edit src/supervisor/supervisor.py to handle model_switch
# Add OpenRouter routing logic
# Test with curl commands above
```

### Rollback Information

**Last stable checkpoint before Phase 7.5:** `de39182` (Phase 7 complete)
**Current commit:** `$(git rev-parse HEAD)`
**Rollback command:** `git reset --hard de39182`

---

**Session end:** 2026-03-13 16:10 CDT  
**Phase 7.5 status:** Core infrastructure complete, UI live  
**Ready for:** Supervisor model switching implementation  
**Next session:** Complete Phase 7.5 by making model selection functional