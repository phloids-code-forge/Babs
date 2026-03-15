# Spark Network & ComfyUI Context
# Purpose: reference doc for scripting CivitAI Link deployment

This document exists so a model can write a CivitAI Link setup script for the Spark
without needing to explore the codebase. All relevant facts are here.

---

## Hardware

- **Machine:** MSI EdgeXpert MS-C931 (DGX Spark platform)
- **CPU/GPU:** GB10 Grace Blackwell Superchip (ARM64, SM_121)
- **OS:** DGX OS (Ubuntu 24.04 LTS, ARM64)
- **Hostname:** `spark`
- **User:** `dave`, home at `/home/dave`

---

## Network Interfaces

| Interface | Address | Purpose |
|-----------|---------|---------|
| `enP7s7` | `192.168.1.129/24` | LAN (local home network) |
| `tailscale0` | `100.109.213.22/32` | Tailscale VPN (accessible from PX13 and G14) |
| `br-499426b11491` | `172.18.0.1/16` | Docker bridge for `docker_babs-net` |
| `br-09b08b1387ee` | `172.19.0.1/16` | Docker bridge for `babs-network` (legacy, babs-jupyter only) |
| `docker0` | `172.17.0.1/16` | Default Docker bridge (unused, no containers on it) |

**PX13 (Dave's Windows workstation)** connects via VS Code Remote SSH over Tailscale.
**G14 (auxiliary node)** is at Tailscale `100.101.118.78`, SSH alias `g14`.

---

## Docker Setup

### Networks

All production containers use a single shared bridge network:

- **Name:** `docker_babs-net`
- **Driver:** bridge
- **Subnet:** `172.18.0.0/16`, gateway `172.18.0.1`
- **Created by:** the main `docker-compose.dashboard.yml` (which defines it as a named network)
- **Referenced as external** in all other compose files with `name: docker_babs-net`

There is also `babs-network` (`172.19.0.0/16`) used only by `babs-jupyter`. Ignore it.

Containers on `docker_babs-net` can reach each other by container name (e.g., `nats-babs`, `comfyui-babs`).

### Running Containers

| Container | Image | Host Ports | Network |
|-----------|-------|-----------|---------|
| `comfyui-babs` | `comfyui-spark:latest` | `8188->8188` | `docker_babs-net` |
| `babs-supervisor` | `docker-supervisor` | none | `docker_babs-net` |
| `nats-babs` | `nats:latest` | `4222, 6222, 8222` | `docker_babs-net` |
| `babs-jupyter` | `docker-babs-jupyter` | 8888 (internal) | `babs-network`, `docker_babs-net` |
| `babs-dashboard` | `docker-dashboard` | `3000->3000` | `docker_babs-net` |
| `qdrant-babs` | `qdrant/qdrant:latest` | `6333-6334->6333-6334` | `docker_babs-net` |

No container runs as a privileged user. The GPU is passed via `deploy.resources.reservations.devices`.

### Compose File Locations

All compose files live in `/home/dave/babs/docker/`. Each service has its own file:

- `docker-compose.dashboard.yml` - dashboard + nats (also defines `docker_babs-net`)
- `docker-compose.comfyui.yml` - comfyui-babs
- `docker-compose.supervisor.yml` - babs-supervisor
- `docker-compose.qdrant.yml` - qdrant-babs
- `docker-compose.jupyter.yml` - babs-jupyter

To start ComfyUI: `docker compose -f /home/dave/babs/docker/docker-compose.comfyui.yml up -d`

---

## ComfyUI Container Details

### Image

Built from `/home/dave/babs/docker/Dockerfile.comfyui`.

- Base: `nvcr.io/nvidia/pytorch:25.01-py3` (ARM64, CUDA 12.8, PyTorch 2.6)
- ComfyUI installed at `/opt/comfyui`
- ComfyUI Manager installed via `pip install --pre comfyui-manager` AND cloned to
  `/opt/comfyui/custom_nodes/ComfyUI-Manager`
- Started with `--enable-manager --extra-model-paths-config /opt/comfyui/extra_model_paths.yaml`

### Volume Mounts (host -> container)

| Host Path | Container Path | Notes |
|-----------|---------------|-------|
| `/home/dave/babs-data/comfyui/models` | `/opt/comfyui/models` | All model files |
| `/home/dave/babs-data/comfyui/output` | `/opt/comfyui/output` | Generated images |
| `/home/dave/babs-data/comfyui/input` | `/opt/comfyui/input` | img2img uploads |
| `/home/dave/babs-data/comfyui/user` | `/opt/comfyui/user` | Workflows, settings |
| `/home/dave/babs-data/comfyui/custom_nodes_data` | `/opt/comfyui/custom_nodes/ComfyUI-Manager/user` | Manager state |
| `/home/dave/babs/config/comfyui-extra-paths.yaml` | `/opt/comfyui/extra_model_paths.yaml` | Read-only |

### Environment Variables in Container

- `NVIDIA_VISIBLE_DEVICES=all`
- `NVIDIA_DRIVER_CAPABILITIES=all`
- `CIVITAI_API_KEY` - passed from host shell environment (empty if not set)

### Model Directory Layout on Host

`/home/dave/babs-data/comfyui/models/` contains:

```
checkpoints/        <- SD/SDXL/Flux checkpoint files (.safetensors, .ckpt)
clip/
clip_vision/
controlnet/
diffusion_models/   <- Flux diffusion models
embeddings/
hypernetworks/
inpaint/
ipadapter/
loras/
text_encoders/      <- Flux text encoders (clip_l.safetensors, t5 GGUF)
upscale_models/
vae/
vae_approx/
```

Each directory may contain a `.parked/` subdirectory for models moved out of active use
(handled by `scripts/comfyui-models.sh unload/restore`).

### ComfyUI Manager Config

Located at `/home/dave/babs-data/comfyui/user/__manager/config.ini`.

Relevant settings:
- `security_level = weak` - required for Manager to function (allows custom node installs)
- `network_mode = public` - Manager can reach the internet
- `model_download_by_agent = False` - Manager's own download agent is off

---

## CivitAI Link - What It Is

CivitAI Link is a small daemon that creates a persistent connection from a machine back to
civitai.com. Once connected, the CivitAI website can push model downloads directly to the
linked machine. The user browses civitai.com normally, clicks "Send to ComfyUI", and the
model downloads to the connected machine instead of the browser's machine.

CivitAI Link is open source: https://github.com/civitai/civitai-link-desktop
There is a Linux CLI version separate from the Electron desktop app.

The daemon:
- Connects outbound to CivitAI's relay server via WebSocket (no inbound port needed)
- Is authenticated by a link key from the user's CivitAI account settings
- Needs to know where to put downloaded models (the model root directory)
- Needs to know the ComfyUI API URL to notify it to refresh after a download

---

## What a Setup Script Needs to Do

1. **Install** the CivitAI Link CLI binary for Linux ARM64 (or build from source if no ARM64
   binary is available - check the releases page first)
2. **Configure** it with:
   - Model root: `/home/dave/babs-data/comfyui/models`
   - ComfyUI URL: `http://localhost:8188` (or `http://comfyui-babs:8188` if run inside Docker)
   - Link key: from `CIVITAI_LINK_KEY` env var or a config file at
     `/home/dave/babs-data/comfyui/civitai-link/config.json`
3. **Decide where to run it:** Two options:
   - **On the host** (simpler): runs as a systemd service, reaches ComfyUI at `localhost:8188`
   - **In Docker** (consistent with rest of stack): add a new service to
     `docker-compose.comfyui.yml` or a new `docker-compose.civitai-link.yml`, on `docker_babs-net`,
     reaches ComfyUI at `http://comfyui-babs:8188`. Volume mount
     `/home/dave/babs-data/comfyui/models` at the same path.
4. **Model type mapping:** CivitAI Link needs to map CivitAI model types to local directories.
   The mapping used by `scripts/comfyui-models.sh` is the reference:
   - `checkpoint/checkpoints` -> `checkpoints/`
   - `lora/loras` -> `loras/`
   - `controlnet` -> `controlnet/`
   - `vae` -> `vae/`
   - `embedding/embeddings` -> `embeddings/`
   - `upscale/upscale_models` -> `upscale_models/`
   - `ipadapter` -> `ipadapter/`

---

## ARM64 Caveat

The Spark is ARM64. Many Linux tools ship only x86_64 binaries. Before writing any install
logic, check whether a prebuilt ARM64 binary exists. If not, the script needs to build from
source (requires Node.js/npm for Electron apps, or Go/Rust toolchain if it's a native binary).

The host has standard Ubuntu 24.04 tools available. Docker and docker compose (v2 plugin) are
installed. `wget`, `curl`, `git` are available.

---

## File Transfer from PX13

Samba is running on Spark. `~/babs-data` is shared as `\\100.109.213.22\babs-data` and mapped as `Z:` on PX13 (Windows). Authentication required, user `dave`. Bound to all interfaces (Tailscale provides the security boundary). Config at `/etc/samba/smb.conf`.

This means model files can be dragged from the browser download folder on PX13 directly into `Z:\comfyui\models\<type>\` without SSH.

---

## Relevant Env Vars (host shell)

- `CIVITAI_API_KEY` - used by `scripts/comfyui-models.sh` for direct API downloads
- `CIVITAI_LINK_KEY` - not yet set; will be the CivitAI Link pairing key

These can be persisted in `/home/dave/.bashrc` or `/home/dave/.profile`.

---

## Scripts Already in Place

`/home/dave/babs/scripts/comfyui-models.sh` handles manual model downloads:
- `dl-civitai <model-id> <type>` - downloads via CivitAI REST API using `CIVITAI_API_KEY`
- `dl-hf <repo> <filename> <type>` - downloads from HuggingFace via `hf` CLI
- `krita-setup` - downloads all 21 Krita AI Diffusion support models
- `list` - shows installed models and disk usage
- `unload/restore <type> <filename>` - parks/restores models

CivitAI Link is a complement to this script, not a replacement. Link handles browser-initiated
downloads; the script handles scripted/bulk downloads.
