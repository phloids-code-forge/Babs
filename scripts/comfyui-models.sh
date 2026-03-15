#!/usr/bin/env bash
# Model management helper for ComfyUI on Spark.
# Downloads models from CivitAI or HuggingFace into the right directories.
#
# Usage:
#   ./comfyui-models.sh list                          - show what's installed
#   ./comfyui-models.sh dl-civitai <model-id> <type>  - download from CivitAI
#   ./comfyui-models.sh dl-hf <repo> <filename> <type> - download from HuggingFace
#   ./comfyui-models.sh unload <type> <filename>      - move model to .parked/
#   ./comfyui-models.sh restore <type> <filename>     - move model back from .parked/
#
# Types: checkpoints, loras, controlnet, vae, embeddings, upscale_models, ipadapter

set -euo pipefail

MODELS_DIR="$HOME/babs-data/comfyui/models"
CIVITAI_API_KEY="${CIVITAI_API_KEY:-}"

# Model type to directory mapping
type_to_dir() {
    case "$1" in
        checkpoint|checkpoints)  echo "$MODELS_DIR/checkpoints" ;;
        lora|loras)              echo "$MODELS_DIR/loras" ;;
        controlnet)              echo "$MODELS_DIR/controlnet" ;;
        vae)                     echo "$MODELS_DIR/vae" ;;
        embedding|embeddings)    echo "$MODELS_DIR/embeddings" ;;
        upscale|upscale_models)  echo "$MODELS_DIR/upscale_models" ;;
        ipadapter)               echo "$MODELS_DIR/ipadapter" ;;
        clip)                    echo "$MODELS_DIR/clip" ;;
        clip_vision)             echo "$MODELS_DIR/clip_vision" ;;
        inpaint)                 echo "$MODELS_DIR/inpaint" ;;
        text_encoders)           echo "$MODELS_DIR/text_encoders" ;;
        diffusion_models)        echo "$MODELS_DIR/diffusion_models" ;;
        *)
            echo "Unknown type '$1'. Valid: checkpoints, loras, controlnet, vae, embeddings, upscale_models, ipadapter, clip, clip_vision, inpaint, text_encoders, diffusion_models" >&2
            exit 1
            ;;
    esac
}

