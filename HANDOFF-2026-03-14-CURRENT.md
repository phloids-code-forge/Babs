# Handoff: 2026-03-14 — ComfyUI NVFP4 Rebuild

## What Happened This Session

Focused entirely on ComfyUI: upgraded the container to CUDA 13 for native NVFP4 acceleration, downloaded a full suite of NVFP4 models, and got ComfyUI Manager fully operational.

---

## ComfyUI Container Rebuild

**Old base:** `nvcr.io/nvidia/pytorch:25.01-py3` (PyTorch 2.6, CUDA 12.8)
**New base:** `nvidia/cuda:13.0.2-devel-ubuntu24.04`

Key changes:
- PyTorch installed from `https://download.pytorch.org/whl/cu130` (ARM64 cu130 wheels)
- SageAttention compiled for SM_121 (`TORCH_CUDA_ARCH_LIST=12.1`) — enables flash attention on GB10, also helps with longer video generation
- Isolated venv at `/opt/venv`
- Added: `gguf`, `gitpython`, `uv` (all required by custom nodes)
- Dropped: `ComfyUI_TensorRT` (no ARM64 tensorrt wheel), `onnxruntime-gpu` (no ARM64 GPU wheel)
- ComfyUI Manager now fully working via `uv`

**NVFP4 status:** Confirmed active on startup:
```
capabilities: ['dequantize_nvfp4', 'quantize_nvfp4', 'scaled_mm_nvfp4', ...]
```

**Nunchaku:** No ARM64 wheels exist for the nunchaku Python lib. The ComfyUI-nunchaku node loads but its loader nodes silently fail. Not a blocker — BFL NVFP4 models use ComfyUI's native path.

---

## Models Downloaded

All in `~/babs-data/comfyui/models/diffusion_models/`:

| File | Size | Source |
|------|------|--------|
| `flux1-dev-nvfp4.safetensors` | 8.6GB | black-forest-labs/FLUX.1-dev-NVFP4 |
| `flux1-kontext-dev-nvfp4.safetensors` | 8.6GB | black-forest-labs/FLUX.1-Kontext-dev-NVFP4 |
| `flux-2-klein-4b-nvfp4.safetensors` | 2.3GB | black-forest-labs/FLUX.2-klein-4b-nvfp4 |
| `flux-2-klein-9b-nvfp4.safetensors` | 5.4GB | black-forest-labs/FLUX.2-klein-9b-nvfp4 |
| `ltx-2.3-22b-distilled-nvfp4.safetensors` | 19GB | Hippotes/LTX-2.3-various-formats |
| `wan2.2_i2v_high_noise_14B_nvfp4_mixed.safetensors` | 9.9GB | GitMylo/Wan_2.2_nvfp4 |
| `wan2.2_i2v_low_noise_14B_nvfp4_mixed.safetensors` | 9.9GB | GitMylo/Wan_2.2_nvfp4 |

HuggingFace token (phloid, write access) stored at `~/.cache/huggingface/token`.

**Model notes:**
- FLUX.2 Klein: image-only, sub-second (4B) to a few seconds (9B), Apache 2.0
- Wan 2.2: image-to-video, 14B. High-noise = more motion, low-noise = faithful to input
- LTX-2.3 distilled: video, 22B. May need PyTorch 2.10 for full NVFP4 accel (on 2.9 now)
- Gemini hallucinated "FLUX.2-dev-NVFP4" — does not exist. FLUX.2 = Klein family only

---

## Nemotron 3 Super Status

Still parked. Investigated current options:
- vLLM v0.17.1 (March 11) added Super support for DGX Spark
- FP8 variant (`nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8`) works cleanly but ~120GB weights barely fits in 128GB — almost no KV cache headroom
- NVFP4 weights (already at `~/babs-data/models/nemotron3-super-nvfp4/`) are the right fit (~60GB), but MIXED_PRECISION quant still not fully supported in mainline vLLM
- Best next move: check if avarok has a v12 image with Super support — would let us use the existing NVFP4 weights

---

## What's Running

| Container | Status | Notes |
|-----------|--------|-------|
| `vllm-babs` | Running | Nemotron 3 Nano NVFP4, 65+ tok/s |
| `nats-babs` | Running | |
| `babs-supervisor` | Running | |
| `qdrant-babs` | Running | |
| `babs-dashboard` | Running | http://100.109.213.22:3000 |
| `babs-jupyter` | Running | |
| `comfyui-babs` | Running | http://100.109.213.22:8188 — NVFP4 active |

---

## Next Session

**Dropzone auto-sorter.** Dave has Chrome set to ask for download location on PX13, and babs-data is mapped as Z:. He downloads models directly to `Z:\dropzone` but doesn't always know the correct ComfyUI subfolder.

Plan: watch `~/babs-data/dropzone/`, inspect safetensors headers (contain architecture metadata — far more reliable than filename guessing), move files to the correct `~/babs-data/comfyui/models/<subdir>/`. Run as a host systemd service using inotifywait. Hold on partial downloads (wait for file size to stabilize). Move unknowns to `dropzone/unknown/` with a notification.

**Git:** `b072278` — Dockerfile.comfyui updated (CUDA 13, PyTorch cu130, SageAttention SM_121)
