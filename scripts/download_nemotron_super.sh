#!/bin/bash
# Download Nemotron 3 Super 120B NVFP4 with progress display

set -e

MODEL_PATH="$HOME/babs-data/models/nemotron3-super-nvfp4"
MODEL_REPO="nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4"

echo "=== Nemotron 3 Super 120B NVFP4 Download ==="
echo ""
echo "Destination: $MODEL_PATH"
echo "Repository:  $MODEL_REPO"
echo "Size:        ~75GB (17 files)"
echo ""

# Check if already exists
if [ -d "$MODEL_PATH" ] && [ -f "$MODEL_PATH/config.json" ]; then
    echo "Model already exists!"
    echo ""
    read -p "Re-download? This will overwrite existing files. (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    echo ""
fi

# Create directory
mkdir -p "$MODEL_PATH"

echo "Starting download..."
echo "The HuggingFace CLI will show progress bars for each file."
echo ""

# Download with HuggingFace CLI (shows built-in progress)
hf download "$MODEL_REPO" \
    --local-dir "$MODEL_PATH" \
    --local-dir-use-symlinks False \
    --resume-download

echo ""
echo "✓ Download complete!"
echo ""

# Verify download
echo "Verifying download..."
FILE_COUNT=$(find "$MODEL_PATH" -type f | wc -l)
echo "Files downloaded: $FILE_COUNT"

if [ -f "$MODEL_PATH/config.json" ]; then
    echo "✓ config.json found"
fi

if [ -f "$MODEL_PATH/tokenizer_config.json" ]; then
    echo "✓ tokenizer_config.json found"
fi

SAFETENSORS_COUNT=$(find "$MODEL_PATH" -name "*.safetensors" | wc -l)
echo "✓ Safetensors files: $SAFETENSORS_COUNT"

TOTAL_SIZE=$(du -sh "$MODEL_PATH" | cut -f1)
echo "Total size: $TOTAL_SIZE"

echo ""
echo "Model ready to use!"
echo "Path: $MODEL_PATH"
