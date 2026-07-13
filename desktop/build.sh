#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

command -v node >/dev/null 2>&1 || { echo "Node.js required"; exit 1; }
command -v cargo >/dev/null 2>&1 || { echo "Rust required"; exit 1; }

cd "$ROOT/desktop"
npm install

if [ "${1:-}" = "dev" ]; then
    npm run tauri dev
else
    npm run tauri build
fi
