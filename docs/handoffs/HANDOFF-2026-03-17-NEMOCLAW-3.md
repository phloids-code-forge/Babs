# Handoff: NemoClaw Session 3 (2026-03-17)

## What Was Done This Session

### 1. Personality Rewrite (SOUL.md, IDENTITY.md, USER.md)

The original soul.md was being interpreted too literally -- "no filler" and "short" collapsed into robotic minimal responses. Rewrote all three files:

- **SOUL.md**: Clarified "no filler" = AI catchphrases only, not personality. Added "when invited to open up, actually open up." Added content creator duo context. Added Projects/Lab directory policy.
- **IDENTITY.md**: Added the public duo framing -- Babs is a co-star in tutorials/animations, not just a private assistant.
- **USER.md**: Added content creation context. Noted phloid's name must be lowercase always. Clarified casual conversation is legitimate time.

To take effect: start a NEW session in OpenClaw (not continue old one).

### 2. Babs Bridge (sandbox → Spark command relay)

**Built:** `~/babs/src/bridge/babs-bridge.py` -- stdlib-only Python HTTP server.
- Listens on 0.0.0.0:7222
- Auth: X-Babs-Token header (HMAC compare)
- Token: stored in `/etc/babs-bridge.env` (mode 600)
- Systemd: `babs-bridge.service` (enabled, running)
- Test from Spark: `curl -s http://localhost:7222/health`

**Blocked:** Sandbox was created in Block network mode. Adding network policies requires a sandbox rebuild (`Block → Proxy mode change requires restart`). The sandbox proxy at `10.200.0.1:3128` blocks all HTTP not in the allowlist.

**To activate after rebuild:**
```bash
# Include this in the policy when rebuilding:
network_policies:
  babs_bridge:
    name: babs_bridge
    endpoints:
      - host: host.openshell.internal
        port: 7222
        protocol: rest
        enforcement: enforce
        rules:
          - allow: { method: GET, path: "/health" }
          - allow: { method: POST, path: "/run" }
```

Usage from sandbox (once active):
```bash
curl -s -X POST http://host.openshell.internal:7222/run \
  -H "Content-Type: application/json" \
  -H "X-Babs-Token: TOKEN" \
  -d '{"command": "ls /home/dave/babs", "cwd": "/home/dave"}'
```

### 3. babs-sync.sh

`~/babs/scripts/babs-sync.sh` -- pushes babs docs into sandbox via tar-over-SSH (rsync not available in sandbox).

Syncs:
- `~/babs/CLAUDE.md` → `/sandbox/.openclaw/workspace/babs/CLAUDE.md`
- `~/babs/docs/` → `/sandbox/.openclaw/workspace/babs/docs/`
- `~/babs/src/*.py,*.md,*.yaml,*.json,*.sh` → `/sandbox/.openclaw/workspace/babs/src/`

Run: `bash ~/babs/scripts/babs-sync.sh`

Initial sync done. Babs can now read the full architecture docs and CLAUDE.md.

### 4. Directory Structure

```
/home/dave/
├── babs/           # System repo
├── babs-data/      # Runtime data
├── projects/       # Dev projects (CONTEXT.md convention)
├── lab/            # Personal experiments (Babs stays out)
└── NemoClaw/       # Infrastructure
```

`~/projects/README.md` documents the CONTEXT.md convention.

### 5. SSH Keypair

Generated ed25519 keypair on Spark, uploaded to sandbox:
- Private key: `/sandbox/.ssh/spark_id`
- Public key added to `~/.ssh/authorized_keys` on Spark (with no-agent-forwarding restriction)
- SSH config at `/sandbox/.ssh/config` with `Host spark` alias

**Blocked by same sandbox network policy issue** -- no SSH binary in sandbox, and even if installed, outbound TCP to Spark would be blocked by the proxy. Activate after sandbox rebuild.

## Sandbox Rebuild Plan

When doing the rebuild (`cd ~/NemoClaw && bash scripts/setup.sh`):

1. Run `bash ~/babs/scripts/babs-sync.sh` first (docs are already there, but good habit)
2. After rebuild, re-seed workspace:
   ```bash
   for f in SOUL IDENTITY USER TOOLS; do
     ssh openshell-nemoclaw "cat > /sandbox/.openclaw/workspace/${f}.md" < ~/babs/openclaw-workspace/${f}.md
   done
   ```
3. Re-apply openclaw.json (from template + fill in real keys):
   ```bash
   # Edit template, fill OPENROUTER_API_KEY and GATEWAY_TOKEN
   cp ~/babs/openclaw-workspace/openclaw.template.json /tmp/openclaw.json
   # ... edit ...
   ssh openshell-nemoclaw "cat > /sandbox/.openclaw/openclaw.json" < /tmp/openclaw.json
   ```
4. Restart dashboard: `sudo systemctl restart openclaw-dashboard-tunnel`
5. Run babs-sync.sh to populate babs docs

## Pending: Model Switching UX

Dave wants easy model switching between:
- Local Nano (vllm-local/nemotron3-nano) -- free, 65 tok/s
- OpenRouter models (claude-sonnet-4-6, gemini-2.5-pro, llama-3.3-70b, etc.)
- NVIDIA cloud (nvidia-nim for Super when ready)
- Claude Code (already separate tool, no change needed)

Current state: models are configured in openclaw.json, switching requires editing the file and restarting the gateway. Need a simple script or alias set.

**Plan for next session:**
- Write `babs-model.sh` with subcommands: `babs-model nano`, `babs-model sonnet`, `babs-model gemini`, `babs-model list`
- Each subcommand edits openclaw.json and sends SIGHUP or restarts gateway
- Add aliases to ~/.bashrc

## Dashboard URL

`http://100.109.213.22:18789/#token=4a4569fb23163c74cd4a4124e02e467fd844141a2708d67b`

(bookmark this on all devices)
