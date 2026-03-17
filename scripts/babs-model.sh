#!/usr/bin/env bash
# babs-model.sh - Switch the active model for the OpenClaw (Babs) agent.
#
# Usage:
#   babs-model <subcommand>
#
# Subcommands:
#   nano         Nemotron 3 Nano 30B (local vLLM, free, 65 tok/s)
#   sonnet       Claude Sonnet 4.6 (OpenRouter, $3/$15/M)
#   opus         Claude Opus 4.6 (OpenRouter, $15/$75/M)
#   deepseek     DeepSeek V3 Chat (OpenRouter, $0.27/$1.10/M, fast)
#   deepseek-r1  DeepSeek R1 (OpenRouter, $0.55/$2.19/M, reasoning)
#   gemini       Gemini 2.5 Pro (OpenRouter, $1.25/$10/M, 1M context)
#   llama        Llama 3.3 70B Instruct (OpenRouter, $0.12/$0.30/M)
#   list         Show current model and all options
#
# What it does:
#   1. Updates /sandbox/.openclaw/openclaw.json (agents.defaults + agents.list[main])
#   2. For local models: also updates openshell inference routing
#   3. Runs 'openclaw models set' inside sandbox for live update (best-effort)
#
# Start a NEW session in the OpenClaw dashboard for the change to take full effect.

set -euo pipefail

SANDBOX_JSON="/sandbox/.openclaw/openclaw.json"
SSH="ssh openshell-nemoclaw"

usage() {
  echo "Usage: babs-model <nano|sonnet|opus|deepseek|deepseek-r1|gemini|llama|list>"
  exit 1
}

get_current() {
  $SSH "python3 -c \"
import json
try:
    c = json.load(open('$SANDBOX_JSON'))
    agents = c.get('agents', {}).get('list', [])
    main = next((a for a in agents if a.get('id') == 'main'), {})
    print(main.get('model', {}).get('primary', c.get('agents', {}).get('defaults', {}).get('model', {}).get('primary', 'unknown')))
except Exception as e:
    print('unknown (' + str(e) + ')')
\"" 2>/dev/null || echo "unknown (ssh failed)"
}

set_model() {
  local provider="$1"
  local model_id="$2"
  local primary="${provider}/${model_id}"

  $SSH "python3 -c \"
import json
path = '$SANDBOX_JSON'
c = json.load(open(path))
c.setdefault('agents', {}).setdefault('defaults', {}).setdefault('model', {})['primary'] = '$primary'
for agent in c.get('agents', {}).get('list', []):
    if agent.get('id') == 'main':
        agent.setdefault('model', {})['primary'] = '$primary'
json.dump(c, open(path, 'w'), indent=2)
\""

  # Live update inside sandbox (best-effort -- may not take effect mid-session)
  $SSH "openclaw models set '$primary' > /dev/null 2>&1 || true" 2>/dev/null || true
}

case "${1:-}" in
  list)
    current=$(get_current)
    echo "Current: $current"
    echo ""
    echo "Available:"
    printf "  %-14s  %s\n" "nano"        "vllm-local/nemotron3-nano         (local, free, 65 tok/s)"
    printf "  %-14s  %s\n" "sonnet"      "openrouter/anthropic/claude-sonnet-4-6   (\$3/\$15/M)"
    printf "  %-14s  %s\n" "opus"        "openrouter/anthropic/claude-opus-4-6     (\$15/\$75/M)"
    printf "  %-14s  %s\n" "deepseek"    "openrouter/deepseek/deepseek-chat         (\$0.27/\$1.10/M)"
    printf "  %-14s  %s\n" "deepseek-r1" "openrouter/deepseek/deepseek-r1           (\$0.55/\$2.19/M, reasoning)"
    printf "  %-14s  %s\n" "gemini"      "openrouter/google/gemini-2.5-pro-preview  (\$1.25/\$10/M)"
    printf "  %-14s  %s\n" "llama"       "openrouter/meta-llama/llama-3.3-70b-instruct (\$0.12/\$0.30/M)"
    exit 0
    ;;

  nano)
    PROVIDER="vllm-local"
    MODEL_ID="nemotron3-nano"
    DISPLAY="Nemotron 3 Nano 30B (local, free)"
    DO_OPENSHELL_INFERENCE=1
    ;;

  sonnet)
    PROVIDER="openrouter"
    MODEL_ID="anthropic/claude-sonnet-4-6"
    DISPLAY="Claude Sonnet 4.6"
    DO_OPENSHELL_INFERENCE=0
    ;;

  opus)
    PROVIDER="openrouter"
    MODEL_ID="anthropic/claude-opus-4-6"
    DISPLAY="Claude Opus 4.6"
    DO_OPENSHELL_INFERENCE=0
    ;;

  deepseek)
    PROVIDER="openrouter"
    MODEL_ID="deepseek/deepseek-chat"
    DISPLAY="DeepSeek V3 Chat"
    DO_OPENSHELL_INFERENCE=0
    ;;

  deepseek-r1)
    PROVIDER="openrouter"
    MODEL_ID="deepseek/deepseek-r1"
    DISPLAY="DeepSeek R1 (reasoning)"
    DO_OPENSHELL_INFERENCE=0
    ;;

  gemini)
    PROVIDER="openrouter"
    MODEL_ID="google/gemini-2.5-pro-preview"
    DISPLAY="Gemini 2.5 Pro"
    DO_OPENSHELL_INFERENCE=0
    ;;

  llama)
    PROVIDER="openrouter"
    MODEL_ID="meta-llama/llama-3.3-70b-instruct"
    DISPLAY="Llama 3.3 70B"
    DO_OPENSHELL_INFERENCE=0
    ;;

  ""|--help|-h)
    usage
    ;;

  *)
    echo "Unknown model: $1"
    usage
    ;;
esac

echo "Switching to: $DISPLAY ($PROVIDER/$MODEL_ID)"

if [ "${DO_OPENSHELL_INFERENCE:-0}" = "1" ]; then
  openshell inference set --no-verify --provider "$PROVIDER" --model "$MODEL_ID" > /dev/null 2>&1 \
    && echo "  openshell inference route: $PROVIDER/$MODEL_ID" \
    || echo "  (openshell inference set failed -- continuing)"
fi

set_model "$PROVIDER" "$MODEL_ID"
echo "  openclaw.json updated"
echo ""
echo "Start a new session in the OpenClaw dashboard for the change to take effect."
echo "  http://100.109.213.22:18789/#token=4a4569fb23163c74cd4a4124e02e467fd844141a2708d67b"
