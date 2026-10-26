#!/usr/bin/env bash
# Instadash compatibility adapter; shared implementation lives in .instadash/.
exec python3 "$(dirname "$0")/../../.instadash/hooks/runtime.py" claude
