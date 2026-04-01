#!/usr/bin/env bash
# launch.sh — Launch DDP training via torchrun
#
# Usage:
#   ./launch.sh                        # 2 GPUs, fresh run
#   ./launch.sh 4                      # 4 GPUs, fresh run
#   ./launch.sh 4 config.json          # 4 GPUs, custom config
#   ./launch.sh 4 config.json resume   # 4 GPUs, resume from checkpoint
#
# torchrun handles:
#   - MASTER_ADDR / MASTER_PORT environment variables
#   - LOCAL_RANK / RANK / WORLD_SIZE injection into each subprocess
#   - Graceful SIGTERM propagation to all worker processes

set -euo pipefail

NUM_GPUS="${1:-2}"
CONFIG="${2:-}"
RESUME="${3:-}"

echo "==> Launching DDP training: ${NUM_GPUS} GPU(s)"

EXTRA_ARGS=""
if [[ -n "${CONFIG}" ]]; then
    EXTRA_ARGS="${EXTRA_ARGS} --config ${CONFIG}"
fi
if [[ -n "${RESUME}" ]]; then
    EXTRA_ARGS="${EXTRA_ARGS} --resume"
fi

# --standalone     : single-node mode (no rendezvous server needed)
# --nproc_per_node : one process per GPU
# --rdzv_backend   : c10d is built-in, no external server required
torchrun \
    --standalone \
    --nproc_per_node="${NUM_GPUS}" \
    --rdzv_backend=c10d \
    --rdzv_endpoint="localhost:0" \
    train_ddp.py ${EXTRA_ARGS}

echo "==> Training complete."
