#!/usr/bin/env python3
"""
dropzone-watch.py - Auto-sort model files from babs-data/dropzone to ComfyUI model dirs.

Watches ~/babs-data/dropzone/ for new files, waits for them to finish downloading,
classifies by type, and moves them to the correct ~/babs-data/comfyui/models/<type>/.
Unknowns and conflicts go to dropzone/unknown/.

Log: ~/babs-data/dropzone/dropzone.log
"""

import json
import logging
import logging.handlers
import shutil
import struct
import sys
import time
from pathlib import Path

DROPZONE  = Path.home() / "babs-data" / "dropzone"
MODELS    = Path.home() / "babs-data" / "comfyui" / "models"
UNKNOWN   = DROPZONE / "unknown"
LOG_FILE  = DROPZONE / "dropzone.log"

STABLE_SECS   = 15   # file size must be stable this long before we touch it
POLL_INTERVAL = 5    # seconds between directory scans

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}

# All valid destination subdirs under MODELS
VALID_TYPES = {
    "checkpoints", "loras", "controlnet", "vae", "embeddings",
    "upscale_models", "ipadapter", "clip", "clip_vision", "inpaint",
    "text_encoders", "diffusion_models", "hypernetworks", "vae_approx",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    log = logging.getLogger("dropzone")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)

    DROPZONE.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    return log


# ---------------------------------------------------------------------------
# safetensors header reader
# ---------------------------------------------------------------------------

