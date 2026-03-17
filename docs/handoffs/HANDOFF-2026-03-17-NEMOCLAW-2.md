# Handoff: NemoClaw Session 2 (2026-03-17)

## What Was Done This Session

### 1. OpenClaw Dashboard CORS Fix

The gateway was rejecting WebSocket connections from the Tailscale IP (100.109.213.22) because `gateway.controlUi.allowedOrigins` only listed localhost. Added the Tailscale origin:

```json
"allowedOrigins": [
  "http://127.0.0.1:18789",
  "http://localhost:18789",
  "http://100.109.213.22:18789"
]
```

Edit location: `/sandbox/.openclaw/openclaw.json`

### 2. OpenRouter Provider Added

Added OpenRouter as an inference provider in `/sandbox/.openclaw/openclaw.json`. Models available in the OpenClaw model picker:

| Model | Provider ID | Cost ($/M in/out) | Notes |
|-------|-------------|-------------------|-------|
| Claude Sonnet 4.6 | anthropic/claude-sonnet-4-6 | $3 / $15 | Default cloud fallback |
| Claude Opus 4.6 | anthropic/claude-opus-4-6 | $15 / $75 | Max reasoning |
| Gemini 2.5 Pro | google/gemini-2.5-pro-preview | $1.25 / $10 | 1M context, reasoning |
| Llama 3.3 70B | meta-llama/llama-3.3-70b-instruct | $0.12 / $0.30 | Near-free |
| Nemotron 4 340B | nvidia/nemotron-4-340b-instruct | $4.20 / $4.20 | NVIDIA cloud |

OpenRouter API key is stored in the sandbox config. Not committed to git. Template at `~/babs/openclaw-workspace/openclaw.template.json`.

### 3. vllm-local Added to Model Picker

Added Nemotron 3 Nano 30B as a named model in the OpenClaw provider list so it shows up alongside cloud models:

```json
"vllm-local": {
  "baseUrl": "https://inference.local/v1",
  "apiKey": "openshell-managed",
  "models": [{"id": "nemotron3-nano", "name": "Nemotron 3 Nano 30B (local, 65 tok/s)"}]
}
```

## Current System State

- **Primary Babs interface:** http://100.109.213.22:18789/ (OpenClaw dashboard, systemd-managed)
- **Active inference:** vllm-local / Nemotron 3 Nano (65 tok/s, free)
- **Cloud fallback:** OpenRouter / Claude Sonnet 4.6 (recommended) or any of the above models
- **Workspace files:** Seeded. SOUL.md, IDENTITY.md, USER.md, TOOLS.md in /sandbox/.openclaw/workspace/
- **Supervisor stack:** Still running (babs-supervisor, NATS, Qdrant, Dashboard on :3000) but not the primary Babs interface

## To Switch Active Model in OpenClaw

Via CLI:
```bash
# Switch to Claude Sonnet via OpenRouter
ssh openshell-nemoclaw "openclaw agent config set --agent main --model openrouter/anthropic/claude-sonnet-4-6"

# Switch back to local Nano
ssh openshell-nemoclaw "openclaw agent config set --agent main --model vllm-local/nemotron3-nano"
```

Via dashboard: Settings > Config or use the model picker in the chat UI.

## Rebuild After Sandbox Reset

If the sandbox is rebuilt, the openclaw.json config will reset. To restore:

1. Re-seed workspace files (SOUL.md, IDENTITY.md, USER.md, TOOLS.md):
   ```bash
   for f in SOUL IDENTITY USER TOOLS; do
     ssh openshell-nemoclaw "cat > /sandbox/.openclaw/workspace/${f}.md" < ~/babs/openclaw-workspace/${f}.md
   done
   ```

2. Re-apply openclaw.json config:
   - Copy from `~/babs/openclaw-workspace/openclaw.template.json`
   - Fill in `OPENROUTER_API_KEY` and `GATEWAY_TOKEN` from secure storage
   - Upload: `ssh openshell-nemoclaw "cat > /sandbox/.openclaw/openclaw.json" < /tmp/openclaw.json`
   - Restart gateway service: `sudo systemctl restart openclaw-dashboard-tunnel`

## Open Questions / Next Steps

See docs/05-open-questions.md items 26-28:
- GPU passthrough to sandbox (untested)
- Supervisor/OpenClaw integration pattern (Option A: rewrite supervisor tools vs Option B: subprocess orchestration)
- OpenShell policy file schema mapping Trust Tiers to OS-level enforcement rules

Workflow going forward: Babs conversations happen in OpenClaw (http://100.109.213.22:18789/). Standalone app development uses VS Code + Continue. Architecture/major changes use Claude Code.
