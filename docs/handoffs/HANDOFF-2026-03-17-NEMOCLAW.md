# Handoff: NemoClaw/OpenClaw Integration

**Date:** 2026-03-17
**Phase:** 9 (in progress)
**Previous handoff:** HANDOFF-2026-03-15-CURRENT.md

---

## What Changed Today

NVIDIA announced OpenClaw and NemoClaw at GTC 2026 (2026-03-16). Decision made to pivot Babs to use OpenClaw/NemoClaw as the agent runtime, with Babs integration wrapping around it. Rationale: standard configuration means community troubleshooting resources apply directly; OpenShell provides stronger enforcement than our hand-rolled Trust Tier checks; builds familiarity with the mainstream NVIDIA ecosystem stack.

This handoff covers the Phase 9 installation work completed 2026-03-17.

---

## What Was Done

### Installation (all on Spark)

1. **OpenShell v0.0.6** installed at `/usr/local/bin/openshell`
   - Static aarch64 musl binary from GitHub releases (tarball extract)
   - URL: `https://github.com/NVIDIA/OpenShell/releases/download/v0.0.6/openshell-aarch64-unknown-linux-musl.tar.gz`

2. **NemoClaw v0.1.0** cloned and installed
   - Source: `~/NemoClaw/` (git clone of github.com/NVIDIA/NemoClaw)
   - Installed globally via npm: `sudo npm install -g .` (from ~/NemoClaw)
   - Node.js v24 was pre-existing via nvm. npm and node symlinked to /usr/local/bin for sudo access.
   - `nemoclaw` binary at `/home/dave/.nvm/versions/node/v24.14.0/bin/nemoclaw`, symlinked to `/usr/local/bin/nemoclaw`

3. **Docker daemon patched** for cgroup v2 Spark compatibility
   - `/etc/docker/daemon.json`: `{"default-cgroupns-mode": "host"}`
   - Required for k3s-in-Docker. Without this, k3s fails with "openat2 /sys/fs/cgroup/kubepods/pids.max: no"
   - Docker restarted after patch. All existing containers (vllm-babs, nats-babs, etc.) came back normally.

4. **NVIDIA API key saved** to `~/.nemoclaw/credentials.json` (mode 600)
   - Key retrieved from build.nvidia.com -> Settings -> API Keys

5. **`nemoclaw setup-spark` partial run**
   - Steps 1-3 (docker group, cgroupns, Docker restart): passed (already configured)
   - Step 4 (pip install vLLM): FAILED -- system Python PEP 668 protection blocks pip
   - Note: we do not want pip-installed vLLM. We run vLLM in Docker (vllm-babs container).
   - Workaround: started vllm-babs container first, then ran `scripts/setup.sh` directly

6. **vllm-babs container started** before running setup so setup.sh auto-detected it on :8000
   - `docker start vllm-babs` (was stopped for 32 hours)
   - Waited for model load (~30s), confirmed `GET /v1/models` returns `nemotron3-nano`

7. **`scripts/setup.sh` ran successfully**
   - OpenShell gateway started: name=nemoclaw, Ready
   - Providers created:
     - `nvidia-nim`: NVIDIA cloud, model nvidia/nemotron-3-super-120b-a12b (default route)
     - `vllm-local`: our Docker vLLM, endpoint http://host.openshell.internal:8000/v1 (auto-detected)
   - NemoClaw sandbox built from Dockerfile (22 steps, node:22-slim base, openclaw@2026.3.11 + NemoClaw plugin)
   - Sandbox image: openshell/sandbox-from:1773705733 (1448 MiB)

8. **Inference route switched to vllm-local**
   - `openshell inference set --no-verify --provider vllm-local --model nemotron3-nano`
   - `--no-verify` needed because openshell's validation request sends wrong Content-Type; the actual inference works fine

9. **SSH access to sandbox configured**
   - `openshell sandbox ssh-config nemoclaw >> ~/.ssh/config`
   - Entry: `Host openshell-nemoclaw`, ProxyCommand uses openshell ssh-proxy

