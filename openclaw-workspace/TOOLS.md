# TOOLS.md - Infrastructure Notes

## This Machine (Spark)

- **Hostname:** spark
- **OS:** DGX OS (Ubuntu 24.04 ARM64)
- **Tailscale IP:** 100.109.213.22
- **User:** dave (passwordless sudo)
- **Repo:** ~/babs/ (git, main branch, github.com:phloids-code-forge/Babs.git)
- **Runtime data:** ~/babs-data/ (not in git -- models, qdrant, nats, cache, threads)

## Auxiliary Node (G14)

- **SSH:** ssh g14
- **Tailscale IP:** 100.101.118.78
- **OS:** Ubuntu 24.04 LTS Server (headless)
- **GPU:** RTX 3060 Mobile 6GB

## Running Services

| Service | Host | Port | Notes |
|---------|------|------|-------|
| vLLM | spark | 8000 | Nemotron 3 Nano NVFP4. OpenAI-compatible API. |
| NATS | spark | 4222 | JetStream enabled. Data at ~/babs-data/nats. |
| Qdrant | spark | 6333 | Procedural + Episodic memory collections. |
| Dashboard | spark | 3000 | http://100.109.213.22:3000 |
| ComfyUI | spark | 8188 | Image generation. 70GB memory cap. |
| Jupyter | spark | -- | Code execution kernel. |
| SearXNG | g14 | 8888 | Web search. JSON API enabled. |
| Embedding | g14 | 8080 | nomic-embed-text-v1.5, 768-dim vectors. |
| Whisper STT | g14 | 9000 | whisper-medium on GPU. |

## OpenClaw / NemoClaw

- **OpenShell gateway:** nemoclaw (k3s in Docker)
- **Inference route (active):** vllm-local -> localhost:8000 -> Nano
- **Inference route (standby):** nvidia-nim -> NVIDIA cloud -> Super
- **Switch to cloud:** `openshell inference set --provider nvidia-nim --model nvidia/nemotron-3-super-120b-a12b`
- **Switch to local:** `openshell inference set --no-verify --provider vllm-local --model nemotron3-nano`
- **Sandbox SSH:** ssh openshell-nemoclaw

## Client Devices

| Device | Tailscale IP | Notes |
|--------|-------------|-------|
| PX13 (Windows workstation) | 100.75.27.94 | Dave's main dev machine. VS Code Remote SSH to Spark. |
| Samsung Tab S9 Ultra | 100.91.246.51 | Dashboard access. |
| Samsung Galaxy S25 Ultra | 100.119.249.52 | Quick approvals, notifications. |

## Models

| Model | Location | Status |
|-------|----------|--------|
| nemotron3-nano | ~/babs-data/models/nemotron3-nano-nvfp4/ | Active. 65+ tok/s. |
| nemotron3-super | ~/babs-data/models/nemotron3-super-nvfp4/ | Parked. 14-16 tok/s single-node (community Marlin patches). Waiting for avarok v24. |

## Filesystem Access from Sandbox

Babs runs inside the OpenShell sandbox. The Babs git repo is cloned at `/sandbox/babs/`.

**To read or edit repo files:** Work directly in `/sandbox/babs/`. It's a live git clone.

**To commit and push changes:**
```bash
cd /sandbox/babs
git add -p        # review changes
git commit -m "your message"
git push
```

**To pull latest from Spark (after phloid or Claude Code commits):**
```bash
cd /sandbox/babs && git pull
```

**To run commands on Spark:** Not yet possible. OpenShell 0.0.6 proxy blocks sandbox→host connections (SSRF protection). Planned for a future OpenShell release.

## Directory Structure on Spark

```
/home/dave/
├── babs/           # The system repo (Babs helps maintain this)
├── babs-data/      # Runtime data (models, qdrant, nats, threads)
├── projects/       # Dev projects -- Babs helps when invited via CONTEXT.md
├── lab/            # Personal experiments -- Babs stays out by default
└── NemoClaw/       # Infrastructure
```

## Key Commands

```bash
# Check what's running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
openshell sandbox list

# Start vLLM if it's not running
docker start vllm-babs

# Check vLLM is healthy
curl -s http://localhost:8000/v1/models | python3 -m json.tool
```