def read_safetensors_header(path: Path) -> dict | None:
    """Return the parsed JSON header dict from a safetensors file, or None on failure."""
    try:
        with open(path, "rb") as f:
            raw = f.read(8)
            if len(raw) < 8:
                return None
            header_len = struct.unpack("<Q", raw)[0]
            if header_len == 0 or header_len > 100 * 1024 * 1024:
                return None
            header_bytes = f.read(header_len)
            if len(header_bytes) < header_len:
                return None
            return json.loads(header_bytes.decode("utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_from_header(header: dict) -> str | None:
    """Return model type from safetensors metadata + tensor key patterns, or None."""
    meta = header.get("__metadata__") or {}

    # kohya-style LoRA training metadata
    net_mod = meta.get("ss_network_module", "").lower()
    if any(x in net_mod for x in ("lora", "locon", "loha", "lokr", "oft")):
        return "loras"

    # modelspec standard field
    arch = meta.get("modelspec.architecture", "").lower()
    if arch:
        if "lora" in arch:
            return "loras"
        if "vae" in arch:
            return "vae"
        if any(x in arch for x in ("flux", "wan", "ltx", "sd3", "sana", "aura", "hunyuan", "cogvideo", "mochi")):
            return "diffusion_models"
        if any(x in arch for x in ("stable-diffusion", "sdxl", "sd1", "sd2")):
            return "checkpoints"

    # Inspect tensor key names (sample up to 100)
    tensor_keys = [k for k in header if k != "__metadata__"]
    sample = tensor_keys[:100]
    joined = " ".join(sample)

    # LoRA tensors
    if any(("lora_up" in k or "lora_down" in k or ".lora_A" in k or ".lora_B" in k) for k in sample):
        return "loras"

    # Flux: double_blocks / single_blocks
    if any(k.startswith(("double_blocks.", "single_blocks.", "img_in.", "txt_in.")) for k in sample):
        return "diffusion_models"

    # ControlNet
    if any("zero_conv" in k for k in sample) and any("input_blocks" in k or "middle_block" in k for k in sample):
        return "controlnet"

    # SD checkpoint (UNet + optionally VAE embedded)
    if any(k.startswith("model.diffusion_model.") for k in sample):
        return "checkpoints"

    # Standalone VAE (encoder + decoder, no UNet)
    if any(k.startswith("encoder.") for k in sample) and any(k.startswith("decoder.") for k in sample):
        if not any(k.startswith("model.diffusion_model.") for k in sample):
            return "vae"

    # CLIP / text encoder
    if any(k.startswith("text_model.") for k in sample):
        return "text_encoders"

    # T5-style encoder
    if any(k.startswith("encoder.block.") for k in sample):
        return "text_encoders"

    # CLIP vision (no text side)
    if any(k.startswith("vision_model.") for k in sample) and "text_model" not in joined:
        return "clip_vision"

    # IP-Adapter
    if any("image_proj" in k for k in sample) and any("ip_adapter" in k or "to_k_ip" in k for k in sample):
        return "ipadapter"

    return None


def _classify_by_filename(stem: str) -> str | None:
    """Return model type from filename stem (lowercased), or None."""
    n = stem.lower()

    # LoRA -- check early before architecture names confuse things
    if any(x in n for x in ("lora", "locon", "loha", "lokr")):
        return "loras"

    # VAE
    if "vae" in n and "ipadapter" not in n and "ip_adapter" not in n:
        return "vae"

    # ControlNet
    if "controlnet" in n or n.startswith("control_") or "control_v1" in n or "control_lora" in n:
        return "controlnet"

    # IP-Adapter
    if "ipadapter" in n or "ip-adapter" in n or "ip_adapter" in n:
        return "ipadapter"

    # CLIP Vision
    if "clip_vision" in n or "clip-vision" in n:
        return "clip_vision"
    if any(x in n for x in ("vit-h", "vit-g", "vit-l", "vit_h", "vit_g", "vit_l")):
        return "clip_vision"

    # Text encoders
    if any(x in n for x in ("clip_l", "clip_g", "text_encoder", "t5xxl", "t5-v1", "t5_v1", "llm_t5")):
        return "text_encoders"

    # Upscalers
    if any(x in n for x in ("esrgan", "realesrgan", "swinir", "nmkd", "omnisr", "bsrgan", "ldsr")):
        return "upscale_models"
    if any(x in n for x in ("_x2_", "_x4_", "_x8_", "hat_sr", "4x_", "2x_", "8x_")):
        return "upscale_models"

    # Inpaint (not controlnet)
    if "inpaint" in n and "control" not in n:
        return "inpaint"

    # Hypernetworks
    if "hypernetwork" in n or "hypernet" in n:
        return "hypernetworks"

    # Textual inversion embeddings
    if "embedding" in n or "textual_inversion" in n:
        return "embeddings"

    # New-style diffusion models (not wrapped as SD checkpoints)
    if any(x in n for x in ("flux1", "flux-1", "flux_1", "wan2", "ltx-", "ltx_", "sd3_", "sd3-",
                             "sana_", "hunyuan", "cogvideo", "mochi", "aura_", "auraflow")):
        return "diffusion_models"

    return None


def _classify_by_heuristics(path: Path) -> tuple[str, str]:
    """Return (model_type, confidence) using extension and file size."""
    ext  = path.suffix.lower()
    size = path.stat().st_size
    gb   = size / 1024 ** 3
    mb   = size / 1024 ** 2

    if ext == ".gguf":
        n = path.stem.lower()
        if any(x in n for x in ("t5", "clip", "text", "encoder")):
            return "text_encoders", "medium"
        if gb > 5:
            return "diffusion_models", "low"
        return "text_encoders", "low"

    if ext in (".pt", ".pth"):
        if mb < 20:
            return "embeddings", "medium"
        if mb < 500:
            return "loras", "low"
        return "checkpoints", "low"

    if ext == ".bin":
        if mb < 20:
            return "embeddings", "medium"
        return "checkpoints", "low"

    # .safetensors and .ckpt
    if gb > 5:
        return "diffusion_models", "low"
    if gb > 1:
        return "checkpoints", "low"
    return "checkpoints", "low"


def classify(path: Path, log: logging.Logger) -> str:
    """
    Classify a model file. Returns the destination subdirectory name.
    May return "unknown" if nothing matches with any confidence.
    """
    ext  = path.suffix.lower()
    stem = path.stem

    # 1. safetensors header
    if ext == ".safetensors":
        header = read_safetensors_header(path)
        if header is not None:
            result = _classify_from_header(header)
            if result:
                log.info(f"  classified via header: {result}")
                return result
        else:
            log.warning("  could not read safetensors header (truncated/corrupt?)")

    # 2. filename
    result = _classify_by_filename(stem)
    if result:
        log.info(f"  classified via filename: {result}")
        return result

    # 3. heuristics (low confidence -- always logs a warning)
    result, confidence = _classify_by_heuristics(path)
    if confidence == "low":
        log.warning(
            f"  classified via heuristics (low confidence): {result} "
            f"-- verify manually or move from dropzone/unknown/"
        )
        # For truly unknown, send to unknown dir so user can decide
        # "low" heuristic on .safetensors/.ckpt with no filename signal is a real guess
        if ext in (".safetensors", ".ckpt") and not result:
            return "unknown"
    else:
        log.info(f"  classified via heuristics: {result}")

    return result


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


def main() -> None:
    log = setup_logging()
    DROPZONE.mkdir(parents=True, exist_ok=True)
    UNKNOWN.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Dropzone watcher started")
    log.info(f"  Watching : {DROPZONE}")
    log.info(f"  Models   : {MODELS}")
    log.info(f"  Unknown  : {UNKNOWN}")
    log.info(f"  Stable   : {STABLE_SECS}s, Poll: {POLL_INTERVAL}s")
    log.info("=" * 60)

    # path -> (last_seen_size, time_size_last_changed)
    watching: dict[Path, tuple[int, float]] = {}

    while True:
        try:
            # Scan dropzone for model files (not in subdirs)
            present: set[Path] = set()
            for entry in DROPZONE.iterdir():
                if entry.is_file() and entry.suffix.lower() in MODEL_EXTENSIONS:
                    present.add(entry)

            # New arrivals
            for f in present - set(watching):
                sz = file_size(f)
                if sz is not None:
                    mb = sz / 1024 ** 2
                    log.info(f"Detected: {f.name}  ({mb:.1f} MB)")
                    watching[f] = (sz, time.monotonic())

            # Check stability
            ready: list[Path] = []
            gone:  list[Path] = []

            for f, (last_sz, stable_since) in list(watching.items()):
                if f not in present:
                    gone.append(f)
                    continue
                cur_sz = file_size(f)
                if cur_sz is None:
                    gone.append(f)
                    continue
                if cur_sz != last_sz:
                    watching[f] = (cur_sz, time.monotonic())  # reset timer
                elif time.monotonic() - stable_since >= STABLE_SECS:
                    ready.append(f)

            for f in gone:
                log.info(f"Gone (removed/renamed before processing): {f.name}")
                del watching[f]

            # Move ready files
            for f in ready:
                del watching[f]
                sz_gb = (file_size(f) or 0) / 1024 ** 3
                log.info(f"Processing: {f.name}  ({sz_gb:.2f} GB)")

                model_type = classify(f, log)

                if model_type == "unknown":
                    dest_dir = UNKNOWN
                else:
                    dest_dir = MODELS / model_type
                    dest_dir.mkdir(parents=True, exist_ok=True)

                dest = dest_dir / f.name

                if dest.exists():
                    log.warning(
                        f"  conflict: {dest} already exists -- "
                        f"moving to unknown/ to avoid overwrite"
                    )
                    dest = UNKNOWN / f.name
                    if dest.exists():
                        ts = int(time.time())
                        dest = UNKNOWN / f"{f.stem}_{ts}{f.suffix}"

                shutil.move(str(f), str(dest))
                rel = dest.relative_to(Path.home() / "babs-data")
                log.info(f"  -> babs-data/{rel}")

        except Exception as exc:
            log.error(f"Unexpected error in watch loop: {exc}", exc_info=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