10. **Test verified**
    - `ssh openshell-nemoclaw "openclaw agent --agent main --local -m 'how many rs are there in strawberry?' --session-id test1"`
    - Answer: `3` (correct)
    - vLLM logs confirmed: `172.17.0.1 - "POST /v1/chat/completions HTTP/1.1" 200 OK` at correct timestamp
    - Inference is flowing: OpenClaw -> OpenShell -> host.openshell.internal:8000 -> vllm-babs Docker container

---

## System State After This Handoff

### What's Running

| Service | State |
|---------|-------|
| vllm-babs | Running. Nano, :8000. |
| openshell gateway (nemoclaw) | Running. k3s in Docker. |
| nemoclaw sandbox | Ready. |
| nats-babs | Running. |
| babs-supervisor | Running. |
| qdrant-babs | Running. |
| babs-dashboard | Running. :3000 |
| comfyui-babs | Running. :8188 |
| babs-jupyter | Running. |

### Inference Routes Available

| Provider | Endpoint | Model | Active? |
|----------|----------|-------|---------|
| vllm-local | http://host.openshell.internal:8000/v1 | nemotron3-nano | YES |
| nvidia-nim | https://integrate.api.nvidia.com/v1 | nvidia/nemotron-3-super-120b-a12b | No (standby) |

### Key Files

| Path | Notes |
|------|-------|
| `~/NemoClaw/` | NemoClaw v0.1.0 source |
| `~/.nemoclaw/credentials.json` | NVIDIA API key (mode 600) |
| `~/.openclaw/` | OpenClaw config (host-side) |
| `/etc/docker/daemon.json` | cgroupns=host patch |
| `~/.ssh/config` | openshell-nemoclaw SSH entry |

---

## Nemotron Super Status (Updated 2026-03-17)

Previously documented as 1 tok/s (unusable). Community update: namake-taro vLLM 0.17.0 Marlin patches (github.com/namake-taro/vllm-custom) fix a shared memory race condition in the 256-thread Marlin MoE kernel on SM121. With patches + env vars, single-node Super reaches 14-16 tok/s. Two-node TP=2 reaches 80 tok/s on gpt-oss-120b. Still not interactive-fast for single-node; parked. vllm-super image and weights kept.

The nvidia-nim provider in NemoClaw gives us cloud-speed Super access in the interim (API call, billed against NVIDIA API credits).

---

## What Comes Next (Phase 9 Remaining)

The critical open question is answered: NemoClaw accepts our existing vLLM Docker container as the inference backend. The remaining Phase 9 work is integration:

1. **Define supervisor/OpenClaw integration pattern** (open question 27 in docs/05-open-questions.md)
   - Option A: Babs supervisor reimplemented as OpenClaw tools (clean but big rewrite)
   - Option B: Babs supervisor orchestrates OpenClaw via SSH as a subprocess (low-risk starting point)
   - Recommendation: start with Option B, validate the architecture, then evaluate migration to A

2. **Wire Babs identity and memory into the OpenClaw agent**
   - Barbara Gordon system prompt injection into the sandbox's openclaw.json
   - Procedural/episodic memory retrieval feeding into the agent context before each request
   - Tool registrations (web_search, read_file, write_file, shell) configured in the agent

3. **OpenShell policy definition for Trust Tiers** (open question 28)
   - Map Tier 0/1/2/3 actions to specific OpenShell policy rules
   - Version-control the policy files alongside Trust Tier config

4. **Test GPU passthrough** (open question 26)
   - `openshell gateway start --gpu` -- currently untested on Spark

---

## Known Issues / Gotchas

- `nemoclaw setup-spark` fails at pip install vLLM step. Workaround: run `scripts/setup.sh` directly with vllm-babs already running. setup-spark steps 1-3 (the actual Spark-specific fixes) already completed manually.
- `openshell inference set` validation fails with "Unsupported Media Type" against vLLM. Use `--no-verify`. The actual inference works correctly -- the validation probe sends wrong Content-Type.
- npm/node must be symlinked to /usr/local/bin for sudo commands to work (nvm installs under user home, not system PATH).
- The NemoClaw plugin banner inside the sandbox always shows "build.nvidia.com / nemotron-3-super" regardless of the actual inference route. This is just the plugin's registered display name from the Dockerfile. The actual routing is controlled by `openshell inference get`.