cmd_list() {
    echo "=== Installed Models ==="
    for d in "$MODELS_DIR"/*/; do
        type=$(basename "$d")
        count=$(find "$d" -maxdepth 1 -name "*.safetensors" -o -name "*.ckpt" -o -name "*.pt" -o -name "*.bin" 2>/dev/null | wc -l)
        parked=$(find "$d/.parked" -maxdepth 1 -name "*.safetensors" -o -name "*.ckpt" -o -name "*.pt" -o -name "*.bin" 2>/dev/null | wc -l)
        if [[ "$count" -gt 0 || "$parked" -gt 0 ]]; then
            echo ""
            echo "[$type]"
            find "$d" -maxdepth 1 \( -name "*.safetensors" -o -name "*.ckpt" -o -name "*.pt" -o -name "*.bin" \) \
                -printf "  %-60f  %s bytes\n" 2>/dev/null | sort || true
            if [[ "$parked" -gt 0 ]]; then
                echo "  -- parked (unloaded) --"
                find "$d/.parked" -maxdepth 1 \( -name "*.safetensors" -o -name "*.ckpt" -o -name "*.pt" -o -name "*.bin" \) \
                    -printf "  %-60f  %s bytes\n" 2>/dev/null | sort || true
            fi
        fi
    done
    echo ""
    echo "=== Disk Usage ==="
    du -sh "$MODELS_DIR" 2>/dev/null || true
}

cmd_dl_civitai() {
    local model_id="$1"
    local type="$2"
    local dest
    dest=$(type_to_dir "$type")

    if [[ -z "$CIVITAI_API_KEY" ]]; then
        echo "Set CIVITAI_API_KEY first: export CIVITAI_API_KEY=your_key"
        exit 1
    fi

    echo "==> Fetching model info for ID $model_id..."
    local info
    info=$(curl -sf "https://civitai.com/api/v1/models/$model_id" \
        -H "Authorization: Bearer $CIVITAI_API_KEY")

    local name
    name=$(echo "$info" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['name'])")
    local dl_url
    dl_url=$(echo "$info" | python3 -c "
import sys, json
d = json.load(sys.stdin)
v = d['modelVersions'][0]
f = next((x for x in v['files'] if x.get('primary', False)), v['files'][0])
print(f['downloadUrl'])
")
    local filename
    filename=$(echo "$info" | python3 -c "
import sys, json
d = json.load(sys.stdin)
v = d['modelVersions'][0]
f = next((x for x in v['files'] if x.get('primary', False)), v['files'][0])
print(f['name'])
")

    echo "==> Downloading: $name"
    echo "    -> $dest/$filename"
    mkdir -p "$dest"
    wget --show-progress \
        --header "Authorization: Bearer $CIVITAI_API_KEY" \
        -O "$dest/$filename" \
        "$dl_url"
    echo "==> Done: $dest/$filename"
}

cmd_dl_hf() {
    local repo="$1"
    local filename="$2"
    local type="$3"
    local dest
    dest=$(type_to_dir "$type")

    echo "==> Downloading $repo/$filename..."
    mkdir -p "$dest"
    hf download "$repo" "$filename" --local-dir "$dest" --local-dir-use-symlinks False
    echo "==> Done: $dest/$filename"
}

cmd_unload() {
    local type="$1"
    local filename="$2"
    local dir
    dir=$(type_to_dir "$type")

    if [[ ! -f "$dir/$filename" ]]; then
        echo "Not found: $dir/$filename"
        exit 1
    fi
    mkdir -p "$dir/.parked"
    mv "$dir/$filename" "$dir/.parked/$filename"
    echo "==> Parked: $filename (removed from ComfyUI model list)"
    echo "    Restart ComfyUI to apply: docker restart comfyui-babs"
}

dl_file() {
    local url="$1"
    local dest_dir="$2"
    local filename="$3"
    mkdir -p "$dest_dir"
    if [[ -f "$dest_dir/$filename" ]]; then
        echo "  [skip] $filename already exists"
        return
    fi
    echo "  -> $filename"
    wget -q --show-progress -O "$dest_dir/$filename" "$url"
}

cmd_krita_setup() {
    echo "==> Downloading required Krita AI Diffusion support models..."
    echo "    All free from HuggingFace. This will take a while."
    echo ""

    # CLIP Vision
    dl_file \
        "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" \
        "$MODELS_DIR/clip_vision" "clip-vision_vit-h.safetensors"

    # Upscalers
    dl_file \
        "https://huggingface.co/gemasai/4x_NMKD-Superscale-SP_178000_G/resolve/main/4x_NMKD-Superscale-SP_178000_G.pth" \
        "$MODELS_DIR/upscale_models" "4x_NMKD-Superscale-SP_178000_G.pth"
    dl_file \
        "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X2_DIV2K.safetensors" \
        "$MODELS_DIR/upscale_models" "OmniSR_X2_DIV2K.safetensors"
    dl_file \
        "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X3_DIV2K.safetensors" \
        "$MODELS_DIR/upscale_models" "OmniSR_X3_DIV2K.safetensors"
    dl_file \
        "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X4_DIV2K.safetensors" \
        "$MODELS_DIR/upscale_models" "OmniSR_X4_DIV2K.safetensors"
    dl_file \
        "https://huggingface.co/Acly/hat/resolve/main/HAT_SRx4_ImageNet-pretrain.pth" \
        "$MODELS_DIR/upscale_models" "HAT_SRx4_ImageNet-pretrain.pth"
    dl_file \
        "https://huggingface.co/Acly/hat/resolve/main/Real_HAT_GAN_sharper.pth" \
        "$MODELS_DIR/upscale_models" "Real_HAT_GAN_sharper.pth"

    # ControlNet
    dl_file \
        "https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_v11p_sd15_inpaint_fp16.safetensors" \
        "$MODELS_DIR/controlnet" "control_v11p_sd15_inpaint_fp16.safetensors"
    dl_file \
        "https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_lora_rank128_v11f1e_sd15_tile_fp16.safetensors" \
        "$MODELS_DIR/controlnet" "control_lora_rank128_v11f1e_sd15_tile_fp16.safetensors"

    # IP-Adapter
    dl_file \
        "https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter_sd15.safetensors" \
        "$MODELS_DIR/ipadapter" "ip-adapter_sd15.safetensors"
    dl_file \
        "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter_sdxl_vit-h.safetensors" \
        "$MODELS_DIR/ipadapter" "ip-adapter_sdxl_vit-h.safetensors"

    # Inpaint
    dl_file \
        "https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/fooocus_inpaint_head.pth" \
        "$MODELS_DIR/inpaint" "fooocus_inpaint_head.pth"
    dl_file \
        "https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/inpaint_v26.fooocus.patch" \
        "$MODELS_DIR/inpaint" "inpaint_v26.fooocus.patch"
    dl_file \
        "https://huggingface.co/Acly/MAT/resolve/main/MAT_Places512_G_fp16.safetensors" \
        "$MODELS_DIR/inpaint" "MAT_Places512_G_fp16.safetensors"

    # LoRAs
    dl_file \
        "https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SD15-8steps-CFG-lora.safetensors" \
        "$MODELS_DIR/loras" "Hyper-SD15-8steps-CFG-lora.safetensors"
    dl_file \
        "https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SDXL-8steps-CFG-lora.safetensors" \
        "$MODELS_DIR/loras" "Hyper-SDXL-8steps-CFG-lora.safetensors"

    # Text encoders for Flux
    dl_file \
        "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
        "$MODELS_DIR/text_encoders" "clip_l.safetensors"
    dl_file \
        "https://huggingface.co/city96/t5-v1_1-xxl-encoder-gguf/resolve/main/t5-v1_1-xxl-encoder-Q5_K_M.gguf" \
        "$MODELS_DIR/text_encoders" "t5-v1_1-xxl-encoder-Q5_K_M.gguf"

    # VAE for Flux
    dl_file \
        "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors" \
        "$MODELS_DIR/vae" "flux_vae.safetensors"

    echo ""
    echo "==> Done. Support models installed."
    echo "    You still need a diffusion model (checkpoint). Examples:"
    echo "      SD1.5:  ./comfyui-models.sh dl-hf Lykon/dreamshaper-8 dreamshaper_8.safetensors checkpoints"
    echo "      SDXL:   ./comfyui-models.sh dl-hf SG161222/RealVisXL_V5.0 RealVisXL_V5.0_fp16.safetensors checkpoints"
    echo "      Flux:   ./comfyui-models.sh dl-hf black-forest-labs/FLUX.1-schnell flux1-schnell.safetensors diffusion_models"
}

cmd_restore() {
    local type="$1"
    local filename="$2"
    local dir
    dir=$(type_to_dir "$type")

    if [[ ! -f "$dir/.parked/$filename" ]]; then
        echo "Not found in parked: $dir/.parked/$filename"
        exit 1
    fi
    mv "$dir/.parked/$filename" "$dir/$filename"
    echo "==> Restored: $filename"
    echo "    Restart ComfyUI to apply: docker restart comfyui-babs"
}

# Dispatch
CMD="${1:-list}"
case "$CMD" in
    list)                   cmd_list ;;
    dl-civitai)             cmd_dl_civitai "${2:?model-id required}" "${3:?type required}" ;;
    dl-hf)                  cmd_dl_hf "${2:?repo required}" "${3:?filename required}" "${4:?type required}" ;;
    unload)                 cmd_unload "${2:?type required}" "${3:?filename required}" ;;
    restore)                cmd_restore "${2:?type required}" "${3:?filename required}" ;;
    krita-setup)            cmd_krita_setup ;;
    *)
        echo "Unknown command: $CMD"
        echo "Usage: $0 {list|dl-civitai|dl-hf|unload|restore|krita-setup}"
        exit 1
        ;;
esac
