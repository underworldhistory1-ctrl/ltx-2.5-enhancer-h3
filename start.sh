#!/bin/bash
set -e

DIR="${LTX_BASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

echo "=========================================="
echo " Starting LTX 2.5 Video Enhancement Studio"
echo " Working Directory: $DIR"
echo "=========================================="

bash "$DIR/start_worker.sh"
sleep 2
bash "$DIR/start_server.sh"

echo ""
echo "=========================================="
echo " LTX Enhancer service is active!"
echo " Web Studio: http://localhost:7860"
echo " Worker (internal): http://127.0.0.1:8189"
echo " Logs: $DIR/logs/"
echo "=========================================="
