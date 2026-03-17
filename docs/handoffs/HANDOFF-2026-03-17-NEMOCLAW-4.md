# Handoff: NemoClaw Session 4 (2026-03-17)

## What Was Done This Session

### 1. Sandbox Rebuilt in Proxy Mode

The old sandbox was created in Block network mode (no outbound traffic). Rebuilt using `OPENSHELL_SANDBOX_POLICY=/tmp/nemoclaw-policy.yaml bash ~/NemoClaw/scripts/setup.sh`, which creates the sandbox in Proxy mode with network policies active from the start.

Active network policies (policy version 4, stored at `/tmp/nemoclaw-policy.yaml`):
- `babs_bridge`: host.openshell.internal:7222, access: full (parked -- see below)
- `openrouter`: openrouter.ai:443
- `nvidia`: integrate.api.nvidia.com:443, inference-api.nvidia.com:443
- `github`: github.com:443, api.github.com:443
- `clawhub`, `openclaw_api`, `openclaw_docs`, `npm_registry`, `telegram`

**Important:** `/sandbox` is ephemeral container storage. Every time the sandbox pod restarts (gateway rebuild, k3s restart, etc.) all files in `/sandbox` are wiped. Use the re-seed procedure in CLAUDE.md.

### 2. Babs Bridge -- Parked

The bridge (`babs-bridge.service`) was upgraded to HTTPS (self-signed cert at `/etc/babs-bridge-tls/`, port 7222). But it can't be reached from the sandbox.

**Root cause:** OpenShell 0.0.6's proxy (10.200.0.1:3128) has SSRF protection that blocks all connections to RFC 1918 private IPs (172.x.x.x, 10.x.x.x, 192.168.x.x). This is enforced at the kernel level -- even with `access: full` policy and correct HTTPS, CONNECT tunnels to private IPs are blocked. SSH reverse port forwarding is also blocked. No workaround exists without modifying OpenShell itself.

**Status:** Policy entry is in place. Will activate when OpenShell adds host-routing support. The `inference.local` hostname works because it's a special hardcoded proxy route, not via the policy system.

### 3. DeepSeek Models Added

Added to OpenRouter provider in openclaw.json (live) and openclaw.template.json (tracked):
- `deepseek/deepseek-r1`: reasoning model, $0.55/$2.19/M input/output
- `deepseek/deepseek-chat`: DeepSeek V3 Chat, fast/cheap, $0.27/$1.10/M

### 4. Model Switcher: babs-model.sh

`~/babs/scripts/babs-model.sh` with subcommands:
- `nano` -- vllm-local/nemotron3-nano (local, free, 65 tok/s)
- `sonnet` -- openrouter/anthropic/claude-sonnet-4-6
- `opus` -- openrouter/anthropic/claude-opus-4-6
- `deepseek` -- openrouter/deepseek/deepseek-chat
- `deepseek-r1` -- openrouter/deepseek/deepseek-r1
- `gemini` -- openrouter/google/gemini-2.5-pro-preview
- `llama` -- openrouter/meta-llama/llama-3.3-70b-instruct
- `list` -- show current + all options

Alias `babs-model` added to `~/.bashrc`. Updates openclaw.json in sandbox + openshell inference route (for local models). Start a new OpenClaw session for the change to take effect.

### 5. Babs Git Access

The correct "OpenClaw first" approach for file access: Babs has a live git clone of the repo inside her sandbox.

- Clone location: `/sandbox/babs/`
- Credentials: `/sandbox/.git-credentials` (mode 600, GitHub PAT)
- Git identity: `Babs <babs@openclaw>`
- Remote: `https://github.com/phloids-code-forge/Babs.git`
- Deploy key (ed25519) added to GitHub repo (not used -- HTTPS with PAT is what works since no SSH binary in sandbox)

Babs reads, edits, commits, and pushes directly. No babs-sync.sh needed. This is the standard OpenClaw workflow.

## Current State

- Sandbox: Ready, running, Proxy mode, policy v4 active
- Inference: vllm-local/nemotron3-nano (65+ tok/s)
- OpenClaw dashboard: http://100.109.213.22:18789/#token=4a4569fb23163c74cd4a4124e02e467fd844141a2708d67b
- Workspace files: seeded (SOUL.md, IDENTITY.md, USER.md, TOOLS.md)
- Git repo: cloned at /sandbox/babs/
- openclaw.json: live config with all 7 OpenRouter models + vllm-local

## Re-seed Procedure (after any sandbox pod restart)

Pod restarts wipe `/sandbox`. Run this from Spark:

```bash
# 1. Create dirs
ssh openshell-nemoclaw "mkdir -p /sandbox/.openclaw/workspace /sandbox/.ssh"

# 2. Apply openclaw.json (has real API keys -- keep /tmp/openclaw-post-rebuild.json safe)
ssh openshell-nemoclaw "cat > /sandbox/.openclaw/openclaw.json" < /tmp/openclaw-post-rebuild.json

# 3. Workspace seed files
for f in SOUL IDENTITY USER TOOLS; do
  ssh openshell-nemoclaw "cat > /sandbox/.openclaw/workspace/${f}.md" < ~/babs/openclaw-workspace/${f}.md
done

# 4. Git credentials and clone
ssh openshell-nemoclaw "cat > /sandbox/.git-credentials && chmod 600 /sandbox/.git-credentials" <<< 'https://TOKEN@github.com'
ssh openshell-nemoclaw "git config --global credential.helper store && git config --global user.name 'Babs' && git config --global user.email 'babs@openclaw'"
ssh openshell-nemoclaw "cd /sandbox && git clone https://github.com/phloids-code-forge/Babs.git babs"

# 5. Restore inference route and restart dashboard
openshell inference set --no-verify --provider vllm-local --model nemotron3-nano
sudo systemctl restart openclaw-dashboard-tunnel
```

Replace `TOKEN` with the GitHub PAT (stored separately, not in git).

## Known Limitations

- **No sandbox→host command execution.** OpenShell 0.0.6 SSRF protection is a hard wall. Babs can't run commands on Spark directly. For Spark operations, ask phloid or Claude Code.
- **Sandbox storage is ephemeral.** Any files Babs creates in `/sandbox` that aren't committed to git are lost on pod restart. Babs should commit important work regularly.
- **No SSH binary in sandbox.** git@github.com doesn't work; must use HTTPS with PAT.

## What's Next

- **Phase 10:** Babs starts actively using her git access. She can read the full architecture, update docs, write code, commit, push. Real agentic loop begins.
- **Model switching UX in OpenClaw:** Babs could write her own version of babs-model.sh that she invokes from within OpenClaw sessions.
- **Super when avarok v24 ships:** Switch to Super when the local 14-16 tok/s becomes interactive-fast enough.
