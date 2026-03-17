# Handoff: NemoClaw Session 5 (2026-03-17)

## What Was Done This Session

### Auto-seed on sandbox restart

The sandbox (`/sandbox`) is ephemeral container storage -- pod restarts wipe everything. Previously this required a manual 6-step re-seed procedure. Now it's fully automatic.

**How it works:**
- `openclaw-dashboard-start.sh` calls `babs-seed.sh` every time the service starts
- `babs-seed.sh` polls until the sandbox is SSH-reachable, then seeds everything in ~8s
- Seeds: openclaw.json, SOUL/IDENTITY/USER/TOOLS.md, git credentials, git clone (or pull if already cloned)

**Persistent secrets (NOT in git, must recreate if machine is rebuilt):**
- `/etc/babs-reseed.env` (mode 600, owner dave): `GITHUB_TOKEN=...`
- `/etc/babs-openclaw.json` (mode 600, owner dave): full openclaw.json with OpenRouter API key and gateway token

**Script:** `~/babs/scripts/babs-seed.sh` (version-controlled). Deployed copy at `/usr/local/bin/babs-seed.sh`.

To run manually: `bash /usr/local/bin/babs-seed.sh`

## Current System State

### What's Running

| Service | Status | Notes |
|---------|--------|-------|
| vllm-babs | Running | Nano 30B NVFP4, 65+ tok/s, port 8000 |
| nats-babs | Running | JetStream, port 4222 |
| babs-supervisor | Running | Legacy stack (not primary interface anymore) |
| qdrant-babs | Running | Memory collections, port 6333 |
| babs-dashboard | Running | Legacy dashboard, port 3000 |
| comfyui-babs | Running | 70GB memory cap |
| OpenShell gateway | Running | nemoclaw, k3s-in-Docker |
| nemoclaw sandbox | Running | Ready, Proxy mode, policy v4 |
| openclaw-dashboard-tunnel | Running | Tailscale:18789 -> sandbox:18789 |
| babs-bridge | Running | HTTPS port 7222. Parked -- proxy SSRF blocks sandbox->host |

### Babs Interface

**Primary:** http://100.109.213.22:18789/#token=4a4569fb23163c74cd4a4124e02e467fd844141a2708d67b

**Current model:** vllm-local/nemotron3-nano -- **this is the problem for next session.**

### Model Switcher

```bash
babs-model list          # show current + options
babs-model sonnet        # Claude Sonnet 4.6 via OpenRouter
babs-model deepseek-r1   # DeepSeek R1 via OpenRouter (reasoning)
babs-model nano          # back to local Nano
```

## Next Session: Better Base Model

**Problem:** Nano (30B) is too small for the persona work. It can't follow basic instructions reliably -- repeatedly misspells "phloid" as "phloyd" no matter how many corrections are given in-session.

**Goal:** Find a model that can actually hold a coherent identity and follow simple instructions consistently.

**Options to evaluate (in order of preference):**

1. **Sonnet 4.6 via OpenRouter** -- already configured, `babs-model sonnet`. Immediate fix, costs money. Good baseline to test against. Start here to validate that the persona works correctly before optimizing for cost/speed.

2. **DeepSeek R1 via OpenRouter** -- reasoning model, cheaper than Sonnet. `babs-model deepseek-r1`. Good candidate for the "always-on" model if it handles persona well.

3. **DeepSeek V3 Chat** -- fast/cheap, `babs-model deepseek`. Non-reasoning. Might be enough for casual conversation.

4. **Local Super (Nemotron 3 Super 120B)** -- 14-16 tok/s with Marlin patches. Not interactive-fast yet. Still parked. Revisit when avarok v24 ships.

**Recommended approach for next session:**
1. `babs-model sonnet` -- test if persona/name/identity works correctly
2. If yes, evaluate cost tolerance and try DeepSeek R1 as a cheaper alternative
3. Set whichever works as the default in openclaw.json + babs-seed.sh

**Important:** The persona files (SOUL.md, IDENTITY.md, USER.md) are solid -- the problem is model capability, not the prompt. Don't rewrite the persona files to compensate for a weak model; just use a stronger model.

## Key Paths Quick Reference

| What | Where |
|------|-------|
| Babs dashboard | http://100.109.213.22:18789/#token=4a4569fb23163c74cd4a4124e02e467fd844141a2708d67b |
| Switch model | `babs-model <name>` |
| Sandbox git repo | `/sandbox/babs/` |
| Workspace files | `/sandbox/.openclaw/workspace/` |
| OpenClaw config | `/sandbox/.openclaw/openclaw.json` |
| Seed secrets | `/etc/babs-reseed.env`, `/etc/babs-openclaw.json` |
| Auto-seed script | `/usr/local/bin/babs-seed.sh` |
| Network policy | `openshell policy set nemoclaw --policy /tmp/nemoclaw-policy.yaml --wait` |
